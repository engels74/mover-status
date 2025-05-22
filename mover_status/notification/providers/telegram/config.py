"""
Configuration schema for the Telegram notification provider.

This module defines the configuration schema for the Telegram notification provider,
including field definitions, validation rules, and default values.
"""

from mover_status.config.schema import ConfigSchema, SchemaField, FieldType
from mover_status.notification.providers.telegram.defaults import TELEGRAM_DEFAULTS

# Schema name for the Telegram provider
TELEGRAM_SCHEMA_NAME = "telegram"


def get_telegram_schema() -> ConfigSchema:
    """
    Get the configuration schema for the Telegram notification provider.
    
    Returns:
        The Telegram provider configuration schema.
    """
    # Define the schema fields based on the Telegram provider requirements
    fields = [
        SchemaField(
            name="enabled",
            field_type=FieldType.BOOLEAN,
            required=False,
            default_value=TELEGRAM_DEFAULTS["enabled"],
            description="Whether the Telegram provider is enabled"
        ),
        SchemaField(
            name="bot_token",
            field_type=FieldType.STRING,
            required=True,
            default_value=TELEGRAM_DEFAULTS["bot_token"],
            description="Telegram bot token for API authentication"
        ),
        SchemaField(
            name="chat_id",
            field_type=FieldType.STRING,
            required=True,
            default_value=TELEGRAM_DEFAULTS["chat_id"],
            description="Telegram chat ID to send messages to"
        ),
        SchemaField(
            name="parse_mode",
            field_type=FieldType.STRING,
            required=False,
            default_value=TELEGRAM_DEFAULTS["parse_mode"],
            description="Parse mode for message formatting (HTML, MarkdownV2, Markdown)"
        ),
        SchemaField(
            name="disable_notification",
            field_type=FieldType.BOOLEAN,
            required=False,
            default_value=TELEGRAM_DEFAULTS["disable_notification"],
            description="Whether to send the message silently"
        ),
        SchemaField(
            name="message_template",
            field_type=FieldType.STRING,
            required=False,
            default_value=TELEGRAM_DEFAULTS["message_template"],
            description="Template for formatting notification messages"
        ),
    ]
    
    # Create and return the schema
    return ConfigSchema(
        name=TELEGRAM_SCHEMA_NAME,
        fields=fields
    )


def validate_telegram_config(config: dict[str, object]) -> dict[str, object]:
    """
    Validate a Telegram provider configuration against the schema.
    
    Args:
        config: The configuration to validate.
        
    Returns:
        The validated configuration with defaults applied.
        
    Raises:
        SchemaValidationError: If the configuration is invalid.
    """
    schema = get_telegram_schema()
    return schema.validate(config)
