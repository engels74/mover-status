# notifications/providers/discord/templates.py

"""
Message templates and formatting utilities for Discord notifications.
Provides template management and message construction for the Discord provider.

Example:
    >>> from notifications.providers.discord.templates import create_progress_embed
    >>> embed = create_progress_embed(
    ...     percent=75.5,
    ...     remaining="1.2 GB",
    ...     elapsed="2 hours",
    ...     etc="15:30"
    ... )
"""

from datetime import datetime
from typing import Dict, List, Optional, Union

from shared.providers.discord import (
    ApiLimits,
    DiscordColor,
    Embed,
    EmbedAuthor,
    EmbedField,
    EmbedFooter,
    ForumConfig,
    WebhookPayload,
    get_progress_color,
)
from utils.formatters import format_timestamp
from utils.version import version_checker


def truncate_string(text: str, max_length: int) -> str:
    """Truncate string to maximum length with ellipsis if needed.

    Args:
        text: String to truncate
        max_length: Maximum allowed length

    Returns:
        str: Truncated string

    Raises:
        ValueError: If max_length is negative
    """
    if max_length < 0:
        raise ValueError("max_length cannot be negative")

    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def create_footer(version_info: Optional[str] = None) -> EmbedFooter:
    """Create embed footer with version information.

    Args:
        version_info: Optional version string to include

    Returns:
        EmbedFooter: Formatted footer
    """
    footer_text = f"Mover Status v{version_checker.current_version}"
    if version_info:
        footer_text += f" ({version_info})"
    return {
        "text": truncate_string(footer_text, ApiLimits.FOOTER_TEXT_LENGTH)
    }


def create_progress_field(
    percent: float,
    remaining: str,
    elapsed: str,
    etc: str,
) -> EmbedField:
    """Create formatted progress field for embed.

    Args:
        percent: Progress percentage (0-100)
        remaining: Remaining data amount
        elapsed: Elapsed time
        etc: Estimated time of completion

    Returns:
        EmbedField: Formatted progress field

    Raises:
        ValueError: If percent is out of range
    """
    if not 0 <= percent <= 100:
        raise ValueError("Percent must be between 0 and 100")

    name = format_timestamp(datetime.now())
    value = (
        f"Progress: **{percent:.1f}%**\n"
        f"Remaining: {remaining}\n"
        f"Elapsed: {elapsed}\n"
        f"ETC: {etc}"
    )

    return {
        "name": truncate_string(name, ApiLimits.FIELD_NAME_LENGTH),
        "value": truncate_string(value, ApiLimits.FIELD_VALUE_LENGTH),
        "inline": False
    }


def create_progress_embed(
    percent: float,
    remaining: str,
    elapsed: str,
    etc: str,
    title: str = "Mover Status",
    description: Optional[str] = None,
    author: Optional[EmbedAuthor] = None,
) -> Embed:
    """Create a complete progress update embed.

    Args:
        percent: Progress percentage (0-100)
        remaining: Remaining data amount
        elapsed: Elapsed time
        etc: Estimated time of completion
        title: Optional embed title
        description: Optional description
        author: Optional author information

    Returns:
        Embed: Formatted Discord embed

    Raises:
        ValueError: If percent is out of range or field lengths exceed limits
    """
    embed: Embed = {
        "title": truncate_string(title, ApiLimits.TITLE_LENGTH),
        "color": get_progress_color(percent),
        "fields": [
            create_progress_field(
                percent=percent,
                remaining=remaining,
                elapsed=elapsed,
                etc=etc
            )
        ],
        "footer": create_footer(),
        "timestamp": datetime.utcnow().isoformat()
    }

    if description:
        embed["description"] = truncate_string(
            description,
            ApiLimits.DESCRIPTION_LENGTH
        )

    if author:
        embed["author"] = {
            "name": truncate_string(author["name"], ApiLimits.AUTHOR_NAME_LENGTH),
            "url": author.get("url"),
            "icon_url": author.get("icon_url")
        }

    validate_embed_lengths(embed)
    return embed


def create_completion_embed(
    description: Optional[str] = None,
    stats: Optional[Dict[str, Union[str, int, float]]] = None
) -> Embed:
    """Create embed for transfer completion notification.

    Args:
        description: Optional custom description
        stats: Optional transfer statistics to include

    Returns:
        Embed: Formatted completion embed
    """
    embed: Embed = {
        "title": "Transfer Complete",
        "description": description or "All data has been successfully moved from cache to array.",
        "color": DiscordColor.SUCCESS,
        "footer": create_footer(),
        "timestamp": datetime.utcnow().isoformat()
    }

    if stats:
        fields: List[EmbedField] = []
        for key, value in stats.items():
            fields.append({
                "name": truncate_string(str(key), ApiLimits.FIELD_NAME_LENGTH),
                "value": truncate_string(str(value), ApiLimits.FIELD_VALUE_LENGTH),
                "inline": True
            })
        if fields:
            embed["fields"] = fields

    validate_embed_lengths(embed)
    return embed


def create_error_embed(
    error_message: str,
    error_code: Optional[int] = None,
    error_details: Optional[Dict[str, str]] = None
) -> Embed:
    """Create embed for error notification.

    Args:
        error_message: Error description
        error_code: Optional error code
        error_details: Optional error details

    Returns:
        Embed: Formatted error embed

    Raises:
        ValueError: If error_message is empty
    """
    if not error_message.strip():
        raise ValueError("Error message cannot be empty")

    description = error_message
    if error_code:
        description = f"Error {error_code}: {description}"

    embed: Embed = {
        "title": "Transfer Error",
        "description": truncate_string(description, ApiLimits.DESCRIPTION_LENGTH),
        "color": DiscordColor.ERROR,
        "footer": create_footer(),
        "timestamp": datetime.utcnow().isoformat()
    }

    if error_details:
        fields: List[EmbedField] = []
        for key, value in error_details.items():
            fields.append({
                "name": truncate_string(key, ApiLimits.FIELD_NAME_LENGTH),
                "value": truncate_string(value, ApiLimits.FIELD_VALUE_LENGTH),
                "inline": True
            })
        if fields:
            embed["fields"] = fields

    validate_embed_lengths(embed)
    return embed


def validate_title(title: Optional[str]) -> int:
    """Validate embed title length.

    Args:
        title: Title to validate

    Returns:
        int: Length of title

    Raises:
        ValueError: If title exceeds length limit
    """
    if not title:
        return 0
    if len(title) > ApiLimits.TITLE_LENGTH:
        raise ValueError(f"Title exceeds {ApiLimits.TITLE_LENGTH} characters")
    return len(title)


def validate_description(description: Optional[str]) -> int:
    """Validate embed description length.

    Args:
        description: Description to validate

    Returns:
        int: Length of description

    Raises:
        ValueError: If description exceeds length limit
    """
    if not description:
        return 0
    if len(description) > ApiLimits.DESCRIPTION_LENGTH:
        raise ValueError(f"Description exceeds {ApiLimits.DESCRIPTION_LENGTH} characters")
    return len(description)


def validate_fields(fields: Optional[List[EmbedField]]) -> int:
    """Validate embed fields.

    Args:
        fields: Fields to validate

    Returns:
        int: Total length of fields

    Raises:
        ValueError: If fields exceed limits
    """
    if not fields:
        return 0

    if len(fields) > ApiLimits.FIELDS_COUNT:
        raise ValueError(f"Maximum of {ApiLimits.FIELDS_COUNT} fields allowed")

    total_length = 0
    for field in fields:
        if len(field["name"]) > ApiLimits.FIELD_NAME_LENGTH:
            raise ValueError(f"Field name exceeds {ApiLimits.FIELD_NAME_LENGTH} characters")
        if len(field["value"]) > ApiLimits.FIELD_VALUE_LENGTH:
            raise ValueError(f"Field value exceeds {ApiLimits.FIELD_VALUE_LENGTH} characters")
        total_length += len(field["name"]) + len(field["value"])

    return total_length


def validate_footer(footer: Optional[Dict[str, str]]) -> int:
    """Validate embed footer.

    Args:
        footer: Footer to validate

    Returns:
        int: Length of footer text

    Raises:
        ValueError: If footer text exceeds length limit
    """
    if not footer or "text" not in footer:
        return 0
    if len(footer["text"]) > ApiLimits.FOOTER_TEXT_LENGTH:
        raise ValueError(f"Footer text exceeds {ApiLimits.FOOTER_TEXT_LENGTH} characters")
    return len(footer["text"])


def validate_author(author: Optional[Dict[str, str]]) -> int:
    """Validate embed author.

    Args:
        author: Author to validate

    Returns:
        int: Length of author name

    Raises:
        ValueError: If author name exceeds length limit
    """
    if not author or "name" not in author:
        return 0
    if len(author["name"]) > ApiLimits.AUTHOR_NAME_LENGTH:
        raise ValueError(f"Author name exceeds {ApiLimits.AUTHOR_NAME_LENGTH} characters")
    return len(author["name"])


def validate_embed_lengths(embed: Embed) -> None:
    """Validate embed field lengths against Discord limits.

    Args:
        embed: Discord embed to validate

    Raises:
        ValueError: If any component exceeds Discord limits
    """
    total_length = 0
    total_length += validate_title(embed.get("title"))
    total_length += validate_description(embed.get("description"))
    total_length += validate_fields(embed.get("fields"))
    total_length += validate_footer(embed.get("footer"))
    total_length += validate_author(embed.get("author"))

    if total_length > ApiLimits.TOTAL_LENGTH:
        raise ValueError(f"Total embed length exceeds {ApiLimits.TOTAL_LENGTH} characters")


def create_webhook_payload(
    embeds: List[Embed],
    username: str = "Mover Bot",
    avatar_url: Optional[str] = None,
    forum_config: Optional[ForumConfig] = None
) -> WebhookPayload:
    """Create complete webhook payload with optional forum support.

    Args:
        embeds: List of embeds to include
        username: Bot username to display
        avatar_url: Optional avatar URL
        forum_config: Optional forum configuration for thread creation

    Returns:
        WebhookPayload: Complete webhook payload

    Raises:
        ValueError: If payload exceeds Discord limits
    """
    if len(embeds) > ApiLimits.EMBEDS_PER_MESSAGE:
        raise ValueError(f"Maximum of {ApiLimits.EMBEDS_PER_MESSAGE} embeds allowed")

    for embed in embeds:
        validate_embed_lengths(embed)

    # Create base payload
    payload: WebhookPayload = {
        "username": truncate_string(username, ApiLimits.USERNAME_LENGTH),
        "embeds": embeds
    }

    if avatar_url:
        payload["avatar_url"] = avatar_url

    # Add forum-specific settings if enabled
    if forum_config and forum_config.get("enabled"):
        if forum_config.get("auto_thread"):
            thread_name = forum_config.get("default_thread_name")
            if thread_name:
                payload["thread_name"] = truncate_string(
                    thread_name,
                    ApiLimits.CHANNEL_NAME_LENGTH
                )

            if forum_config.get("thread_archive_duration"):
                payload["thread_auto_archive_duration"] = forum_config["thread_archive_duration"]

    return payload
