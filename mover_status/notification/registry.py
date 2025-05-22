"""
Provider registry for notification providers.

This module provides the ProviderRegistry class that manages provider registration
and discovery for the notification system.
"""

import importlib
import importlib.metadata
import logging

from mover_status.notification.base import NotificationProvider

# Get logger for this module
logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Registry for notification providers.

    This class manages the registration and discovery of notification providers.
    It provides methods to register providers, discover providers from entry points,
    and load provider modules dynamically.

    Attributes:
        _providers: A dictionary of registered providers.
    """

    def __init__(self) -> None:
        """Initialize the provider registry."""
        self._providers: dict[str, NotificationProvider] = {}

    def register_provider(self, name: str, provider: NotificationProvider) -> None:
        """
        Register a notification provider with the registry.

        Args:
            name: The name of the provider.
            provider: The provider instance to register.

        Raises:
            ValueError: If the provider is already registered or metadata is invalid.
        """
        # Check if provider is already registered
        if name in self._providers:
            raise ValueError(f"Provider '{name}' is already registered")

        # Validate provider metadata
        if provider.metadata is None:
            raise ValueError("Provider metadata is required")

        # Note: provider.metadata is already typed as Mapping[str, object] | None
        # so this check is redundant but kept for runtime safety

        # Register the provider
        logger.debug("Registering provider: %s", name)
        self._providers[name] = provider

    def get_registered_providers(self) -> dict[str, NotificationProvider]:
        """
        Get all registered providers.

        Returns:
            A dictionary of registered providers.
        """
        return self._providers.copy()

    def discover_providers(self) -> dict[str, type[NotificationProvider]]:
        """
        Discover providers from entry points.

        Returns:
            A dictionary of discovered provider classes.
        """
        discovered_providers: dict[str, type[NotificationProvider]] = {}

        try:
            # Get entry points for notification providers
            entry_points = importlib.metadata.entry_points(group="mover_status.notification_providers")

            for entry_point in entry_points:
                try:
                    # Load the provider class
                    provider_class = entry_point.load()  # pyright: ignore[reportAny]

                    # Validate that it's a NotificationProvider
                    if not issubclass(provider_class, NotificationProvider):
                        logger.warning("Entry point '%s' does not provide a valid NotificationProvider", entry_point.name)
                        continue

                    # Create an instance (this would need configuration in real usage)
                    # For discovery purposes, we just validate the class
                    discovered_providers[entry_point.name] = provider_class

                except (ImportError, AttributeError, TypeError) as e:
                    logger.warning("Failed to load provider from entry point '%s': %s", entry_point.name, e)
                    continue

        except Exception as e:
            logger.error("Error discovering providers from entry points: %s", e)

        return discovered_providers

    def load_provider_module(self, module_name: str) -> type[NotificationProvider]:
        """
        Load a provider module dynamically.

        Args:
            module_name: The name of the module to load.

        Returns:
            The provider class from the module.

        Raises:
            ImportError: If the module cannot be imported.
            AttributeError: If the module doesn't have a get_provider_class function.
        """
        try:
            # Import the module
            module = importlib.import_module(module_name)

            # Get the provider class
            if hasattr(module, 'get_provider_class'):
                provider_class = module.get_provider_class()  # pyright: ignore[reportAny]
                return provider_class  # pyright: ignore[reportAny]
            else:
                raise AttributeError(f"Module '{module_name}' does not have a 'get_provider_class' function")

        except ImportError as e:
            logger.error("Failed to import module '%s': %s", module_name, e)
            raise
        except AttributeError as e:
            logger.error("Failed to get provider class from module '%s': %s", module_name, e)
            raise
