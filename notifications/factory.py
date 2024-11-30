# notifications/factory.py

"""
Factory module for notification provider creation, configuration, and lifecycle management.

This module provides a centralized factory system for managing notification providers,
handling their registration, instantiation, and configuration. It supports advanced
features such as priority-based message handling, validator caching, and comprehensive
performance monitoring.

Key Features:
    - Provider Registration: Dynamic registration of notification providers with optional validators
    - Priority Management: Three-tier priority system (LOW, NORMAL, HIGH) with configurable settings
    - Performance Optimization: Caching system for validators with automatic TTL management
    - Statistics Tracking: Comprehensive tracking of message priorities and validation performance
    - Thread Safety: Async-safe operations with proper locking mechanisms

Priority Levels:
    - LOW: Non-critical messages that can be delayed or dropped (50% base rate)
    - NORMAL: Standard messages with default priority (100% base rate)
    - HIGH: Urgent messages requiring immediate delivery (200% base rate)

Configuration:
    Each provider can have priority-specific configurations including:
    - Rate limits
    - Retry attempts
    - Timeout settings
    - Custom validation rules

Examples:
    Basic provider registration and usage:
    >>> @NotificationFactory.register("custom")
    ... class CustomProvider(NotificationProvider):
    ...     def __init__(self, config: Dict[str, Any]):
    ...         super().__init__()
    ...         self.client = CustomClient(config["api_key"])
    ...         self._priority_rate_limits = {
    ...             MessagePriority.LOW: config["rate_limit"] // 2,
    ...             MessagePriority.NORMAL: config["rate_limit"],
    ...             MessagePriority.HIGH: config["rate_limit"] * 2
    ...         }
    ...
    ...     async def send_notification(self, message: str) -> bool:
    ...         return await self.client.send(message)
    ...
    ...     @classmethod
    ...     def validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
    ...         if "api_key" not in config:
    ...             raise ValueError("API key is required")
    ...         return config

    Advanced usage with priority configuration:
    >>> factory = NotificationFactory()
    >>> priority_config = {
    ...     MessagePriority.HIGH: {
    ...         "rate_limit": 60,
    ...         "retry_attempts": 5,
    ...         "timeout": 30
    ...     },
    ...     MessagePriority.NORMAL: {
    ...         "rate_limit": 30,
    ...         "retry_attempts": 3,
    ...         "timeout": 20
    ...     },
    ...     MessagePriority.LOW: {
    ...         "rate_limit": 15,
    ...         "retry_attempts": 1,
    ...         "timeout": 10
    ...     }
    ... }
    >>> provider = await factory.create_provider(
    ...     "custom",
    ...     {"api_key": "your-api-key", "rate_limit": 30},
    ...     priority_config=priority_config
    ... )
    >>> # Send high-priority notification
    >>> await provider.notify(
    ...     "Critical system alert!",
    ...     priority=MessagePriority.HIGH
    ... )

Note:
    The factory maintains a global instance (notification_factory) for convenience,
    but you can create separate instances if needed for isolation or testing.
"""

import asyncio
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from structlog import get_logger

from config.constants import MessagePriority
from config.constants import NotificationProvider as ProviderType
from notifications.base import NotificationError, NotificationProvider
from utils.validators import BaseProviderValidator

logger = get_logger(__name__)

# Type variables for generic typing
T_Config = TypeVar('T_Config', bound=Dict[str, Any])
T_Provider = TypeVar('T_Provider', bound=NotificationProvider)
T_Validator = TypeVar('T_Validator', bound=BaseProviderValidator)

@dataclass
class ValidationContext:
    """Context manager for tracking validation operations and performance metrics.

    This class provides a context for validation operations, tracking timing and
    performance metrics for provider validation processes. It helps identify
    slow validations and maintain performance statistics.

    Attributes:
        provider_id (str): Identifier of the provider being validated
        operation (str): Name of the validation operation
        start_time (float): Timestamp when validation started
        validation_time (float): Total time taken for validation

    Example:
        >>> with factory._validation_context("discord", "config_validation") as ctx:
        ...     # Perform validation
        ...     result = validator.validate(config)
        ...     # Context automatically tracks timing
        >>> print(f"Validation took {ctx.validation_time:.2f} seconds")
    """
    provider_id: str
    operation: str
    start_time: float = 0.0
    validation_time: float = 0.0

@dataclass
class ValidatorCacheEntry:
    """Cache entry for storing and managing validator instances.

    Maintains metadata about validator usage and performance, including creation time,
    usage statistics, and priority-based validation counts. This helps in optimizing
    validator lifecycle and identifying performance patterns.

    Attributes:
        validator (BaseProviderValidator): The cached validator instance
        created_at (float): Timestamp when the validator was created
        last_used (float): Timestamp of last validator usage
        validation_count (int): Total number of validations performed
        total_validation_time (float): Cumulative time spent in validation
        priority_validation_counts (Dict[MessagePriority, int]): Validation counts per priority

    Example:
        >>> entry = ValidatorCacheEntry(
        ...     validator=DiscordValidator(),
        ...     created_at=time.time(),
        ...     last_used=time.time()
        ... )
        >>> entry.validation_count += 1
        >>> entry.total_validation_time += 0.5
        >>> entry.priority_validation_counts[MessagePriority.HIGH] += 1
    """
    validator: BaseProviderValidator
    created_at: float
    last_used: float
    validation_count: int = 0
    total_validation_time: float = 0.0
    priority_validation_counts: Dict[MessagePriority, int] = None

    def __post_init__(self):
        if self.priority_validation_counts is None:
            self.priority_validation_counts = {
                MessagePriority.LOW: 0,
                MessagePriority.NORMAL: 0,
                MessagePriority.HIGH: 0
            }

class ProviderError(NotificationError):
    """Base exception for provider-related errors in the notification system.

    This exception serves as the root for all provider-specific errors,
    allowing for granular error handling and appropriate recovery strategies.

    Example:
        >>> try:
        ...     await factory.create_provider("unknown")
        ... except ProviderError as e:
        ...     logger.error("Provider operation failed", error=str(e))
    """
    pass


class ProviderRegistrationError(ProviderError):
    """Exception raised when provider registration fails.

    This can occur due to duplicate registration attempts, invalid provider
    implementations, or configuration validation failures during registration.

    Example:
        >>> try:
        ...     @NotificationFactory.register("discord")
        ...     class InvalidProvider:
        ...         pass  # Missing required interface
        ... except ProviderRegistrationError as e:
        ...     logger.error("Provider registration failed", error=str(e))
    """
    pass


class ProviderNotFoundError(ProviderError):
    """Exception raised when attempting to use an unregistered provider.

    Occurs when trying to create or access a provider that hasn't been
    registered with the factory.

    Example:
        >>> try:
        ...     provider = await factory.create_provider("nonexistent")
        ... except ProviderNotFoundError as e:
        ...     logger.error("Provider not found", provider_id="nonexistent")
    """
    pass


class ProviderConfigError(ProviderError):
    """Exception raised when provider configuration validation fails.

    This occurs when the provided configuration doesn't meet the requirements
    specified by the provider's validator.

    Example:
        >>> try:
        ...     config = {"invalid_key": "value"}  # Missing required fields
        ...     provider = await factory.create_provider("discord", config)
        ... except ProviderConfigError as e:
        ...     logger.error("Invalid provider configuration", error=str(e))
    """
    pass


class NotificationFactory:
    """Factory for creating and managing notification providers with advanced lifecycle management.

    This factory class serves as the central hub for notification provider management,
    handling provider registration, instantiation, configuration validation, and
    lifecycle management. It provides a robust system for creating and managing
    notification providers with features such as priority-based message handling,
    performance monitoring, and validator caching.

    Key Features:
        - Provider Registration: Dynamic registration of providers with optional validators
        - Configuration Management: Validation and caching of provider configurations
        - Priority Handling: Support for LOW, NORMAL, and HIGH priority messages
        - Performance Monitoring: Tracking of validation times and message statistics
        - Validator Caching: Optimization of validation performance with TTL-based caching
        - Thread Safety: Async-safe operations with proper locking mechanisms

    Attributes:
        VALIDATOR_CACHE_TTL (int): Cache time-to-live in seconds (default: 1800)
        SLOW_VALIDATION_THRESHOLD (float): Threshold for slow validation warning (1.0s)
        VERY_SLOW_VALIDATION_THRESHOLD (float): Threshold for critical validation warning (3.0s)
        PRIORITY_RATE_LIMITS (Dict[MessagePriority, float]): Rate limits per priority level

    Usage Examples:
        1. Basic Provider Registration:
            >>> @NotificationFactory.register("discord")
            ... class DiscordProvider(NotificationProvider):
            ...     def __init__(self, config: Dict[str, Any]):
            ...         super().__init__()
            ...         self.webhook_url = config["webhook_url"]
            ...
            ...     async def send_notification(self, message: str) -> bool:
            ...         return await self._send_webhook(message)

        2. Registration with Custom Validator:
            >>> class DiscordValidator(BaseProviderValidator):
            ...     def validate_webhook_url(self, url: str) -> str:
            ...         if not url.startswith("https://discord.com/api/webhooks/"):
            ...             raise ValueError("Invalid Discord webhook URL")
            ...         return url
            ...
            >>> @NotificationFactory.register("discord", DiscordValidator)
            ... class DiscordProvider(NotificationProvider):
            ...     pass

        3. Creating and Using a Provider:
            >>> factory = NotificationFactory()
            >>> config = {
            ...     "webhook_url": "https://discord.com/api/webhooks/123/abc",
            ...     "username": "Alert Bot",
            ...     "rate_limit": 30
            ... }
            >>> provider = await factory.create_provider("discord", config)
            >>> await provider.notify(
            ...     "System alert!",
            ...     priority=MessagePriority.HIGH
            ... )

        4. Priority-based Configuration:
            >>> priority_config = {
            ...     MessagePriority.HIGH: {
            ...         "rate_limit": 60,
            ...         "retry_attempts": 5
            ...     },
            ...     MessagePriority.LOW: {
            ...         "rate_limit": 15,
            ...         "retry_attempts": 1
            ...     }
            ... }
            >>> provider = await factory.create_provider(
            ...     "discord",
            ...     config,
            ...     priority_config=priority_config
            ... )

    Note:
        - The factory maintains internal caches and statistics for optimization
        - All provider operations are thread-safe and suitable for async environments
        - Priority configurations allow for fine-grained control of message handling
        - Validator caching improves performance for frequently used configurations
    """

    # Cache TTL in seconds (30 minutes)
    VALIDATOR_CACHE_TTL = 1800

    # Performance thresholds in seconds
    SLOW_VALIDATION_THRESHOLD = 1.0
    VERY_SLOW_VALIDATION_THRESHOLD = 3.0

    # Priority-based rate limits
    PRIORITY_RATE_LIMITS = {
        MessagePriority.LOW: 0.5,     # 50% of base rate
        MessagePriority.NORMAL: 1.0,  # 100% of base rate
        MessagePriority.HIGH: 2.0     # 200% of base rate
    }

    def __init__(self):
        """Initialize a new NotificationFactory instance.

        Creates a new factory instance with empty provider and validator caches,
        and initializes internal state tracking for providers and tasks.

        Instance Attributes:
            _providers (Dict[str, Tuple[Type[NotificationProvider], Type[BaseProviderValidator]]]):
                Mapping of provider IDs to their provider and validator class types
            _active_providers (Dict[str, NotificationProvider]):
                Currently active provider instances
            _validator_cache (Dict[str, ValidatorCacheEntry]):
                Cache of validator instances with usage statistics
            _registered_configs (Dict[str, Dict[str, Any]]):
                Registered configurations for providers
            _active_tasks (Set[asyncio.Task]):
                Set of active asynchronous tasks
            _lock (asyncio.Lock):
                Lock for thread-safe operations
            _priority_stats (Dict[str, Dict[MessagePriority, int]]):
                Statistics tracking for message priorities per provider
        """
        self._providers: Dict[str, Tuple[Type[NotificationProvider], Type[BaseProviderValidator]]] = {}
        self._active_providers: Dict[str, NotificationProvider] = {}
        self._validator_cache: Dict[str, ValidatorCacheEntry] = {}
        self._registered_configs: Dict[str, Dict[str, Any]] = {}
        self._active_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._priority_stats: Dict[str, Dict[MessagePriority, int]] = {}

    def _update_priority_stats(self, provider_id: str, priority: MessagePriority) -> None:
        """Update usage statistics for message priorities.

        Tracks the frequency of different priority levels used for each provider,
        which can be used for monitoring, optimization, and capacity planning.

        Args:
            provider_id (str): Unique identifier of the provider
            priority (MessagePriority): Priority level of the message

        Note:
            Statistics are maintained per provider and priority level:
            - LOW: Non-critical messages (can be delayed)
            - NORMAL: Standard priority messages
            - HIGH: Critical messages requiring immediate delivery

        Example:
            >>> await provider.notify("System alert", priority=MessagePriority.HIGH)
            >>> stats = factory._priority_stats["discord"]
            >>> print(f"High priority messages: {stats[MessagePriority.HIGH]}")
            High priority messages: 1
        """
        if provider_id not in self._priority_stats:
            self._priority_stats[provider_id] = {
                MessagePriority.LOW: 0,
                MessagePriority.NORMAL: 0,
                MessagePriority.HIGH: 0
            }
        self._priority_stats[provider_id][priority] += 1

    @contextmanager
    def _validation_context(self, provider_id: str, operation: str) -> 'ValidationContext':
        """Create a context manager for tracking validation operations.

        Provides performance monitoring and logging for validation operations,
        including timing measurements and cache statistics updates.

        Args:
            provider_id (str): Unique identifier of the provider
            operation (str): Name of the validation operation being performed

        Yields:
            ValidationContext: Context object containing timing and operation details

        Performance Monitoring:
            - SLOW_VALIDATION_THRESHOLD (1.0s): Warning threshold for slow operations
            - VERY_SLOW_VALIDATION_THRESHOLD (3.0s): Critical threshold for very slow operations

        Example:
            >>> with factory._validation_context("discord", "config_validation") as ctx:
            ...     result = validator.validate(config)
            ...     if ctx.validation_time >= SLOW_VALIDATION_THRESHOLD:
            ...         logger.warning("Slow validation detected")
        """
        context = ValidationContext(provider_id=provider_id, operation=operation)
        context.start_time = time.time()

        try:
            yield context
        finally:
            end_time = time.time()
            context.validation_time = end_time - context.start_time

            # Update cache statistics if applicable
            if provider_id in self._validator_cache:
                entry = self._validator_cache[provider_id]
                entry.validation_count += 1
                entry.total_validation_time += context.validation_time

            # Log performance metrics
            if context.validation_time >= self.VERY_SLOW_VALIDATION_THRESHOLD:
                logger.warning(
                    "Very slow validation operation",
                    provider_id=provider_id,
                    operation=operation,
                    validation_time=context.validation_time,
                )
            elif context.validation_time >= self.SLOW_VALIDATION_THRESHOLD:
                logger.warning(
                    "Slow validation operation",
                    provider_id=provider_id,
                    operation=operation,
                    validation_time=context.validation_time,
                )

            logger.debug(
                "Validation operation completed",
                provider_id=provider_id,
                operation=operation,
                validation_time=context.validation_time,
            )

    def _get_cached_validator(
        self,
        provider_id: str,
        validator_class: Type[BaseProviderValidator]
    ) -> Optional[BaseProviderValidator]:
        """Retrieve a cached validator instance if it exists and is valid.

        Manages the validator cache with TTL-based expiration and usage tracking.
        If a cached validator is found but expired, it is removed from the cache.

        Args:
            provider_id (str): Unique identifier of the provider
            validator_class (Type[BaseProviderValidator]): Class type of the validator

        Returns:
            Optional[BaseProviderValidator]: Cached validator instance if valid, None otherwise

        Cache Management:
            - TTL (Time-To-Live): VALIDATOR_CACHE_TTL (default: 1800 seconds)
            - Usage tracking: Updates last_used timestamp for cache entries
            - Auto-cleanup: Removes expired entries when accessed

        Example:
            >>> validator = factory._get_cached_validator("discord", DiscordValidator)
            >>> if validator:
            ...     print("Using cached validator")
            ... else:
            ...     validator = DiscordValidator()
            ...     factory._cache_validator("discord", validator)
        """
        now = time.time()
        cache_entry = self._validator_cache.get(provider_id)

        if cache_entry:
            # Check if cache entry is still valid
            if now - cache_entry.created_at <= self.VALIDATOR_CACHE_TTL:
                cache_entry.last_used = now
                logger.debug(
                    "Using cached validator",
                    provider_id=provider_id,
                    validator_class=validator_class.__name__,
                    cache_age=now - cache_entry.created_at,
                    validation_count=cache_entry.validation_count,
                )
                return cache_entry.validator

            # Remove expired cache entry
            logger.debug(
                "Removing expired validator from cache",
                provider_id=provider_id,
                validator_class=validator_class.__name__,
                cache_age=now - cache_entry.created_at,
            )
            del self._validator_cache[provider_id]

        return None

    def _cache_validator(
        self,
        provider_id: str,
        validator: BaseProviderValidator
    ) -> None:
        """Cache a validator instance for future use.

        Creates a new cache entry for a validator instance with usage statistics
        tracking. The cache entry includes creation time, usage count, and
        performance metrics.

        Args:
            provider_id (str): Unique identifier of the provider
            validator (BaseProviderValidator): Validator instance to cache

        Cache Entry Attributes:
            - created_at: Timestamp when the validator was cached
            - last_used: Timestamp of most recent usage
            - validation_count: Number of validations performed
            - total_validation_time: Cumulative time spent in validation

        Example:
            >>> validator = DiscordValidator()
            >>> factory._cache_validator("discord", validator)
            >>> # Later retrieval
            >>> cached = factory._get_cached_validator("discord", DiscordValidator)
            >>> assert cached is validator
        """
        now = time.time()
        self._validator_cache[provider_id] = ValidatorCacheEntry(
            validator=validator,
            created_at=now,
            last_used=now,
            validation_count=0,
            total_validation_time=0.0
        )
        logger.debug(
            "Cached new validator instance",
            provider_id=provider_id,
            validator_class=validator.__class__.__name__,
        )

    @classmethod
    def register(
        cls,
        provider_id: str,
        validator_class: Optional[Type[T_Validator]] = None
    ) -> callable:
        """Register a new notification provider with optional validator.

        This decorator registers a provider class with its associated validator class.
        If no validator is provided, the provider's own validate_config method will be used.

        Args:
            provider_id (str): Unique identifier for the provider
            validator_class (Optional[Type[T_Validator]]): Optional validator class for the provider

        Returns:
            callable: Decorator function for provider registration

        Raises:
            ProviderRegistrationError: If registration fails or provider already exists
            ValueError: If provider_id is invalid

        Examples:
            >>> @NotificationFactory.register("custom", CustomValidator)
            ... class CustomProvider(NotificationProvider):
            ...     def __init__(self, config: Dict[str, Any]):
            ...         super().__init__()
            ...
            ... # Register without explicit validator
            >>> @NotificationFactory.register("simple")
            ... class SimpleProvider(NotificationProvider):
            ...     @classmethod
            ...     def validate_config(cls, config: Dict[str, Any]):
            ...         return config
        """
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ValueError("Provider ID must be a non-empty string")

        def decorator(provider_class: Type[T_Provider]) -> Type[T_Provider]:
            if not issubclass(provider_class, NotificationProvider):
                raise ProviderRegistrationError(
                    f"Provider {provider_class.__name__} must inherit from NotificationProvider"
                )

            # If no validator class is provided, use the provider's validate_config method
            actual_validator = validator_class or provider_class

            # Register provider using singleton instance
            factory = cls()
            with factory._lock:
                if provider_id in factory._providers:
                    raise ProviderRegistrationError(f"Provider {provider_id} already registered")

                factory._providers[provider_id] = (provider_class, actual_validator)
                logger.info(
                    "Registered notification provider",
                    provider_id=provider_id,
                    provider_class=provider_class.__name__,
                    validator_class=actual_validator.__name__,
                )

            return provider_class

        return decorator

    def _validate_provider_exists(self, provider_id: str) -> Tuple[Type[NotificationProvider], Type[BaseProviderValidator]]:
        """Validate that a provider exists and return its class and validator.

        Args:
            provider_id (str): Provider identifier

        Returns:
            Tuple[Type[NotificationProvider], Type[BaseProviderValidator]]: Provider and validator classes

        Raises:
            ProviderNotFoundError: If provider is not registered
        """
        provider_tuple = self._providers.get(provider_id)
        if not provider_tuple:
            logger.warning(
                "Attempted to create unregistered provider",
                provider_id=provider_id,
            )
            raise ProviderNotFoundError(f"Provider {provider_id} not registered")
        return provider_tuple

    def _get_config(self, provider_id: str, config: Optional[T_Config]) -> Dict[str, Any]:
        """Get configuration for a provider.

        Args:
            provider_id (str): Provider identifier
            config (Optional[T_Config]): Optional provider configuration

        Returns:
            Dict[str, Any]: Provider configuration

        Raises:
            ProviderConfigError: If no configuration is available
        """
        provider_config = config or self._registered_configs.get(provider_id, {})
        if not provider_config:
            raise ProviderConfigError(f"No configuration available for provider: {provider_id}")
        return provider_config

    async def _validate_config(
        self,
        provider_id: str,
        validator_class: Type[BaseProviderValidator],
        config: Dict[str, Any],
        priority_config: Optional[Dict[MessagePriority, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Validate provider configuration including priority-specific settings.

        This method validates both the base configuration and any priority-specific
        overrides. Priority configurations are merged with the base configuration
        before validation to ensure all required fields are present.

        Args:
            provider_id (str): Provider identifier
            validator_class (Type[BaseProviderValidator]): Validator class
            config (Dict[str, Any]): Provider configuration
            priority_config (Optional[Dict[MessagePriority, Dict[str, Any]]]): Optional priority-specific configuration overrides

        Returns:
            Dict[str, Any]: Validated configuration

        Example:
            >>> priority_config = {
            ...     MessagePriority.HIGH: {"rate_limit": 60},
            ...     MessagePriority.LOW: {"rate_limit": 15}
            ... }
            >>> validated_config = factory._validate_config(
            ...     "telegram",
            ...     TelegramValidator,
            ...     {"bot_token": "123:abc"},
            ...     priority_config
            ... )
        """
        validator = self._get_cached_validator(provider_id, validator_class)
        if not validator and callable(validator_class):
            validator = validator_class()
            self._cache_validator(provider_id, validator)

        with self._validation_context(provider_id, "create_provider"):
            if validator and hasattr(validator, 'validate_config'):
                config = validator.validate_config(config)
            else:
                config = validator_class.validate_config(config)

            if priority_config:
                for _priority, override in priority_config.items():
                    if validator and hasattr(validator, 'validate_priority_config'):
                        validator.validate_priority_config(override, _priority)
                    else:
                        validator_class.validate_priority_config(override, _priority)

        return config

    async def create_provider(
        self,
        provider_id: Union[str, ProviderType],
        config: Optional[T_Config] = None,
        validate: bool = True,
        priority_config: Optional[Dict[MessagePriority, Dict[str, Any]]] = None
    ) -> T_Provider:
        """Create or retrieve a provider instance with priority configuration.

        This method creates a new provider instance or retrieves an existing one,
        applying priority-specific configuration overrides if provided. Each priority
        level (LOW, NORMAL, HIGH) can have its own settings for rate limits, retry
        attempts, and other provider-specific parameters.

        Args:
            provider_id (Union[str, ProviderType]): Provider identifier
            config (Optional[T_Config]): Optional provider configuration
            validate (bool): Whether to validate configuration
            priority_config (Optional[Dict[MessagePriority, Dict[str, Any]]]): Optional priority-specific configuration overrides.
                           Can include settings for each MessagePriority level.

        Returns:
            T_Provider: Provider instance

        Raises:
            ProviderNotFoundError: If provider is not registered
            ProviderConfigError: If configuration is invalid

        Example:
            >>> priority_config = {
            ...     MessagePriority.HIGH: {"rate_limit": 60},
            ...     MessagePriority.LOW: {"rate_limit": 15}
            ... }
            >>> provider = await factory.create_provider(
            ...     "telegram",
            ...     {"bot_token": "123:abc"},
            ...     priority_config=priority_config
            ... )
        """
        provider_id = str(provider_id)

        async with self._lock:
            # Return existing instance if available
            if provider_id in self._active_providers:
                logger.debug("Returning existing provider instance", provider_id=provider_id)
                return self._active_providers[provider_id]

            # Get provider class and validator
            provider_class, validator_class = self._validate_provider_exists(provider_id)

            # Get and validate configuration
            provider_config = self._get_config(provider_id, config)
            if validate:
                provider_config = await self._validate_config(
                    provider_id,
                    validator_class,
                    provider_config,
                    priority_config
                )

            # Apply priority-specific configuration overrides
            if priority_config:
                for _priority, override in priority_config.items():
                    provider_config = self._merge_configs(provider_config, override)

            try:
                # Initialize provider
                provider = provider_class(provider_config)
                if hasattr(provider, 'connect'):
                    logger.debug("Connecting provider", provider_id=provider_id)
                    await provider.connect()

                self._active_providers[provider_id] = provider
                logger.info(
                    "Created provider instance",
                    provider_id=provider_id,
                    provider_class=provider_class.__name__
                )
                return provider

            except NotificationError:
                logger.error(
                    "Provider creation failed with NotificationError",
                    provider_id=provider_id,
                    error_type=type(NotificationError).__name__
                )
                raise
            except Exception as err:
                logger.error(
                    "Provider creation failed with unexpected error",
                    provider_id=provider_id,
                    error_type=type(err).__name__,
                    error=str(err)
                )
                raise ProviderConfigError(f"Failed to create provider {provider_id}: {err}") from err

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two configuration dictionaries with override support.

        Performs a recursive merge of two configuration dictionaries, where values
        from the override dictionary take precedence over the base dictionary.
        Nested dictionaries are merged recursively while preserving structure.

        Args:
            base (Dict[str, Any]): Base configuration dictionary
            override (Dict[str, Any]): Configuration dictionary to override with

        Returns:
            Dict[str, Any]: New dictionary containing the merged configuration

        Example:
            >>> base = {"rate_limit": 30, "retry": {"attempts": 3, "delay": 5}}
            >>> override = {"rate_limit": 60, "retry": {"attempts": 5}}
            >>> merged = factory._merge_configs(base, override)
            >>> assert merged == {
            ...     "rate_limit": 60,
            ...     "retry": {"attempts": 5, "delay": 5}
            ... }
        """
        result = base.copy()
        for key, value in override.items():
            if (
                key in result and
                isinstance(result[key], dict) and
                isinstance(value, dict)
            ):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result

    async def register_config(
        self,
        provider_id: Union[str, ProviderType],
        config: Dict[str, Any],
        validate: bool = True
    ) -> None:
        """Register a default configuration for a provider.

        Stores a configuration for a provider that can be used as a default when
        creating new instances. The configuration is optionally validated before
        being stored.

        Args:
            provider_id (Union[str, ProviderType]): Provider identifier
            config (Dict[str, Any]): Provider configuration to register
            validate (bool, optional): Whether to validate the configuration.
                                     Defaults to True.

        Raises:
            ProviderNotFoundError: If the specified provider is not registered
            ProviderConfigError: If the configuration fails validation

        Example:
            >>> config = {
            ...     "webhook_url": "https://discord.com/api/webhooks/123/abc",
            ...     "username": "Alert Bot",
            ...     "rate_limit": 30
            ... }
            >>> await factory.register_config("discord", config)
            >>> provider = await factory.create_provider("discord")  # Uses registered config
        """
        provider_id = str(provider_id)
        provider_class, validator_class = self._validate_provider_exists(provider_id)

        if validate:
            config = await self._validate_config(
                provider_id,
                validator_class,
                config
            )

        self._registered_configs[provider_id] = config
        logger.info(
            "Registered provider configuration",
            provider_id=provider_id,
            config=config
        )

    def get_available_providers(self) -> List[str]:
        """Get a list of all registered provider identifiers.

        Returns a list of provider IDs that have been registered with the factory
        and are available for use. This can be used to discover available
        notification providers.

        Returns:
            List[str]: List of registered provider identifiers

        Example:
            >>> providers = factory.get_available_providers()
            >>> print("Available providers:", providers)
            Available providers: ['discord', 'telegram', 'slack']
            >>> if "discord" in providers:
            ...     provider = await factory.create_provider("discord")
        """
        return list(self._providers.keys())

    async def get_provider(
        self,
        provider_id: Union[str, ProviderType],
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[NotificationProvider]:
        """Get an existing provider instance or create a new one.

        Retrieves an existing provider instance if one exists, or creates a new
        instance with the specified configuration. If no configuration is provided,
        uses the registered default configuration if available.

        Args:
            provider_id (Union[str, ProviderType]): Provider identifier
            config (Optional[Dict[str, Any]], optional): Provider configuration.
                                                       Defaults to None.

        Returns:
            Optional[NotificationProvider]: Provider instance or None if not available

        Example:
            >>> # Get or create with specific config
            >>> config = {"webhook_url": "https://discord.com/webhooks/123/abc"}
            >>> provider = await factory.get_provider("discord", config)
            >>>
            >>> # Get existing or use registered config
            >>> provider = await factory.get_provider("discord")
        """
        provider_id = str(provider_id)
        if provider_id in self._active_providers:
            return self._active_providers[provider_id]

        try:
            return await self.create_provider(provider_id, config)
        except (ProviderNotFoundError, ProviderConfigError) as e:
            logger.error(
                "Failed to get or create provider",
                provider_id=provider_id,
                error=str(e)
            )
            return None

    async def cleanup(self, timeout: float = 30.0) -> None:
        """Clean up all active provider instances and resources.

        Performs an orderly shutdown of all active provider instances, ensuring
        that resources are properly released and connections are closed. This
        method should be called when shutting down the application.

        Args:
            timeout (float, optional): Maximum time in seconds to wait for cleanup.
                                     Defaults to 30.0.

        Note:
            - Providers are cleaned up concurrently for efficiency
            - Each provider's cleanup is logged for monitoring
            - Failed cleanups are logged but don't prevent other cleanups

        Example:
            >>> try:
            ...     # Application shutdown
            ...     await factory.cleanup(timeout=60.0)
            ... except Exception as e:
            ...     logger.error("Cleanup failed", error=str(e))
        """
        async with self._lock:
            cleanup_tasks = []
            for provider_id, provider in self._active_providers.items():
                task = asyncio.create_task(
                    self._cleanup_provider(provider_id, provider)
                )
                cleanup_tasks.append(task)

            if cleanup_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*cleanup_tasks),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        "Provider cleanup timed out",
                        timeout=timeout
                    )
                except Exception as e:
                    logger.error(
                        "Provider cleanup failed",
                        error=str(e)
                    )

            self._active_providers.clear()
            self._validator_cache.clear()
            self._active_tasks.clear()

    async def _cleanup_provider(
        self,
        provider_id: str,
        provider: NotificationProvider
    ) -> None:
        """Clean up a single provider instance and its resources.

        Performs cleanup operations for a specific provider instance, including
        disconnecting from services, closing connections, and releasing resources.

        Args:
            provider_id (str): Unique identifier of the provider
            provider (NotificationProvider): Provider instance to clean up

        Note:
            - Failed cleanups are logged but don't raise exceptions
            - Provider state is tracked for monitoring purposes
            - Resources are released even if disconnect fails

        Example:
            >>> provider = await factory.create_provider("discord", config)
            >>> # Later during cleanup
            >>> await factory._cleanup_provider("discord", provider)
        """
        try:
            await provider.disconnect()
            logger.info(
                "Provider cleaned up successfully",
                provider_id=provider_id
            )
        except Exception as e:
            logger.error(
                "Provider cleanup failed",
                provider_id=provider_id,
                error=str(e)
            )


# Global factory instance
notification_factory = NotificationFactory()
