"""
Tests for the configuration validator module.

This module tests the ConfigValidator class which provides configuration
validation functionality against registered schemas.
"""

import pytest

from mover_status.config.validator import ConfigValidator, ValidationError
from mover_status.config.registry import ConfigRegistry
from mover_status.config.schema import ConfigSchema, SchemaField, FieldType


class TestConfigValidator:
    """Test cases for the ConfigValidator class."""

    def test_validate_configuration_against_schemas(self) -> None:
        """Test case: Validate configuration against schemas."""
        # Create a registry with test schemas
        registry = ConfigRegistry()

        # Create test schemas
        telegram_schema = ConfigSchema(
            name="telegram",
            fields=[
                SchemaField("bot_token", FieldType.STRING, required=True),
                SchemaField("chat_id", FieldType.STRING, required=True),
                SchemaField("enabled", FieldType.BOOLEAN, required=False, default_value=True),
            ]
        )

        discord_schema = ConfigSchema(
            name="discord",
            fields=[
                SchemaField("webhook_url", FieldType.STRING, required=True),
                SchemaField("username", FieldType.STRING, required=False, default_value="MoverStatus"),
                SchemaField("enabled", FieldType.BOOLEAN, required=False, default_value=True),
            ]
        )

        # Register schemas
        registry.register_schema("telegram", telegram_schema)
        registry.register_schema("discord", discord_schema)

        # Create validator
        validator = ConfigValidator(registry)

        # Test valid configuration
        valid_config = {
            "telegram": {
                "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                "chat_id": "123456789",
                "enabled": True
            },
            "discord": {
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "username": "TestBot"
            }
        }

        # Should not raise an exception
        result = validator.validate(valid_config)

        # Check that defaults are applied
        assert result["telegram"]["enabled"] is True
        assert result["discord"]["enabled"] is True  # Default value
        assert result["discord"]["username"] == "TestBot"

    def test_handle_validation_errors(self) -> None:
        """Test case: Handle validation errors."""
        # Create a registry with test schema
        registry = ConfigRegistry()

        test_schema = ConfigSchema(
            name="test_provider",
            fields=[
                SchemaField("required_field", FieldType.STRING, required=True),
                SchemaField("optional_field", FieldType.INTEGER, required=False, default_value=42),
            ]
        )

        registry.register_schema("test_provider", test_schema)
        validator = ConfigValidator(registry)

        # Test configuration with missing required field
        invalid_config: dict[str, object] = {
            "test_provider": {
                "optional_field": 100
                # Missing required_field
            }
        }

        # Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            _ = validator.validate(invalid_config)

        # Check error details
        assert "required_field" in str(exc_info.value)
        assert len(exc_info.value.errors) > 0

    def test_dynamic_validation_based_on_registered_providers(self) -> None:
        """Test case: Dynamic validation based on registered providers."""
        # Create registry and validator
        registry = ConfigRegistry()
        validator = ConfigValidator(registry)

        # Initially no providers registered
        empty_config: dict[str, object] = {}
        result = validator.validate(empty_config)
        assert result == {}

        # Register a provider schema dynamically
        new_schema = ConfigSchema(
            name="new_provider",
            fields=[
                SchemaField("api_key", FieldType.STRING, required=True),
            ]
        )
        registry.register_schema("new_provider", new_schema)

        # Now validation should work for the new provider
        config_with_new_provider = {
            "new_provider": {
                "api_key": "test-key-123"
            }
        }

        result = validator.validate(config_with_new_provider)
        assert result["new_provider"]["api_key"] == "test-key-123"

    def test_validate_unknown_provider_configuration(self) -> None:
        """Test validation with unknown provider configuration."""
        registry = ConfigRegistry()
        validator = ConfigValidator(registry)

        # Configuration for unknown provider
        config_with_unknown: dict[str, object] = {
            "unknown_provider": {
                "some_setting": "value"
            }
        }

        # Should raise ValidationError for unknown provider
        with pytest.raises(ValidationError) as exc_info:
            _ = validator.validate(config_with_unknown)

        assert "unknown_provider" in str(exc_info.value)

    def test_validate_partial_configuration(self) -> None:
        """Test validation of partial configuration (only some providers)."""
        registry = ConfigRegistry()

        # Register multiple schemas
        schema1 = ConfigSchema(
            name="provider1",
            fields=[SchemaField("setting1", FieldType.STRING, required=True)]
        )
        schema2 = ConfigSchema(
            name="provider2",
            fields=[SchemaField("setting2", FieldType.INTEGER, required=False, default_value=10)]
        )

        registry.register_schema("provider1", schema1)
        registry.register_schema("provider2", schema2)

        validator = ConfigValidator(registry)

        # Configuration for only one provider
        partial_config = {
            "provider1": {
                "setting1": "test_value"
            }
            # provider2 not included
        }

        # Should validate successfully (partial configs are allowed)
        result = validator.validate(partial_config)
        assert result["provider1"]["setting1"] == "test_value"
        assert "provider2" not in result

    def test_validate_empty_configuration(self) -> None:
        """Test validation of empty configuration."""
        registry = ConfigRegistry()
        validator = ConfigValidator(registry)

        # Empty configuration should be valid
        result = validator.validate({})
        assert result == {}

    def test_validate_with_nested_validation_errors(self) -> None:
        """Test handling of nested validation errors from schema validation."""
        registry = ConfigRegistry()

        # Schema with complex validation
        complex_schema = ConfigSchema(
            name="complex_provider",
            fields=[
                SchemaField("string_field", FieldType.STRING, required=True),
                SchemaField("int_field", FieldType.INTEGER, required=True),
                SchemaField("bool_field", FieldType.BOOLEAN, required=False, default_value=False),
            ]
        )

        registry.register_schema("complex_provider", complex_schema)
        validator = ConfigValidator(registry)

        # Configuration with multiple validation errors
        invalid_config = {
            "complex_provider": {
                "string_field": 123,  # Wrong type
                "int_field": "not_an_int",  # Wrong type
                "unknown_field": "value"  # Unknown field
            }
        }

        # Should raise ValidationError with multiple errors
        with pytest.raises(ValidationError) as exc_info:
            _ = validator.validate(invalid_config)

        # Should contain multiple error messages
        assert len(exc_info.value.errors) > 1
        error_str = str(exc_info.value)
        assert "string_field" in error_str
        assert "int_field" in error_str
