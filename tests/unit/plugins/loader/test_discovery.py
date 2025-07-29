"""Tests for plugin discovery system."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import Mock, patch

import pytest  # pyright: ignore[reportUnusedImport] # used for fixtures

from mover_status.notifications.base.provider import NotificationProvider
from mover_status.plugins.loader.discovery import PluginDiscovery, PluginDiscoveryError, PluginInfo

if TYPE_CHECKING:
    from unittest.mock import MagicMock


class TestPluginInfo:
    """Test PluginInfo data class."""
    
    def test_plugin_info_initialization(self) -> None:
        """Test PluginInfo initialization with default values."""
        info = PluginInfo(
            name="test_plugin",
            path=Path("/test/path"),
            module_name="test.module"
        )
        
        assert info.name == "test_plugin"
        assert info.path == Path("/test/path")
        assert info.module_name == "test.module"
        assert info.provider_class is None
        assert info.metadata is None
        assert info.load_error is None
        assert info.version == "1.0.0"
        assert info.description == ""
        assert info.author == "Unknown"
        assert info.tags == []
        assert info.dependencies == []
    
    def test_plugin_info_with_all_fields(self) -> None:
        """Test PluginInfo with all fields populated."""
        mock_provider_class = cast(type[NotificationProvider], Mock())
        mock_metadata = Mock()
        mock_error = Exception("test error")
        
        info = PluginInfo(
            name="test_plugin",
            path=Path("/test/path"),
            module_name="test.module",
            provider_class=mock_provider_class,
            metadata=mock_metadata,
            load_error=mock_error,
            version="2.0.0",
            description="Test plugin",
            author="Test Author",
            tags=["test", "plugin"],
            dependencies=["dep1", "dep2"]
        )
        
        assert info.provider_class is mock_provider_class
        assert info.metadata is mock_metadata
        assert info.load_error is mock_error
        assert info.version == "2.0.0"
        assert info.description == "Test plugin"
        assert info.author == "Test Author"
        assert info.tags == ["test", "plugin"]
        assert info.dependencies == ["dep1", "dep2"]


class TestPluginDiscovery:
    """Test PluginDiscovery class."""
    
    def test_initialization(self) -> None:
        """Test PluginDiscovery initialization."""
        discovery = PluginDiscovery()
        
        assert discovery.base_package == "mover_status.plugins"
        assert discovery._discovered_plugins == {}
        assert len(discovery._search_paths) >= 0  # May have default paths
    
    def test_initialization_with_custom_package(self) -> None:
        """Test PluginDiscovery initialization with custom package."""
        discovery = PluginDiscovery(base_package="custom.plugins")
        
        assert discovery.base_package == "custom.plugins"
    
    def test_add_search_path(self) -> None:
        """Test adding search paths."""
        discovery = PluginDiscovery()
        initial_count = len(discovery._search_paths)
        
        test_path = Path("/test/path")
        discovery.add_search_path(test_path)
        
        assert len(discovery._search_paths) == initial_count + 1
        assert test_path in discovery._search_paths
    
    def test_add_duplicate_search_path(self) -> None:
        """Test adding duplicate search path is ignored."""
        discovery = PluginDiscovery()
        
        test_path = Path("/test/path")
        discovery.add_search_path(test_path)
        initial_count = len(discovery._search_paths)
        
        discovery.add_search_path(test_path)
        
        assert len(discovery._search_paths) == initial_count
    
    @patch('importlib.import_module')
    def test_add_default_search_paths_success(self, mock_import: MagicMock) -> None:
        """Test successful addition of default search paths."""
        # Mock module with __path__ attribute
        mock_module = Mock()
        mock_module.__path__ = ["/test/plugins/path"]
        mock_import.return_value = mock_module
        
        discovery = PluginDiscovery()
        
        mock_import.assert_called_with("mover_status.plugins")
        assert Path("/test/plugins/path") in discovery._search_paths
    
    @patch('importlib.import_module')
    def test_add_default_search_paths_import_error(self, mock_import: MagicMock) -> None:
        """Test handling of import error when adding default search paths."""
        mock_import.side_effect = ImportError("Module not found")
        
        discovery = PluginDiscovery()  # Should not raise exception
        
        mock_import.assert_called_with("mover_status.plugins")
    
    def test_discover_plugins_empty_directory(self) -> None:
        """Test plugin discovery with empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            discovery = PluginDiscovery()
            discovery._search_paths = [Path(temp_dir)]
            
            plugins = discovery.discover_plugins()
            
            assert plugins == {}
            assert discovery._discovered_plugins == {}
    
    def test_discover_plugins_with_excluded_directories(self) -> None:
        """Test that excluded directories are ignored."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create excluded directories
            (temp_path / "template").mkdir()
            (temp_path / "loader").mkdir()
            (temp_path / "__pycache__").mkdir()
            (temp_path / ".hidden").mkdir()
            
            discovery = PluginDiscovery()
            discovery._search_paths = [temp_path]
            
            plugins = discovery.discover_plugins()
            
            assert plugins == {}
    
    def test_discover_plugins_missing_provider_file(self) -> None:
        """Test discovery skips directories without provider.py."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create plugin directory without provider.py
            plugin_dir = temp_path / "test_plugin"
            plugin_dir.mkdir()
            (plugin_dir / "__init__.py").write_text("")
            
            discovery = PluginDiscovery()
            discovery._search_paths = [temp_path]
            
            plugins = discovery.discover_plugins()
            
            assert plugins == {}
    
    def test_discover_plugins_missing_init_file(self) -> None:
        """Test discovery skips directories without __init__.py."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create plugin directory without __init__.py
            plugin_dir = temp_path / "test_plugin"
            plugin_dir.mkdir()
            (plugin_dir / "provider.py").write_text("")
            
            discovery = PluginDiscovery()
            discovery._search_paths = [temp_path]
            
            plugins = discovery.discover_plugins()
            
            assert plugins == {}
    
    @patch('importlib.import_module')
    def test_discover_plugins_import_error(self, mock_import: MagicMock) -> None:
        """Test discovery handles import errors gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create valid plugin directory structure
            plugin_dir = temp_path / "test_plugin"
            plugin_dir.mkdir()
            (plugin_dir / "__init__.py").write_text("")
            (plugin_dir / "provider.py").write_text("")
            
            # Mock import error
            mock_import.side_effect = ImportError("Module not found")
            
            discovery = PluginDiscovery()
            discovery._search_paths = [temp_path]
            
            plugins = discovery.discover_plugins()
            
            assert "test_plugin" in plugins
            assert plugins["test_plugin"].load_error is not None
            assert isinstance(plugins["test_plugin"].load_error, ImportError)
    
    def test_discover_plugins_force_reload(self) -> None:
        """Test force reload clears existing discoveries."""
        discovery = PluginDiscovery()
        
        # Add fake plugin
        fake_plugin = PluginInfo("fake", Path("/fake"), "fake.module")
        discovery._discovered_plugins["fake"] = fake_plugin
        
        # Mock empty discovery
        discovery._search_paths = []
        
        plugins = discovery.discover_plugins(force_reload=True)
        
        assert "fake" not in plugins
        assert discovery._discovered_plugins == {}
    
    def test_get_plugin_existing(self) -> None:
        """Test getting existing plugin."""
        discovery = PluginDiscovery()
        fake_plugin = PluginInfo("test", Path("/test"), "test.module")
        discovery._discovered_plugins["test"] = fake_plugin
        
        result = discovery.get_plugin("test")
        
        assert result is fake_plugin
    
    def test_get_plugin_nonexistent(self) -> None:
        """Test getting non-existent plugin returns None."""
        discovery = PluginDiscovery()
        
        result = discovery.get_plugin("nonexistent")
        
        assert result is None
    
    @patch.object(PluginDiscovery, 'discover_plugins')
    def test_get_plugin_triggers_discovery(self, mock_discover: MagicMock) -> None:
        """Test that get_plugin triggers discovery if not done yet."""
        discovery = PluginDiscovery()
        mock_discover.return_value = {}
        
        _ = discovery.get_plugin("test")
        
        mock_discover.assert_called_once()
    
    def test_list_available_plugins(self) -> None:
        """Test listing available plugins."""
        discovery = PluginDiscovery()
        
        # Add fake plugins
        plugin1 = PluginInfo("plugin1", Path("/test1"), "test1.module")
        plugin2 = PluginInfo("plugin2", Path("/test2"), "test2.module")
        discovery._discovered_plugins = {"plugin1": plugin1, "plugin2": plugin2}
        
        plugins = discovery.list_available_plugins()
        
        assert set(plugins) == {"plugin1", "plugin2"}
    
    def test_list_loaded_plugins(self) -> None:
        """Test listing successfully loaded plugins."""
        discovery = PluginDiscovery()
        
        # Add plugins with different states
        loaded_plugin = PluginInfo("loaded", Path("/loaded"), "loaded.module")
        loaded_plugin.provider_class = cast(type[NotificationProvider], Mock())
        
        failed_plugin = PluginInfo("failed", Path("/failed"), "failed.module")
        failed_plugin.load_error = Exception("Load error")
        
        discovery._discovered_plugins = {
            "loaded": loaded_plugin,
            "failed": failed_plugin
        }
        
        loaded_plugins = discovery.list_loaded_plugins()
        
        assert loaded_plugins == ["loaded"]
    
    def test_list_failed_plugins(self) -> None:
        """Test listing failed plugins."""
        discovery = PluginDiscovery()
        
        # Add plugins with different states
        loaded_plugin = PluginInfo("loaded", Path("/loaded"), "loaded.module")
        loaded_plugin.provider_class = cast(type[NotificationProvider], Mock())
        
        error = Exception("Load error")
        failed_plugin = PluginInfo("failed", Path("/failed"), "failed.module")
        failed_plugin.load_error = error
        
        discovery._discovered_plugins = {
            "loaded": loaded_plugin,
            "failed": failed_plugin
        }
        
        failed_plugins = discovery.list_failed_plugins()
        
        assert len(failed_plugins) == 1
        assert failed_plugins[0][0] == "failed"
        assert failed_plugins[0][1] is error
    
    def test_get_discovery_summary(self) -> None:
        """Test getting discovery summary."""
        discovery = PluginDiscovery()
        
        # Add plugins with different states
        loaded_plugin = PluginInfo("loaded", Path("/loaded"), "loaded.module")
        loaded_plugin.provider_class = cast(type[NotificationProvider], Mock())
        
        failed_plugin = PluginInfo("failed", Path("/failed"), "failed.module")
        failed_plugin.load_error = Exception("Load error")
        
        discovery._discovered_plugins = {
            "loaded": loaded_plugin,
            "failed": failed_plugin
        }
        discovery._search_paths = [Path("/test/path1"), Path("/test/path2")]
        
        summary = discovery.get_discovery_summary()
        
        assert summary["total_plugins"] == 2
        assert summary["loaded_plugins"] == 1
        assert summary["failed_plugins"] == 1
        assert summary["loaded_plugin_names"] == ["loaded"]
        assert summary["failed_plugin_names"] == ["failed"]
        assert len(summary["search_paths"]) == 2
        assert "plugin_details" in summary
        assert len(summary["plugin_details"]) == 2


class TestPluginDiscoveryErrorHandling:
    """Test error handling in plugin discovery."""
    
    def test_plugin_discovery_error_creation(self) -> None:
        """Test PluginDiscoveryError creation."""
        error = PluginDiscoveryError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_discover_plugins_handles_directory_errors(self) -> None:
        """Test discovery handles directory access errors."""
        discovery = PluginDiscovery()
        
        # Add non-existent path
        discovery._search_paths = [Path("/nonexistent/path")]
        
        # Should not raise exception
        plugins = discovery.discover_plugins()
        assert plugins == {}
    
    @patch('pathlib.Path.iterdir')
    def test_discover_plugins_handles_iteration_errors(self, mock_iterdir: MagicMock) -> None:
        """Test discovery handles directory iteration errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Mock iteration error
            mock_iterdir.side_effect = PermissionError("Access denied")
            
            discovery = PluginDiscovery()
            discovery._search_paths = [temp_path]
            
            # Should not raise exception
            plugins = discovery.discover_plugins()
            assert plugins == {}