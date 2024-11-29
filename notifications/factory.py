# notifications/factory.py

"""
Factory for notification provider creation and management.
Provides centralized provider registration, instantiation, and priority-based configuration handling.

The factory supports priority-based message handling with three levels:
- LOW: For non-urgent messages that can be delayed or dropped
- NORMAL: Default priority for regular messages
- HIGH: For urgent messages requiring immediate delivery

Each priority level can have its own configuration settings, including rate limits and retry attempts.
The factory tracks priority-based statistics and manages validator caching for improved performance.

Examples:
    # Register a new provider class with priority support:
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
    ...         # Custom validation logic
    ...         return config

    # Create and use the provider with priority configuration:
    >>> factory = NotificationFactory()
    >>> priority_config = {
    ...     MessagePriority.HIGH: {"rate_limit": 60, "retry_attempts": 5},
    ...     MessagePriority.LOW: {"rate_limit": 15, "retry_attempts": 1}
    ... }
    >>> provider = await factory.create_provider(
    ...     "custom",
    ...     {
    ...         "api_key": "your-api-key",
    ...         "rate_limit": 30,
    ...         "retry_attempts": 3
    ...     },
    ...     priority_config=priority_config
    ... )
    >>> await provider.notify("Hello World")
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
    """Context for validation operations."""
    provider_id: str
    operation: str
    start_time: float = 0.0
    validation_time: float = 0.0

@dataclass
class ValidatorCacheEntry:
    """Cache entry for validator instances."""
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
    """Base exception for provider-related errors."""
    pass


class ProviderRegistrationError(ProviderError):
    """Raised when provider registration fails."""
    pass


class ProviderNotFoundError(ProviderError):
    """Raised when requested provider is not registered."""
    pass


class ProviderConfigError(ProviderError):
    """Raised when provider configuration is invalid."""
    pass


class NotificationFactory:
    """Factory for managing notification provider and validator lifecycle.
    This factory handles the registration, creation, and lifecycle management of notification
    providers and their associated validators. It supports caching of validator instances
    and provides a consistent validation interface across different provider types.

    Examples:
        # Register a provider with its validator
        >>> @NotificationFactory.register("discord", DiscordValidator)
        ... class DiscordProvider(NotificationProvider):
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
        """Initialize notification factory."""
        self._providers: Dict[str, Tuple[Type[NotificationProvider], Type[BaseProviderValidator]]] = {}
        self._active_providers: Dict[str, NotificationProvider] = {}
        self._validator_cache: Dict[str, ValidatorCacheEntry] = {}
        self._registered_configs: Dict[str, Dict[str, Any]] = {}
        self._active_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._priority_stats: Dict[str, Dict[MessagePriority, int]] = {}

    def _update_priority_stats(self, provider_id: str, priority: MessagePriority) -> None:
        """Update priority-based statistics for a provider.

        Tracks the usage count of each priority level (LOW, NORMAL, HIGH) for the
        specified provider. This information can be used for monitoring and
        optimization purposes.

        Args:
            provider_id: Provider identifier
            priority: Message priority level

        Example:
            >>> factory._update_priority_stats("telegram", MessagePriority.HIGH)
            >>> stats = factory._priority_stats["telegram"]
            >>> assert stats[MessagePriority.HIGH] > 0
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
        """Create a validation context for monitoring and logging.

        Args:
            provider_id: Provider identifier
            operation: Name of the validation operation

        Yields:
            ValidationContext: Context object for the validation operation
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
        """Get a cached validator instance if valid.

        Args:
            provider_id: Provider identifier
            validator_class: Validator class to instantiate if needed

        Returns:
            Optional[BaseProviderValidator]: Cached validator instance or None
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
        """Cache a validator instance.

        Args:
            provider_id: Provider identifier
            validator: Validator instance to cache
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
            provider_id: Unique identifier for the provider
            validator_class: Optional validator class for the provider

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
            provider_id: Provider identifier

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
            provider_id: Provider identifier
            config: Optional provider configuration

        Returns:
            Dict[str, Any]: Provider configuration

        Raises:
            ProviderConfigError: If no configuration is available
        """
        provider_config = config or self._registered_configs.get(provider_id, {})
        if not provider_config:
            raise ProviderConfigError(f"No configuration available for provider: {provider_id}")
        return provider_config

    def _validate_config(
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
            provider_id: Provider identifier
            validator_class: Validator class
            config: Provider configuration
            priority_config: Optional priority-specific configuration overrides

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
            provider_id: Provider identifier
            config: Optional provider configuration
            validate: Whether to validate configuration
            priority_config: Optional priority-specific configuration overrides.
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
                provider_config = self._validate_config(
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
        """Deep merge two configuration dictionaries.

        Args:
            base: Base configuration
            override: Configuration to override with

        Returns:
            Dict[str, Any]: Merged configuration
        """
        result = base.copy()
        for key, value in override.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
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
        """Register configuration for a provider.
        Args:
            provider_id: Provider identifier
            config: Provider configuration
            validate: Whether to validate configuration

        Raises:
            ProviderNotFoundError: If provider is not registered
            ProviderConfigError: If configuration is invalid
        """
        provider_id = str(provider_id)

        # Verify provider is registered
        provider_tuple = self._providers.get(provider_id)
        if not provider_tuple:
            logger.warning(
                "Attempted to register config for unregistered provider",
                provider_id=provider_id,
            )
            raise ProviderNotFoundError(f"Provider {provider_id} not registered")

        provider_class, validator_class = provider_tuple

        try:
            # Validate if requested
            if validate:
                # Try to get cached validator
                validator = self._get_cached_validator(provider_id, validator_class)

                if not validator and callable(validator_class):
                    # Create new validator instance
                    validator = validator_class()
                    self._cache_validator(provider_id, validator)

                # Validate configuration using validation context
                with self._validation_context(provider_id, "register_config"):
                    if validator and hasattr(validator, 'validate_config'):
                        config = validator.validate_config(config)
                    else:
                        # Fallback to class method if no validator instance
                        config = validator_class.validate_config(config)

            async with self._lock:
                self._registered_configs[provider_id] = config
                logger.debug(
                    "Registered provider configuration",
                    provider_id=provider_id,
                )

        except NotificationError:
            logger.error(
                "Config registration failed with NotificationError",
                provider_id=provider_id,
                error_type=type(NotificationError).__name__,
            )
            raise
        except Exception as err:
            logger.error(
                "Config registration failed with unexpected error",
                provider_id=provider_id,
                error_type=type(err).__name__,
                error=str(err),
            )
            raise ProviderConfigError(
                f"Invalid configuration for {provider_id}: {err}"
            ) from err

    async def get_provider(
        self,
        provider_id: Union[str, ProviderType],
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[NotificationProvider]:
        """Get or create provider instance.
        Args:
            provider_id: Provider identifier
            config: Optional configuration for new instance

        Returns:
            Optional[NotificationProvider]: Provider instance or None if not available
        """
        provider_id = str(provider_id)
        try:
            return await self.create_provider(provider_id, config)
        except ProviderError:
            return None

    def get_available_providers(self) -> List[str]:
        """Get list of registered provider IDs.
        Returns:
            List[str]: List of provider identifiers
        """
        return list(self._providers.keys())

    async def cleanup(self, timeout: float = 30.0) -> None:
        """Clean up all active provider instances.
        Args:
            timeout: Maximum time to wait for cleanup in seconds
        """
        async with self._lock:
            cleanup_tasks = []

            # Disconnect providers
            for provider_id, provider in self._active_providers.items():
                if hasattr(provider, 'disconnect'):
                    task = asyncio.create_task(self._cleanup_provider(provider_id, provider))
                    cleanup_tasks.append(task)

            # Wait for all cleanup tasks
            if cleanup_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*cleanup_tasks, return_exceptions=True),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning("Provider cleanup timed out")

            # Clear provider references
            self._active_providers.clear()
            self._registered_configs.clear()

    async def _cleanup_provider(
        self,
        provider_id: str,
        provider: NotificationProvider
    ) -> None:
        """Clean up a single provider instance.
        Args:
            provider_id: Provider identifier
            provider: Provider instance to clean up
        """
        try:
            await provider.disconnect()
            logger.debug(f"Disconnected provider: {provider_id}")
        except Exception as err:
            logger.warning(
                "Error disconnecting provider",
                provider_id=provider_id,
                error=str(err)
            )


# Global factory instance
notification_factory = NotificationFactory()
