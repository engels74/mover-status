# notifications/providers/discord/templates.py

"""Discord message templates and formatting utilities.

This module provides a comprehensive set of utilities for creating and formatting
Discord webhook messages, with a focus on rich embeds for various notification types.

Features:
    - Rich embeds for progress updates, errors, warnings, and system status
    - Automatic length validation against Discord API limits
    - Support for native Discord timestamps and formatting
    - Thread and forum integration support
    - Customizable appearance with colors and fields

Template Types:
    - Progress: Real-time progress updates with progress bars
    - Completion: Operation completion notifications with statistics
    - Error: Error reports with optional stack traces
    - Warning: Warning messages with resolution suggestions
    - System: System status updates with metrics
    - Debug: Debug information with context
    - Interactive: User-interactive messages with actions
    - Batch: Batch operation status updates

Example:
    >>> from notifications.providers.discord.templates import create_progress_embed
    >>>
    >>> # Create a progress update embed
    >>> embed = create_progress_embed(
    ...     percent=75.5,
    ...     remaining="1.2 GB",
    ...     elapsed="2 hours",
    ...     etc="15:30",
    ...     description="Transferring files...",
    ...     color_enabled=True
    ... )
    >>>
    >>> # Create a webhook payload
    >>> payload = create_webhook_payload(
    ...     embeds=[embed],
    ...     username="Transfer Bot",
    ...     avatar_url="https://example.com/avatar.png"
    ... )

Note:
    All template functions handle Discord's API limits automatically and will
    truncate content if necessary. See Discord's documentation for details:
    https://discord.com/developers/docs/resources/webhook#execute-webhook
"""

from datetime import datetime, timedelta, UTC
from typing import Any, Dict, List, Optional, cast

from shared.providers.discord.types import (
    EmbedField,
    EmbedFooter,
    get_progress_color,
)
from utils.formatters import (
    TimeFormat,
    format_timestamp,
)
from utils.version import version_checker


def truncate_string(text: str, max_length: int) -> str:
    """Truncate string to maximum length with ellipsis.

    Ensures strings fit within Discord's length limits by truncating them
    and adding an ellipsis (...) if they exceed the maximum length.

    Args:
        text (str): String to truncate
        max_length (int): Maximum allowed length

    Returns:
        str: Original string if within limits, or truncated string with ellipsis

    Raises:
        ValueError: If max_length is negative

    Example:
        >>> truncate_string("This is a long string", 10)
        'This is...'
    """
    if max_length < 0:
        raise ValueError("max_length cannot be negative")

    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def create_footer() -> Dict[str, Optional[str]]:
    """Create footer with version information."""
    return {
        "text": f"v{version_checker.get_version()}",
        "icon_url": None
    }


def create_progress_field(
    percent: float,
    remaining: str,
    elapsed: str,
    etc: str,
) -> EmbedField:
    """Create formatted progress field with progress bar.

    Generates a field containing a visual progress bar and timing information
    for use in progress update embeds.

    Args:
        percent (float): Progress percentage (0-100)
        remaining (str): Remaining data/time amount (e.g., "1.2 GB")
        elapsed (str): Elapsed time (e.g., "2 hours")
        etc (str): Estimated time of completion (e.g., "15:30")

    Returns:
        EmbedField: Dictionary containing formatted progress information

    Raises:
        ValueError: If percent is not between 0 and 100

    Example:
        >>> field = create_progress_field(75.5, "500MB", "1h", "12:30")
        >>> print(field["value"])
        ```
        ███████████████░░░░░ 75.5%
        ```
        ⏱️ Elapsed: 1h
        ⌛ Remaining: 500MB
        🏁 ETC: 12:30
    """
    if not 0 <= percent <= 100:
        raise ValueError("Percent must be between 0 and 100")

    # Create progress bar
    bar_length = 20
    filled = int(bar_length * percent / 100)
    empty = bar_length - filled
    progress_bar = "█" * filled + "░" * empty

    name = format_timestamp(datetime.now())
    value = (
        f"```\n{progress_bar} {percent:.1f}%\n```\n"
        f"⏱️ Elapsed: {elapsed}\n"
        f"⌛ Remaining: {remaining}\n"
        f"🏁 ETC: {etc}"
    )

    return {
        "name": name,
        "value": value,
        "inline": False
    }


def _process_embed_fields(embed: Dict[str, Any], fields: List[Dict[str, Any]]) -> None:
    """Process and add fields to the embed."""
    if fields:
        embed["fields"] = fields


def _process_embed_author(embed: Dict[str, Any], author: Dict[str, Any]) -> None:
    """Process and add author to the embed."""
    if author:
        embed["author"] = author


def _process_embed_footer(embed: Dict[str, Any], footer: Dict[str, Any]) -> None:
    """Process and add footer to the embed."""
    if footer:
        embed["footer"] = footer


def create_embed(**kwargs) -> Dict[str, Any]:
    """Create a new Discord embed with the given parameters."""
    embed: Dict[str, Any] = {}

    # Process basic fields
    if title := kwargs.get("title"):
        embed["title"] = str(title)

    if description := kwargs.get("description"):
        embed["description"] = str(description)

    if url := kwargs.get("url"):
        embed["url"] = str(url)

    if timestamp := kwargs.get("timestamp"):
        embed["timestamp"] = timestamp

    if color := kwargs.get("color"):
        embed["color"] = color

    # Process thumbnail and image
    if thumbnail_url := kwargs.get("thumbnail_url"):
        embed["thumbnail"] = {"url": str(thumbnail_url)}

    if image_url := kwargs.get("image_url"):
        embed["image"] = {"url": str(image_url)}

    # Process complex fields
    _process_embed_fields(embed, kwargs.get("fields", []))
    _process_embed_author(embed, kwargs.get("author", {}))
    _process_embed_footer(embed, kwargs.get("footer", {}))

    return embed


def add_field(embed: Dict[str, Any], name: str, value: str, inline: Optional[bool] = False) -> None:
    """Add a field to an embed."""
    fields = embed.get("fields", [])
    if fields is None:
        fields = []
        embed["fields"] = fields

    if len(fields) >= 25:
        raise ValueError("Cannot have more than 25 fields")

    field: EmbedField = {
        "name": truncate_string(name, 256),
        "value": truncate_string(value, 1024),
        "inline": bool(inline)  # Convert Optional[bool] to bool
    }
    fields.append(field)


def set_footer(embed: Dict[str, Any], text: Optional[str], icon_url: Optional[str] = None) -> None:
    """Set footer for an embed."""
    if not text:
        return

    footer: EmbedFooter = {}
    footer["text"] = truncate_string(text, 2048)
    if icon_url:
        footer["icon_url"] = icon_url
    embed["footer"] = footer


def set_author(embed: Dict[str, Any], name: Optional[str], url: Optional[str] = None, icon_url: Optional[str] = None) -> None:
    """Set author for an embed."""
    if not name:
        return

    author: Dict[str, Any] = {}
    author["name"] = truncate_string(name, 256)
    if url:
        author["url"] = url
    if icon_url:
        author["icon_url"] = icon_url
    embed["author"] = author


def create_progress_embed(
    percent: float,
    remaining: str,
    elapsed: str,
    etc: str,
    title: str = "Mover Status",
    description: Optional[str] = None,
    author: Optional[Dict[str, str]] = None,
    use_native_timestamps: bool = True,
    color: Optional[int] = None,
    color_enabled: bool = True
) -> Dict[str, Any]:
    """Create a complete progress update embed."""
    # Create base embed
    embed = create_embed(
        title=title,
        description=description,
        color=color if color is not None else (
            get_progress_color(percent) if color_enabled else None
        ),
        timestamp=datetime.now(UTC).isoformat() if use_native_timestamps else None
    )

    # Create and add progress field
    progress_field = create_progress_field(percent, remaining, elapsed, etc)
    add_field(
        embed,
        name=progress_field["name"],
        value=progress_field["value"],
        inline=progress_field.get("inline", False)
    )

    # Add footer with version
    footer = create_footer()
    if "text" in footer:
        set_footer(embed, text=footer["text"], icon_url=footer.get("icon_url"))

    # Add author if provided
    if author:
        embed["author"] = cast(Dict[str, Any], author)

    return embed


def create_completion_embed(
    description: Optional[str] = None,
    stats: Optional[Dict[str, Any]] = None,
    color: Optional[int] = None,
    color_enabled: bool = True
) -> Dict[str, Any]:
    """Create embed for transfer completion notification."""
    embed = create_embed(
        title="Transfer Complete",
        description=description,
        color=color if color is not None else (
            0x00ff00 if color_enabled else None
        )
    )

    if stats:
        for key, value in stats.items():
            add_field(
                embed,
                name=key.replace('_', ' ').title(),
                value=str(value),
                inline=True
            )

    footer = create_footer()
    set_footer(embed, text=footer["text"], icon_url=footer.get("icon_url"))

    return embed


def create_error_embed(
    error_message: str,
    error_code: Optional[int] = None,
    error_details: Optional[Dict[str, Any]] = None,
    color: Optional[int] = None,
    color_enabled: bool = True
) -> Dict[str, Any]:
    """Create embed for error notification."""
    embed = create_embed(
        title="Error",
        description=error_message,
        color=color if color is not None else (
            0xff0000 if color_enabled else None
        )
    )

    if error_code is not None:
        add_field(
            embed,
            name="Error Code",
            value=str(error_code),
            inline=True
        )

    if error_details:
        for key, value in error_details.items():
            add_field(
                embed,
                name=key.replace('_', ' ').title(),
                value=str(value),
                inline=True
            )

    footer = create_footer()
    set_footer(embed, text=footer["text"], icon_url=footer.get("icon_url"))

    return embed


def create_warning_embed(
    message: str,
    title: str = "Warning",
    color: Optional[int] = None,
    use_native_timestamps: bool = True
) -> Dict[str, Any]:
    """Create a warning embed."""
    embed = create_embed(
        title=title,
        description=message,
        color=color if color is not None else 0xffff00,
        timestamp=datetime.now(UTC).isoformat() if use_native_timestamps else None
    )

    current_time = datetime.now()
    warning_time = format_discord_timestamp(current_time, "f") if use_native_timestamps else format_timestamp(current_time, format_type=TimeFormat.FRIENDLY)
    set_footer(embed, text=f"Warning issued at {warning_time}")
    return embed


def create_system_embed(
    message: str,
    title: str = "System Message",
    color: Optional[int] = None,
    use_native_timestamps: bool = True
) -> Dict[str, Any]:
    """Create a system message embed."""
    embed = create_embed(
        title=title,
        description=message,
        color=color if color is not None else 0x0000ff,
        timestamp=datetime.now(UTC).isoformat() if use_native_timestamps else None
    )

    current_time = datetime.now()
    status_time = format_discord_timestamp(current_time, "f") if use_native_timestamps else format_timestamp(current_time, format_type=TimeFormat.FRIENDLY)
    set_footer(embed, text=f"Status as of {status_time}")
    return embed


def create_interactive_embed(
    title: str,
    description: str,
    actions: List[Dict[str, str]],
    expires_in: Optional[int] = None,
    use_native_timestamps: bool = True
) -> Dict[str, Any]:
    """Create an interactive embed with action buttons."""
    embed = create_embed(
        title=title,
        description=description,
        color=0x0000ff,
        timestamp=datetime.now(UTC).isoformat() if use_native_timestamps else None
    )

    actions_text = "\n".join(
        f"• **{action['label']}**: {action.get('description', 'No description')}"
        for action in actions
    )
    add_field(
        embed,
        name="Available Actions",
        value=actions_text,
        inline=False
    )

    if expires_in:
        expiry_time = datetime.now(UTC) + timedelta(seconds=expires_in)
        add_field(
            embed,
            name="Expires",
            value=f"<t:{int(expiry_time.timestamp())}:R>",
            inline=False
        )

    footer = create_footer()
    set_footer(embed, text=footer["text"], icon_url=footer.get("icon_url"))
    validate_embed_lengths(embed)
    return embed


def create_debug_embed(
    message: str,
    context: Optional[Dict[str, Any]] = None,
    stack_trace: Optional[str] = None,
    use_native_timestamps: bool = True
) -> Dict[str, Any]:
    """Create a debug information embed."""
    embed = create_embed(
        title="Debug Information",
        description=message,
        color=0x808080,  # Using DEBUG instead of LIGHT_GREY
        timestamp=datetime.now(UTC).isoformat() if use_native_timestamps else None
    )

    if context:
        context_text = "\n".join(f"**{k}:** {v}" for k, v in context.items())
        add_field(
            embed,
            name="Context",
            value=context_text,
            inline=False
        )

    if stack_trace:
        # Truncate stack trace if too long
        if len(stack_trace) > 1000:
            stack_trace = stack_trace[:997] + "..."
        add_field(
            embed,
            name="Stack Trace",
            value=f"```\n{stack_trace}\n```",
            inline=False
        )

    footer = create_footer()
    if "text" in footer:
        set_footer(embed, text=footer["text"], icon_url=footer.get("icon_url"))
    validate_embed_lengths(embed)
    return embed


def create_batch_embed(
    operation: str,
    items: List[Dict[str, Any]],
    summary: Optional[str] = None
) -> Dict[str, Any]:
    """Create embed for batch operation updates."""
    # Create base embed
    embed: Dict[str, Any] = {
        "type": "rich",
        "title": f"Batch {operation}",
        "color": 0x0000ff,
        "fields": []
    }

    # Add summary if provided
    if summary:
        embed["description"] = summary

    # Add items as fields
    for item in items:
        field: EmbedField = {
            "name": item.get("name", "Item"),
            "value": "\n".join(f"{k}: {v}" for k, v in item.items() if k != "name"),
            "inline": False
        }
        add_field(embed, **field)

    # Add footer with version
    footer = create_footer()
    set_footer(embed, text=footer["text"], icon_url=footer.get("icon_url"))

    # Validate lengths
    validate_embed_lengths(embed)

    return embed


def _validate_basic_fields(embed: Dict[str, Any]) -> None:
    """Validate basic embed field lengths."""
    if "title" in embed and len(embed["title"]) > 256:
        raise ValueError("Embed title cannot exceed 256 characters")
    if "description" in embed and len(embed["description"]) > 4096:
        raise ValueError("Embed description cannot exceed 4096 characters")


def _validate_author_fields(embed: Dict[str, Any]) -> None:
    """Validate author field lengths."""
    if "author" in embed:
        if "name" in embed["author"] and len(embed["author"]["name"]) > 256:
            raise ValueError("Embed author name cannot exceed 256 characters")


def _validate_footer_fields(embed: Dict[str, Any]) -> None:
    """Validate footer field lengths."""
    if "footer" in embed:
        if "text" in embed["footer"] and len(embed["footer"]["text"]) > 2048:
            raise ValueError("Embed footer text cannot exceed 2048 characters")


def _validate_field_entries(embed: Dict[str, Any]) -> None:
    """Validate individual field entries."""
    if "fields" in embed:
        for field in embed["fields"]:
            if len(field["name"]) > 256:
                raise ValueError("Embed field name cannot exceed 256 characters")
            if len(field["value"]) > 1024:
                raise ValueError("Embed field value cannot exceed 1024 characters")


def validate_embed_lengths(embed: Dict[str, Any]) -> None:
    """Validate embed field lengths."""
    _validate_basic_fields(embed)
    _validate_author_fields(embed)
    _validate_footer_fields(embed)
    _validate_field_entries(embed)

    # Validate total length
    total_length = 0
    if "title" in embed:
        total_length += len(embed["title"])
    if "description" in embed:
        total_length += len(embed["description"])
    if "footer" in embed and "text" in embed["footer"]:
        total_length += len(embed["footer"]["text"])
    if "author" in embed and "name" in embed["author"]:
        total_length += len(embed["author"]["name"])
    if "fields" in embed:
        for field in embed["fields"]:
            total_length += len(field["name"]) + len(field["value"])

    if total_length > 6000:
        raise ValueError("Total embed length cannot exceed 6000 characters")


def validate_title(title: Optional[str]) -> int:
    """Validate embed title length.

    Checks if the embed title length is within Discord's limit of 256 characters.
    Returns the length of the title for cumulative length calculations.

    Args:
        title (Optional[str]): Title to validate

    Returns:
        int: Length of title (0 if None)

    Raises:
        ValueError: If title exceeds 256 characters

    Example:
        >>> try:
        ...     length = validate_title("My Title")
        ...     print(f"Title length: {length}")
        ... except ValueError as e:
        ...     print(f"Title too long: {e}")
    """
    if not title:
        return 0

    length = len(title)
    if length > 256:
        raise ValueError("Embed title cannot exceed 256 characters")
    return length


def validate_description(description: Optional[str]) -> int:
    """Validate embed description length.

    Checks if the embed description length is within Discord's limit of
    4096 characters. Returns the length for cumulative length calculations.

    Args:
        description (Optional[str]): Description to validate

    Returns:
        int: Length of description (0 if None)

    Raises:
        ValueError: If description exceeds 4096 characters

    Example:
        >>> try:
        ...     length = validate_description("Detailed status update...")
        ...     print(f"Description length: {length}")
        ... except ValueError as e:
        ...     print(f"Description too long: {e}")
    """
    if not description:
        return 0

    length = len(description)
    if length > 4096:
        raise ValueError("Embed description cannot exceed 4096 characters")
    return length


def validate_fields(fields: Optional[List[Dict[str, str]]]) -> int:
    """Validate embed fields.

    Checks if embed fields meet Discord's requirements:
    - Maximum 25 fields
    - Field name: max 256 characters
    - Field value: max 1024 characters
    - Total characters across all fields

    Args:
        fields (Optional[List[Dict[str, str]]]): List of fields to validate

    Returns:
        int: Total length of all fields (0 if None)

    Raises:
        ValueError: If fields exceed Discord's limits

    Example:
        >>> fields = [
        ...     {"name": "Status", "value": "Online", "inline": True},
        ...     {"name": "Users", "value": "150", "inline": True}
        ... ]
        >>> try:
        ...     total_length = validate_fields(fields)
        ...     print(f"Total fields length: {total_length}")
        ... except ValueError as e:
        ...     print(f"Fields validation failed: {e}")
    """
    if not fields:
        return 0

    total_length = 0
    if len(fields) > 25:
        raise ValueError("Too many embed fields")

    for field in fields:
        name_len = len(field["name"])
        value_len = len(field["value"])

        if name_len > 256:
            raise ValueError("Field name exceeds Discord limit")

        if value_len > 1024:
            raise ValueError("Field value exceeds Discord limit")

        total_length += name_len + value_len

    return total_length


def validate_footer(footer: Optional[Dict[str, str]]) -> int:
    """Validate embed footer.

    Checks if the embed footer text length is within Discord's limit of
    2048 characters. Returns the length of the footer text for cumulative
    length calculations.

    Args:
        footer (Optional[Dict[str, str]]): Footer to validate

    Returns:
        int: Length of footer text (0 if None)

    Raises:
        ValueError: If footer text exceeds 2048 characters

    Example:
        >>> try:
        ...     length = validate_footer({"text": "Footer text"})
        ...     print(f"Footer length: {length}")
        ... except ValueError as e:
        ...     print(f"Footer too long: {e}")
    """
    if not footer or "text" not in footer:
        return 0

    length = len(footer["text"])
    if length > 2048:
        raise ValueError("Footer text exceeds Discord limit")
    return length


def validate_author(author: Optional[Dict[str, str]]) -> int:
    """Validate embed author.

    Checks if the embed author name length is within Discord's limit of
    256 characters. Returns the length of the author name for cumulative
    length calculations.

    Args:
        author (Optional[Dict[str, str]]): Author to validate

    Returns:
        int: Length of author name (0 if None)

    Raises:
        ValueError: If author name exceeds 256 characters

    Example:
        >>> try:
        ...     length = validate_author({"name": "Author Name"})
        ...     print(f"Author length: {length}")
        ... except ValueError as e:
        ...     print(f"Author too long: {e}")
    """
    if not author or "name" not in author:
        return 0

    length = len(author["name"])
    if length > 256:
        raise ValueError("Author name exceeds Discord limit")
    return length


def validate_nesting_depth(data: Any, current_depth: int = 0, max_depth: int = 2) -> bool:
    """Validate nesting depth of data structure.

    Recursively checks the nesting depth of a data structure to ensure it
    doesn't exceed Discord's maximum allowed depth. This prevents errors
    when sending deeply nested objects via webhooks.

    Args:
        data (Any): Data structure to validate
        current_depth (int, optional): Current nesting level. Defaults to 0
        max_depth (int, optional): Maximum allowed nesting. Defaults to 2

    Returns:
        bool: True if nesting depth is valid

    Raises:
        ValueError: If nesting depth exceeds maximum allowed depth

    Example:
        >>> data = {
        ...     "level1": {
        ...         "level2": {
        ...             "level3": "value"
        ...         }
        ...     }
        ... }
        >>> try:
        ...     is_valid = validate_nesting_depth(data, max_depth=3)
        ...     print(f"Valid nesting: {is_valid}")
        ... except ValueError as e:
        ...     print(f"Invalid nesting: {e}")
    """
    if current_depth > max_depth:
        raise ValueError(f"Maximum nesting depth of {max_depth} exceeded")

    if isinstance(data, dict):
        for value in data.values():
            validate_nesting_depth(value, current_depth + 1, max_depth)
    elif isinstance(data, list):
        for item in data:
            validate_nesting_depth(item, current_depth + 1, max_depth)

    return True


def format_discord_timestamp(dt: datetime, style: str = "R") -> str:
    """Format timestamp using Discord's native format.

    Args:
        dt: Datetime to format
        style: Discord timestamp style (R=relative, t=short time, T=long time, d=short date, D=long date, f=short datetime, F=long datetime)
    """
    unix_timestamp = int(dt.timestamp())
    return f"<t:{unix_timestamp}:{style}>"


def _process_basic_embed_fields(embed: Dict[str, Any]) -> Dict[str, Any]:
    """Process basic embed fields."""
    result = {}
    for field in ["title", "description", "url", "timestamp", "color"]:
        if field in embed:
            result[field] = embed[field]
    return result

def _process_media_fields(embed: Dict[str, Any]) -> Dict[str, Any]:
    """Process media-related embed fields."""
    result = {}
    for field in ["image", "thumbnail", "video", "provider"]:
        if field in embed:
            result[field] = embed[field]
    return result

def _process_complex_fields(embed: Dict[str, Any]) -> Dict[str, Any]:
    """Process complex embed fields."""
    result = {}
    if "author" in embed:
        result["author"] = embed["author"]
    if "footer" in embed:
        result["footer"] = embed["footer"]
    if "fields" in embed:
        result["fields"] = embed["fields"]
    return result

def _create_embed_dict(embed: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Embed object to dictionary format."""
    result = {"type": "rich"}  # Only "rich" is supported for webhook embeds
    result.update(_process_basic_embed_fields(embed))
    result.update(_process_media_fields(embed))
    result.update(_process_complex_fields(embed))
    return result


def create_webhook_payload(
    embeds: List[Dict[str, Any]],
    username: str = "Mover Bot",
    avatar_url: Optional[str] = None,
    forum_config: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Create Discord webhook payload."""
    # Create base payload
    payload: Dict[str, Any] = {
        "username": username,
        "embeds": embeds
    }

    # Add optional fields
    if avatar_url:
        payload["avatar_url"] = avatar_url

    # Add forum config if provided
    if forum_config and "thread_title" in forum_config:
        thread_title = forum_config["thread_title"]
        if thread_title:
            payload["thread_name"] = thread_title

    # Validate payload
    if len(embeds) > 10:
        raise ValueError("Cannot have more than 10 embeds per message")

    # Validate each embed
    for embed in embeds:
        validate_embed_lengths(embed)
    return payload


def _copy_basic_fields(embed: Dict[str, Any], new_embed: Dict[str, Any]) -> None:
    """Copy basic embed fields."""
    for field in ["title", "description", "url", "timestamp", "color"]:
        if field in embed:
            new_embed[field] = embed[field]

def _copy_media_fields(embed: Dict[str, Any], new_embed: Dict[str, Any]) -> None:
    """Copy media-related embed fields."""
    for field in ["image", "thumbnail", "video", "provider"]:
        if field in embed:
            new_embed[field] = dict(embed[field])

def _copy_author(embed: Dict[str, Any], new_embed: Dict[str, Any]) -> None:
    """Copy author field."""
    if "author" in embed:
        new_embed["author"] = dict(embed["author"])

def _copy_footer(embed: Dict[str, Any], new_embed: Dict[str, Any]) -> None:
    """Copy footer field."""
    if "footer" in embed:
        new_embed["footer"] = dict(embed["footer"])

def _copy_fields(embed: Dict[str, Any], new_embed: Dict[str, Any]) -> None:
    """Copy fields array."""
    if "fields" in embed:
        new_embed["fields"] = [dict(field) for field in embed["fields"]]

def copy_embed(embed: Dict[str, Any]) -> Dict[str, Any]:
    """Create a deep copy of an embed."""
    new_embed: Dict[str, Any] = {}

    _copy_basic_fields(embed, new_embed)
    _copy_media_fields(embed, new_embed)
    _copy_author(embed, new_embed)
    _copy_footer(embed, new_embed)
    _copy_fields(embed, new_embed)

    return new_embed
