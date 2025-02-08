# notifications/factory.py

"""
Factory module for notification provider creation, configuration, and lifecycle management.

This module provides a centralized factory system for managing notification providers,
handling their registration, instantiation, and configuration. It supports advanced
features such as priority-based message handling, validator caching, and comprehensive
performance monitoring.

Key Features:
    - Provider Registration: Dynamic registration of notification providers with optional validators
    - Configuration Management: Validation and caching of provider configurations
    - Priority Handling: Support for LOW, NORMAL, and HIGH priority messages
    - Performance Monitoring: Tracking of validation times and message statistics
    - Validator Caching: Optimization of validation performance with TTL-based caching
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
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    runtime_checkable,
)

from structlog import get_logger

from config.constants import (
    API,
    MessagePriority,
)
from config.constants import (
    NotificationProvider as ProviderType,
)
from notifications.base import NotificationError, NotificationProvider
from utils.validators import BaseProviderValidator

logger = get_logger(__name__)

# Type variables for generic typing
T_Config = TypeVar('T_Config', bound=Dict[str, Any])
T_Provider = TypeVar('T_Provider', bound=NotificationProvider)
T_Validator = TypeVar('T_Validator', bound=BaseProviderValidator)

@runtime_checkable
class ValidatorProtocol(Protocol):
    """Protocol defining the validator interface."""
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]: ...

    @classmethod
    def validate_priority_config(cls, config: Dict[str, Any], priority: MessagePriority) -> Dict[str, Any]: ...

@runtime_checkable
class ProviderProtocol(Protocol):
    """Protocol defining the provider interface."""
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    def __init__(self, rate_limit: int = API.DEFAULT_RATE_LIMIT): ...

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
class ValidatorMetrics:
    """Metrics for tracking validator usage."""
    validation_count: int = 0
    total_validation_time: float = 0.0

@dataclass
class ValidatorCacheEntry:
    """Cache entry for validator instances."""
    validator: ValidatorProtocol
    metrics: ValidatorMetrics
    created_at: float
    last_used: float

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


class NotificationFactory(Generic[T_Provider]):
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

    def __init__(self) -> None:
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
            _validator_metrics (Dict[str, ValidatorMetrics]):
                Metrics for validator usage
            _registered_configs (Dict[str, Dict[str, Any]]):
                Registered configurations for providers
            _priority_stats (Dict[str, Dict[MessagePriority, int]]):
                Statistics tracking for message priorities per provider
        """
        self._registered_providers: Dict[str, Type[T_Provider]] = {}
        self._registered_validators: Dict[str, Type[ValidatorProtocol]] = {}
        self._active_providers: Dict[str, T_Provider] = {}
        self._validator_cache: Dict[str, ValidatorCacheEntry] = {}
        self._validator_metrics: Dict[str, ValidatorMetrics] = {}
        self._registered_configs: Dict[str, Dict[str, Any]] = {}
        self._priority_stats: Dict[str, Dict[MessagePriority, int]] = defaultdict(
            lambda: {priority: 0 for priority in MessagePriority}
        )
        self._lock = asyncio.Lock()

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
    def _validation_context(self, provider_id: str, operation: str) -> Iterator[ValidationContext]:
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
            ...     # Perform validation
            ...     result = validator.validate(config)
            ...     # Context automatically tracks timing
            >>> print(f"Validation took {ctx.validation_time:.2f} seconds")
        """
        context = ValidationContext(provider_id=provider_id, operation=operation)
        context.start_time = time.time()

        try:
            yield context
        finally:
            end_time = time.time()
            context.validation_time = end_time - context.start_time

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
        validator_class: Type[ValidatorProtocol]
    ) -> Optional[ValidatorProtocol]:
        """Retrieve a cached validator instance if it exists and is valid.

        Manages the validator cache with TTL-based expiration and usage tracking.
        If a cached validator is found but expired, it is removed from the cache.

        Args:
            provider_id (str): Unique identifier of the provider
            validator_class (Type[ValidatorProtocol]): Class type of the validator

        Returns:
            Optional[ValidatorProtocol]: Cached validator instance if valid, None otherwise

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
        cache_entry = self._validator_cache.get(provider_id)
        if cache_entry and isinstance(cache_entry.validator, validator_class):
            now = time.time()
            if now - cache_entry.created_at <= self.VALIDATOR_CACHE_TTL:
                cache_entry.last_used = now
                return cache_entry.validator
            # Remove expired cache entry
            del self._validator_cache[provider_id]
            del self._validator_metrics[provider_id]
        return None

    def _cache_validator(
        self,
        provider_id: str,
        validator: ValidatorProtocol
    ) -> None:
        """Cache a validator instance for future use.

        Creates a new cache entry for a validator instance with usage statistics
        tracking. The cache entry includes creation time, usage count, and
        performance metrics.

        Args:
            provider_id (str): Unique identifier of the provider
            validator (ValidatorProtocol): Validator instance to cache

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
        metrics = ValidatorMetrics()
        self._validator_metrics[provider_id] = metrics
        self._validator_cache[provider_id] = ValidatorCacheEntry(
            validator=validator,
            metrics=metrics,
            created_at=now,
            last_used=now
        )

    @classmethod
    def register(
        cls,
        provider_id: str,
        validator_class: Optional[Type[ValidatorProtocol]] = None
    ) -> Callable[[Type[T_Provider]], Type[T_Provider]]:
        """Register a new notification provider with optional validator.

        This decorator registers a provider class with its associated validator class.
        If no validator is provided, the provider's own validate_config method will be used.

        Args:
            provider_id (str): Unique identifier for the provider
            validator_class (Optional[Type[ValidatorProtocol]]): Optional validator class for the provider

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
            actual_validator = validator_class or cast(Type[ValidatorProtocol], provider_class)

            # Register provider using singleton instance
            factory = cls()

            # Use a new event loop for synchronous registration
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(factory._register_provider(provider_id, provider_class, actual_validator))
            finally:
                loop.close()

            return provider_class

        return decorator

    async def _register_provider(
        self,
        provider_id: str,
        provider_class: Type[T_Provider],
        validator_class: Type[ValidatorProtocol]
    ) -> None:
        """Internal method to register a provider with async lock."""
        async with self._lock:
            if provider_id in self._registered_providers:
                raise ProviderRegistrationError(f"Provider {provider_id} already registered")

            self._registered_providers[provider_id] = provider_class
            self._registered_validators[provider_id] = validator_class
            logger.info(
                "Registered notification provider",
                provider_id=provider_id,
                provider_class=provider_class.__name__,
                validator_class=validator_class.__name__,
            )

    def _validate_provider_exists(self, provider_id: str) -> Tuple[Type[NotificationProvider], Type[ValidatorProtocol]]:
        """Validate that a provider exists and return its class and validator.

        Args:
            provider_id (str): Provider identifier

        Returns:
            Tuple[Type[NotificationProvider], Type[ValidatorProtocol]]: Provider and validator classes

        Raises:
            ProviderNotFoundError: If provider is not registered
        """
        provider_class = self._registered_providers.get(provider_id)
        validator_class = self._registered_validators.get(provider_id)
        if not provider_class or not validator_class:
            logger.warning(
                "Attempted to create unregistered provider",
                provider_id=provider_id,
            )
            raise ProviderNotFoundError(f"Provider {provider_id} not registered")
        return provider_class, validator_class

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
        validator_class: Type[ValidatorProtocol],
        config: Dict[str, Any],
        priority_config: Optional[Dict[MessagePriority, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Validate provider configuration including priority-specific settings.

        This method validates both the base configuration and any priority-specific
        overrides. Priority configurations are merged with the base configuration
        before validation to ensure all required fields are present.

        Args:
            provider_id (str): Provider identifier
            validator_class (Type[ValidatorProtocol]): Validator class
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
        if not validator:
            validator = validator_class()
            self._cache_validator(provider_id, validator)

        metrics = self._validator_metrics[provider_id]
        start_time = time.time()
        try:
            config = validator.validate_config(config)
            if priority_config:
                for priority, override in priority_config.items():
                    override = validator.validate_priority_config(override, priority)
                    config = self._merge_configs(config, override)
        finally:
            validation_time = time.time() - start_time
            metrics.validation_count += 1
            metrics.total_validation_time += validation_time

        return config

    async def create_provider(
        self,
        provider_id: Union[str, ProviderType],
        config: Optional[Dict[str, Any]] = None,
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
            config (Optional[Dict[str, Any]], optional): Provider configuration.
                                                       Defaults to None.
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

            try:
                # Initialize provider with validated config
                rate_limit = provider_config.get('rate_limit')
                if isinstance(rate_limit, dict):
                    provider_config['rate_limit'] = rate_limit.get('value', API.DEFAULT_RATE_LIMIT)
                elif rate_limit is None:
                    provider_config['rate_limit'] = API.DEFAULT_RATE_LIMIT

                # Create provider instance
                provider = provider_class(rate_limit=provider_config['rate_limit'])

                # Set additional config after initialization
                for key, value in provider_config.items():
                    if key != 'rate_limit' and hasattr(provider, key):
                        setattr(provider, key, value)

                if isinstance(provider, ProviderProtocol):
                    logger.debug("Connecting provider", provider_id=provider_id)
                    await provider.connect()

                self._active_providers[provider_id] = cast(T_Provider, provider)
                logger.info(
                    "Created provider instance",
                    provider_id=provider_id,
                    provider_class=provider_class.__name__
                )
                return cast(T_Provider, provider)

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
        return list(self._registered_providers.keys())

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
            >>> config = {"webhook_url": "https://discord.com/api/webhooks/123/abc"}
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

    async def cleanup(self) -> None:
        """Cleanup active providers."""
        for provider_id, provider in self._active_providers.items():
            try:
                if isinstance(provider, ProviderProtocol):
                    await provider.disconnect()
            except Exception as e:
                logger.error(
                    "Error disconnecting provider",
                    provider_id=provider_id,
                    error=str(e)
                )

        self._active_providers.clear()
        self._validator_cache.clear()

# Global factory instance
notification_factory = NotificationFactory()
