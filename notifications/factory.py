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
    ...     def _format_message(self, message: str) -> Dict[str, Any]:
    ...         return {"text": message, "format": "plain"}

    # Create and use the provider:
    >>> factory = NotificationFactory()
    >>> provider = await factory.create_provider("custom", {
    ...     "api_key": "your-api-key",
    ...     "rate_limit": 30
    ... })
    >>> await provider.notify("Hello World")
"""

import asyncio
from typing import Any, Callable, Dict, Optional, Type, Union

from structlog import get_logger

from config.constants import NotificationProvider as ProviderType
from notifications.base import NotificationProvider
from utils.validators import validate_provider_config

logger = get_logger(__name__)


class ProviderError(Exception):
    """Base exception for provider-related errors."""
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
        """Initialize the notification factory."""
        self._providers: Dict[str, Type[NotificationProvider]] = {}
        self._validators: Dict[str, Callable] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._active_providers: Dict[str, NotificationProvider] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def register(
        cls,
        provider_id: str,
        validator: Optional[Callable] = None,
    ) -> Callable:
        """Register a new notification provider.

        Args:
            provider_id: Unique identifier for the provider
            validator: Optional configuration validator function

        Returns:
            Callable: Decorator function for provider registration

        Raises:
            ProviderError: If registration fails
            ValueError: If provider_id is invalid
        """
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ValueError("Provider ID must be a non-empty string")

        def decorator(provider_class: Type[NotificationProvider]) -> Type[NotificationProvider]:
            if not issubclass(provider_class, NotificationProvider):
                raise ProviderError(
                    f"Provider {provider_class.__name__} must inherit from NotificationProvider"
                )

            # Register provider and validator
            factory = cls()
            with factory._lock:
                if provider_id in factory._providers:
                    raise ProviderError(f"Provider {provider_id} already registered")

                factory._providers[provider_id] = provider_class
                if validator:
                    factory._validators[provider_id] = validator

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
    ) -> NotificationProvider:
        """Create or retrieve a provider instance.

        Args:
            provider_id: Provider identifier
            config: Optional provider configuration

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

            if provider_id not in self._providers:
                raise ProviderNotFoundError(f"Provider {provider_id} not registered")

            # Use provided config or fall back to registered config
            provider_config = config or self._configs.get(provider_id, {})

            # Validate configuration
            try:
                if provider_id in self._validators:
                    provider_config = self._validators[provider_id](provider_config)
                else:
                    provider_config = validate_provider_config(provider_config)
            except ValueError as err:
                raise ProviderConfigError(f"Invalid configuration for {provider_id}: {err}") from err

            # Create provider instance
            try:
                provider_class = self._providers[provider_id]
                provider = provider_class(provider_config)
                self._active_providers[provider_id] = provider

                logger.info(
                    "Created provider instance",
                    provider_id=provider_id,
                    provider_class=provider_class.__name__,
                )
                return provider

            except Exception as err:
                raise ProviderConfigError(
                    f"Failed to create provider {provider_id}: {err}"
                ) from err

    async def register_config(
        self,
        provider_id: Union[str, ProviderType],
        config: Dict[str, Any]
    ) -> None:
        """Register configuration for a provider.

        Args:
            provider_id: Provider identifier
            config: Provider configuration

        Raises:
            ProviderNotFoundError: If provider is not registered
            ProviderConfigError: If configuration is invalid
        """
        provider_id = str(provider_id)

        async with self._lock:
            if provider_id not in self._providers:
                raise ProviderNotFoundError(f"Provider {provider_id} not registered")

            try:
                if provider_id in self._validators:
                    config = self._validators[provider_id](config)
                else:
                    config = validate_provider_config(config)
            except ValueError as err:
                raise ProviderConfigError(f"Invalid configuration for {provider_id}: {err}") from err

            self._configs[provider_id] = config
            logger.debug(
                "Registered provider configuration",
                provider_id=provider_id,
            )

    def get_provider(self, provider_id: Union[str, ProviderType]) -> Optional[NotificationProvider]:
        """Get active provider instance if available.

        Args:
            provider_id: Provider identifier

        Returns:
            Optional[NotificationProvider]: Provider instance or None if not active
        """
        return self._active_providers.get(str(provider_id))

    def get_available_providers(self) -> Dict[str, Type[NotificationProvider]]:
        """Get all registered provider types.

        Returns:
            Dict[str, Type[NotificationProvider]]: Mapping of provider IDs to classes
        """
        return self._providers.copy()

    async def cleanup(self) -> None:
        """Clean up all active provider instances."""
        async with self._lock:
            for provider in self._active_providers.values():
                if hasattr(provider, 'disconnect'):
                    try:
                        await provider.disconnect()
                    except Exception as err:
                        logger.warning(
                            "Error disconnecting provider",
                            provider=provider.__class__.__name__,
                            error=str(err)
                        )
            self._active_providers.clear()


# Global factory instance
notification_factory = NotificationFactory()
