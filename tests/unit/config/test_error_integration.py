"""Integration tests for error handling with configuration loaders."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mover_status.config.exceptions import ConfigLoadError, EnvLoadError, ConfigMergeError
from mover_status.config.loader.yaml_loader import YamlLoader
from mover_status.config.loader.env_loader import EnvLoader
from mover_status.config.manager.config_merger import ConfigMerger


class TestYamlLoaderErrorIntegration:
    """Test error handling integration with YamlLoader."""
    
    def test_yaml_loader_file_not_found(self) -> None:
        """Test that YamlLoader raises ConfigLoadError for missing files."""
        loader = YamlLoader()
        missing_file = Path("/nonexistent/config.yaml")
        
        with pytest.raises(ConfigLoadError) as exc_info:
            loader.load(missing_file)
            
        error = exc_info.value
        assert "Failed to load /nonexistent/config.yaml" in str(error)
        assert error.file_path == "/nonexistent/config.yaml"
        assert error.context["file_path"] == "/nonexistent/config.yaml"
        
    def test_yaml_loader_invalid_yaml(self) -> None:
        """Test that YamlLoader raises ConfigLoadError for invalid YAML."""
        loader = YamlLoader()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()
            invalid_file = Path(f.name)
            
        try:
            with pytest.raises(ConfigLoadError) as exc_info:
                loader.load(invalid_file)
                
            error = exc_info.value
            assert "Failed to load" in str(error)
            assert error.file_path == str(invalid_file)
            assert error.context["file_path"] == str(invalid_file)
        finally:
            invalid_file.unlink()


class TestEnvLoaderErrorIntegration:
    """Test error handling integration with EnvLoader."""
    
    def test_env_loader_json_parse_error(self) -> None:
        """Test that EnvLoader raises EnvLoadError for invalid JSON."""
        import os
        
        # Set an environment variable with invalid JSON
        os.environ["MOVER_STATUS_JSON_CONFIG"] = '{"invalid": json}'
        
        try:
            loader = EnvLoader(convert_types=True)
            with pytest.raises(EnvLoadError) as exc_info:
                loader.load()
                
            error = exc_info.value
            assert "Failed to parse JSON" in str(error)
            assert error.env_var == "MOVER_STATUS_JSON_CONFIG"
            assert error.context["env_var"] == "MOVER_STATUS_JSON_CONFIG"
        finally:
            # Clean up
            del os.environ["MOVER_STATUS_JSON_CONFIG"]


class TestConfigMergerErrorIntegration:
    """Test error handling integration with ConfigMerger."""
    
    def test_config_merger_invalid_base_type(self) -> None:
        """Test that ConfigMerger raises ConfigMergeError for invalid types."""
        merger = ConfigMerger()
        
        with pytest.raises(ConfigMergeError) as exc_info:
            merger.merge("not a dict", {})
            
        error = exc_info.value
        assert "Base configuration must be a dictionary" in str(error)
        
    def test_config_merger_invalid_override_type(self) -> None:
        """Test that ConfigMerger raises ConfigMergeError for invalid types."""
        merger = ConfigMerger()
        
        with pytest.raises(ConfigMergeError) as exc_info:
            merger.merge({}, "not a dict")
            
        error = exc_info.value
        assert "Override configuration must be a dictionary" in str(error)
        
    def test_config_merger_invalid_source_type(self) -> None:
        """Test that ConfigMerger raises ConfigMergeError for invalid source types."""
        merger = ConfigMerger()
        
        with pytest.raises(ConfigMergeError) as exc_info:
            merger.merge_multiple([{}, "not a dict"])
            
        error = exc_info.value
        assert "Source 1 must be a dictionary" in str(error)


class TestErrorHandlingWorkflow:
    """Test complete error handling workflow."""
    
    def test_error_context_propagation(self) -> None:
        """Test that error context is properly propagated through the system."""
        # Test that file path context is preserved
        loader = YamlLoader()
        missing_file = Path("/test/config.yaml")
        
        try:
            loader.load(missing_file)
        except ConfigLoadError as error:
            # Error should have file path context
            assert error.file_path == str(missing_file)
            assert error.context["file_path"] == str(missing_file)
            
            # Error should be chainable
            assert error.__cause__ is not None
            
    def test_error_hierarchy(self) -> None:
        """Test that all configuration errors inherit from ConfigError."""
        from mover_status.config.exceptions import ConfigError
        
        # Test inheritance hierarchy
        assert issubclass(ConfigLoadError, ConfigError)
        assert issubclass(EnvLoadError, ConfigError)
        assert issubclass(ConfigMergeError, ConfigError)
        
        # Create instances and verify inheritance
        config_load_error = ConfigLoadError("Load error")
        env_load_error = EnvLoadError("Env error")
        config_merge_error = ConfigMergeError("Merge error")
        
        assert isinstance(config_load_error, ConfigError)
        assert isinstance(env_load_error, ConfigError)
        assert isinstance(config_merge_error, ConfigError)