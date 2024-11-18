# notifications/providers/discord/__init__.py

"""
Discord webhook notification provider package.
Provides functionality for sending notifications via Discord webhooks.

Example:
    >>> from notifications.providers.discord import DiscordConfig, DiscordProvider
    >>> config = DiscordConfig(webhook_url="https://discord.com/api/webhooks/...")
    >>> provider = DiscordProvider(config.to_provider_config())
    >>> async with provider:
    ...     await provider.notify_progress(75.5, "1.2 GB", "2 hours", "15:30")
"""

from typing import TYPE_CHECKING

from notifications.providers.discord.config import DiscordConfig
from notifications.providers.discord.provider import (
    DiscordProvider,
    DiscordWebhookError,
)
from notifications.providers.discord.types import DiscordColor

if TYPE_CHECKING:
    from notifications.providers.discord.templates import (
        create_completion_embed,
        create_error_embed,
        create_progress_embed,
        create_webhook_data,
    )
    from notifications.providers.discord.types import (
        Embed,
        EmbedAuthor,
        EmbedField,
        EmbedFooter,
        EmbedImage,
        EmbedThumbnail,
        WebhookPayload,
    )

__all__ = [
    # Main classes
    "DiscordProvider",
    "DiscordConfig",
    # Exceptions
    "DiscordWebhookError",
    # Enums and constants
    "DiscordColor",
    # Template functions
    "create_completion_embed",
    "create_error_embed",
    "create_progress_embed",
    "create_webhook_data",
    # Type definitions
    "Embed",
    "EmbedAuthor",
    "EmbedField",
    "EmbedFooter",
    "EmbedImage",
    "EmbedThumbnail",
    "WebhookPayload",
]

__version__ = "0.1.0"
__author__ = "engels74"
__description__ = "Discord webhook notification provider for MoverStatus"

# Version information for the provider
VERSION_INFO = {
    "major": 0,
    "minor": 1,
    "patch": 0,
    "release": None,  # e.g., "alpha", "beta", "rc1"
}

def get_version() -> str:
    """Get current version string.

    Returns:
        str: Version string
    """
    version = f"{VERSION_INFO['major']}.{VERSION_INFO['minor']}.{VERSION_INFO['patch']}"
    if VERSION_INFO['release']:
        version += f"-{VERSION_INFO['release']}"
    return version

def is_available() -> bool:
    """Check if provider requirements are met.

    Returns:
        bool: True if provider can be used
    """
    try:
        import aiohttp  # noqa: F401
        return True
    except ImportError:
        return False
