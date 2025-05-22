"""
Tests for the Telegram notification provider configuration schema.

This module contains tests for the Telegram provider configuration schema,
including schema validation, default values, and field requirements.
"""

import pytest

from mover_status.config.schema import SchemaValidationError, FieldType
from mover_status.notification.providers.telegram.config import (
    get_telegram_schema,
    TELEGRAM_SCHEMA_NAME,
)


class TestTelegramConfigSchema:
    """Test cases for the Telegram configuration schema."""

    def test_provider_specific_configuration_schema(self) -> None:
        """Test that the Telegram provider has a specific configuration schema."""
        # Get the Telegram schema
        schema = get_telegram_schema()

        # Check that the schema has the correct name
        assert schema.name == TELEGRAM_SCHEMA_NAME

        # Check that the schema has the expected fields
        fields = schema.get_all_fields()
        expected_fields = {
            "enabled", "bot_token", "chat_id", "parse_mode",
            "disable_notification", "message_template"
        }
        assert set(fields.keys()) == expected_fields

        # Check field types
        assert fields["enabled"].field_type == FieldType.BOOLEAN
        assert fields["bot_token"].field_type == FieldType.STRING
        assert fields["chat_id"].field_type == FieldType.STRING
        assert fields["parse_mode"].field_type == FieldType.STRING
        assert fields["disable_notification"].field_type == FieldType.BOOLEAN
        assert fields["message_template"].field_type == FieldType.STRING

    def test_schema_validation_valid_config(self) -> None:
        """Test schema validation for a valid Telegram configuration."""
        # Get the Telegram schema
        schema = get_telegram_schema()

        # Create a valid configuration
        config = {
            "enabled": True,
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message: {percent}%"
        }

        # Validate the configuration
        validated_config = schema.validate(config)

        # Check that validation succeeded
        assert validated_config == config

    def test_schema_validation_missing_required_fields(self) -> None:
        """Test schema validation with missing required fields."""
        # Get the Telegram schema
        schema = get_telegram_schema()

        # Create a configuration missing required fields
        config = {
            "enabled": True,
            # Missing bot_token and chat_id
            "parse_mode": "HTML",
        }

        # Validate the configuration and expect an error
        with pytest.raises(SchemaValidationError) as exc_info:
            _ = schema.validate(config)

        # Check that the error mentions the missing fields
        error_message = str(exc_info.value)
        assert "bot_token" in error_message
        assert "chat_id" in error_message

    def test_schema_validation_invalid_field_types(self) -> None:
        """Test schema validation with invalid field types."""
        # Get the Telegram schema
        schema = get_telegram_schema()

        # Create a configuration with invalid field types
        config = {
            "enabled": "true",  # Should be boolean
            "bot_token": 123456,  # Should be string
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": "false",  # Should be boolean
            "message_template": "Test message"
        }

        # Validate the configuration and expect an error
        with pytest.raises(SchemaValidationError) as exc_info:
            _ = schema.validate(config)

        # Check that the error mentions the invalid types
        error_message = str(exc_info.value)
        assert "enabled" in error_message
        assert "bot_token" in error_message
        assert "disable_notification" in error_message

    def test_schema_validation_unknown_fields(self) -> None:
        """Test schema validation with unknown fields."""
        # Get the Telegram schema
        schema = get_telegram_schema()

        # Create a configuration with unknown fields
        config = {
            "enabled": True,
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message",
            "unknown_field": "value",  # Unknown field
            "another_unknown": 123     # Another unknown field
        }

        # Validate the configuration and expect an error
        with pytest.raises(SchemaValidationError) as exc_info:
            _ = schema.validate(config)

        # Check that the error mentions the unknown fields
        error_message = str(exc_info.value)
        assert "unknown_field" in error_message
        assert "another_unknown" in error_message

    def test_default_values_for_telegram_provider(self) -> None:
        """Test default values for the Telegram provider configuration."""
        # Get the Telegram schema
        schema = get_telegram_schema()

        # Create a minimal configuration with only required fields
        config = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
        }

        # Validate the configuration
        validated_config = schema.validate(config)

        # Check that default values are applied
        assert validated_config["enabled"] is False  # Default value
        assert validated_config["parse_mode"] == "HTML"  # Default value
        assert validated_config["disable_notification"] is False  # Default value
        assert "message_template" in validated_config  # Should have default template

    def test_required_fields_validation(self) -> None:
        """Test that required fields are properly validated."""
        # Get the Telegram schema
        schema = get_telegram_schema()
        fields = schema.get_all_fields()

        # Check that bot_token and chat_id are required
        assert fields["bot_token"].required is True
        assert fields["chat_id"].required is True

        # Check that other fields are optional
        assert fields["enabled"].required is False
        assert fields["parse_mode"].required is False
        assert fields["disable_notification"].required is False
        assert fields["message_template"].required is False

    def test_parse_mode_validation(self) -> None:
        """Test that parse_mode field accepts valid values."""
        # Get the Telegram schema
        schema = get_telegram_schema()

        # Test valid parse modes
        valid_parse_modes = ["HTML", "MarkdownV2", "Markdown"]

        for parse_mode in valid_parse_modes:
            config = {
                "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                "chat_id": "12345678",
                "parse_mode": parse_mode,
            }

            # Should not raise an exception
            validated_config = schema.validate(config)
            assert validated_config["parse_mode"] == parse_mode
