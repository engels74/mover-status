"""
Discord notification provider package.

This package provides the implementation of the Discord notification provider.
"""

from .defaults import DISCORD_DEFAULTS
from .formatter import (
    format_discord_message,
    format_discord_eta,
    format_markdown_text,
    format_timestamp_for_discord,
    create_embed,
)
from .provider import DiscordProvider

__all__ = [
    "DISCORD_DEFAULTS",
    "DiscordProvider",
    "format_discord_message",
    "format_discord_eta",
    "format_markdown_text",
    "format_timestamp_for_discord",
    "create_embed",
]