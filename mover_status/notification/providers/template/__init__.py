"""
Template notification provider package.

This package provides a reference implementation of a notification provider,
demonstrating best practices and patterns for creating new providers.

The Template provider serves as:
1. A complete working example of a notification provider
2. Documentation of the provider architecture
3. A starting point for creating new providers
4. A test case for the provider system

Usage Example:
    ```python
    from mover_status.notification.providers.template import TemplateProvider
    
    config = {
        "enabled": True,
        "api_endpoint": "https://api.example.com/webhook",
        "api_key": "your_api_key_here",
        "message_template": "Progress: {percent}% - ETA: {etc}"
    }
    
    provider = TemplateProvider("template", config)
    success = provider.send_notification("Test message")
    ```
"""

from .defaults import TEMPLATE_DEFAULTS
from .formatter import (
    format_template_message,
    format_template_eta,
    format_template_text,
    format_template_progress_bar,
)
from .provider import TemplateProvider

__all__ = [
    "TEMPLATE_DEFAULTS",
    "TemplateProvider",
    "format_template_message",
    "format_template_eta",
    "format_template_text",
    "format_template_progress_bar",
]
