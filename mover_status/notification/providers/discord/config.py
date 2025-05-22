"""
Configuration schema for the Discord notification provider.

This module defines the configuration schema for the Discord notification provider,
including field definitions, validation rules, and default values.
"""

from mover_status.config.schema import ConfigSchema, SchemaField, FieldType
from mover_status.notification.providers.discord.defaults import DISCORD_DEFAULTS

# Schema name for the Discord provider
DISCORD_SCHEMA_NAME = "discord"


def get_discord_schema() -> ConfigSchema:
    """
    Get the configuration schema for the Discord notification provider.
    
    Returns:
        The Discord provider configuration schema.
    """
    # Define the schema fields based on the Discord provider requirements
    fields = [
        SchemaField(
            name="enabled",
            field_type=FieldType.BOOLEAN,
            required=False,
            default_value=DISCORD_DEFAULTS["enabled"],
            description="Whether the Discord provider is enabled"
        ),
        SchemaField(
            name="webhook_url",
            field_type=FieldType.STRING,
            required=True,
            default_value=DISCORD_DEFAULTS["webhook_url"],
            description="Discord webhook URL for sending messages"
        ),
        SchemaField(
            name="username",
            field_type=FieldType.STRING,
            required=False,
            default_value=DISCORD_DEFAULTS["username"],
            description="Username to display for the webhook"
        ),
        SchemaField(
            name="message_template",
            field_type=FieldType.STRING,
            required=False,
            default_value=DISCORD_DEFAULTS["message_template"],
            description="Template for formatting notification messages"
        ),
        SchemaField(
            name="use_embeds",
            field_type=FieldType.BOOLEAN,
            required=False,
            default_value=DISCORD_DEFAULTS["use_embeds"],
            description="Whether to use embeds for messages"
        ),
        SchemaField(
            name="embed_title",
            field_type=FieldType.STRING,
            required=False,
            default_value=DISCORD_DEFAULTS["embed_title"],
            description="Title to use for embeds"
        ),
        SchemaField(
            name="embed_colors",
            field_type=FieldType.DICT,
            required=False,
            default_value=DISCORD_DEFAULTS["embed_colors"],
            description="Colors to use for embeds based on progress",
            value_type=FieldType.INTEGER
        ),
    ]
    
    # Create and return the schema
    return ConfigSchema(
        name=DISCORD_SCHEMA_NAME,
        fields=fields
    )


def validate_discord_config(config: dict[str, object]) -> dict[str, object]:
    """
    Validate a Discord provider configuration against the schema.
    
    Args:
        config: The configuration to validate.
        
    Returns:
        The validated configuration with defaults applied.
        
    Raises:
        SchemaValidationError: If the configuration is invalid.
    """
    schema = get_discord_schema()
    return schema.validate(config)
