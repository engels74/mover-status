"""
Tests for the configuration registry module.

This module contains tests for the ConfigRegistry class, including
schema registration, retrieval, and validation functionality.
"""

import pytest

from mover_status.config.schema import ConfigSchema, SchemaField, FieldType, SchemaValidationError
from mover_status.config.registry import ConfigRegistry, RegistryError


class TestConfigRegistry:
    """Test cases for the ConfigRegistry class."""

    def test_register_provider_configuration_schemas(self) -> None:
        """Test case: Register provider configuration schemas."""
        # Create a registry
        registry = ConfigRegistry()

        # Create a test schema
        test_schema = ConfigSchema(
            name="test_provider",
            fields=[
                SchemaField(
                    name="enabled",
                    field_type=FieldType.BOOLEAN,
                    required=False,
                    default_value=False,
                    description="Whether the provider is enabled"
                ),
                SchemaField(
                    name="api_key",
                    field_type=FieldType.STRING,
                    required=True,
                    description="API key for the provider"
                ),
            ]
        )

        # Register the schema
        registry.register_schema("test_provider", test_schema)

        # Verify the schema was registered
        assert registry.has_schema("test_provider")
        assert registry.get_schema("test_provider") == test_schema

    def test_get_registered_schemas(self) -> None:
        """Test case: Get registered schemas."""
        # Create a registry
        registry = ConfigRegistry()

        # Create multiple test schemas
        schema1 = ConfigSchema(
            name="provider1",
            fields=[
                SchemaField(
                    name="enabled",
                    field_type=FieldType.BOOLEAN,
                    required=False,
                    default_value=False
                )
            ]
        )

        schema2 = ConfigSchema(
            name="provider2",
            fields=[
                SchemaField(
                    name="url",
                    field_type=FieldType.STRING,
                    required=True
                )
            ]
        )

        # Register the schemas
        registry.register_schema("provider1", schema1)
        registry.register_schema("provider2", schema2)

        # Get all registered schemas
        all_schemas = registry.get_all_schemas()

        # Verify all schemas are returned
        assert len(all_schemas) == 2
        assert "provider1" in all_schemas
        assert "provider2" in all_schemas
        assert all_schemas["provider1"] == schema1
        assert all_schemas["provider2"] == schema2

        # Get list of registered provider names
        provider_names = registry.get_registered_providers()
        assert set(provider_names) == {"provider1", "provider2"}

    def test_validate_configuration_against_schemas(self) -> None:
        """Test case: Validate configuration against schemas."""
        # Create a registry
        registry = ConfigRegistry()

        # Create a test schema
        test_schema = ConfigSchema(
            name="test_provider",
            fields=[
                SchemaField(
                    name="enabled",
                    field_type=FieldType.BOOLEAN,
                    required=False,
                    default_value=True
                ),
                SchemaField(
                    name="api_key",
                    field_type=FieldType.STRING,
                    required=True
                ),
                SchemaField(
                    name="timeout",
                    field_type=FieldType.INTEGER,
                    required=False,
                    default_value=30
                ),
            ]
        )

        # Register the schema
        registry.register_schema("test_provider", test_schema)

        # Test valid configuration
        valid_config = {
            "api_key": "test-key-123",
            "timeout": 60
        }

        validated_config = registry.validate_config("test_provider", valid_config)

        # Should include defaults
        expected_config = {
            "enabled": True,
            "api_key": "test-key-123",
            "timeout": 60
        }
        assert validated_config == expected_config

        # Test invalid configuration (missing required field)
        invalid_config = {
            "enabled": True,
            "timeout": 60
            # Missing required api_key
        }

        with pytest.raises(SchemaValidationError):
            _ = registry.validate_config("test_provider", invalid_config)

    def test_register_duplicate_schema_raises_error(self) -> None:
        """Test that registering a duplicate schema raises an error."""
        # Create a registry
        registry = ConfigRegistry()

        # Create a test schema
        test_schema = ConfigSchema(name="test_provider")

        # Register the schema
        registry.register_schema("test_provider", test_schema)

        # Try to register the same provider again
        duplicate_schema = ConfigSchema(name="test_provider")

        with pytest.raises(RegistryError) as exc_info:
            registry.register_schema("test_provider", duplicate_schema)

        assert "already registered" in str(exc_info.value)

    def test_get_nonexistent_schema_raises_error(self) -> None:
        """Test that getting a non-existent schema raises an error."""
        # Create a registry
        registry = ConfigRegistry()

        # Try to get a schema that doesn't exist
        with pytest.raises(RegistryError) as exc_info:
            _ = registry.get_schema("nonexistent_provider")

        assert "not found" in str(exc_info.value)

    def test_validate_config_for_nonexistent_provider_raises_error(self) -> None:
        """Test that validating config for non-existent provider raises an error."""
        # Create a registry
        registry = ConfigRegistry()

        # Try to validate config for a provider that doesn't exist
        with pytest.raises(RegistryError) as exc_info:
            _ = registry.validate_config("nonexistent_provider", {})

        assert "not found" in str(exc_info.value)

    def test_has_schema_returns_correct_boolean(self) -> None:
        """Test that has_schema returns correct boolean values."""
        # Create a registry
        registry = ConfigRegistry()

        # Check for non-existent schema
        assert not registry.has_schema("nonexistent_provider")

        # Register a schema
        test_schema = ConfigSchema(name="test_provider")
        registry.register_schema("test_provider", test_schema)

        # Check for existing schema
        assert registry.has_schema("test_provider")

        # Check for different non-existent schema
        assert not registry.has_schema("another_provider")

    def test_unregister_schema(self) -> None:
        """Test that schemas can be unregistered."""
        # Create a registry
        registry = ConfigRegistry()

        # Register a schema
        test_schema = ConfigSchema(name="test_provider")
        registry.register_schema("test_provider", test_schema)

        # Verify it's registered
        assert registry.has_schema("test_provider")

        # Unregister the schema
        registry.unregister_schema("test_provider")

        # Verify it's no longer registered
        assert not registry.has_schema("test_provider")

        # Try to unregister a non-existent schema
        with pytest.raises(RegistryError) as exc_info:
            registry.unregister_schema("nonexistent_provider")

        assert "not found" in str(exc_info.value)

    def test_clear_registry(self) -> None:
        """Test that the registry can be cleared."""
        # Create a registry
        registry = ConfigRegistry()

        # Register multiple schemas
        schema1 = ConfigSchema(name="provider1")
        schema2 = ConfigSchema(name="provider2")
        registry.register_schema("provider1", schema1)
        registry.register_schema("provider2", schema2)

        # Verify they're registered
        assert len(registry.get_all_schemas()) == 2

        # Clear the registry
        registry.clear()

        # Verify it's empty
        assert len(registry.get_all_schemas()) == 0
        assert not registry.has_schema("provider1")
        assert not registry.has_schema("provider2")
