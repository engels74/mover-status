# notifications/factory.py

"""
Factory for notification provider creation and management.
Handles provider registration, instantiation, and configuration validation.
Designed for easy addition of new providers without modifying existing code.

Example:
    # Register a new provider
    @NotificationFactory.register("custom")
    class CustomProvider(NotificationProvider):
        def __init__(self, config: Dict[str, Any]):
            super().__init__()
            self.client = CustomClient(config["api_key"])

    # Create provider instance
    factory = NotificationFactory()
    provider = await factory.create_provider("custom", {"api_key": "..."})
"""

from typing import Any, Callable, Dict, Optional, Type

from structlog import get_logger

from config.constants import NotificationProvider

logger = get_logger(__name__)


class ProviderRegistrationError(Exception):
    """Raised when provider registration fails."""


class ProviderNotFoundError(Exception):
    """Raised when requested provider is not registered."""


class InvalidProviderConfigError(Exception):
    """Raised when provider configuration is invalid."""


class NotificationFactory:
    """
    Factory for creating notification provider instances.
    Supports runtime provider registration and configuration validation.
    """

    def __init__(self):
        """Initialize the notification factory."""
        self._providers: Dict[str, Type[NotificationProvider]] = {}
        self._validators: Dict[str, Callable] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}

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

        Example:
            @NotificationFactory.register("discord", validate_discord_config)
            class DiscordProvider(NotificationProvider):
                pass
        """
        def decorator(provider_class: Type[NotificationProvider]) -> Type[NotificationProvider]:
            if not issubclass(provider_class, NotificationProvider):
                raise ProviderRegistrationError(
                    f"Provider {provider_class.__name__} must inherit from NotificationProvider"
                )

            # Register provider and validator
            factory = cls()
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

    def register_config(self, provider_id: str, config: Dict[str, Any]) -> None:
        """Register configuration for a provider.

        Args:
            provider_id: Provider identifier
            config: Provider configuration

        Raises:
            ProviderNotFoundError: If provider is not registered
            InvalidProviderConfigError: If configuration is invalid
        """
        if provider_id not in self._providers:
            raise ProviderNotFoundError(f"Provider {provider_id} not registered")

        # Validate configuration if validator exists
        if provider_id in self._validators:
            try:
                config = self._validators[provider_id](config)
            except ValueError as err:
                raise InvalidProviderConfigError(
                    f"Invalid configuration for {provider_id}: {err}"
                ) from err

        self._configs[provider_id] = config
        logger.debug(
            "Registered provider configuration",
            provider_id=provider_id,
            config=config,
        )

    async def create_provider(
        self,
        provider_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> NotificationProvider:
        """Create a new provider instance.

        Args:
            provider_id: Provider identifier
            config: Optional provider configuration (overrides registered config)

        Returns:
            NotificationProvider: Configured provider instance

        Raises:
            ProviderNotFoundError: If provider is not registered
            InvalidProviderConfigError: If configuration is invalid
        """
        if provider_id not in self._providers:
            raise ProviderNotFoundError(f"Provider {provider_id} not registered")

        # Use provided config or fall back to registered config
        provider_config = config or self._configs.get(provider_id, {})

        # Validate configuration
        if provider_id in self._validators:
            try:
                provider_config = self._validators[provider_id](provider_config)
            except ValueError as err:
                raise InvalidProviderConfigError(
                    f"Invalid configuration for {provider_id}: {err}"
                ) from err

        # Create provider instance
        provider_class = self._providers[provider_id]
        try:
            provider = provider_class(provider_config)
            logger.info(
                "Created provider instance",
                provider_id=provider_id,
                provider_class=provider_class.__name__,
            )
            return provider
        except Exception as err:
            raise InvalidProviderConfigError(
                f"Failed to create provider {provider_id}: {err}"
            ) from err

    def get_available_providers(self) -> Dict[str, Type[NotificationProvider]]:
        """Get all registered providers.

        Returns:
            Dict[str, Type[NotificationProvider]]: Mapping of provider IDs to classes
        """
        return self._providers.copy()

    def remove_provider(self, provider_id: str) -> None:
        """Remove a registered provider.

        Args:
            provider_id: Provider identifier to remove

        Raises:
            ProviderNotFoundError: If provider is not registered
        """
        if provider_id not in self._providers:
            raise ProviderNotFoundError(f"Provider {provider_id} not registered")

        self._providers.pop(provider_id)
        self._validators.pop(provider_id, None)
        self._configs.pop(provider_id, None)
        logger.info("Removed provider registration", provider_id=provider_id)


# Global factory instance
notification_factory = NotificationFactory()
