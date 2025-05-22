"""
Tests for the configuration loader module.

This module tests the ConfigLoader class which handles loading configuration
from YAML files, merging with defaults, and handling various error conditions.
"""

import tempfile
import os
from typing import final

import pytest
import yaml

from mover_status.config.loader import ConfigLoader, LoaderError
from mover_status.config.schema import ConfigSchema, SchemaField, FieldType
from mover_status.config.registry import ConfigRegistry


@final
class TestConfigLoader:
    """Test cases for the ConfigLoader class."""

    registry: ConfigRegistry  # pyright: ignore[reportUninitializedInstanceVariable]
    loader: ConfigLoader  # pyright: ignore[reportUninitializedInstanceVariable]
    test_schema: ConfigSchema  # pyright: ignore[reportUninitializedInstanceVariable]

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.registry = ConfigRegistry()
        self.loader = ConfigLoader(self.registry)

        # Create a simple test schema
        self.test_schema = ConfigSchema(
            name="test_provider",
            fields=[
                SchemaField("enabled", FieldType.BOOLEAN, required=True, default_value=False),
                SchemaField("api_key", FieldType.STRING, required=True),
                SchemaField("timeout", FieldType.INTEGER, required=False, default_value=30),
                SchemaField("retries", FieldType.INTEGER, required=False, default_value=3),
            ]
        )

        # Register the test schema
        self.registry.register_schema("test_provider", self.test_schema)

    def test_load_configuration_from_file(self) -> None:
        """Test case: Load configuration from file."""
        # Create a temporary config file
        config_data = {
            "test_provider": {
                "enabled": True,
                "api_key": "test_key_123",
                "timeout": 60
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name

        try:
            # This should fail initially as ConfigLoader doesn't exist yet
            result = self.loader.load_from_file(config_file)

            # Verify the configuration was loaded correctly
            assert "test_provider" in result
            provider_config = result["test_provider"]
            assert provider_config["enabled"] is True
            assert provider_config["api_key"] == "test_key_123"
            assert provider_config["timeout"] == 60
            assert provider_config["retries"] == 3  # Default value should be applied

        finally:
            os.unlink(config_file)

    def test_merge_with_defaults(self) -> None:
        """Test case: Merge with defaults."""
        # Partial configuration (missing some fields)
        user_config = {
            "test_provider": {
                "enabled": True,
                "api_key": "user_key"
                # timeout and retries are missing
            }
        }

        # This should fail initially as ConfigLoader doesn't exist yet
        result = self.loader.merge_with_defaults(user_config)

        # Verify defaults were applied
        assert "test_provider" in result
        provider_config = result["test_provider"]
        assert provider_config["enabled"] is True
        assert provider_config["api_key"] == "user_key"
        assert provider_config["timeout"] == 30  # Default value
        assert provider_config["retries"] == 3   # Default value

    def test_handle_missing_file(self) -> None:
        """Test case: Handle missing or invalid files."""
        non_existent_file = "/path/that/does/not/exist.yaml"

        # Should handle missing file gracefully
        # This should fail initially as ConfigLoader doesn't exist yet
        result = self.loader.load_from_file(non_existent_file)

        # Should return empty configuration or defaults
        assert isinstance(result, dict)

    def test_handle_invalid_yaml_file(self) -> None:
        """Test case: Handle invalid YAML files."""
        # Create a file with invalid YAML
        invalid_yaml = "invalid: yaml: content: [unclosed"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            _ = f.write(invalid_yaml)
            config_file = f.name

        try:
            # Should raise LoaderError for invalid YAML
            # This should fail initially as ConfigLoader doesn't exist yet
            with pytest.raises(LoaderError, match="Invalid YAML"):
                _ = self.loader.load_from_file(config_file)

        finally:
            os.unlink(config_file)

    def test_handle_empty_file(self) -> None:
        """Test case: Handle empty configuration files."""
        # Create an empty file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            _ = f.write("")
            config_file = f.name

        try:
            # Should handle empty file gracefully
            # This should fail initially as ConfigLoader doesn't exist yet
            result = self.loader.load_from_file(config_file)

            # Should return empty configuration
            assert isinstance(result, dict)

        finally:
            os.unlink(config_file)

    def test_load_with_validation_errors(self) -> None:
        """Test case: Handle configuration with validation errors."""
        # Configuration with validation errors (missing required field)
        config_data = {
            "test_provider": {
                "enabled": True
                # api_key is missing (required field)
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name

        try:
            # Should raise LoaderError for validation failures
            # This should fail initially as ConfigLoader doesn't exist yet
            with pytest.raises(LoaderError, match="Configuration validation failed"):
                _ = self.loader.load_from_file(config_file)

        finally:
            os.unlink(config_file)

    def test_load_configuration_with_multiple_providers(self) -> None:
        """Test case: Load configuration with multiple providers."""
        # Register another schema
        another_schema = ConfigSchema(
            name="another_provider",
            fields=[
                SchemaField("enabled", FieldType.BOOLEAN, required=True, default_value=False),
                SchemaField("url", FieldType.STRING, required=True),
            ]
        )
        self.registry.register_schema("another_provider", another_schema)

        # Configuration with multiple providers
        config_data = {
            "test_provider": {
                "enabled": True,
                "api_key": "test_key"
            },
            "another_provider": {
                "enabled": False,
                "url": "https://example.com"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name

        try:
            # This should fail initially as ConfigLoader doesn't exist yet
            result = self.loader.load_from_file(config_file)

            # Verify both providers were loaded
            assert "test_provider" in result
            assert "another_provider" in result
            assert result["test_provider"]["enabled"] is True
            assert result["another_provider"]["enabled"] is False

        finally:
            os.unlink(config_file)

    def test_load_from_string(self) -> None:
        """Test case: Load configuration from YAML string."""
        yaml_content = """
        test_provider:
          enabled: true
          api_key: "string_key"
          timeout: 45
        """

        # This should fail initially as ConfigLoader doesn't exist yet
        result = self.loader.load_from_string(yaml_content)

        # Verify the configuration was loaded correctly
        assert "test_provider" in result
        provider_config = result["test_provider"]
        assert provider_config["enabled"] is True
        assert provider_config["api_key"] == "string_key"
        assert provider_config["timeout"] == 45
