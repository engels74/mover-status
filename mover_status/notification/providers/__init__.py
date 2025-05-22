"""
Provider package discovery and registration.

This module provides functionality to discover and register notification providers
from the providers directory.
"""

import importlib
import logging
import os
from typing import override

from mover_status.notification.base import NotificationProvider
from mover_status.notification.registry import ProviderRegistry

# Get logger for this module
logger = logging.getLogger(__name__)


def discover_provider_packages() -> list[str]:
    """
    Discover provider packages from the providers directory.

    Returns:
        A list of provider package names.
    """
    provider_packages: list[str] = []

    # Get the directory containing this file
    providers_dir = os.path.dirname(__file__)

    try:
        # List all items in the providers directory
        items = os.listdir(providers_dir)

        for item in items:
            item_path = os.path.join(providers_dir, item)

            # Skip non-directories and special directories
            if not os.path.isdir(item_path) or item.startswith('__'):
                continue

            # Check if it's a valid provider package
            if validate_provider_package(item):
                provider_packages.append(item)
                logger.debug("Discovered provider package: %s", item)
            else:
                logger.warning("Invalid provider package: %s", item)

    except OSError as e:
        logger.error("Error discovering provider packages: %s", e)

    return provider_packages


def validate_provider_package(package_name: str) -> bool:
    """
    Validate that a provider package has the required structure.

    Args:
        package_name: The name of the provider package to validate.

    Returns:
        True if the package is valid, False otherwise.
    """
    providers_dir = os.path.dirname(__file__)
    package_dir = os.path.join(providers_dir, package_name)

    # Check for required files
    init_file = os.path.join(package_dir, '__init__.py')
    provider_file = os.path.join(package_dir, 'provider.py')

    return os.path.exists(init_file) and os.path.exists(provider_file)


def load_provider_class(package_name: str) -> type[NotificationProvider] | None:
    """
    Load a provider class from a provider package.

    Args:
        package_name: The name of the provider package.

    Returns:
        The provider class, or None if loading failed.
    """
    try:
        # Import the provider module
        module_name = f"mover_status.notification.providers.{package_name}"
        module = importlib.import_module(module_name)

        # Get the provider class
        if hasattr(module, 'get_provider_class'):
            provider_class = module.get_provider_class()  # pyright: ignore[reportAny]

            # Validate that it's a NotificationProvider subclass
            if (isinstance(provider_class, type) and
                issubclass(provider_class, NotificationProvider)):
                logger.debug("Loaded provider class: %s", provider_class.__name__)
                return provider_class
            else:
                logger.warning("Provider class from %s is not a valid NotificationProvider", package_name)
                return None
        else:
            logger.warning("Provider package %s does not have a get_provider_class function", package_name)
            return None

    except ImportError as e:
        logger.warning("Failed to import provider package %s: %s", package_name, e)
        return None
    except Exception as e:
        logger.error("Unexpected error loading provider class from %s: %s", package_name, e)
        return None


def register_discovered_providers(registry: ProviderRegistry, package_names: list[str]) -> int:
    """
    Register discovered providers with the registry.

    Args:
        registry: The provider registry to register with.
        package_names: List of provider package names to register.

    Returns:
        The number of providers successfully registered.
    """
    registered_count = 0

    for package_name in package_names:
        try:
            provider_class = load_provider_class(package_name)
            if provider_class is not None:
                # Create an instance with minimal configuration for registration
                # In a real implementation, this would use actual configuration
                # For now, we'll create a mock instance with metadata only
                mock_metadata: dict[str, object] = {
                    "version": "1.0.0",
                    "description": f"{package_name.title()} notification provider",
                    "package_name": package_name
                }

                # Create a mock provider instance for registration
                # This is a temporary solution - in the real implementation,
                # providers would be registered as classes, not instances
                class MockProviderInstance(NotificationProvider):
                    def __init__(self, name: str, metadata: dict[str, object], provider_cls: type[NotificationProvider]) -> None:
                        super().__init__(name, metadata)
                        self.provider_class: type[NotificationProvider] = provider_cls

                    @override
                    def send_notification(self, message: str, **kwargs: object) -> bool:
                        # This is a placeholder - real instances would be created with config
                        return False

                    @override
                    def validate_config(self) -> list[str]:
                        return ["Provider not configured - this is a registry placeholder"]

                provider_instance = MockProviderInstance(package_name, mock_metadata, provider_class)

                # Register the provider
                registry.register_provider(package_name, provider_instance)
                registered_count += 1
                logger.info("Registered provider: %s", package_name)
            else:
                logger.warning("Failed to load provider class for package: %s", package_name)

        except Exception as e:
            logger.error("Failed to register provider %s: %s", package_name, e)

    return registered_count


def auto_discover_and_register(registry: ProviderRegistry) -> int:
    """
    Automatically discover and register all available providers.

    Args:
        registry: The provider registry to register with.

    Returns:
        The number of providers successfully registered.
    """
    logger.info("Starting automatic provider discovery...")

    # Discover provider packages
    package_names = discover_provider_packages()
    logger.info("Discovered %d provider packages: %s", len(package_names), package_names)

    # Register discovered providers
    registered_count = register_discovered_providers(registry, package_names)
    logger.info("Successfully registered %d providers", registered_count)

    return registered_count