"""Provider Registry System for notification providers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypeVar
from collections.abc import Mapping
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from collections.abc import Callable, Awaitable
    from mover_status.notifications.base.provider import NotificationProvider

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="NotificationProvider")


class ProviderRegistryError(Exception):
    """Exception raised by the provider registry."""
    pass


@dataclass
class ProviderMetadata:
    """Metadata for a notification provider."""
    name: str
    description: str
    version: str
    author: str
    provider_class: type[NotificationProvider]
    config_schema: dict[str, object] | None = None
    enabled: bool = True
    priority: int = 0
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        """String representation of metadata."""
        return f"{self.name} v{self.version} by {self.author}"


class ProviderRegistry:
    """Registry for managing notification providers."""
    
    def __init__(self) -> None:
        """Initialize the provider registry."""
        self._providers: dict[str, type[NotificationProvider]] = {}
        self._metadata: dict[str, ProviderMetadata] = {}
        self._instances: dict[str, NotificationProvider] = {}
        logger.info("Provider registry initialized")
        
    def register(
        self,
        name: str,
        provider_class: type[NotificationProvider],
        metadata: ProviderMetadata,
        force: bool = False
    ) -> None:
        """Register a notification provider.
        
        Args:
            name: Unique name for the provider
            provider_class: The provider class
            metadata: Provider metadata
            force: Whether to overwrite existing provider
            
        Raises:
            ProviderRegistryError: If provider already exists and force is False
        """
        if name in self._providers and not force:
            raise ProviderRegistryError(f"Provider '{name}' is already registered")
            
        self._providers[name] = provider_class
        self._metadata[name] = metadata
        
        # Clear cached instance if it exists
        if name in self._instances:
            del self._instances[name]
            
        logger.info("Registered provider: %s", name)
        
    def unregister(self, name: str) -> None:
        """Unregister a notification provider.
        
        Args:
            name: Name of the provider to unregister
            
        Raises:
            ProviderRegistryError: If provider is not registered
        """
        if name not in self._providers:
            raise ProviderRegistryError(f"Provider '{name}' is not registered")
            
        del self._providers[name]
        del self._metadata[name]
        
        # Clear cached instance if it exists
        if name in self._instances:
            del self._instances[name]
            
        logger.info("Unregistered provider: %s", name)
        
    def create_provider(
        self,
        name: str,
        config: Mapping[str, object],
        cache: bool = True
    ) -> NotificationProvider:
        """Create a provider instance.
        
        Args:
            name: Name of the provider
            config: Provider configuration
            cache: Whether to cache the instance
            
        Returns:
            Provider instance
            
        Raises:
            ProviderRegistryError: If provider is not registered
        """
        if name not in self._providers:
            raise ProviderRegistryError(f"Provider '{name}' is not registered")
            
        # Return cached instance if available and caching is enabled
        if cache and name in self._instances:
            return self._instances[name]
            
        provider_class = self._providers[name]
        provider = provider_class(config)
        
        # Cache the instance if caching is enabled
        if cache:
            self._instances[name] = provider
            
        logger.debug("Created provider instance: %s", name)
        return provider
        
    def list_providers(self, enabled_only: bool = False) -> list[str]:
        """List all registered providers.
        
        Args:
            enabled_only: Whether to only include enabled providers
            
        Returns:
            List of provider names
        """
        if not enabled_only:
            return list(self._providers.keys())
            
        return [
            name for name, metadata in self._metadata.items()
            if metadata.enabled
        ]
        
    def get_provider_metadata(self, name: str) -> ProviderMetadata | None:
        """Get metadata for a provider.
        
        Args:
            name: Name of the provider
            
        Returns:
            Provider metadata or None if not found
        """
        return self._metadata.get(name)
        
    def provider_exists(self, name: str) -> bool:
        """Check if a provider is registered.
        
        Args:
            name: Name of the provider
            
        Returns:
            True if provider exists, False otherwise
        """
        return name in self._providers


class ProviderDiscovery:
    """Discovery system for finding providers."""
    
    def __init__(self) -> None:
        """Initialize the discovery system."""
        self._search_paths: list[str] = []
        logger.info("Provider discovery initialized")
        
    def add_search_path(self, path: str) -> None:
        """Add a search path for providers.
        
        Args:
            path: Path to search for providers
        """
        if path not in self._search_paths:
            self._search_paths.append(path)
            logger.debug("Added search path: %s", path)
            
    def remove_search_path(self, path: str) -> None:
        """Remove a search path.
        
        Args:
            path: Path to remove
        """
        if path in self._search_paths:
            self._search_paths.remove(path)
            logger.debug("Removed search path: %s", path)
            
    def discover_providers(self) -> dict[str, tuple[type[NotificationProvider], ProviderMetadata]]:
        """Discover providers in search paths.
        
        Returns:
            Dictionary mapping provider names to (class, metadata) tuples
        """
        discovered: dict[str, tuple[type[NotificationProvider], ProviderMetadata]] = {}
        
        for search_path in self._search_paths:
            logger.debug("Searching for providers in: %s", search_path)
            # TODO: Implement actual provider discovery logic
            # This would involve scanning directories, importing modules,
            # and extracting provider classes and metadata
            
        logger.info("Discovered %d providers", len(discovered))
        return discovered
        
    def auto_register_providers(self, registry: ProviderRegistry) -> int:
        """Auto-register discovered providers.
        
        Args:
            registry: Registry to register providers in
            
        Returns:
            Number of providers registered
        """
        discovered = self.discover_providers()
        count = 0
        
        for name, (provider_class, metadata) in discovered.items():
            try:
                registry.register(name, provider_class, metadata)
                count += 1
            except ProviderRegistryError as e:
                logger.warning("Failed to auto-register provider %s: %s", name, e)
                
        logger.info("Auto-registered %d providers", count)
        return count


class ProviderLifecycleManager:
    """Manager for provider lifecycle operations."""
    
    def __init__(self) -> None:
        """Initialize the lifecycle manager."""
        self._instances: dict[str, NotificationProvider] = {}
        self._startup_hooks: list[Callable[[], Awaitable[None]]] = []
        self._shutdown_hooks: list[Callable[[], Awaitable[None]]] = []
        logger.info("Provider lifecycle manager initialized")
        
    def add_startup_hook(self, hook: Callable[[], Awaitable[None]]) -> None:
        """Add a startup hook.
        
        Args:
            hook: Async function to call on startup
        """
        self._startup_hooks.append(hook)
        logger.debug("Added startup hook: %s", hook.__name__)
        
    def add_shutdown_hook(self, hook: Callable[[], Awaitable[None]]) -> None:
        """Add a shutdown hook.
        
        Args:
            hook: Async function to call on shutdown
        """
        self._shutdown_hooks.append(hook)
        logger.debug("Added shutdown hook: %s", hook.__name__)
        
    async def startup_provider(self, name: str, provider: NotificationProvider) -> None:
        """Start up a provider.
        
        Args:
            name: Name of the provider
            provider: Provider instance
        """
        self._instances[name] = provider
        
        # Execute startup hooks
        for hook in self._startup_hooks:
            try:
                await hook()
            except Exception as e:
                logger.error("Startup hook failed: %s", e)
                
        logger.info("Started provider: %s", name)
        
    async def shutdown_provider(self, name: str) -> None:
        """Shutdown a provider.
        
        Args:
            name: Name of the provider
        """
        if name not in self._instances:
            return
            
        # Execute shutdown hooks
        for hook in self._shutdown_hooks:
            try:
                await hook()
            except Exception as e:
                logger.error("Shutdown hook failed: %s", e)
                
        del self._instances[name]
        logger.info("Shutdown provider: %s", name)
        
    async def shutdown_all_providers(self) -> None:
        """Shutdown all active providers."""
        provider_names = list(self._instances.keys())
        
        for name in provider_names:
            await self.shutdown_provider(name)
            
        logger.info("Shutdown all providers")
        
    def get_active_providers(self) -> list[str]:
        """Get list of active provider names.
        
        Returns:
            List of active provider names
        """
        return list(self._instances.keys())
        
    def is_provider_active(self, name: str) -> bool:
        """Check if a provider is active.
        
        Args:
            name: Name of the provider
            
        Returns:
            True if provider is active, False otherwise
        """
        return name in self._instances


# Global provider registry instance
_global_registry: ProviderRegistry | None = None


def get_global_registry() -> ProviderRegistry:
    """Get the global provider registry.
    
    Returns:
        Global provider registry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ProviderRegistry()
    return _global_registry


def reset_global_registry() -> None:
    """Reset the global provider registry."""
    global _global_registry
    _global_registry = None