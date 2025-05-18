"""
Default configuration values for the Discord notification provider.

This module defines the default configuration dictionary specific to the Discord
notification provider. These values will be used if no user configuration is provided
or as a fallback for missing values.
"""

from typing import TypedDict


class EmbedColorsType(TypedDict):
    """Type definition for Discord embed colors."""
    low_progress: int
    mid_progress: int
    high_progress: int
    complete: int


class DiscordDefaultsType(TypedDict):
    """Type definition for Discord provider defaults."""
    name: str
    enabled: bool
    webhook_url: str
    username: str
    message_template: str
    use_embeds: bool
    embed_title: str
    embed_colors: EmbedColorsType


# Discord provider default configuration
DISCORD_DEFAULTS: DiscordDefaultsType = {
    # Provider identification
    "name": "discord",
    "enabled": False,

    # API configuration
    "webhook_url": "",
    "username": "Mover Bot",

    # Message formatting
    "message_template": (
        "Moving data from SSD Cache to HDD Array.\n"
        "Progress: **{percent}%** complete.\n"
        "Remaining data: {remaining_data}.\n"
        "Estimated completion time: {etc}.\n\n"
        "Note: Services like Plex may run slow or be unavailable during the move."
    ),

    # Embed options
    "use_embeds": True,
    "embed_title": "Mover: Moving Data",
    "embed_colors": {
        "low_progress": 16744576,  # Light Red (0-34%)
        "mid_progress": 16753920,  # Light Orange (35-65%)
        "high_progress": 9498256,  # Light Green (66-99%)
        "complete": 65280,         # Green (100%)
    },
}
