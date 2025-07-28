"""Template notification provider plugin.

This plugin serves as a complete example and template for creating new
notification providers for the Mover Status Monitor.

Usage:
    This template is not meant to be used directly in production, but rather
    as a reference for creating your own custom notification providers.

To create a new provider based on this template:
    1. Copy the entire template directory to a new directory
    2. Rename the directory to match your provider name
    3. Update the provider class name and implementation
    4. Modify the plugin metadata below
    5. Test your implementation thoroughly

Plugin Metadata:
    The metadata below is used by the plugin discovery system to identify
    and load this plugin. Make sure to update all fields when creating
    a new provider.
"""

from __future__ import annotations

from .provider import TemplateProvider, PLUGIN_METADATA

# Export the main provider class and metadata
__all__ = [
    "TemplateProvider",
    "PLUGIN_METADATA",
]

# Plugin information for discovery system
# This metadata is used by the plugin loader to identify and register the plugin
PLUGIN_INFO = {
    "name": "template",
    "version": "1.0.0",
    "description": "Template notification provider for development reference",
    "author": "Mover Status Team",
    "provider_class": TemplateProvider,
    "enabled": False,  # Template is disabled by default
    "tags": ["template", "example", "development"],
    "dependencies": [],
    "config_schema": {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "default": False,
                "description": "Enable this notification provider"
            },
            "api_key": {
                "type": "string",
                "description": "API key for the notification service (required)"
            },
            "endpoint": {
                "type": "string",
                "format": "uri",
                "description": "Service endpoint URL (required)"
            },
            "timeout": {
                "type": "number",
                "minimum": 1,
                "maximum": 300,
                "default": 30.0,
                "description": "Request timeout in seconds"
            },
            "retries": {
                "type": "integer",
                "minimum": 0,
                "maximum": 10,
                "default": 3,
                "description": "Number of retry attempts"
            },
            "format": {
                "type": "string",
                "enum": ["json", "text"],
                "default": "json",
                "description": "Message format"
            },
            "custom_field": {
                "type": "string",
                "default": "default_value",
                "description": "Example custom configuration field"
            }
        },
        "required": ["api_key", "endpoint"],
        "additionalProperties": False
    }
}
