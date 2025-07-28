"""Plugin loader for dynamically loading notification providers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from collections.abc import Mapping, Sequence

from mover_status.notifications.base.registry import ProviderRegistry, get_global_registry
from mover_status.plugins.loader.discovery import PluginDiscovery

if TYPE_CHECKING:
    from mover_status.notifications.base.provider import NotificationProvider

logger = logging.getLogger(__name__)


class PluginLoadError(Exception):
    """Exception raised when a plugin fails to load."""
    pass


class PluginLoader:
    """Loads and manages notification provider plugins."""
    
    def __init__(
        self, 
        registry: ProviderRegistry | None = None,
        discovery: PluginDiscovery | None = None
    ) -> None:
        """Initialize plugin loader.
        
        Args:
            registry: Provider registry to use (defaults to global registry)
            discovery: Plugin discovery system (creates new if None)
        """
        self.registry: ProviderRegistry = registry or get_global_registry()
        self.discovery: PluginDiscovery = discovery or PluginDiscovery()
        self._loaded_plugins: dict[str, str] = {}  # Maps plugin name to provider name
        
        logger.info("Plugin loader initialized")
    
    def discover_and_load_all_plugins(self) -> dict[str, bool]:
        """Discover and load all available plugins.
        
        Returns:
            Dictionary mapping plugin names to load success status
        """
        logger.info("Starting plugin discovery and loading")
        
        # Discover plugins
        plugins = self.discovery.discover_plugins(force_reload=True)
        
        results: dict[str, bool] = {}
        
        for plugin_name, plugin_info in plugins.items():
            try:
                if plugin_info.provider_class and plugin_info.metadata:
                    success = self.load_plugin(plugin_name)
                    results[plugin_name] = success
                    
                    if success:
                        logger.info("Successfully loaded plugin: %s", plugin_name)
                    else:
                        logger.error("Failed to load plugin: %s", plugin_name)
                else:
                    results[plugin_name] = False
                    error_msg = str(plugin_info.load_error) if plugin_info.load_error else "No provider class or metadata"
                    logger.error("Plugin %s cannot be loaded: %s", plugin_name, error_msg)
                    
            except Exception as e:
                results[plugin_name] = False
                logger.error("Error loading plugin %s: %s", plugin_name, e)
        
        successful_loads = sum(1 for success in results.values() if success)
        logger.info("Plugin loading completed. Loaded %d/%d plugins", successful_loads, len(results))
        
        return results
    
    def load_plugin(self, plugin_name: str) -> bool:
        """Load a specific plugin.
        
        Args:
            plugin_name: Name of the plugin to load
            
        Returns:
            True if plugin was loaded successfully, False otherwise
        """
        if plugin_name in self._loaded_plugins:
            logger.debug("Plugin %s already loaded", plugin_name)
            return True
        
        plugin_info = self.discovery.get_plugin(plugin_name)
        if not plugin_info:
            logger.error("Plugin %s not found", plugin_name)
            return False
        
        if plugin_info.load_error:
            logger.error("Plugin %s has load error: %s", plugin_name, plugin_info.load_error)
            return False
        
        if not plugin_info.provider_class or not plugin_info.metadata:
            logger.error("Plugin %s missing provider class or metadata", plugin_name)
            return False
        
        try:
            # Register the plugin with the registry
            provider_name = plugin_info.metadata.name or plugin_name
            
            self.registry.register(
                name=provider_name,
                provider_class=plugin_info.provider_class,
                metadata=plugin_info.metadata
            )
            
            self._loaded_plugins[plugin_name] = provider_name
            logger.info("Loaded plugin %s as provider %s", plugin_name, provider_name)
            return True
            
        except Exception as e:
            logger.error("Error registering plugin %s: %s", plugin_name, e)
            return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a specific plugin.
        
        Args:
            plugin_name: Name of the plugin to unload
            
        Returns:
            True if plugin was unloaded successfully, False otherwise
        """
        if plugin_name not in self._loaded_plugins:
            logger.debug("Plugin %s not loaded", plugin_name)
            return True
        
        try:
            provider_name = self._loaded_plugins[plugin_name]
            self.registry.unregister(provider_name)
            del self._loaded_plugins[plugin_name]
            
            logger.info("Unloaded plugin %s (provider: %s)", plugin_name, provider_name)
            return True
            
        except Exception as e:
            logger.error("Error unloading plugin %s: %s", plugin_name, e)
            return False
    
    def load_enabled_plugins(self, enabled_providers: Sequence[object]) -> dict[str, bool]:
        """Load only plugins for enabled providers.
        
        Args:
            enabled_providers: List of enabled provider names
            
        Returns:
            Dictionary mapping plugin names to load success status
        """
        # Convert to strings to handle different literal types
        enabled_provider_names = [str(provider) for provider in enabled_providers]
        
        logger.info("Loading plugins for enabled providers: %s", enabled_provider_names)
        
        # Discover all plugins first
        plugins = self.discovery.discover_plugins(force_reload=True)
        
        results: dict[str, bool] = {}
        
        for plugin_name, plugin_info in plugins.items():
            # Check if this plugin provides an enabled provider
            if (plugin_info.metadata and 
                plugin_info.metadata.name in enabled_provider_names):
                
                try:
                    success = self.load_plugin(plugin_name)
                    results[plugin_name] = success
                    
                    if success:
                        logger.info("Loaded enabled plugin: %s", plugin_name)
                    else:
                        logger.error("Failed to load enabled plugin: %s", plugin_name)
                        
                except Exception as e:
                    results[plugin_name] = False
                    logger.error("Error loading enabled plugin %s: %s", plugin_name, e)
            else:
                logger.debug("Skipping plugin %s (not in enabled providers)", plugin_name)
        
        # Check for missing enabled providers
        loaded_provider_names: set[str] = set()
        for plugin_name in results:
            if results[plugin_name] and plugin_name in self._loaded_plugins:
                provider_name = self._loaded_plugins[plugin_name]
                metadata = self.registry.get_provider_metadata(provider_name)
                if metadata:
                    loaded_provider_names.add(metadata.name)
        
        missing_providers = set(enabled_provider_names) - loaded_provider_names
        if missing_providers:
            logger.warning("Some enabled providers could not be loaded: %s", missing_providers)
        
        return results
    
    def create_provider_instance(
        self, 
        provider_name: str, 
        config: Mapping[str, object]
    ) -> NotificationProvider | None:
        """Create an instance of a loaded provider.
        
        Args:
            provider_name: Name of the provider
            config: Provider configuration
            
        Returns:
            Provider instance or None if creation failed
        """
        try:
            return self.registry.create_provider(provider_name, config)
        except Exception as e:
            logger.error("Error creating provider instance %s: %s", provider_name, e)
            return None
    
    def get_loaded_plugins(self) -> dict[str, str]:
        """Get mapping of loaded plugins to their provider names.
        
        Returns:
            Dictionary mapping plugin names to provider names
        """
        return self._loaded_plugins.copy()
    
    def get_available_plugins(self) -> list[str]:
        """Get list of available plugin names.
        
        Returns:
            List of plugin names that can be loaded
        """
        return self.discovery.list_available_plugins()
    
    def get_loaded_plugin_count(self) -> int:
        """Get count of successfully loaded plugins.
        
        Returns:
            Number of loaded plugins
        """
        return len(self._loaded_plugins)
    
    def is_plugin_loaded(self, plugin_name: str) -> bool:
        """Check if a plugin is loaded.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            True if plugin is loaded, False otherwise
        """
        return plugin_name in self._loaded_plugins
    
    def get_plugin_provider_name(self, plugin_name: str) -> str | None:
        """Get the provider name for a loaded plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Provider name or None if plugin not loaded
        """
        return self._loaded_plugins.get(plugin_name)
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a plugin (unload and load again).
        
        Args:
            plugin_name: Name of the plugin to reload
            
        Returns:
            True if plugin was reloaded successfully, False otherwise
        """
        logger.info("Reloading plugin: %s", plugin_name)
        
        # Unload if currently loaded
        if self.is_plugin_loaded(plugin_name):
            if not self.unload_plugin(plugin_name):
                logger.error("Failed to unload plugin %s for reload", plugin_name)
                return False
        
        # Force rediscovery to pick up any changes
        _ = self.discovery.discover_plugins(force_reload=True)
        
        # Load the plugin
        return self.load_plugin(plugin_name)
    
    def get_loader_status(self) -> dict[str, object]:
        """Get comprehensive status of the plugin loader.
        
        Returns:
            Dictionary with loader status information
        """
        discovery_summary = self.discovery.get_discovery_summary()
        
        return {
            "loaded_plugins": len(self._loaded_plugins),
            "available_plugins": len(self.discovery.list_available_plugins()),
            "registered_providers": len(self.registry.list_providers()),
            "plugin_mappings": self._loaded_plugins.copy(),
            "discovery_summary": discovery_summary
        }
    
    def validate_plugin_dependencies(self, plugin_name: str) -> tuple[bool, list[str]]:
        """Validate that a plugin's dependencies are satisfied.
        
        Args:
            plugin_name: Name of the plugin to validate
            
        Returns:
            Tuple of (is_valid, missing_dependencies)
        """
        plugin_info = self.discovery.get_plugin(plugin_name)
        if not plugin_info or not plugin_info.metadata:
            return False, ["Plugin not found or has no metadata"]
        
        missing_deps: list[str] = []
        
        for dependency in plugin_info.metadata.dependencies:
            # Check if dependency is available as a loaded plugin or system module
            if not self.is_plugin_loaded(dependency):
                try:
                    __import__(dependency)
                except ImportError:
                    missing_deps.append(dependency)
        
        return len(missing_deps) == 0, missing_deps