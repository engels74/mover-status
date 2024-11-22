# notifications/providers/discord/templates.py

"""
Message templates and formatting utilities for Discord notifications.
Provides template management and message construction for the Discord provider.

Example:
    >>> from notifications.discord.templates import create_progress_embed
    >>> embed = create_progress_embed(
    ...     percent=75.5,
    ...     remaining="1.2 GB",
    ...     elapsed="2 hours",
    ...     etc="15:30"
    ... )
"""

from datetime import datetime
from typing import Dict, List, Optional, Sequence

from notifications.providers.discord.types import (
    EMBED_LIMITS,
    WEBHOOK_LIMITS,
    DiscordColor,
    Embed,
    EmbedField,
    EmbedFooter,
    get_progress_color,
)
from utils.formatters import format_timestamp
from utils.version import version_checker


def truncate_string(text: str, max_length: int) -> str:
    """Truncate string to maximum length considering Discord limits.

    Args:
        text: String to truncate
        max_length: Maximum allowed length

    Returns:
        str: Truncated string with ellipsis if needed
    """
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
        "text": truncate_string(footer_text, EMBED_LIMITS["footer_text"])
    }

def create_progress_field(
    percent: float,
    remaining: str,
    elapsed: str,
    etc: str,
) -> EmbedField:
    """Create formatted progress field for embed.

    Args:
        percent: Progress percentage
        remaining: Remaining data amount
        elapsed: Elapsed time
        etc: Estimated time of completion

    Returns:
        EmbedField: Formatted progress field
    """
    value = (
        f"Progress: **{percent:.1f}%**\n"
        f"Remaining: {remaining}\n"
        f"Elapsed: {elapsed}\n"
        f"ETC: {etc}"
    )
    return {
        "name": format_timestamp(datetime.now()),
        "value": truncate_string(value, EMBED_LIMITS["field_value"]),
        "inline": False
    }

def create_progress_embed(
    percent: float,
    remaining: str,
    elapsed: str,
    etc: str,
    title: str = "Mover Status",
    description: Optional[str] = None,
) -> Embed:
    """Create a complete progress update embed.

    Args:
        percent: Progress percentage
        remaining: Remaining data amount
        elapsed: Elapsed time
        etc: Estimated time of completion
        title: Optional embed title
        description: Optional description

    Returns:
        Embed: Formatted Discord embed
    """
    embed: Embed = {
        "title": truncate_string(title, EMBED_LIMITS["title"]),
        "color": get_progress_color(percent),
        "fields": [
            create_progress_field(
                percent=percent,
                remaining=remaining,
                elapsed=elapsed,
                etc=etc
            )
        ],
        "footer": create_footer()
    }
    if description:
        embed["description"] = truncate_string(
            description,
            EMBED_LIMITS["description"]
        )
    return embed

def create_completion_embed() -> Embed:
    """Create embed for transfer completion notification.

    Returns:
        Embed: Formatted completion embed
    """
    return {
        "title": "Transfer Complete",
        "description": "All data has been successfully moved from cache to array.",
        "color": DiscordColor.SUCCESS,
        "footer": create_footer()
    }

def create_error_embed(error_message: str) -> Embed:
    """Create embed for error notification.

    Args:
        error_message: Error description

    Returns:
        Embed: Formatted error embed
    """
    return {
        "title": "Transfer Error",
        "description": truncate_string(
            error_message,
            EMBED_LIMITS["description"]
        ),
        "color": DiscordColor.ERROR,
        "footer": create_footer()
    }

def validate_field_lengths(fields: Sequence[EmbedField]) -> int:
    """Validate and calculate total length of embed fields.

    Args:
        fields: List of embed fields to validate

    Returns:
        int: Total length of fields

    Raises:
        ValueError: If any field exceeds Discord limits
    """
    total_length = 0
    for field in fields:
        if len(field["name"]) > EMBED_LIMITS["field_name"]:
            raise ValueError(f"Field name exceeds {EMBED_LIMITS['field_name']} characters")
        if len(field["value"]) > EMBED_LIMITS["field_value"]:
            raise ValueError(f"Field value exceeds {EMBED_LIMITS['field_value']} characters")
        total_length += len(field["name"]) + len(field["value"])
    return total_length

def validate_embed_lengths(embed: Embed) -> None:
    """Validate embed field lengths against Discord limits.

    Args:
        embed: Discord embed to validate

    Raises:
        ValueError: If any field exceeds Discord limits
    """
    total_length = 0
    if "title" in embed:
        if len(embed["title"]) > EMBED_LIMITS["title"]:
            raise ValueError(f"Title exceeds {EMBED_LIMITS['title']} characters")
        total_length += len(embed["title"])

    if "description" in embed:
        if len(embed["description"]) > EMBED_LIMITS["description"]:
            raise ValueError(f"Description exceeds {EMBED_LIMITS['description']} characters")
        total_length += len(embed["description"])

    if "fields" in embed:
        if len(embed["fields"]) > EMBED_LIMITS["fields"]:
            raise ValueError(f"Embed exceeds {EMBED_LIMITS['fields']} fields")
        total_length += validate_field_lengths(embed["fields"])

    if total_length > EMBED_LIMITS["total"]:
        raise ValueError(f"Total embed length exceeds {EMBED_LIMITS['total']} characters")

def create_webhook_data(
    embeds: List[Embed],
    username: str = "Mover Status"
) -> Dict:
    """Create complete webhook payload.

    Args:
        embeds: List of embeds to include
        username: Bot username to display

    Returns:
        Dict: Complete webhook payload

    Raises:
        ValueError: If payload exceeds Discord limits
    """
    if len(embeds) > WEBHOOK_LIMITS["embeds"]:
        raise ValueError(f"Maximum of {WEBHOOK_LIMITS['embeds']} embeds allowed")
    for embed in embeds:
        validate_embed_lengths(embed)
    return {
        "username": truncate_string(username, WEBHOOK_LIMITS["username"]),
        "embeds": embeds
    }
