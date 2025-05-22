"""
Tests for the Discord notification provider configuration schema.

This module contains tests for the Discord provider configuration schema,
including schema validation, default values, and field requirements.
"""

import pytest

from mover_status.config.schema import SchemaValidationError, FieldType
from mover_status.notification.providers.discord.config import (
    get_discord_schema,
    DISCORD_SCHEMA_NAME,
)


class TestDiscordConfigSchema:
    """Test cases for the Discord configuration schema."""

    def test_provider_specific_configuration_schema(self) -> None:
        """Test that the Discord provider has a specific configuration schema."""
        # Get the Discord schema
        schema = get_discord_schema()

        # Check that the schema has the correct name
        assert schema.name == DISCORD_SCHEMA_NAME

        # Check that the schema has the expected fields
        fields = schema.get_all_fields()
        expected_fields = {
            "enabled", "webhook_url", "username", "message_template",
            "use_embeds", "embed_title", "embed_colors"
        }
        assert set(fields.keys()) == expected_fields

        # Check field types
        assert fields["enabled"].field_type == FieldType.BOOLEAN
        assert fields["webhook_url"].field_type == FieldType.STRING
        assert fields["username"].field_type == FieldType.STRING
        assert fields["message_template"].field_type == FieldType.STRING
        assert fields["use_embeds"].field_type == FieldType.BOOLEAN
        assert fields["embed_title"].field_type == FieldType.STRING
        assert fields["embed_colors"].field_type == FieldType.DICT

    def test_schema_validation_valid_config(self) -> None:
        """Test schema validation for a valid Discord configuration."""
        # Get the Discord schema
        schema = get_discord_schema()

        # Create a valid configuration
        config = {
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefg",
            "username": "Test Bot",
            "message_template": "Test message: {percent}%",
            "use_embeds": True,
            "embed_title": "Test Title",
            "embed_colors": {
                "low_progress": 16744576,
                "mid_progress": 16753920,
                "high_progress": 9498256,
                "complete": 65280
            }
        }

        # Validate the configuration
        validated_config = schema.validate(config)

        # Check that validation succeeded
        assert validated_config == config

    def test_schema_validation_missing_required_fields(self) -> None:
        """Test schema validation with missing required fields."""
        # Get the Discord schema
        schema = get_discord_schema()

        # Create a configuration missing required fields
        config = {
            "enabled": True,
            # Missing webhook_url
            "username": "Test Bot",
        }

        # Validate the configuration and expect an error
        with pytest.raises(SchemaValidationError) as exc_info:
            _ = schema.validate(config)

        # Check that the error mentions the missing field
        error_message = str(exc_info.value)
        assert "webhook_url" in error_message

    def test_schema_validation_invalid_field_types(self) -> None:
        """Test schema validation with invalid field types."""
        # Get the Discord schema
        schema = get_discord_schema()

        # Create a configuration with invalid field types
        config = {
            "enabled": "true",  # Should be boolean
            "webhook_url": 123456,  # Should be string
            "username": "Test Bot",
            "message_template": "Test message",
            "use_embeds": "true",  # Should be boolean
            "embed_title": "Test Title",
            "embed_colors": "invalid"  # Should be dict
        }

        # Validate the configuration and expect an error
        with pytest.raises(SchemaValidationError) as exc_info:
            _ = schema.validate(config)

        # Check that the error mentions the invalid types
        error_message = str(exc_info.value)
        assert "enabled" in error_message
        assert "webhook_url" in error_message
        assert "use_embeds" in error_message
        assert "embed_colors" in error_message

    def test_schema_validation_unknown_fields(self) -> None:
        """Test schema validation with unknown fields."""
        # Get the Discord schema
        schema = get_discord_schema()

        # Create a configuration with unknown fields
        config: dict[str, object] = {
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefg",
            "username": "Test Bot",
            "message_template": "Test message",
            "use_embeds": True,
            "embed_title": "Test Title",
            "embed_colors": {},
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

    def test_default_values_for_discord_provider(self) -> None:
        """Test default values for the Discord provider configuration."""
        # Get the Discord schema
        schema = get_discord_schema()

        # Create a minimal configuration with only required fields
        config = {
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefg",
        }

        # Validate the configuration
        validated_config = schema.validate(config)

        # Check that default values are applied
        assert validated_config["enabled"] is False  # Default value
        assert validated_config["username"] == "Mover Bot"  # Default value
        assert validated_config["use_embeds"] is True  # Default value
        assert validated_config["embed_title"] == "Mover: Moving Data"  # Default value
        assert "message_template" in validated_config  # Should have default template
        assert "embed_colors" in validated_config  # Should have default colors

    def test_required_fields_validation(self) -> None:
        """Test that required fields are properly validated."""
        # Get the Discord schema
        schema = get_discord_schema()
        fields = schema.get_all_fields()

        # Check that webhook_url is required
        assert fields["webhook_url"].required is True

        # Check that other fields are optional
        assert fields["enabled"].required is False
        assert fields["username"].required is False
        assert fields["message_template"].required is False
        assert fields["use_embeds"].required is False
        assert fields["embed_title"].required is False
        assert fields["embed_colors"].required is False

    def test_embed_colors_dict_validation(self) -> None:
        """Test that embed_colors field accepts valid dictionary values."""
        # Get the Discord schema
        schema = get_discord_schema()

        # Test valid embed colors
        config = {
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefg",
            "embed_colors": {
                "low_progress": 16744576,
                "mid_progress": 16753920,
                "high_progress": 9498256,
                "complete": 65280
            }
        }

        # Should not raise an exception
        validated_config = schema.validate(config)
        assert validated_config["embed_colors"] == config["embed_colors"]

    def test_webhook_url_validation(self) -> None:
        """Test that webhook_url field accepts valid Discord webhook URLs."""
        # Get the Discord schema
        schema = get_discord_schema()

        # Test valid webhook URL
        config = {
            "webhook_url": "https://discord.com/api/webhooks/123456789012345678/abcdefghijklmnopqrstuvwxyz1234567890",
        }

        # Should not raise an exception
        validated_config = schema.validate(config)
        assert validated_config["webhook_url"] == config["webhook_url"]
