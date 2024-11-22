# shared/types/discord.py

"""
Shared type definitions for Discord integration.
Contains types used by both configuration and notification components.

Example:
    >>> from shared.types.discord import DiscordColor, Embed
    >>> color = DiscordColor.SUCCESS
    >>> embed = Embed(title="Test", description="Message", color=color)
"""

from enum import IntEnum
from typing import List, Literal, Optional, TypedDict


class DiscordColor(IntEnum):
    """Discord embed color codes."""
    SUCCESS = 0x00FF00      # Green
    WARNING = 0xFFA500      # Orange
    ERROR = 0xFF0000        # Red
    INFO = 0x0099FF         # Light Blue
    PROGRESS_LOW = 0xFF6B6B # Light Red (0-33%)
    PROGRESS_MID = 0xFFB347 # Light Orange (34-66%)
    PROGRESS_HIGH = 0x90EE90 # Light Green (67-100%)

class ApiLimits(IntEnum):
    """Discord API limits."""
    # Message Limits
    CONTENT_LENGTH = 2000    # Maximum message content length
    EMBEDS_PER_MESSAGE = 10  # Maximum embeds per message
    TOTAL_LENGTH = 6000      # Maximum total length across all embeds

    # Embed Limits
    TITLE_LENGTH = 256       # Maximum embed title length
    DESCRIPTION_LENGTH = 4096 # Maximum embed description length
    FIELDS_COUNT = 25        # Maximum number of fields
    FIELD_NAME_LENGTH = 256  # Maximum field name length
    FIELD_VALUE_LENGTH = 1024 # Maximum field value length
    FOOTER_LENGTH = 2048     # Maximum footer text length
    AUTHOR_NAME_LENGTH = 256 # Maximum author name length

    # Webhook Limits
    USERNAME_LENGTH = 80     # Maximum webhook username length

class EmbedField(TypedDict):
    """Discord embed field structure."""
    name: str
    value: str
    inline: Optional[bool]

class EmbedFooter(TypedDict, total=False):
    """Discord embed footer structure."""
    text: str
    icon_url: Optional[str]

class EmbedAuthor(TypedDict, total=False):
    """Discord embed author structure."""
    name: str
    url: Optional[str]
    icon_url: Optional[str]

class EmbedImage(TypedDict, total=False):
    """Discord embed image structure."""
    url: str
    height: Optional[int]
    width: Optional[int]

class EmbedThumbnail(TypedDict, total=False):
    """Discord embed thumbnail structure."""
    url: str
    height: Optional[int]
    width: Optional[int]

class Embed(TypedDict, total=False):
    """Discord embed structure following official API specification."""
    title: str
    type: Literal["rich"]  # Only "rich" is supported for webhook embeds
    description: str
    url: str
    timestamp: str        # ISO8601 timestamp
    color: int
    footer: EmbedFooter
    image: EmbedImage
    thumbnail: EmbedThumbnail
    author: EmbedAuthor
    fields: List[EmbedField]

class WebhookPayload(TypedDict, total=False):
    """Discord webhook payload structure."""
    username: str
    avatar_url: Optional[str]
    content: Optional[str]
    embeds: List[Embed]
    thread_name: Optional[str]
    tts: bool
    flags: int

def get_progress_color(percent: float) -> int:
    """Get appropriate color based on progress percentage.

    Args:
        percent: Progress percentage (0-100)

    Returns:
        int: Discord color code

    Raises:
        ValueError: If percentage is out of valid range

    Example:
        >>> get_progress_color(75.5)
        9498256  # PROGRESS_HIGH color
    """
    if not 0 <= percent <= 100:
        raise ValueError("Percentage must be between 0 and 100")

    if percent < 34:
        return DiscordColor.PROGRESS_LOW
    elif percent < 67:
        return DiscordColor.PROGRESS_MID
    else:
        return DiscordColor.PROGRESS_HIGH
