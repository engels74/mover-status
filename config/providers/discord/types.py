# config/providers/discord/types.py

"""
Type definitions specific to Discord webhook configuration.
Contains types used only for configuration purposes, importing shared types as needed.

Example:
    >>> from config.providers.discord.types import WebhookConfig
    >>> config = WebhookConfig(url="https://discord.com/api/webhooks/...", username="Bot")
"""

from typing import Optional, TypedDict

from shared.types.discord import ApiLimits, DiscordColor  # Import shared types we need


class WebhookConfig(TypedDict, total=False):
    """Discord webhook configuration structure."""
    url: str
    username: str
    avatar_url: Optional[str]
    embed_color: Optional[int]
    thread_name: Optional[str]

class RateLimitConfig(TypedDict):
    """Discord rate limit configuration."""
    max_retries: int
    retry_delay: int
    requests_per_second: int
    requests_per_minute: int

# Re-export commonly used items for convenience
# This allows users to import these from either location
__all__ = [
    'WebhookConfig',
    'RateLimitConfig',
    'ApiLimits',
    'DiscordColor',
]
