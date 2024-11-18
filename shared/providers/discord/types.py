# shared/providers/discord/types.py

"""
Shared type definitions for Discord integration.
Contains types used by both configuration and notification components.
Provides constants, TypedDict classes, and utility functions for Discord webhook API.

Example:
    >>> from shared.providers.discord import DiscordColor, Embed
    >>> color = DiscordColor.SUCCESS
    >>> embed = {"title": "Test", "description": "Message", "color": color}
"""

from enum import IntEnum
from typing import Final, List, Literal, Optional, TypedDict
from urllib.parse import urlparse


class DiscordColor(IntEnum):
    """Discord embed color codes."""
    SUCCESS = 0x2ECC71      # Green
    WARNING = 0xF1C40F      # Yellow
    ERROR = 0xE74C3C        # Red
    INFO = 0x3498DB         # Blue
    PROGRESS_LOW = 0xFF6B6B  # Light Red (0-33%)
    PROGRESS_MID = 0xFFA07A  # Light Orange (34-66%)
    PROGRESS_HIGH = 0x98FB98  # Light Green (67-100%)


class ApiLimit(IntEnum):
    """Discord API limits and constraints."""
    # Message Limits
    CONTENT_LENGTH: Final = 2000      # Maximum message content length
    EMBEDS_PER_MESSAGE: Final = 10    # Maximum embeds per message
    TOTAL_LENGTH: Final = 6000        # Maximum combined length across all embeds
    COMPONENTS_PER_ROW: Final = 5     # Maximum buttons/components per row
    ROWS_PER_MESSAGE: Final = 5       # Maximum component rows per message

    # Embed Limits
    TITLE_LENGTH: Final = 256         # Maximum embed title length
    DESCRIPTION_LENGTH: Final = 4096   # Maximum embed description length
    FIELDS_COUNT: Final = 25          # Maximum number of fields
    FIELD_NAME_LENGTH: Final = 256    # Maximum field name length
    FIELD_VALUE_LENGTH: Final = 1024   # Maximum field value length
    FOOTER_LENGTH: Final = 2048       # Maximum footer text length
    AUTHOR_NAME_LENGTH: Final = 256   # Maximum author name length

    # Webhook Limits
    USERNAME_LENGTH: Final = 80       # Maximum webhook username length
    WEBHOOK_NAME_LENGTH: Final = 32   # Maximum webhook name length
    CHANNEL_NAME_LENGTH: Final = 100   # Maximum channel name length
    RATE_LIMIT_PER_SEC: Final = 30    # Maximum webhook requests per second


class EmbedFooter(TypedDict, total=False):
    """Discord embed footer structure."""
    text: str
    icon_url: Optional[str]


class EmbedImage(TypedDict, total=False):
    """Discord embed image structure."""
    url: str
    proxy_url: Optional[str]
    height: Optional[int]
    width: Optional[int]


class EmbedThumbnail(TypedDict, total=False):
    """Discord embed thumbnail structure."""
    url: str
    proxy_url: Optional[str]
    height: Optional[int]
    width: Optional[int]


class EmbedVideo(TypedDict, total=False):
    """Discord embed video structure."""
    url: Optional[str]
    proxy_url: Optional[str]
    height: Optional[int]
    width: Optional[int]


class EmbedProvider(TypedDict, total=False):
    """Discord embed provider structure."""
    name: Optional[str]
    url: Optional[str]


class EmbedAuthor(TypedDict, total=False):
    """Discord embed author structure."""
    name: str
    url: Optional[str]
    icon_url: Optional[str]
    proxy_icon_url: Optional[str]


class EmbedField(TypedDict):
    """Discord embed field structure."""
    name: str
    value: str
    inline: Optional[bool]


class Embed(TypedDict, total=False):
    """Discord embed structure following official API specification."""
    title: Optional[str]
    type: Literal["rich"]  # Only "rich" is supported for webhook embeds
    description: Optional[str]
    url: Optional[str]
    timestamp: Optional[str]  # ISO8601 timestamp
    color: Optional[int]
    footer: Optional[EmbedFooter]
    image: Optional[EmbedImage]
    thumbnail: Optional[EmbedThumbnail]
    video: Optional[EmbedVideo]
    provider: Optional[EmbedProvider]
    author: Optional[EmbedAuthor]
    fields: Optional[List[EmbedField]]


class WebhookPayload(TypedDict, total=False):
    """Discord webhook payload structure."""
    content: Optional[str]
    username: Optional[str]
    avatar_url: Optional[str]
    tts: Optional[bool]
    embeds: List[Embed]  # Changed from Optional[List[Embed]] as it's always required
    allowed_mentions: Optional[dict]
    components: Optional[List[dict]]
    flags: Optional[int]
    thread_name: Optional[str]


def get_progress_color(percent: float) -> int:
    """Get appropriate color based on progress percentage.

    Args:
        percent: Progress percentage (0-100)

    Returns:
        int: Discord color code

    Raises:
        ValueError: If percentage is out of valid range
    """
    if not 0 <= percent <= 100:
        raise ValueError("Percentage must be between 0 and 100")

    if percent < 33.33:
        return DiscordColor.PROGRESS_LOW
    elif percent < 66.67:
        return DiscordColor.PROGRESS_MID
    return DiscordColor.PROGRESS_HIGH


def validate_url(url: str, allowed_domains: set[str]) -> bool:
    """Validate URL against allowed domains.

    Args:
        url: URL to validate
        allowed_domains: Set of allowed domain names

    Returns:
        bool: True if URL is valid and from allowed domain

    Example:
        >>> allowed = {"discord.com", "cdn.discord.com"}
        >>> validate_url("https://discord.com/api/webhooks/123", allowed)
        True
    """
    try:
        parsed = urlparse(url)
        return bool(
            parsed.scheme in {"http", "https"}
            and any(domain in parsed.netloc for domain in allowed_domains)
        )
    except Exception:
        return False


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate string to maximum length with suffix.

    Args:
        text: String to truncate
        max_length: Maximum allowed length
        suffix: String to append when truncating

    Returns:
        str: Truncated string

    Example:
        >>> truncate_string("Very long text", 8)
        'Very ...'
    """
    if len(text) <= max_length:
        return text
    return text[:(max_length - len(suffix))] + suffix
