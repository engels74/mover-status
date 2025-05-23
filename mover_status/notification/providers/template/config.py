"""
Configuration schema for the Template notification provider.

This module defines the configuration schema for the Template notification provider,
including field definitions, validation rules, and default values. This serves as
a reference implementation for creating configuration schemas for new providers.
"""

from mover_status.config.schema import ConfigSchema, SchemaField, FieldType
from mover_status.notification.providers.template.defaults import TEMPLATE_DEFAULTS

# Schema name for the Template provider
TEMPLATE_SCHEMA_NAME = "template"


def get_template_schema() -> ConfigSchema:
    """
    Get the configuration schema for the Template notification provider.
    
    This function demonstrates how to create a comprehensive configuration
    schema for a notification provider, including all common field types
    and validation patterns.
    
    Returns:
        The Template provider configuration schema.
    """
    # Define the schema fields based on the Template provider requirements
    fields = [
        SchemaField(
            name="enabled",
            field_type=FieldType.BOOLEAN,
            required=False,
            default_value=TEMPLATE_DEFAULTS["enabled"],
            description="Whether the Template provider is enabled"
        ),
        SchemaField(
            name="api_endpoint",
            field_type=FieldType.STRING,
            required=True,
            default_value=TEMPLATE_DEFAULTS["api_endpoint"],
            description="API endpoint URL for sending notifications"
        ),
        SchemaField(
            name="api_key",
            field_type=FieldType.STRING,
            required=True,
            default_value=TEMPLATE_DEFAULTS["api_key"],
            description="API key for authentication"
        ),
        SchemaField(
            name="message_template",
            field_type=FieldType.STRING,
            required=False,
            default_value=TEMPLATE_DEFAULTS["message_template"],
            description="Template for formatting notification messages"
        ),
        SchemaField(
            name="timeout",
            field_type=FieldType.INTEGER,
            required=False,
            default_value=TEMPLATE_DEFAULTS["timeout"],
            description="Request timeout in seconds"
        ),
        SchemaField(
            name="retry_attempts",
            field_type=FieldType.INTEGER,
            required=False,
            default_value=TEMPLATE_DEFAULTS["retry_attempts"],
            description="Number of retry attempts for failed requests"
        ),
        SchemaField(
            name="verify_ssl",
            field_type=FieldType.BOOLEAN,
            required=False,
            default_value=TEMPLATE_DEFAULTS["verify_ssl"],
            description="Whether to verify SSL certificates"
        ),
        SchemaField(
            name="custom_headers",
            field_type=FieldType.DICT,
            required=False,
            default_value=TEMPLATE_DEFAULTS["custom_headers"],
            description="Custom headers to include in requests",
            value_type=FieldType.STRING
        ),
    ]
    
    # Create and return the schema
    return ConfigSchema(
        name=TEMPLATE_SCHEMA_NAME,
        fields=fields
    )


def validate_template_config(config: dict[str, object]) -> dict[str, object]:
    """
    Validate a Template provider configuration against the schema.
    
    This function demonstrates how to validate provider configuration
    using the schema system.
    
    Args:
        config: The configuration to validate.
        
    Returns:
        The validated configuration with defaults applied.
        
    Raises:
        SchemaValidationError: If the configuration is invalid.
    """
    schema = get_template_schema()
    return schema.validate(config)
