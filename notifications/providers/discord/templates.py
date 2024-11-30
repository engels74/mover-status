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

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from config.constants import ErrorMessages, JsonDict, JsonValue
from shared.providers.discord import (
    ApiLimits,
    DiscordColor,
    DiscordWebhookError,
    Embed,
    EmbedAuthor,
    EmbedField,
    EmbedFooter,
    ForumConfig,
    WebhookPayload,
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


def create_footer(version_info: Optional[str] = None) -> EmbedFooter:
    """Create embed footer with version information.

    Creates a standardized footer containing the application version and
    optional additional version information.

    Args:
        version_info (Optional[str]): Additional version details to include

    Returns:
        EmbedFooter: Dictionary containing footer text, truncated if needed

    Example:
        >>> footer = create_footer("beta")
        >>> footer["text"]
        'Mover Status v1.2.3 (beta)'
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


def create_progress_embed(
    percent: float,
    remaining: str,
    elapsed: str,
    etc: str,
    title: str = "Mover Status",
    description: Optional[str] = None,
    author: Optional[EmbedAuthor] = None,
    use_native_timestamps: bool = True,
    color: Optional[int] = None,
    color_enabled: bool = True
) -> Embed:
    """Create a complete progress update embed.

    Generates a rich embed for progress updates, including a visual progress bar,
    timing information, and optional metadata. The embed automatically handles
    Discord's length limits and supports native timestamps.

    Args:
        percent (float): Progress percentage (0-100)
        remaining (str): Remaining data/time amount (e.g., "1.2 GB")
        elapsed (str): Elapsed time (e.g., "2 hours")
        etc (str): Estimated time of completion (e.g., "15:30")
        title (str, optional): Embed title. Defaults to "Mover Status"
        description (Optional[str], optional): Additional context. Defaults to None
        author (Optional[EmbedAuthor], optional): Author information. Defaults to None
        use_native_timestamps (bool, optional): Use Discord timestamps. Defaults to True
        color (Optional[int], optional): Override embed color. Defaults to None
        color_enabled (bool, optional): Enable color support. Defaults to True

    Returns:
        Embed: Formatted Discord embed with progress information

    Raises:
        ValueError: If percent is not between 0 and 100
        ValueError: If any component exceeds Discord's length limits

    Example:
        >>> # Create a basic progress embed
        >>> embed = create_progress_embed(
        ...     percent=50.0,
        ...     remaining="500MB",
        ...     elapsed="1h 30m",
        ...     etc="16:45",
        ...     description="Transferring files..."
        ... )
        >>>
        >>> # Create a customized progress embed
        >>> embed = create_progress_embed(
        ...     percent=75.5,
        ...     remaining="1.2 GB",
        ...     elapsed="2h 15m",
        ...     etc="18:30",
        ...     title="File Transfer",
        ...     description="Uploading backup files",
        ...     author={"name": "Backup Service"},
        ...     color=0x00ff00
        ... )
    """
    if not 0 <= percent <= 100:
        raise ValueError("Percent must be between 0 and 100")

    # Create progress field
    progress_field = create_progress_field(
        percent=percent,
        remaining=remaining,
        elapsed=elapsed,
        etc=etc
    )

    # Build embed
    embed: Embed = {
        "title": truncate_string(title, ApiLimits.TITLE_LENGTH),
        "fields": [progress_field],
        "footer": create_footer(),
        "timestamp": datetime.utcnow().isoformat() if use_native_timestamps else None,
    }

    # Set color if enabled
    if color_enabled:
        embed["color"] = color if color is not None else get_progress_color(percent)

    # Add optional components
    if description:
        embed["description"] = truncate_string(description, ApiLimits.DESCRIPTION_LENGTH)
    if author:
        embed["author"] = author

    validate_embed_lengths(embed)
    return embed


def create_completion_embed(
    description: Optional[str] = None,
    stats: Optional[Dict[str, Union[str, int, float]]] = None,
    use_native_timestamps: bool = True,
    color: Optional[int] = None,
    color_enabled: bool = True
) -> Embed:
    """Create embed for transfer completion notification.

    Generates a rich embed for completion notifications, optionally including
    statistics and metrics about the completed operation. Supports both
    simple completion messages and detailed statistical summaries.

    Args:
        description (Optional[str], optional): Completion message. Defaults to None
        stats (Optional[Dict[str, Union[str, int, float]]], optional): Operation
            statistics to display (e.g., {"files": 100, "size": "1.5 GB"}).
            Defaults to None
        use_native_timestamps (bool, optional): Use Discord timestamps. Defaults to True
        color (Optional[int], optional): Override embed color. Defaults to None
        color_enabled (bool, optional): Enable color support. Defaults to True

    Returns:
        Embed: Formatted Discord embed for completion notification

    Example:
        >>> # Simple completion notification
        >>> embed = create_completion_embed(
        ...     description="Backup completed successfully!"
        ... )
        >>>
        >>> # Detailed completion with statistics
        >>> embed = create_completion_embed(
        ...     description="File transfer completed",
        ...     stats={
        ...         "files": 150,
        ...         "size": "2.5 GB",
        ...         "duration": "3h 45m",
        ...         "speed": "10 MB/s"
        ...     }
        ... )
    """
    # Build base embed
    embed: Embed = {
        "title": "Transfer Complete",
        "footer": create_footer(),
        "timestamp": datetime.utcnow().isoformat() if use_native_timestamps else None,
    }

    # Set color if enabled
    if color_enabled:
        embed["color"] = color if color is not None else DiscordColor.SUCCESS

    # Add description if provided
    if description:
        embed["description"] = truncate_string(description, ApiLimits.DESCRIPTION_LENGTH)

    # Add stats as fields if provided
    if stats:
        embed["fields"] = []
        for name, value in stats.items():
            embed["fields"].append({
                "name": truncate_string(str(name), ApiLimits.FIELD_NAME_LENGTH),
                "value": truncate_string(str(value), ApiLimits.FIELD_VALUE_LENGTH),
                "inline": True
            })

    validate_embed_lengths(embed)
    return embed


def create_error_embed(
    error_message: str,
    error_code: Optional[int] = None,
    error_details: Optional[Dict[str, str]] = None,
    use_native_timestamps: bool = True,
    color: Optional[int] = None,
    color_enabled: bool = True
) -> Embed:
    """Create embed for error notification.

    Generates a rich embed for error notifications with support for error codes,
    detailed error information, and optional stack traces. The embed is formatted
    to highlight the error and provide relevant debugging information.

    Args:
        error_message (str): Main error description
        error_code (Optional[int], optional): Error code for reference. Defaults to None
        error_details (Optional[Dict[str, str]], optional): Additional error context
            (e.g., {"file": "data.txt", "reason": "permission denied"}).
            Defaults to None
        use_native_timestamps (bool, optional): Use Discord timestamps. Defaults to True
        color (Optional[int], optional): Override error color. Defaults to None
        color_enabled (bool, optional): Enable color support. Defaults to True

    Returns:
        Embed: Formatted Discord embed for error notification

    Raises:
        ValueError: If error_message is empty or exceeds Discord limits

    Example:
        >>> # Basic error notification
        >>> embed = create_error_embed(
        ...     error_message="Failed to connect to server"
        ... )
        >>>
        >>> # Detailed error with context
        >>> embed = create_error_embed(
        ...     error_message="Database connection failed",
        ...     error_code=500,
        ...     error_details={
        ...         "host": "db.example.com",
        ...         "port": "5432",
        ...         "reason": "Connection timeout"
        ...     }
        ... )
    """
    if not error_message:
        raise ValueError("Error message cannot be empty")

    # Build base embed
    embed: Embed = {
        "title": "Error",
        "description": truncate_string(error_message, ApiLimits.DESCRIPTION_LENGTH),
        "footer": create_footer(),
        "timestamp": datetime.utcnow().isoformat() if use_native_timestamps else None,
    }

    # Set color if enabled
    if color_enabled:
        embed["color"] = color if color is not None else DiscordColor.ERROR

    # Add error code if provided
    if error_code is not None:
        embed["fields"] = [{
            "name": "Error Code",
            "value": str(error_code),
            "inline": True
        }]

    # Add error details if provided
    if error_details:
        if "fields" not in embed:
            embed["fields"] = []
        for name, value in error_details.items():
            embed["fields"].append({
                "name": truncate_string(str(name), ApiLimits.FIELD_NAME_LENGTH),
                "value": truncate_string(str(value), ApiLimits.FIELD_VALUE_LENGTH),
                "inline": True
            })

    validate_embed_lengths(embed)
    return embed


def create_warning_embed(
    warning_message: str,
    warning_details: Optional[Dict[str, str]] = None,
    suggestion: Optional[str] = None,
    use_native_timestamps: bool = True
) -> Embed:
    """Create embed for warning notification.

    Generates a rich embed for warning notifications with optional context details
    and suggestions for resolution. The embed is formatted to be noticeable but
    less severe than error notifications.

    Args:
        warning_message (str): Main warning description
        warning_details (Optional[Dict[str, str]], optional): Additional warning
            context (e.g., {"component": "cache", "status": "degraded"}).
            Defaults to None
        suggestion (Optional[str], optional): Suggested action or resolution.
            Defaults to None
        use_native_timestamps (bool, optional): Use Discord timestamps. Defaults to True

    Returns:
        Embed: Formatted Discord embed for warning notification

    Raises:
        ValueError: If warning_message is empty or exceeds Discord limits

    Example:
        >>> # Basic warning notification
        >>> embed = create_warning_embed(
        ...     warning_message="Low disk space detected"
        ... )
        >>>
        >>> # Warning with details and suggestion
        >>> embed = create_warning_embed(
        ...     warning_message="Performance degradation detected",
        ...     warning_details={
        ...         "component": "file system",
        ...         "usage": "95%",
        ...         "threshold": "90%"
        ...     },
        ...     suggestion="Consider cleaning up old log files"
        ... )
    """
    if not warning_message:
        raise ValueError("Warning message cannot be empty")

    embed = Embed(
        title="Warning",
        description=warning_message,
        color=DiscordColor.WARNING
    )

    if warning_details:
        formatted_details = []
        for key, value in warning_details.items():
            if isinstance(value, datetime):
                if use_native_timestamps:
                    value = format_discord_timestamp(value, "f")
                else:
                    value = format_timestamp(value, format_type=TimeFormat.FRIENDLY)
            formatted_details.append(f"**{key}:** {value}")

        if formatted_details:
            embed.add_field(
                name="Warning Details",
                value="\n".join(formatted_details),
                inline=False
            )

    if suggestion:
        embed.add_field(
            name="Suggestion",
            value=suggestion,
            inline=False
        )

    current_time = datetime.now()
    warning_time = format_discord_timestamp(current_time, "f") if use_native_timestamps else format_timestamp(current_time, format_type=TimeFormat.FRIENDLY)
    embed.set_footer(text=f"Warning issued at {warning_time}")
    return embed


def create_system_embed(
    status: str,
    metrics: Optional[Dict[str, Union[str, int, float]]] = None,
    issues: Optional[List[str]] = None,
    use_native_timestamps: bool = True
) -> Embed:
    """Create embed for system status update.

    Generates a rich embed for system status notifications, including optional
    performance metrics and current issues. Useful for system health monitoring
    and periodic status reports.

    Args:
        status (str): Current system status description
        metrics (Optional[Dict[str, Union[str, int, float]]], optional): System
            performance metrics (e.g., {"cpu": "45%", "memory": "2.1 GB"}).
            Defaults to None
        issues (Optional[List[str]], optional): List of current system issues
            or warnings. Defaults to None
        use_native_timestamps (bool, optional): Use Discord timestamps. Defaults to True

    Returns:
        Embed: Formatted Discord embed for system status

    Example:
        >>> # Basic system status
        >>> embed = create_system_embed(
        ...     status="System running normally"
        ... )
        >>>
        >>> # Detailed system status with metrics
        >>> embed = create_system_embed(
        ...     status="System operating at high load",
        ...     metrics={
        ...         "cpu_usage": "85%",
        ...         "memory_used": "7.5 GB",
        ...         "disk_space": "120 GB free",
        ...         "active_users": 150
        ...     },
        ...     issues=[
        ...         "High CPU utilization",
        ...         "Database connections near limit"
        ...     ]
        ... )
    """
    embed = Embed(
        title="System Status",
        description=status,
        color=DiscordColor.INFO
    )

    if metrics:
        formatted_metrics = []
        for key, value in metrics.items():
            if isinstance(value, datetime):
                if use_native_timestamps:
                    value = format_discord_timestamp(value, "f")
                else:
                    value = format_timestamp(value, format_type=TimeFormat.FRIENDLY)
            elif isinstance(value, (int, float)) and "time" in key.lower():
                # Convert numeric time values (assumed to be timestamps)
                dt = datetime.fromtimestamp(float(value))
                if use_native_timestamps:
                    value = format_discord_timestamp(dt, "R")
                else:
                    value = format_timestamp(dt, format_type=TimeFormat.RELATIVE)
            formatted_metrics.append(f"**{key}:** {value}")

        if formatted_metrics:
            embed.add_field(
                name="System Metrics",
                value="\n".join(formatted_metrics),
                inline=False
            )

    if issues:
        embed.add_field(
            name="Current Issues",
            value="\n".join(f"• {issue}" for issue in issues),
            inline=False
        )

    current_time = datetime.now()
    status_time = format_discord_timestamp(current_time, "f") if use_native_timestamps else format_timestamp(current_time, format_type=TimeFormat.FRIENDLY)
    embed.set_footer(text=f"Status as of {status_time}")
    return embed


def create_batch_embed(
    operation: str,
    items: List[Dict[str, Any]],
    summary: Optional[str] = None
) -> Embed:
    """Create embed for batch operation updates.

    Generates a rich embed for batch operation notifications, showing the
    operation type and affected items. Useful for reporting bulk actions
    like file processing or data migrations.

    Args:
        operation (str): Type of batch operation being performed
        items (List[Dict[str, Any]]): List of items being processed, each item
            should be a dictionary with relevant details
        summary (Optional[str], optional): Optional operation summary or
            additional context. Defaults to None

    Returns:
        Embed: Formatted Discord embed for batch operation

    Example:
        >>> # Basic batch operation
        >>> embed = create_batch_embed(
        ...     operation="File Processing",
        ...     items=[
        ...         {"name": "data.csv", "size": "1.2 MB"},
        ...         {"name": "config.json", "size": "4 KB"}
        ...     ]
        ... )
        >>>
        >>> # Detailed batch operation
        >>> embed = create_batch_embed(
        ...     operation="Database Migration",
        ...     items=[
        ...         {
        ...             "table": "users",
        ...             "records": 1000,
        ...             "status": "completed"
        ...         },
        ...         {
        ...             "table": "orders",
        ...             "records": 5000,
        ...             "status": "in_progress"
        ...         }
        ...     ],
        ...     summary="Migrating to new schema v2.0"
        ... )
    """
    embed = Embed(
        title=f"Batch {operation}",
        description=summary or f"Processing {len(items)} items",
        color=DiscordColor.INFO,
        timestamp=datetime.utcnow().isoformat()
    )

    # Add items summary
    items_text = "\n".join(
        f"• {item.get('name', 'Unknown')}: {item.get('status', 'Pending')}"
        for item in items[:10]  # Limit to first 10 items
    )
    if len(items) > 10:
        items_text += f"\n... and {len(items) - 10} more items"

    embed.fields.append(
        EmbedField(name="Items", value=items_text, inline=False)
    )

    embed.footer = create_footer()
    validate_embed_lengths(embed)
    return embed


def create_interactive_embed(
    title: str,
    description: str,
    actions: List[Dict[str, str]],
    expires_in: Optional[int] = None
) -> Embed:
    """Create embed for interactive messages.

    Generates a rich embed for interactive messages that require user input
    or response. Supports action buttons/links and optional expiration time
    for time-sensitive interactions.

    Args:
        title (str): Message title
        description (str): Message description or instructions
        actions (List[Dict[str, str]]): List of available actions, each action
            should be a dictionary with 'label' and 'value' keys
        expires_in (Optional[int], optional): Time in seconds until the
            interaction expires. Defaults to None

    Returns:
        Embed: Formatted Discord embed for interactive message

    Example:
        >>> # Basic interactive message
        >>> embed = create_interactive_embed(
        ...     title="Confirm Action",
        ...     description="Do you want to proceed with the backup?",
        ...     actions=[
        ...         {"label": "Yes", "value": "confirm"},
        ...         {"label": "No", "value": "cancel"}
        ...     ]
        ... )
        >>>
        >>> # Interactive message with expiration
        >>> embed = create_interactive_embed(
        ...     title="Update Available",
        ...     description="A new version is available. Update now?",
        ...     actions=[
        ...         {"label": "Update Now", "value": "update"},
        ...         {"label": "Remind Later", "value": "remind"},
        ...         {"label": "Skip", "value": "skip"}
        ...     ],
        ...     expires_in=3600  # Expires in 1 hour
        ... )
    """
    embed = Embed(
        title=title,
        description=description,
        color=DiscordColor.BLURPLE,
        timestamp=datetime.utcnow().isoformat()
    )

    # Add available actions
    actions_text = "\n".join(
        f"• **{action['label']}**: {action.get('description', 'No description')}"
        for action in actions
    )
    embed.fields.append(
        EmbedField(name="Available Actions", value=actions_text, inline=False)
    )

    if expires_in:
        expiry_time = datetime.utcnow() + timedelta(seconds=expires_in)
        embed.fields.append(
            EmbedField(
                name="Expires",
                value=f"<t:{int(expiry_time.timestamp())}:R>",
                inline=False
            )
        )

    embed.footer = create_footer()
    validate_embed_lengths(embed)
    return embed


def create_debug_embed(
    message: str,
    context: Optional[Dict[str, Any]] = None,
    stack_trace: Optional[str] = None
) -> Embed:
    """Create embed for debug messages.

    Generates a rich embed for debug messages with detailed context and
    optional stack traces. Useful for development and troubleshooting
    with comprehensive debugging information.

    Args:
        message (str): Main debug message
        context (Optional[Dict[str, Any]], optional): Additional debug context
            like variables, states, or environment info. Defaults to None
        stack_trace (Optional[str], optional): Formatted stack trace if
            available. Defaults to None

    Returns:
        Embed: Formatted Discord embed for debug information

    Example:
        >>> # Basic debug message
        >>> embed = create_debug_embed(
        ...     message="Cache miss in user service"
        ... )
        >>>
        >>> # Detailed debug with context and stack trace
        >>> embed = create_debug_embed(
        ...     message="Unexpected data format in API response",
        ...     context={
        ...         "endpoint": "/api/users",
        ...         "method": "GET",
        ...         "status_code": 200,
        ...         "response_type": "application/xml",
        ...         "expected_type": "application/json"
        ...     },
        ...     stack_trace="Traceback (most recent call last):..."
        ... )
    """
    embed = Embed(
        title="Debug Information",
        description=message,
        color=DiscordColor.GREYPLE,
        timestamp=datetime.utcnow().isoformat()
    )

    if context:
        context_text = "\n".join(f"**{k}:** {v}" for k, v in context.items())
        embed.fields.append(
            EmbedField(name="Context", value=context_text, inline=False)
        )

    if stack_trace:
        # Truncate stack trace if too long
        if len(stack_trace) > 1000:
            stack_trace = stack_trace[:997] + "..."
        embed.fields.append(
            EmbedField(name="Stack Trace", value=f"```\n{stack_trace}\n```", inline=False)
        )

    embed.footer = create_footer()
    validate_embed_lengths(embed)
    return embed


def validate_embed_lengths(embed: Embed) -> None:
    """Validate embed field lengths against Discord limits.

    Checks all components of a Discord embed against Discord's API limits
    to ensure the message can be sent successfully. This includes title,
    description, fields, footer, and author components.

    Args:
        embed (Embed): Discord embed to validate

    Raises:
        DiscordWebhookError: If any component exceeds Discord limits:
            - Title: 256 characters
            - Description: 4096 characters
            - Fields: 25 fields
            - Field name: 256 characters
            - Field value: 1024 characters
            - Footer text: 2048 characters
            - Author name: 256 characters

    Example:
        >>> embed = create_progress_embed(...)
        >>> try:
        ...     validate_embed_lengths(embed)
        ... except DiscordWebhookError as e:
        ...     print(f"Validation failed: {e}")
    """
    try:
        total_length = 0
        total_length += validate_title(embed.get("title"))
        total_length += validate_description(embed.get("description"))
        total_length += validate_fields(embed.get("fields"))
        total_length += validate_footer(embed.get("footer"))
        total_length += validate_author(embed.get("author"))

        if total_length > ApiLimits.TOTAL_LENGTH:
            raise DiscordWebhookError(
                "Total embed length exceeds Discord limit",
                context={
                    "total_length": total_length,
                    "max_length": ApiLimits.TOTAL_LENGTH
                }
            )

    except ValueError as err:
        raise DiscordWebhookError(str(err), context={"embed": embed}) from err


def validate_title(title: Optional[str]) -> int:
    """Validate embed title length.

    Checks if the embed title length is within Discord's limit of 256 characters.
    Returns the length of the title for cumulative length calculations.

    Args:
        title (Optional[str]): Title to validate

    Returns:
        int: Length of title (0 if None)

    Raises:
        DiscordWebhookError: If title exceeds 256 characters

    Example:
        >>> try:
        ...     length = validate_title("My Title")
        ...     print(f"Title length: {length}")
        ... except DiscordWebhookError as e:
        ...     print(f"Title too long: {e}")
    """
    if not title:
        return 0

    length = len(title)
    if length > ApiLimits.TITLE_LENGTH:
        raise DiscordWebhookError(
            "Embed title exceeds Discord limit",
            context={
                "title_length": length,
                "max_length": ApiLimits.TITLE_LENGTH
            }
        )
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
        DiscordWebhookError: If description exceeds 4096 characters

    Example:
        >>> try:
        ...     length = validate_description("Detailed status update...")
        ...     print(f"Description length: {length}")
        ... except DiscordWebhookError as e:
        ...     print(f"Description too long: {e}")
    """
    if not description:
        return 0

    length = len(description)
    if length > ApiLimits.DESCRIPTION_LENGTH:
        raise DiscordWebhookError(
            "Embed description exceeds Discord limit",
            context={
                "description_length": length,
                "max_length": ApiLimits.DESCRIPTION_LENGTH
            }
        )
    return length


def validate_fields(fields: Optional[List[EmbedField]]) -> int:
    """Validate embed fields.

    Checks if embed fields meet Discord's requirements:
    - Maximum 25 fields
    - Field name: max 256 characters
    - Field value: max 1024 characters
    - Total characters across all fields

    Args:
        fields (Optional[List[EmbedField]]): List of fields to validate

    Returns:
        int: Total length of all fields (0 if None)

    Raises:
        DiscordWebhookError: If fields exceed Discord's limits

    Example:
        >>> fields = [
        ...     {"name": "Status", "value": "Online", "inline": True},
        ...     {"name": "Users", "value": "150", "inline": True}
        ... ]
        >>> try:
        ...     total_length = validate_fields(fields)
        ...     print(f"Total fields length: {total_length}")
        ... except DiscordWebhookError as e:
        ...     print(f"Fields validation failed: {e}")
    """
    if not fields:
        return 0

    total_length = 0
    if len(fields) > ApiLimits.FIELDS_COUNT:
        raise DiscordWebhookError(
            "Too many embed fields",
            context={
                "field_count": len(fields),
                "max_fields": ApiLimits.FIELDS_COUNT
            }
        )

    for i, field in enumerate(fields):
        name_len = len(field["name"])
        value_len = len(field["value"])

        if name_len > ApiLimits.FIELD_NAME_LENGTH:
            raise DiscordWebhookError(
                "Field name exceeds Discord limit",
                context={
                    "field_index": i,
                    "name_length": name_len,
                    "max_length": ApiLimits.FIELD_NAME_LENGTH
                }
            )

        if value_len > ApiLimits.FIELD_VALUE_LENGTH:
            raise DiscordWebhookError(
                "Field value exceeds Discord limit",
                context={
                    "field_index": i,
                    "value_length": value_len,
                    "max_length": ApiLimits.FIELD_VALUE_LENGTH
                }
            )

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
        DiscordWebhookError: If footer text exceeds 2048 characters

    Example:
        >>> try:
        ...     length = validate_footer({"text": "Footer text"})
        ...     print(f"Footer length: {length}")
        ... except DiscordWebhookError as e:
        ...     print(f"Footer too long: {e}")
    """
    if not footer or "text" not in footer:
        return 0

    length = len(footer["text"])
    if length > ApiLimits.FOOTER_LENGTH:
        raise DiscordWebhookError(
            "Footer text exceeds Discord limit",
            context={
                "footer_length": length,
                "max_length": ApiLimits.FOOTER_LENGTH
            }
        )
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
        DiscordWebhookError: If author name exceeds 256 characters

    Example:
        >>> try:
        ...     length = validate_author({"name": "Author Name"})
        ...     print(f"Author length: {length}")
        ... except DiscordWebhookError as e:
        ...     print(f"Author too long: {e}")
    """
    if not author or "name" not in author:
        return 0

    length = len(author["name"])
    if length > ApiLimits.AUTHOR_NAME_LENGTH:
        raise DiscordWebhookError(
            "Author name exceeds Discord limit",
            context={
                "author_length": length,
                "max_length": ApiLimits.AUTHOR_NAME_LENGTH
            }
        )
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


def create_webhook_payload(
    embeds: List[Embed],
    username: str = "Mover Bot",
    avatar_url: Optional[str] = None,
    forum_config: Optional[ForumConfig] = None,
    require_embeds: bool = True
) -> WebhookPayload:
    """Create complete webhook payload with optional forum support.

    Assembles a complete Discord webhook payload with embeds, username,
    avatar, and optional forum thread configuration. Validates all
    components against Discord's API limits.

    Args:
        embeds (List[Embed]): List of embeds to include
        username (str, optional): Bot username to display. Defaults to "Mover Bot"
        avatar_url (Optional[str], optional): URL for bot avatar. Defaults to None
        forum_config (Optional[ForumConfig], optional): Forum thread configuration.
            Defaults to None
        require_embeds (bool, optional): If True, at least one embed is required.
            Defaults to True

    Returns:
        WebhookPayload: Complete webhook payload ready for sending

    Raises:
        ValueError: If payload exceeds Discord limits or nesting depth
        ValueError: If embeds are required but not provided

    Example:
        >>> # Basic webhook payload
        >>> embeds = [create_progress_embed(...)]
        >>> payload = create_webhook_payload(
        ...     embeds=embeds,
        ...     username="Status Bot"
        ... )
        >>>
        >>> # Forum thread payload
        >>> forum_config = {
        ...     "name": "Status Updates",
        ...     "message": "New status thread"
        ... }
        >>> payload = create_webhook_payload(
        ...     embeds=embeds,
        ...     username="Forum Bot",
        ...     forum_config=forum_config
        ... )
    """
    # Validate username length
    if len(username) > ApiLimits.USERNAME_LENGTH:
        raise ValueError(ErrorMessages.FIELD_TOO_LONG.format(
            field="username",
            max_length=ApiLimits.USERNAME_LENGTH
        ))

    # Validate embeds
    if not embeds and require_embeds:
        raise ValueError("At least one embed is required when require_embeds is True")

    # Create base payload
    payload: JsonDict = {"username": username, "embeds": []}

    # Add optional fields
    if avatar_url:
        payload["avatar_url"] = avatar_url

    # Convert and validate embeds
    payload["embeds"] = []
    for embed in embeds:
        # Validate embed before adding
        validate_embed_lengths(embed)
        embed_dict = _create_embed_dict(embed)
        # Validate nesting depth of embed
        validate_nesting_depth(embed_dict)
        payload["embeds"].append(embed_dict)

    # Add forum configuration if provided
    if forum_config:
        if not isinstance(forum_config, dict):
            raise ValueError("Forum configuration must be a dictionary")
        validate_nesting_depth(forum_config)
        payload["thread_name"] = forum_config.get("thread_name")

    # Validate final payload nesting depth
    validate_nesting_depth(payload)

    return payload


def _create_embed_dict(embed: Embed) -> JsonDict:
    """Convert Embed object to JsonDict format.

    Args:
        embed (Embed): Discord embed to convert

    Returns:
        JsonDict: Formatted embed dictionary
    """
    embed_dict: JsonDict = {}

    # Add basic fields
    if embed.title:
        embed_dict["title"] = embed.title
    if embed.description:
        embed_dict["description"] = embed.description
    if embed.color:
        embed_dict["color"] = embed.color

    # Add nested structures
    if embed.author:
        author_dict: Dict[str, JsonValue] = {"name": embed.author.name}
        if embed.author.url:
            author_dict["url"] = embed.author.url
        if embed.author.icon_url:
            author_dict["icon_url"] = embed.author.icon_url
        embed_dict["author"] = author_dict

    if embed.footer:
        footer_dict: Dict[str, JsonValue] = {"text": embed.footer.text}
        if embed.footer.icon_url:
            footer_dict["icon_url"] = embed.footer.icon_url
        embed_dict["footer"] = footer_dict

    if embed.fields:
        embed_dict["fields"] = [
            {
                "name": field.name,
                "value": field.value,
                **({"inline": field.inline} if field.inline is not None else {})
            }
            for field in embed.fields
        ]

    return embed_dict


def format_discord_timestamp(dt: datetime, style: str = "R") -> str:
    """Format timestamp using Discord's native format.

    Formats a datetime object using Discord's timestamp syntax for automatic
    localization and formatting in messages. Supports various display styles.

    Args:
        dt (datetime): Datetime to format
        style (str, optional): Discord timestamp style:
            - t: Short time (e.g., "16:20")
            - T: Long time (e.g., "16:20:30")
            - d: Short date (e.g., "20/04/2023")
            - D: Long date (e.g., "20 April 2023")
            - f: Short date/time (e.g., "20 April 2023 16:20")
            - F: Long date/time (e.g., "Wednesday, 20 April 2023 16:20")
            - R: Relative time (e.g., "2 hours ago")
            Defaults to "R"

    Returns:
        str: Discord formatted timestamp

    Example:
        >>> now = datetime.now()
        >>> # Relative time
        >>> ts = format_discord_timestamp(now)  # "<t:1234567890:R>"
        >>>
        >>> # Full date and time
        >>> ts = format_discord_timestamp(now, "F")  # "<t:1234567890:F>"
    """
    unix_timestamp = int(dt.timestamp())
    return f"<t:{unix_timestamp}:{style}>"
