# shared/types/discord.py

"""
Shared type definitions for Discord integration.
Contains types used by both configuration and notification components.

Example:
    >>> from shared.types.discord import DiscordColor, Embed
    >>> color = DiscordColor.SUCCESS
    >>> embed = {"title": "Test", "description": "Message", "color": color}
"""

from enum import IntEnum
from typing import List, Literal, Optional, TypedDict


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
    CONTENT_LENGTH = 2000    # Maximum message content length
    EMBEDS_PER_MESSAGE = 10  # Maximum embeds per message
    TOTAL_LENGTH = 6000      # Maximum combined length across all embeds
    COMPONENTS_PER_ROW = 5   # Maximum buttons/components per row
    ROWS_PER_MESSAGE = 5     # Maximum component rows per message

    # Embed Limits
    TITLE_LENGTH = 256       # Maximum embed title length
    DESCRIPTION_LENGTH = 4096 # Maximum embed description length
    FIELDS_COUNT = 25        # Maximum number of fields
    FIELD_NAME_LENGTH = 256  # Maximum field name length
    FIELD_VALUE_LENGTH = 1024 # Maximum field value length
    FOOTER_TEXT_LENGTH = 2048 # Maximum footer text length
    AUTHOR_NAME_LENGTH = 256 # Maximum author name length

    # Webhook Limits
    USERNAME_LENGTH = 80     # Maximum webhook username length
    WEBHOOK_NAME_LENGTH = 32 # Maximum webhook name length
    CHANNEL_NAME_LENGTH = 100 # Maximum channel name length
    RATE_LIMIT_PER_SEC = 30  # Maximum webhook requests per second


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
    embeds: Optional[List[Embed]]
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
    else:
        return DiscordColor.PROGRESS_HIGH


def validate_text_field(text: str, max_length: int, field_name: str) -> bool:
    """Validate length of a text field.

    Args:
        text: Text to validate
        max_length: Maximum allowed length
        field_name: Name of the field for error messages

    Returns:
        bool: True if text is valid

    Raises:
        ValueError: If text exceeds maximum length
    """
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds {max_length} characters")
    return True


def validate_embed_fields(fields: List[EmbedField]) -> int:
    """Validate embed fields and return total length.

    Args:
        fields: List of embed fields

    Returns:
        int: Total length of field content

    Raises:
        ValueError: If fields exceed Discord limits
    """
    if len(fields) > ApiLimit.FIELDS_COUNT:
        raise ValueError(f"Maximum of {ApiLimit.FIELDS_COUNT} fields allowed")

    total_length = 0
    for field in fields:
        validate_text_field(field["name"], ApiLimit.FIELD_NAME_LENGTH, "Field name")
        validate_text_field(field["value"], ApiLimit.FIELD_VALUE_LENGTH, "Field value")
        total_length += len(field["name"]) + len(field["value"])

    return total_length


def validate_embed(embed: Embed) -> bool:
    """Validate embed structure against Discord limits.

    Args:
        embed: Discord embed to validate

    Returns:
        bool: True if embed is valid

    Raises:
        ValueError: If embed exceeds Discord limits
    """
    total_length = 0

    # Validate title
    if embed.get("title"):
        validate_text_field(embed["title"], ApiLimit.TITLE_LENGTH, "Title")
        total_length += len(embed["title"])

    # Validate description
    if embed.get("description"):
        validate_text_field(embed["description"], ApiLimit.DESCRIPTION_LENGTH, "Description")
        total_length += len(embed["description"])

    # Validate fields
    if embed.get("fields"):
        total_length += validate_embed_fields(embed["fields"])

    # Validate total length
    if total_length > ApiLimit.TOTAL_LENGTH:
        raise ValueError(f"Total embed length exceeds {ApiLimit.TOTAL_LENGTH} characters")

    return True


def truncate_string(text: str, max_length: int) -> str:
    """Truncate string to maximum length with ellipsis.

    Args:
        text: String to truncate
        max_length: Maximum allowed length

    Returns:
        str: Truncated string

    Example:
        >>> truncate_string("Very long text", 8)
        'Very ...'
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
