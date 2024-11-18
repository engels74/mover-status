# notifications/discord/types.py

"""
Type definitions and constants for Discord webhook notifications.
Defines message structure, embed limits, and color schemes for Discord webhooks.

Example:
    >>> from notifications.discord.types import DiscordColor, WebhookPayload
    >>> payload = WebhookPayload(
    ...     username="Mover Bot",
    ...     embeds=[{
    ...         "title": "Transfer Progress",
    ...         "color": DiscordColor.SUCCESS
    ...     }]
    ... )
"""

from enum import IntEnum
from typing import List, Literal, Optional, TypedDict


class DiscordColor(IntEnum):
    """Discord embed color codes."""
    SUCCESS = 0x00FF00  # Green
    WARNING = 0xFFA500  # Orange
    ERROR = 0xFF0000    # Red
    INFO = 0x0099FF     # Light Blue
    PROGRESS_LOW = 0xFF6B6B    # Light Red (0-33%)
    PROGRESS_MID = 0xFFB347    # Light Orange (34-66%)
    PROGRESS_HIGH = 0x90EE90   # Light Green (67-100%)


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
    timestamp: str  # ISO8601 timestamp
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
    tts: bool
    flags: int


# Discord API Limits
EMBED_LIMITS = {
    "title": 256,        # Maximum title length
    "description": 4096, # Maximum description length
    "fields": 25,        # Maximum number of fields
    "field_name": 256,   # Maximum field name length
    "field_value": 1024, # Maximum field value length
    "footer_text": 2048, # Maximum footer text length
    "author_name": 256,  # Maximum author name length
    "total": 6000,       # Maximum total characters in all embed fields
}

WEBHOOK_LIMITS = {
    "content": 2000,     # Maximum content length
    "embeds": 10,        # Maximum number of embeds
    "username": 80,      # Maximum username length
}

# Rate Limiting
RATE_LIMIT = {
    "max_retries": 3,    # Maximum number of retry attempts
    "retry_delay": 5,    # Delay between retries in seconds
    "rate_limit": 30,    # Maximum requests per rate period
    "rate_period": 60,   # Rate limit period in seconds
}

def get_progress_color(percent: float) -> int:
    """Get appropriate color based on progress percentage.
    Args:
        percent: Progress percentage (0-100)
    Returns:
        int: Discord color code
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
