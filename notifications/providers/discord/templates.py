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
    ProgressStyle,
    TimeFormat,
    format_progress,
    format_timestamp,
)
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
    use_native_timestamps: bool = True
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
        use_native_timestamps: Whether to use Discord's native timestamps

    Returns:
        Embed: Formatted Discord embed

    Raises:
        ValueError: If percent is out of range or field lengths exceed limits
    """
    if not 0 <= percent <= 100:
        raise ValueError("Percent must be between 0 and 100")

    # Format progress bar
    progress_bar = format_progress(percent, style=ProgressStyle.BLOCKS, width=20)

    # Format timestamps based on preference
    elapsed_dt = datetime.now() - timedelta(seconds=float(elapsed))
    completion_time = datetime.strptime(etc, "%H:%M")

    if use_native_timestamps:
        elapsed_time = format_discord_timestamp(elapsed_dt, "R")
        etc_formatted = format_discord_timestamp(completion_time, "t")
    else:
        elapsed_time = format_timestamp(elapsed_dt, format_type=TimeFormat.RELATIVE)
        etc_formatted = format_timestamp(completion_time, format_type=TimeFormat.FRIENDLY)

    embed = Embed(
        title=title,
        description=description or "",
        color=get_progress_color(percent)
    )

    if author:
        embed.set_author(**author)

    embed.add_field(
        name="Progress",
        value=f"{progress_bar} **{percent:.1f}%**",
        inline=False
    )

    embed.add_field(
        name="Time Info",
        value=(
            f"⏱️ Elapsed: {elapsed_time}\n"
            f"⌛ Remaining: {remaining}\n"
            f"🏁 ETC: {etc_formatted}"
        ),
        inline=False
    )

    embed.set_footer(text=f"Last updated: {format_discord_timestamp(datetime.now(), 'R')}")
    return embed


def create_completion_embed(
    description: Optional[str] = None,
    stats: Optional[Dict[str, Union[str, int, float]]] = None,
    use_native_timestamps: bool = True
) -> Embed:
    """Create embed for transfer completion notification.

    Args:
        description: Optional custom description
        stats: Optional transfer statistics to include
        use_native_timestamps: Whether to use Discord's native timestamps

    Returns:
        Embed: Formatted completion embed
    """
    embed = Embed(
        title="Transfer Complete",
        description=description or "The transfer has been completed successfully.",
        color=DiscordColor.SUCCESS
    )

    if stats:
        formatted_stats = []
        for key, value in stats.items():
            if isinstance(value, datetime):
                if use_native_timestamps:
                    value = format_discord_timestamp(value, "f")
                else:
                    value = format_timestamp(value, format_type=TimeFormat.FRIENDLY)
            formatted_stats.append(f"**{key}:** {value}")

        if formatted_stats:
            embed.add_field(
                name="Transfer Statistics",
                value="\n".join(formatted_stats),
                inline=False
            )

    current_time = datetime.now()
    completion_text = format_discord_timestamp(current_time, "f") if use_native_timestamps else format_timestamp(current_time, format_type=TimeFormat.FRIENDLY)
    embed.set_footer(text=f"Completed at {completion_text}")
    return embed


def create_error_embed(
    error_message: str,
    error_code: Optional[int] = None,
    error_details: Optional[Dict[str, str]] = None,
    use_native_timestamps: bool = True
) -> Embed:
    """Create embed for error notification.

    Args:
        error_message: Error description
        error_code: Optional error code
        error_details: Optional error details
        use_native_timestamps: Whether to use Discord's native timestamps

    Returns:
        Embed: Formatted error embed

    Raises:
        ValueError: If error_message is empty
    """
    if not error_message:
        raise ValueError("Error message cannot be empty")

    embed = Embed(
        title="Error",
        description=error_message,
        color=DiscordColor.ERROR
    )

    if error_code:
        embed.add_field(
            name="Error Code",
            value=str(error_code),
            inline=True
        )

    if error_details:
        formatted_details = []
        for key, value in error_details.items():
            if isinstance(value, datetime):
                if use_native_timestamps:
                    value = format_discord_timestamp(value, "f")
                else:
                    value = format_timestamp(value, format_type=TimeFormat.FRIENDLY)
            formatted_details.append(f"**{key}:** {value}")

        if formatted_details:
            embed.add_field(
                name="Error Details",
                value="\n".join(formatted_details),
                inline=False
            )

    current_time = datetime.now()
    error_time = format_discord_timestamp(current_time, "f") if use_native_timestamps else format_timestamp(current_time, format_type=TimeFormat.FRIENDLY)
    embed.set_footer(text=f"Error occurred at {error_time}")
    return embed


def create_warning_embed(
    warning_message: str,
    warning_details: Optional[Dict[str, str]] = None,
    suggestion: Optional[str] = None,
    use_native_timestamps: bool = True
) -> Embed:
    """Create embed for warning notification.

    Args:
        warning_message: Warning description
        warning_details: Optional warning context details
        suggestion: Optional suggestion for resolution
        use_native_timestamps: Whether to use Discord's native timestamps

    Returns:
        Embed: Formatted warning embed

    Raises:
        ValueError: If warning_message is empty
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

    Args:
        status: Current system status
        metrics: Optional system metrics
        issues: Optional list of current issues
        use_native_timestamps: Whether to use Discord's native timestamps

    Returns:
        Embed: Formatted system status embed
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

    Args:
        operation: Type of batch operation
        items: List of items being processed
        summary: Optional operation summary

    Returns:
        Embed: Formatted batch operation embed
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

    Args:
        title: Message title
        description: Message description
        actions: List of available actions
        expires_in: Optional expiration time in seconds

    Returns:
        Embed: Formatted interactive embed
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

    Args:
        message: Debug message
        context: Optional debug context
        stack_trace: Optional stack trace

    Returns:
        Embed: Formatted debug embed
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

    Args:
        embed: Discord embed to validate

    Raises:
        DiscordWebhookError: If any component exceeds Discord limits
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

    Args:
        title: Title to validate

    Returns:
        int: Length of title

    Raises:
        DiscordWebhookError: If title exceeds length limit
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

    Args:
        description: Description to validate

    Returns:
        int: Length of description

    Raises:
        DiscordWebhookError: If description exceeds length limit
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

    Args:
        fields: List of fields to validate

    Returns:
        int: Total length of all fields

    Raises:
        DiscordWebhookError: If fields exceed length limits
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

    Args:
        footer: Footer to validate

    Returns:
        int: Length of footer text

    Raises:
        DiscordWebhookError: If footer text exceeds length limit
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

    Args:
        author: Author to validate

    Returns:
        int: Length of author name

    Raises:
        DiscordWebhookError: If author name exceeds length limit
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

    Args:
        data: Data structure to validate
        current_depth: Current nesting depth
        max_depth: Maximum allowed nesting depth

    Returns:
        bool: True if nesting depth is valid

    Raises:
        ValueError: If nesting depth exceeds maximum
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

    Args:
        embeds: List of embeds to include
        username: Bot username to display
        avatar_url: Optional avatar URL
        forum_config: Optional forum configuration for thread creation
        require_embeds: If True, at least one embed is required

    Returns:
        WebhookPayload: Complete webhook payload

    Raises:
        ValueError: If payload exceeds Discord limits or nesting depth
        ValueError: If embeds are required but not provided
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
        embed: Discord embed to convert

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

    Args:
        dt: Datetime to format
        style: Discord timestamp style (t=short time, T=long time, d=short date,
               D=long date, f=short date/time, F=long date/time, R=relative)

    Returns:
        str: Discord formatted timestamp
    """
    unix_timestamp = int(dt.timestamp())
    return f"<t:{unix_timestamp}:{style}>"
