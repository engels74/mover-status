"""
Discord-specific message formatting.

This module provides functions for formatting messages specifically for the
Discord notification provider. It leverages the common formatters from the
notification.formatter module and adds Discord-specific formatting.
"""

from collections.abc import Mapping
from typing import Literal, TypedDict

from mover_status.notification.formatter import (
    RawValues,
    FormattedValues,
    format_message,
    format_raw_values,
)


class EmbedField(TypedDict, total=False):
    """Type definition for Discord embed field."""
    name: str
    value: str
    inline: bool


class EmbedFooter(TypedDict, total=False):
    """Type definition for Discord embed footer."""
    text: str
    icon_url: str


class EmbedAuthor(TypedDict, total=False):
    """Type definition for Discord embed author."""
    name: str
    url: str
    icon_url: str


class EmbedImage(TypedDict, total=False):
    """Type definition for Discord embed image."""
    url: str
    height: int
    width: int


class EmbedThumbnail(TypedDict, total=False):
    """Type definition for Discord embed thumbnail."""
    url: str
    height: int
    width: int


class Embed(TypedDict, total=False):
    """Type definition for Discord embed."""
    title: str
    description: str
    url: str
    color: int
    timestamp: int
    fields: list[EmbedField]
    footer: EmbedFooter
    author: EmbedAuthor
    image: EmbedImage
    thumbnail: EmbedThumbnail


# Discord timestamp styles
TimestampStyle = Literal["t", "T", "d", "D", "f", "F", "R"]


def format_markdown_text(
    text: str,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    strikethrough: bool = False,
    code: bool = False,
    code_block: bool = False,
) -> str:
    """
    Format text with markdown for Discord.

    Args:
        text: The text to format.
        bold: Whether to make the text bold.
        italic: Whether to make the text italic.
        underline: Whether to make the text underlined.
        strikethrough: Whether to make the text strikethrough.
        code: Whether to format the text as inline code.
        code_block: Whether to format the text as a code block.

    Returns:
        The formatted text with markdown.

    Examples:
        >>> format_markdown_text("Hello")
        'Hello'
        >>> format_markdown_text("Hello", bold=True)
        '**Hello**'
        >>> format_markdown_text("Hello", italic=True)
        '*Hello*'
        >>> format_markdown_text("Hello", bold=True, italic=True)
        '***Hello***'
        >>> format_markdown_text("Hello", code=True)
        '`Hello`'
        >>> format_markdown_text("Hello", code_block=True)
        '```\\nHello\\n```'
    """
    result = text

    # Apply code block formatting (must be applied first)
    if code_block:
        return f"```\n{result}\n```"

    # Apply inline code formatting
    if code:
        result = f"`{result}`"

    # Apply strikethrough formatting
    if strikethrough:
        result = f"~~{result}~~"

    # Apply underline formatting
    if underline:
        result = f"__{result}__"

    # Apply italic formatting
    if italic:
        result = f"*{result}*"

    # Apply bold formatting
    if bold:
        result = f"**{result}**"

    return result


def format_timestamp_for_discord(
    timestamp: float,
    style: TimestampStyle = "R",
) -> str:
    """
    Format a Unix timestamp for display in Discord.

    Discord uses a special format for timestamps: <t:timestamp:style>
    where style can be:
    - t: Short time (e.g., 9:30 AM)
    - T: Long time (e.g., 9:30:00 AM)
    - d: Short date (e.g., 01/01/2021)
    - D: Long date (e.g., January 1, 2021)
    - f: Short date/time (e.g., January 1, 2021 9:30 AM)
    - F: Long date/time (e.g., Friday, January 1, 2021 9:30 AM)
    - R: Relative time (e.g., 2 hours ago, in 3 days)

    Args:
        timestamp: The Unix timestamp to format.
        style: The Discord timestamp style to use.

    Returns:
        A formatted string representation of the timestamp for Discord.

    Examples:
        >>> format_timestamp_for_discord(1609459200)  # 2021-01-01 00:00:00 UTC
        '<t:1609459200:R>'
        >>> format_timestamp_for_discord(1609459200, "F")
        '<t:1609459200:F>'
    """
    # Convert timestamp to integer if it's a float
    int_timestamp = int(timestamp)

    # Format the timestamp for Discord
    return f"<t:{int_timestamp}:{style}>"


def format_discord_eta(eta: float | None) -> str:
    """
    Format an ETA timestamp for display in Discord.

    This function extends the common formatter.format_eta function with
    Discord-specific formatting.

    Args:
        eta: The ETA timestamp as a Unix timestamp, or None if still calculating.

    Returns:
        A formatted string representation of the ETA for Discord, or "Calculating..." if None.

    Examples:
        >>> format_discord_eta(None)
        'Calculating...'
        >>> import time
        >>> current_time = time.time()
        >>> format_discord_eta(current_time + 3600)  # 1 hour in the future
        '<t:1234567890:R>'  # Example output, actual timestamp will vary
    """
    if eta is None:
        return "Calculating..."

    # Format the timestamp for Discord using relative time format
    return format_timestamp_for_discord(eta, "R")


def create_embed(
    title: str,
    description: str | None = None,
    color: int | None = None,
    fields: list[EmbedField] | None = None,
    footer: EmbedFooter | None = None,
    author: EmbedAuthor | None = None,
    image: EmbedImage | None = None,
    thumbnail: EmbedThumbnail | None = None,
    url: str | None = None,
    timestamp: int | None = None,
) -> Embed:
    """
    Create a Discord embed structure.

    Args:
        title: The title of the embed.
        description: The description of the embed.
        color: The color of the embed.
        fields: The fields of the embed.
        footer: The footer of the embed.
        author: The author of the embed.
        image: The image of the embed.
        thumbnail: The thumbnail of the embed.
        url: The URL of the embed.
        timestamp: The timestamp of the embed.

    Returns:
        A Discord embed structure.

    Examples:
        >>> create_embed("Hello", "World", 12345)
        {'title': 'Hello', 'description': 'World', 'color': 12345}
    """
    embed: Embed = {"title": title}

    # Add optional fields if provided
    if description is not None:
        embed["description"] = description
    if color is not None:
        embed["color"] = color
    if fields is not None:
        embed["fields"] = fields
    if footer is not None:
        embed["footer"] = footer
    if author is not None:
        embed["author"] = author
    if image is not None:
        embed["image"] = image
    if thumbnail is not None:
        embed["thumbnail"] = thumbnail
    if url is not None:
        embed["url"] = url
    if timestamp is not None:
        embed["timestamp"] = timestamp

    return embed


def format_discord_message(
    template: str,
    raw_values: RawValues,
    defaults: Mapping[str, object] | None = None,
) -> str:
    """
    Format a message for Discord using the given template and raw values.

    This function first formats the raw values using the common formatter,
    then applies the formatted values to the template.

    Args:
        template: The message template with placeholders.
        raw_values: The raw values to format and substitute.
        defaults: Optional default values to use for missing placeholders.

    Returns:
        The formatted message for Discord.

    Examples:
        >>> template = "Progress: **{percent}**"
        >>> raw_values = {"percent": 50}
        >>> format_discord_message(template, raw_values)
        'Progress: **50%**'
    """
    # First, format the raw values using the common formatter
    formatted_values: FormattedValues = format_raw_values(raw_values)

    # For Discord, we need to convert the ETA to Discord's timestamp format
    if "eta" in raw_values and raw_values["eta"] is not None:
        formatted_values["etc"] = format_discord_eta(raw_values["eta"])

    # Then, apply the formatted values to the template
    return format_message(template, formatted_values, defaults)
