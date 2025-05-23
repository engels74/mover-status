"""
Default configuration values for the Template notification provider.

This module defines the default configuration dictionary for the Template
notification provider. This serves as a reference implementation for creating
new notification providers.

The Template provider demonstrates both API and webhook patterns, showing
developers how to implement different types of notification providers.
"""

from typing import TypedDict


class TemplateDefaultsType(TypedDict):
    """Type definition for Template provider defaults."""
    name: str
    enabled: bool
    api_endpoint: str
    api_key: str
    message_template: str
    timeout: int
    retry_attempts: int
    verify_ssl: bool
    custom_headers: dict[str, str]


# Template provider default configuration
TEMPLATE_DEFAULTS: TemplateDefaultsType = {
    # Provider identification
    "name": "template",
    "enabled": False,

    # API configuration
    "api_endpoint": "",
    "api_key": "",

    # Message formatting
    "message_template": (
        "🔄 **Mover Status Update**\n\n"
        "📊 **Progress:** {percent}% complete\n"
        "💾 **Remaining Data:** {remaining_data}\n"
        "⏱️ **Estimated Completion:** {etc}\n\n"
        "ℹ️ *Note: Services like Plex may run slow during the move.*"
    ),

    # Request configuration
    "timeout": 30,
    "retry_attempts": 3,
    "verify_ssl": True,

    # Custom headers for API requests
    "custom_headers": {
        "User-Agent": "MoverStatus/1.0",
        "Content-Type": "application/json"
    },
}
