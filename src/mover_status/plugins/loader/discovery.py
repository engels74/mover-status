"""Plugin discovery system for dynamically finding and loading notification providers."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from mover_status.notifications.base.provider import NotificationProvider
    from mover_status.notifications.base.registry import ProviderMetadata

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Information about a discovered plugin."""
    
    name: str
    path: Path
    module_name: str
    provider_class: type[NotificationProvider] | None = None
    metadata: ProviderMetadata | None = None
    load_error: Exception | None = None
    version: str = "1.0.0"
    description: str = ""
    author: str = "Unknown"
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


class PluginDiscoveryError(Exception):
    """Exception raised during plugin discovery."""
    pass


class PluginDiscovery:
    """Discovers and loads notification provider plugins dynamically."""
    
    def __init__(self, base_package: str = "mover_status.plugins") -> None:
        """Initialize plugin discovery.
        
        Args:
            base_package: Base package path for plugin discovery
        """
        self.base_package: str = base_package
        self._discovered_plugins: dict[str, PluginInfo] = {}
        self._search_paths: list[Path] = []
        
        # Add default search paths
        self._add_default_search_paths()
        
        logger.info("Plugin discovery initialized for package: %s", base_package)
    
    def _add_default_search_paths(self) -> None:
        """Add default search paths for plugin discovery."""
        # Get the plugins directory from the base package
        try:
            base_module = importlib.import_module(self.base_package)
            if hasattr(base_module, "__path__"):
                for path_str in base_module.__path__:
                    plugins_path = Path(path_str)
                    if plugins_path.exists():
                        self._search_paths.append(plugins_path)
                        logger.debug("Added default search path: %s", plugins_path)
        except ImportError as e:
            logger.warning("Could not import base package %s: %s", self.base_package, e)
    
    def add_search_path(self, path: Path | str) -> None:
        """Add a custom search path for plugins.
        
        Args:
            path: Path to search for plugins
        """
        path_obj = Path(path)
        if path_obj not in self._search_paths:
            self._search_paths.append(path_obj)
            logger.debug("Added search path: %s", path_obj)
    
    def discover_plugins(self, force_reload: bool = False) -> dict[str, PluginInfo]:
        """Discover all available plugins.
        
        Args:
            force_reload: Whether to force rediscovery of plugins
            
        Returns:
            Dictionary mapping plugin names to PluginInfo objects
        """
        if self._discovered_plugins and not force_reload:
            return self._discovered_plugins.copy()
        
        self._discovered_plugins.clear()
        
        logger.info("Starting plugin discovery in %d search paths", len(self._search_paths))
        
        for search_path in self._search_paths:
            try:
                self._discover_plugins_in_path(search_path)
            except Exception as e:
                logger.error("Error discovering plugins in %s: %s", search_path, e)
        
        logger.info("Plugin discovery completed. Found %d plugins", len(self._discovered_plugins))
        return self._discovered_plugins.copy()
    
    def _discover_plugins_in_path(self, search_path: Path) -> None:
        """Discover plugins in a specific path.
        
        Args:
            search_path: Path to search for plugins
        """
        if not search_path.exists() or not search_path.is_dir():
            logger.debug("Search path does not exist or is not a directory: %s", search_path)
            return
        
        logger.debug("Discovering plugins in: %s", search_path)
        
        # Look for plugin directories (exclude template and loader)
        excluded_dirs = {"template", "loader", "__pycache__"}
        
        for plugin_dir in search_path.iterdir():
            if (plugin_dir.is_dir() and 
                plugin_dir.name not in excluded_dirs and 
                not plugin_dir.name.startswith(".")):
                
                try:
                    plugin_info = self._load_plugin_from_directory(plugin_dir)
                    if plugin_info:
                        self._discovered_plugins[plugin_info.name] = plugin_info
                        logger.debug("Discovered plugin: %s", plugin_info.name)
                except Exception as e:
                    logger.error("Error loading plugin from %s: %s", plugin_dir, e)
    
    def _load_plugin_from_directory(self, plugin_dir: Path) -> PluginInfo | None:
        """Load plugin information from a directory.
        
        Args:
            plugin_dir: Directory containing the plugin
            
        Returns:
            PluginInfo object or None if plugin couldn't be loaded
        """
        plugin_name = plugin_dir.name
        
        # Check for provider.py file
        provider_file = plugin_dir / "provider.py"
        if not provider_file.exists():
            logger.debug("No provider.py found in %s", plugin_dir)
            return None
        
        # Check for __init__.py to ensure it's a valid Python package
        init_file = plugin_dir / "__init__.py"
        if not init_file.exists():
            logger.debug("No __init__.py found in %s", plugin_dir)
            return None
        
        # Construct module name
        module_name = f"{self.base_package}.{plugin_name}.provider"
        
        plugin_info = PluginInfo(
            name=plugin_name,
            path=plugin_dir,
            module_name=module_name
        )
        
        try:
            # Import the module
            module = importlib.import_module(module_name)
            
            # Look for provider class
            provider_class = self._find_provider_class(module, plugin_name)
            if provider_class:
                plugin_info.provider_class = provider_class
                
                # Try to load metadata
                metadata = self._load_plugin_metadata(module, plugin_name)
                plugin_info.metadata = metadata
                
                if metadata:
                    plugin_info.version = metadata.version
                    plugin_info.description = metadata.description
                    plugin_info.author = metadata.author
                    plugin_info.tags = metadata.tags.copy()
                    plugin_info.dependencies = metadata.dependencies.copy()
                
                logger.debug("Successfully loaded plugin: %s from %s", plugin_name, module_name)
                return plugin_info
            else:
                logger.warning("No valid provider class found in %s", module_name)
                return None
                
        except Exception as e:
            plugin_info.load_error = e
            logger.error("Error loading plugin %s: %s", plugin_name, e)
            return plugin_info
    
    def _find_provider_class(self, module: object, plugin_name: str) -> type[NotificationProvider] | None:
        """Find the provider class in a module.
        
        Args:
            module: The imported module
            plugin_name: Name of the plugin
            
        Returns:
            Provider class or None if not found
        """
        from mover_status.notifications.base.provider import NotificationProvider
        
        # Common naming patterns for provider classes
        possible_names = [
            f"{plugin_name.title()}Provider",
            f"{plugin_name.capitalize()}Provider", 
            f"{plugin_name.upper()}Provider",
            "Provider",
        ]
        
        for class_name in possible_names:
            if hasattr(module, class_name):
                cls = getattr(module, class_name)  # pyright: ignore[reportAny] # dynamic attribute access
                if (isinstance(cls, type) and 
                    issubclass(cls, NotificationProvider) and 
                    cls is not NotificationProvider):
                    return cls
        
        # Fallback: look for any class that inherits from NotificationProvider
        for attr_name in dir(module):
            attr = getattr(module, attr_name)  # pyright: ignore[reportAny] # dynamic attribute access
            if (isinstance(attr, type) and 
                issubclass(attr, NotificationProvider) and 
                attr is not NotificationProvider):
                return attr
        
        return None
    
    def _load_plugin_metadata(self, module: object, plugin_name: str) -> ProviderMetadata | None:
        """Load plugin metadata from module or metadata file.
        
        Args:
            module: The imported module
            plugin_name: Name of the plugin
            
        Returns:
            ProviderMetadata object or None if not found
        """
        from mover_status.notifications.base.registry import ProviderMetadata
        
        # Try to get metadata from module attributes
        if hasattr(module, "PLUGIN_METADATA"):
            try:
                metadata_dict: dict[str, object] = getattr(module, "PLUGIN_METADATA")  # pyright: ignore[reportAny] # dynamic module attribute
                provider_class = self._find_provider_class(module, plugin_name)
                if provider_class:
                    name: str = str(metadata_dict.get("name", plugin_name))
                    description: str = str(metadata_dict.get("description", f"Plugin {plugin_name}"))
                    version: str = str(metadata_dict.get("version", "1.0.0"))
                    author: str = str(metadata_dict.get("author", "Unknown"))
                    tags_raw = metadata_dict.get("tags", [])
                    dependencies_raw = metadata_dict.get("dependencies", [])
                    
                    tags: list[str] = []
                    if isinstance(tags_raw, (list, tuple)):
                        tags = [str(tag) for tag in tags_raw]  # pyright: ignore[reportUnknownArgumentType] # dynamic tag conversion
                    
                    dependencies: list[str] = []
                    if isinstance(dependencies_raw, (list, tuple)):
                        dependencies = [str(dep) for dep in dependencies_raw]  # pyright: ignore[reportUnknownArgumentType] # dynamic dependency conversion
                    
                    return ProviderMetadata(
                        name=name,
                        description=description,
                        version=version,
                        author=author,
                        provider_class=provider_class,
                        tags=tags,
                        dependencies=dependencies
                    )
            except Exception as e:
                logger.warning("Error loading metadata from module %s: %s", plugin_name, e)
        
        # Create default metadata
        provider_class = self._find_provider_class(module, plugin_name)
        if provider_class:
            return ProviderMetadata(
                name=plugin_name,
                description=f"{plugin_name.title()} notification provider",
                version="1.0.0",
                author="Unknown",
                provider_class=provider_class
            )
        
        return None
    
    def get_plugin(self, name: str) -> PluginInfo | None:
        """Get information about a specific plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            PluginInfo object or None if not found
        """
        if not self._discovered_plugins:
            _ = self.discover_plugins()
        
        return self._discovered_plugins.get(name)
    
    def list_available_plugins(self) -> list[str]:
        """List names of all available plugins.
        
        Returns:
            List of plugin names
        """
        if not self._discovered_plugins:
            _ = self.discover_plugins()
        
        return list(self._discovered_plugins.keys())
    
    def list_loaded_plugins(self) -> list[str]:
        """List names of successfully loaded plugins.
        
        Returns:
            List of plugin names that loaded without errors
        """
        if not self._discovered_plugins:
            _ = self.discover_plugins()
        
        return [
            name for name, info in self._discovered_plugins.items()
            if info.provider_class is not None and info.load_error is None
        ]
    
    def list_failed_plugins(self) -> list[tuple[str, Exception]]:
        """List plugins that failed to load with their errors.
        
        Returns:
            List of tuples containing (plugin_name, error)
        """
        if not self._discovered_plugins:
            _ = self.discover_plugins()
        
        return [
            (name, info.load_error)
            for name, info in self._discovered_plugins.items()
            if info.load_error is not None
        ]
    
    def get_discovery_summary(self) -> dict[str, object]:
        """Get a summary of plugin discovery results.
        
        Returns:
            Dictionary with discovery statistics
        """
        if not self._discovered_plugins:
            _ = self.discover_plugins()
        
        failed_plugins = self.list_failed_plugins()
        loaded_plugins = self.list_loaded_plugins()
        
        return {
            "total_plugins": len(self._discovered_plugins),
            "loaded_plugins": len(loaded_plugins),
            "failed_plugins": len(failed_plugins),
            "search_paths": [str(path) for path in self._search_paths],
            "loaded_plugin_names": loaded_plugins,
            "failed_plugin_names": [name for name, _ in failed_plugins],
            "plugin_details": {
                name: {
                    "version": info.version,
                    "description": info.description,
                    "author": info.author,
                    "path": str(info.path),
                    "has_error": info.load_error is not None,
                    "error": str(info.load_error) if info.load_error else None
                }
                for name, info in self._discovered_plugins.items()
            }
        }