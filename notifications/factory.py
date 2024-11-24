# notifications/factory.py

"""
Factory for notification provider creation and management.
Provides centralized provider registration and instantiation handling.

Examples:
    # Register a new provider class:
    >>> @NotificationFactory.register("custom")
    ... class CustomProvider(NotificationProvider):
    ...     def __init__(self, config: Dict[str, Any]):
    ...         super().__init__()
    ...         self.client = CustomClient(config["api_key"])
    ...
    ...     async def send_notification(self, message: str) -> bool:
    ...         return await self.client.send(message)
    ...
    ...     @classmethod
    ...     def validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
    ...         # Custom validation logic
    ...         return config

    # Create and use the provider:
    >>> factory = NotificationFactory()
    >>> provider = await factory.create_provider("custom", {
    ...     "api_key": "your-api-key",
    ...     "rate_limit": 30
    ... })
    >>> await provider.notify("Hello World")
"""

import asyncio
from typing import Any, Dict, List, Optional, Set, Type, Union

from structlog import get_logger

from config.constants import NotificationProvider as ProviderType
from notifications.base import NotificationError, NotificationProvider

logger = get_logger(__name__)


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
    """Factory for managing notification provider lifecycle."""

    def __init__(self):
        """Initialize notification factory."""
        self._providers: Dict[str, Type[NotificationProvider]] = {}
        self._active_providers: Dict[str, NotificationProvider] = {}
        self._registered_configs: Dict[str, Dict[str, Any]] = {}
        self._active_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()

    @classmethod
    def register(cls, provider_id: str) -> callable:
        """Register a new notification provider.

        Args:
            provider_id: Unique identifier for the provider

        Returns:
            callable: Decorator function for provider registration

        Raises:
            ProviderRegistrationError: If registration fails
            ValueError: If provider_id is invalid
        """
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ValueError("Provider ID must be a non-empty string")

        def decorator(provider_class: Type[NotificationProvider]) -> Type[NotificationProvider]:
            if not issubclass(provider_class, NotificationProvider):
                raise ProviderRegistrationError(
                    f"Provider {provider_class.__name__} must inherit from NotificationProvider"
                )

            # Register provider using singleton instance
            factory = cls()
            with factory._lock:
                if provider_id in factory._providers:
                    raise ProviderRegistrationError(f"Provider {provider_id} already registered")

                factory._providers[provider_id] = provider_class
                logger.info(
                    "Registered notification provider",
                    provider_id=provider_id,
                    provider_class=provider_class.__name__,
                )

            return provider_class

        return decorator

    async def create_provider(
        self,
        provider_id: Union[str, ProviderType],
        config: Optional[Dict[str, Any]] = None,
        validate: bool = True
    ) -> NotificationProvider:
        """Create or retrieve a provider instance.

        Args:
            provider_id: Provider identifier
            config: Optional provider configuration
            validate: Whether to validate configuration

        Returns:
            NotificationProvider: Provider instance

        Raises:
            ProviderNotFoundError: If provider is not registered
            ProviderConfigError: If configuration is invalid
        """
        provider_id = str(provider_id)

        async with self._lock:
            # Return existing instance if available
            if provider_id in self._active_providers:
                return self._active_providers[provider_id]

            # Verify provider is registered
            provider_class = self._providers.get(provider_id)
            if not provider_class:
                raise ProviderNotFoundError(f"Provider {provider_id} not registered")

            # Use provided config or fallback to registered config
            provider_config = config or self._registered_configs.get(provider_id, {})

            try:
                # Validate configuration if requested
                if validate:
                    provider_config = provider_class.validate_config(provider_config)

                # Initialize provider
                provider = provider_class(provider_config)
                if hasattr(provider, 'connect'):
                    await provider.connect()

                self._active_providers[provider_id] = provider
                logger.info(
                    "Created provider instance",
                    provider_id=provider_id,
                    provider_class=provider_class.__name__,
                )
                return provider

            except NotificationError:
                raise
            except Exception as err:
                raise ProviderConfigError(
                    f"Failed to create provider {provider_id}: {err}"
                ) from err

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
        provider_class = self._providers.get(provider_id)
        if not provider_class:
            raise ProviderNotFoundError(f"Provider {provider_id} not registered")

        try:
            # Validate if requested
            if validate:
                config = provider_class.validate_config(config)

            async with self._lock:
                self._registered_configs[provider_id] = config
                logger.debug(
                    "Registered provider configuration",
                    provider_id=provider_id,
                )

        except NotificationError:
            raise
        except Exception as err:
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
