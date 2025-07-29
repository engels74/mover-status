"""Tests for plugin loader system."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import Mock, patch
from pathlib import Path

import pytest  # pyright: ignore[reportUnusedImport] # used for fixtures

from mover_status.notifications.base.provider import NotificationProvider
from mover_status.notifications.base.registry import ProviderRegistry, ProviderMetadata
from mover_status.plugins.loader.discovery import PluginDiscovery, PluginInfo
from mover_status.plugins.loader.loader import PluginLoader, PluginLoadError

if TYPE_CHECKING:
    from unittest.mock import MagicMock


class MockProvider:
    """Mock notification provider for testing."""
    
    def __init__(self, config: dict[str, object]) -> None:
        self.config: dict[str, object] = config
    
    async def send_notification(self, message: object) -> bool:
        _ = message  # Acknowledge parameter
        return True
    
    def validate_config(self) -> None:
        pass
    
    def get_provider_name(self) -> str:
        return "mock"
    
    def is_enabled(self) -> bool:
        return True


class TestPluginLoader:
    """Test PluginLoader class."""
    
    def test_initialization_with_defaults(self) -> None:
        """Test PluginLoader initialization with default parameters."""
        loader = PluginLoader()
        
        assert loader.registry is not None
        assert loader.discovery is not None
        assert loader._loaded_plugins == {}
    
    def test_initialization_with_custom_registry(self) -> None:
        """Test PluginLoader initialization with custom registry."""
        custom_registry = ProviderRegistry()
        loader = PluginLoader(registry=custom_registry)
        
        assert loader.registry is custom_registry
    
    def test_initialization_with_custom_discovery(self) -> None:
        """Test PluginLoader initialization with custom discovery."""
        custom_discovery = PluginDiscovery()
        loader = PluginLoader(discovery=custom_discovery)
        
        assert loader.discovery is custom_discovery
    
    @patch.object(PluginDiscovery, 'discover_plugins')
    def test_discover_and_load_all_plugins_success(self, mock_discover: MagicMock) -> None:
        """Test successful discovery and loading of all plugins."""
        # Create mock plugin info
        mock_provider_class = cast(type[NotificationProvider], Mock())
        mock_metadata = ProviderMetadata(
            name="test_provider",
            description="Test provider",
            version="1.0.0",
            author="Test",
            provider_class=mock_provider_class
        )
        
        plugin_info = PluginInfo(
            name="test_plugin",
            path=Path("test"),
            module_name="test.module",
            provider_class=mock_provider_class,
            metadata=mock_metadata
        )
        
        mock_discover.return_value = {"test_plugin": plugin_info}
        
        loader = PluginLoader()
        results = loader.discover_and_load_all_plugins()
        
        assert results == {"test_plugin": True}
        assert "test_plugin" in loader._loaded_plugins
        assert loader._loaded_plugins["test_plugin"] == "test_provider"
        mock_discover.assert_called_once_with(force_reload=True)
    
    @patch.object(PluginDiscovery, 'discover_plugins')
    def test_discover_and_load_all_plugins_with_failures(self, mock_discover: MagicMock) -> None:
        """Test discovery and loading with some plugin failures."""
        # Create successful plugin
        mock_provider_class = cast(type[NotificationProvider], Mock())
        mock_metadata = ProviderMetadata(
            name="good_provider",
            description="Good provider",
            version="1.0.0",
            author="Test",
            provider_class=mock_provider_class
        )
        
        good_plugin = PluginInfo(
            name="good_plugin",
            path=Path("test"),
            module_name="good.module",
            provider_class=mock_provider_class,
            metadata=mock_metadata
        )
        
        # Create failed plugin
        failed_plugin = PluginInfo(
            name="failed_plugin",
            path=Path("test"),
            module_name="failed.module",
            load_error=Exception("Load failed")
        )
        
        mock_discover.return_value = {
            "good_plugin": good_plugin,
            "failed_plugin": failed_plugin
        }
        
        loader = PluginLoader()
        results = loader.discover_and_load_all_plugins()
        
        assert results == {"good_plugin": True, "failed_plugin": False}
        assert "good_plugin" in loader._loaded_plugins
        assert "failed_plugin" not in loader._loaded_plugins
    
    def test_load_plugin_success(self) -> None:
        """Test successful plugin loading."""
        mock_provider_class = cast(type[NotificationProvider], Mock())
        mock_metadata = ProviderMetadata(
            name="test_provider",
            description="Test provider",
            version="1.0.0",
            author="Test",
            provider_class=mock_provider_class
        )
        
        plugin_info = PluginInfo(
            name="test_plugin",
            path=Path("test"),
            module_name="test.module",
            provider_class=mock_provider_class,
            metadata=mock_metadata
        )
        
        loader = PluginLoader()
        
        # Mock discovery to return our plugin
        with patch.object(loader.discovery, 'get_plugin', return_value=plugin_info):
            result = loader.load_plugin("test_plugin")
        
        assert result is True
        assert "test_plugin" in loader._loaded_plugins
        assert loader._loaded_plugins["test_plugin"] == "test_provider"
    
    def test_load_plugin_already_loaded(self) -> None:
        """Test loading already loaded plugin."""
        loader = PluginLoader()
        loader._loaded_plugins  # pyright: ignore[reportPrivateUsage] # testing internal state["test_plugin"] = "test_provider"
        
        result = loader.load_plugin("test_plugin")
        
        assert result is True
    
    def test_load_plugin_not_found(self) -> None:
        """Test loading non-existent plugin."""
        loader = PluginLoader()
        
        with patch.object(loader.discovery, 'get_plugin', return_value=None):
            result = loader.load_plugin("nonexistent")
        
        assert result is False
    
    def test_load_plugin_with_load_error(self) -> None:
        """Test loading plugin that has load error."""
        plugin_info = PluginInfo(
            name="failed_plugin",
            path=Path("test"),
            module_name="failed.module",
            load_error=Exception("Import failed")
        )
        
        loader = PluginLoader()
        
        with patch.object(loader.discovery, 'get_plugin', return_value=plugin_info):
            result = loader.load_plugin("failed_plugin")
        
        assert result is False
    
    def test_load_plugin_missing_provider_class(self) -> None:
        """Test loading plugin without provider class."""
        plugin_info = PluginInfo(
            name="incomplete_plugin",
            path=Path("test"),
            module_name="incomplete.module"
            # No provider_class or metadata
        )
        
        loader = PluginLoader()
        
        with patch.object(loader.discovery, 'get_plugin', return_value=plugin_info):
            result = loader.load_plugin("incomplete_plugin")
        
        assert result is False
    
    def test_unload_plugin_success(self) -> None:
        """Test successful plugin unloading."""
        loader = PluginLoader()
        loader._loaded_plugins  # pyright: ignore[reportPrivateUsage] # testing internal state["test_plugin"] = "test_provider"
        
        # Mock registry to avoid actual unregistration
        with patch.object(loader.registry, 'unregister') as mock_unregister:
            result = loader.unload_plugin("test_plugin")
        
        assert result is True
        assert "test_plugin" not in loader._loaded_plugins
        mock_unregister.assert_called_once_with("test_provider")
    
    def test_unload_plugin_not_loaded(self) -> None:
        """Test unloading plugin that isn't loaded."""
        loader = PluginLoader()
        
        result = loader.unload_plugin("nonexistent")
        
        assert result is True  # Returns True if plugin wasn't loaded
    
    def test_unload_plugin_registry_error(self) -> None:
        """Test unloading plugin with registry error."""
        loader = PluginLoader()
        loader._loaded_plugins  # pyright: ignore[reportPrivateUsage] # testing internal state["test_plugin"] = "test_provider"
        
        # Mock registry to raise error
        with patch.object(loader.registry, 'unregister', side_effect=Exception("Registry error")):
            result = loader.unload_plugin("test_plugin")
        
        assert result is False
    
    @patch.object(PluginDiscovery, 'discover_plugins')
    def test_load_enabled_plugins(self, mock_discover: MagicMock) -> None:
        """Test loading only enabled plugins."""
        # Create plugins for different providers
        discord_provider_class = cast(type[NotificationProvider], Mock())
        discord_metadata = ProviderMetadata(
            name="discord",
            description="Discord provider",
            version="1.0.0",
            author="Test",
            provider_class=discord_provider_class
        )
        
        telegram_provider_class = cast(type[NotificationProvider], Mock())
        telegram_metadata = ProviderMetadata(
            name="telegram", 
            description="Telegram provider",
            version="1.0.0",
            author="Test",
            provider_class=telegram_provider_class
        )
        
        # Plugin that won't be enabled
        other_provider_class = cast(type[NotificationProvider], Mock())
        other_metadata = ProviderMetadata(
            name="other",
            description="Other provider",
            version="1.0.0", 
            author="Test",
            provider_class=other_provider_class
        )
        
        discord_plugin = PluginInfo(
            name="discord",
            path=Path("test"),
            module_name="discord.module",
            provider_class=discord_provider_class,
            metadata=discord_metadata
        )
        
        telegram_plugin = PluginInfo(
            name="telegram",
            path=Path("test"),
            module_name="telegram.module",
            provider_class=telegram_provider_class,
            metadata=telegram_metadata
        )
        
        other_plugin = PluginInfo(
            name="other",
            path=Path("test"),
            module_name="other.module",
            provider_class=other_provider_class,
            metadata=other_metadata
        )
        
        mock_discover.return_value = {
            "discord": discord_plugin,
            "telegram": telegram_plugin,
            "other": other_plugin
        }
        
        loader = PluginLoader()
        results = loader.load_enabled_plugins(["discord", "telegram"])
        
        assert results == {"discord": True, "telegram": True}
        assert "discord" in loader._loaded_plugins
        assert "telegram" in loader._loaded_plugins
        assert "other" not in loader._loaded_plugins
    
    def test_create_provider_instance_success(self) -> None:
        """Test successful provider instance creation."""
        mock_provider = Mock()
        
        loader = PluginLoader()
        
        with patch.object(loader.registry, 'create_provider', return_value=mock_provider):
            result = loader.create_provider_instance("test_provider", {"key": "value"})
        
        assert result is mock_provider
    
    def test_create_provider_instance_error(self) -> None:
        """Test provider instance creation with error."""
        loader = PluginLoader()
        
        with patch.object(loader.registry, 'create_provider', side_effect=Exception("Creation failed")):
            result = loader.create_provider_instance("test_provider", {"key": "value"})
        
        assert result is None
    
    def test_get_loaded_plugins(self) -> None:
        """Test getting loaded plugins mapping."""
        loader = PluginLoader()
        loader._loaded_plugins  # pyright: ignore[reportPrivateUsage] # testing internal state = {"plugin1": "provider1", "plugin2": "provider2"}
        
        result = loader.get_loaded_plugins()
        
        assert result == {"plugin1": "provider1", "plugin2": "provider2"}
        # Ensure it's a copy
        result["new"] = "value"
        assert "new" not in loader._loaded_plugins
    
    def test_get_available_plugins(self) -> None:
        """Test getting available plugins."""
        loader = PluginLoader()
        
        with patch.object(loader.discovery, 'list_available_plugins', return_value=["plugin1", "plugin2"]):
            result = loader.get_available_plugins()
        
        assert result == ["plugin1", "plugin2"]
    
    def test_get_loaded_plugin_count(self) -> None:
        """Test getting loaded plugin count."""
        loader = PluginLoader()
        loader._loaded_plugins  # pyright: ignore[reportPrivateUsage] # testing internal state = {"plugin1": "provider1", "plugin2": "provider2"}
        
        result = loader.get_loaded_plugin_count()
        
        assert result == 2
    
    def test_is_plugin_loaded(self) -> None:
        """Test checking if plugin is loaded."""
        loader = PluginLoader()
        loader._loaded_plugins  # pyright: ignore[reportPrivateUsage] # testing internal state = {"plugin1": "provider1"}
        
        assert loader.is_plugin_loaded("plugin1") is True
        assert loader.is_plugin_loaded("plugin2") is False
    
    def test_get_plugin_provider_name(self) -> None:
        """Test getting provider name for plugin."""
        loader = PluginLoader()
        loader._loaded_plugins  # pyright: ignore[reportPrivateUsage] # testing internal state = {"plugin1": "provider1"}
        
        assert loader.get_plugin_provider_name("plugin1") == "provider1"
        assert loader.get_plugin_provider_name("plugin2") is None
    
    def test_reload_plugin_success(self) -> None:
        """Test successful plugin reload."""
        mock_provider_class = cast(type[NotificationProvider], Mock())
        mock_metadata = ProviderMetadata(
            name="test_provider",
            description="Test provider",
            version="1.0.0",
            author="Test",
            provider_class=mock_provider_class
        )
        
        plugin_info = PluginInfo(
            name="test_plugin",
            path=Path("test"), 
            module_name="test.module",
            provider_class=mock_provider_class,
            metadata=mock_metadata
        )
        
        loader = PluginLoader()
        loader._loaded_plugins  # pyright: ignore[reportPrivateUsage] # testing internal state["test_plugin"] = "test_provider"
        
        with patch.object(loader.discovery, 'discover_plugins'), \
             patch.object(loader.discovery, 'get_plugin', return_value=plugin_info), \
             patch.object(loader, 'unload_plugin', return_value=True):
            
            result = loader.reload_plugin("test_plugin")
        
        assert result is True
    
    def test_reload_plugin_unload_failure(self) -> None:
        """Test plugin reload with unload failure."""
        loader = PluginLoader()
        loader._loaded_plugins  # pyright: ignore[reportPrivateUsage] # testing internal state["test_plugin"] = "test_provider"
        
        with patch.object(loader, 'unload_plugin', return_value=False):
            result = loader.reload_plugin("test_plugin")
        
        assert result is False
    
    def test_get_loader_status(self) -> None:
        """Test getting loader status."""
        loader = PluginLoader()
        loader._loaded_plugins  # pyright: ignore[reportPrivateUsage] # testing internal state = {"plugin1": "provider1"}
        
        mock_discovery_summary = {
            "total_plugins": 2,
            "loaded_plugins": 1,
            "failed_plugins": 1
        }
        
        with patch.object(loader.discovery, 'get_discovery_summary', return_value=mock_discovery_summary), \
             patch.object(loader.discovery, 'list_available_plugins', return_value=["plugin1", "plugin2"]), \
             patch.object(loader.registry, 'list_providers', return_value=["provider1"]):
            
            status = loader.get_loader_status()
        
        assert status["loaded_plugins"] == 1
        assert status["available_plugins"] == 2
        assert status["registered_providers"] == 1
        assert status["plugin_mappings"] == {"plugin1": "provider1"}
        assert status["discovery_summary"] == mock_discovery_summary
    
    def test_validate_plugin_dependencies_success(self) -> None:
        """Test successful plugin dependency validation.""" 
        mock_metadata = ProviderMetadata(
            name="test_provider",
            description="Test provider",
            version="1.0.0",
            author="Test",
            provider_class=cast(type[NotificationProvider], Mock()),
            dependencies=["os", "sys"]  # Standard library modules
        )
        
        plugin_info = PluginInfo(
            name="test_plugin",
            path=Path("test"),
            module_name="test.module",
            metadata=mock_metadata
        )
        
        loader = PluginLoader()
        
        with patch.object(loader.discovery, 'get_plugin', return_value=plugin_info):
            is_valid, missing_deps = loader.validate_plugin_dependencies("test_plugin")
        
        assert is_valid is True
        assert missing_deps == []
    
    def test_validate_plugin_dependencies_missing(self) -> None:
        """Test plugin dependency validation with missing dependencies."""
        mock_metadata = ProviderMetadata(
            name="test_provider", 
            description="Test provider",
            version="1.0.0",
            author="Test",
            provider_class=cast(type[NotificationProvider], Mock()),
            dependencies=["nonexistent_module"]
        )
        
        plugin_info = PluginInfo(
            name="test_plugin",
            path=Path("test"),
            module_name="test.module",
            metadata=mock_metadata
        )
        
        loader = PluginLoader()
        
        with patch.object(loader.discovery, 'get_plugin', return_value=plugin_info):
            is_valid, missing_deps = loader.validate_plugin_dependencies("test_plugin")
        
        assert is_valid is False
        assert "nonexistent_module" in missing_deps
    
    def test_validate_plugin_dependencies_plugin_not_found(self) -> None:
        """Test dependency validation for non-existent plugin."""
        loader = PluginLoader()
        
        with patch.object(loader.discovery, 'get_plugin', return_value=None):
            is_valid, missing_deps = loader.validate_plugin_dependencies("nonexistent")
        
        assert is_valid is False
        assert "Plugin not found or has no metadata" in missing_deps


class TestPluginLoadError:
    """Test PluginLoadError exception."""
    
    def test_plugin_load_error_creation(self) -> None:
        """Test PluginLoadError creation."""
        error = PluginLoadError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)