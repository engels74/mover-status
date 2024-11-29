# notifications/providers/telegram/templates.py

"""
Message templates and formatting utilities for Telegram notifications.
Provides template management and message construction for the Telegram provider.

Example:
    >>> from notifications.telegram.templates import create_progress_message
    >>> message = create_progress_message(
    ...     percent=75.5,
    ...     remaining_data="1.2 GB",
    ...     elapsed_time="2 hours",
    ...     etc="15:30"
    ... )
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from structlog import get_logger

from config.constants import MessagePriority
from notifications.providers.telegram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity,
    ParseMode,
    validate_message_length,
)
from shared.utils.time import format_timestamp

logger = get_logger(__name__)

# Default message templates with placeholders
DEFAULT_TEMPLATES = {
    "progress": """📊 Transfer Progress: {percent}%

⏳ Remaining: {remaining_data}
⌛ Elapsed: {elapsed_time}
🏁 ETC: {etc}""",

    "completion": """✅ Transfer Complete!

The file transfer has been successfully completed.
{stats}""",

    "error": """❌ Error Occurred

{error_message}
{debug_info}""",

    "status": """ℹ️ Status Update

{status_message}""",

    "warning": """⚠️ Warning

{warning_message}""",
}


def escape_html(text: str) -> str:
    """Escape HTML special characters in text.

    Args:
        text: Text to escape

    Returns:
        str: Escaped text safe for HTML parsing

    Example:
        >>> escape_html("Text with <tags> & symbols")
        'Text with &lt;tags&gt; &amp; symbols'
    """
    html_escape_table = {
        "&": "&amp;",
        '"': "&quot;",
        "'": "&apos;",
        ">": "&gt;",
        "<": "&lt;",
    }
    return "".join(html_escape_table.get(c, c) for c in str(text))


def escape_markdown(text: str) -> str:
    """Escape Markdown special characters in text.

    Args:
        text: Text to escape

    Returns:
        str: Escaped text safe for Markdown parsing

    Example:
        >>> escape_markdown("Text with *bold* and _italic_")
        'Text with \\*bold\\* and \\_italic\\_'
    """
    markdown_escape_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in markdown_escape_chars else c for c in str(text))


def create_progress_message(
    percent: float,
    remaining_data: str,
    elapsed_time: str,
    etc: str,
    priority: MessagePriority = MessagePriority.NORMAL,
    add_keyboard: bool = True,
    description: Optional[str] = None,
) -> Dict[str, Union[str, List[MessageEntity], InlineKeyboardMarkup]]:
    """Create formatted progress update message.

    Args:
        percent: Progress percentage (0-100)
        remaining_data: Remaining data amount
        elapsed_time: Elapsed time
        etc: Estimated time of completion
        priority: Message priority level (LOW, NORMAL, HIGH)
        add_keyboard: Whether to add inline keyboard
        description: Optional description

    Returns:
        Dict: Formatted message data

    Raises:
        ValueError: If percent is out of range or message exceeds length limits
    """
    if not 0 <= percent <= 100:
        raise ValueError("Percent must be between 0 and 100")

    # Escape special characters based on parse mode
    parse_mode = ParseMode.HTML
    escape_func = escape_html if parse_mode == ParseMode.HTML else escape_markdown
    escaped_values = {
        "percent": escape_func(f"{percent:.1f}"),
        "remaining_data": escape_func(remaining_data),
        "elapsed_time": escape_func(elapsed_time),
        "etc": escape_func(etc),
    }

    # Format the message using template
    message = DEFAULT_TEMPLATES["progress"].format(**escaped_values)

    # Add optional description
    if description:
        message = f"{escape_func(description)}\n\n{message}"

    # Validate message length
    message = validate_message_length(message)

    # Prepare response data
    response_data = {
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": priority == MessagePriority.LOW,
    }

    # Add inline keyboard if requested
    if add_keyboard:
        keyboard = [
            [{
                "text": "▓" * round(percent / 10) + "░" * (10 - round(percent / 10)),
                "callback_data": "progress_bar"
            }]
        ]
        response_data["reply_markup"] = {"inline_keyboard": keyboard}

    return response_data


def create_completion_message(
    stats: Optional[Dict[str, Union[str, int, float]]] = None,
    priority: MessagePriority = MessagePriority.NORMAL,
    include_stats: bool = True
) -> Dict[str, Union[str, List[MessageEntity]]]:
    """Create completion notification message.

    Args:
        stats: Optional transfer statistics
        priority: Message priority level (LOW, NORMAL, HIGH)
        include_stats: Whether to include transfer statistics

    Returns:
        Dict: Formatted message data

    Raises:
        ValueError: If message exceeds length limits
    """
    # Format statistics if included
    stats_text = ""
    if include_stats and stats:
        stats_text = "\n\nStatistics:"
        for key, value in stats.items():
            stats_text += f"\n• {key}: {value}"

    # Format the message using template
    message = DEFAULT_TEMPLATES["completion"].format(stats=stats_text)

    # Validate message length
    message = validate_message_length(message)

    return {
        "text": message,
        "parse_mode": ParseMode.HTML,
        "disable_notification": priority == MessagePriority.LOW
    }


def create_error_message(
    error_message: str,
    parse_mode: ParseMode = ParseMode.HTML,
    include_debug: bool = False,
    debug_info: Optional[Dict[str, str]] = None,
    priority: MessagePriority = MessagePriority.HIGH
) -> Dict[str, Union[str, List[MessageEntity]]]:
    """Create error notification message.

    Args:
        error_message: Error description
        parse_mode: Message parsing mode
        include_debug: Whether to include debug information
        debug_info: Optional debug information
        priority: Message priority level (LOW, NORMAL, HIGH)

    Returns:
        Dict: Formatted message data

    Raises:
        ValueError: If error_message is empty or message exceeds length limits
    """
    if not error_message:
        raise ValueError("Error message cannot be empty")

    # Escape special characters based on parse mode
    escape_func = escape_html if parse_mode == ParseMode.HTML else escape_markdown
    error_text = escape_func(error_message)

    # Add debug information if requested
    debug_text = ""
    if include_debug and debug_info:
        debug_text = "\n\nDebug Information:"
        for key, value in debug_info.items():
            debug_text += f"\n• {escape_func(key)}: {escape_func(value)}"

    # Format the message using template
    message = DEFAULT_TEMPLATES["error"].format(
        error_message=error_text,
        debug_info=debug_text
    )

    # Validate message length
    message = validate_message_length(message)

    return {
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": False  # Always notify for errors
    }


def create_status_message(
    status_message: str,
    parse_mode: ParseMode = ParseMode.HTML,
    keyboard: Optional[InlineKeyboardMarkup] = None,
    priority: MessagePriority = MessagePriority.NORMAL
) -> Dict[str, Union[str, List[MessageEntity], InlineKeyboardMarkup]]:
    """Create status update message.

    Args:
        status_message: Status update text
        parse_mode: Message parsing mode
        keyboard: Optional inline keyboard
        priority: Message priority level (LOW, NORMAL, HIGH)

    Returns:
        Dict: Formatted message data

    Raises:
        ValueError: If status_message is empty or message exceeds length limits
    """
    if not status_message:
        raise ValueError("Status message cannot be empty")

    # Escape special characters based on parse mode
    escape_func = escape_html if parse_mode == ParseMode.HTML else escape_markdown
    status_text = escape_func(status_message)

    # Format the message using template
    message = DEFAULT_TEMPLATES["status"].format(status_message=status_text)

    # Validate message length
    message = validate_message_length(message)

    # Prepare response data
    response_data = {
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": priority == MessagePriority.LOW
    }

    # Add keyboard if provided
    if keyboard:
        response_data["reply_markup"] = keyboard

    return response_data


def create_warning_message(
    warning_message: str,
    warning_details: Optional[Dict[str, str]] = None,
    suggestion: Optional[str] = None
) -> str:
    """Create formatted warning message.

    Args:
        warning_message: Warning description
        warning_details: Optional warning context details
        suggestion: Optional suggestion for resolution

    Returns:
        str: Formatted warning message

    Raises:
        ValueError: If warning_message is empty
    """
    if not warning_message:
        raise ValueError("Warning message cannot be empty")

    message_parts = ["⚠️ *Warning*\n", warning_message]

    if warning_details:
        details = "\n\n*Details:*\n" + "\n".join(
            f"• {k}: {v}" for k, v in warning_details.items()
        )
        message_parts.append(details)

    if suggestion:
        message_parts.append(f"\n\n💡 *Suggestion:*\n{suggestion}")

    return "\n".join(message_parts)


def create_system_message(
    status: str,
    metrics: Optional[Dict[str, Union[str, int, float]]] = None,
    issues: Optional[List[str]] = None
) -> str:
    """Create formatted system status message.

    Args:
        status: Current system status
        metrics: Optional system metrics
        issues: Optional list of current issues

    Returns:
        str: Formatted system status message
    """
    message_parts = ["🖥️ *System Status*\n", status]

    if metrics:
        metrics_text = "\n\n📊 *Metrics:*\n" + "\n".join(
            f"• {k}: {v}" for k, v in metrics.items()
        )
        message_parts.append(metrics_text)

    if issues and len(issues) > 0:
        issues_text = "\n\n❗ *Current Issues:*\n" + "\n".join(
            f"• {issue}" for issue in issues
        )
        message_parts.append(issues_text)

    return "\n".join(message_parts)


def create_batch_message(
    operation: str,
    items: List[Dict[str, Any]],
    summary: Optional[str] = None
) -> str:
    """Create formatted batch operation message.

    Args:
        operation: Type of batch operation
        items: List of items being processed
        summary: Optional operation summary

    Returns:
        str: Formatted batch operation message
    """
    message_parts = [f"📦 *Batch {operation}*"]

    if summary:
        message_parts.append(summary)
    else:
        message_parts.append(f"Processing {len(items)} items")

    # Add items summary (limit to first 10)
    items_text = "\n\n*Items:*\n" + "\n".join(
        f"• {item.get('name', 'Unknown')}: {item.get('status', 'Pending')}"
        for item in items[:10]
    )
    if len(items) > 10:
        items_text += f"\n... and {len(items) - 10} more items"

    message_parts.append(items_text)
    return "\n".join(message_parts)


def create_interactive_message(
    title: str,
    description: str,
    actions: List[Dict[str, str]],
    expires_in: Optional[int] = None
) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """Create formatted interactive message with keyboard.

    Args:
        title: Message title
        description: Message description
        actions: List of available actions
        expires_in: Optional expiration time in seconds

    Returns:
        Tuple[str, Optional[InlineKeyboardMarkup]]: Message text and keyboard markup
    """
    message_parts = [f"🔄 *{title}*\n", description]

    # Add expiry time if provided
    if expires_in:
        expiry_time = datetime.utcnow() + timedelta(seconds=expires_in)
        message_parts.append(f"\n\n⏰ Expires: {format_timestamp(expiry_time)}")

    # Create inline keyboard for actions
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=action['label'],
                callback_data=action.get('callback_data', action['label'])
            )]
            for action in actions
        ]
    )

    return "\n".join(message_parts), keyboard


def create_debug_message(
    message: str,
    context: Optional[Dict[str, Any]] = None,
    stack_trace: Optional[str] = None
) -> str:
    """Create formatted debug message.

    Args:
        message: Debug message
        context: Optional debug context
        stack_trace: Optional stack trace

    Returns:
        str: Formatted debug message
    """
    message_parts = ["🔍 *Debug Information*\n", message]

    if context:
        context_text = "\n\n*Context:*\n" + "\n".join(
            f"• {k}: {v}" for k, v in context.items()
        )
        message_parts.append(context_text)

    if stack_trace:
        # Truncate stack trace if too long
        if len(stack_trace) > 1000:
            stack_trace = stack_trace[:997] + "..."
        message_parts.append(f"\n\n*Stack Trace:*\n```\n{stack_trace}\n```")

    return "\n".join(message_parts)


def extract_html_entities(text: str) -> tuple[str, List[MessageEntity]]:
    """Extract message entities from HTML-formatted text.

    Args:
        text: HTML-formatted text

    Returns:
        tuple: (Plain text, List of message entities)

    Example:
        >>> text, entities = extract_html_entities("<b>Bold</b> and <i>italic</i>")
        >>> text
        'Bold and italic'
        >>> entities
        [{'type': 'bold', 'offset': 0, 'length': 4},
         {'type': 'italic', 'offset': 9, 'length': 6}]

    Raises:
        ValueError: If HTML tags are malformed
    """
    if not text:
        return "", []

    entities = []
    plain_text = ""
    current_offset = 0
    tag_stack = []
    last_end = 0

    # Simple HTML tag pattern
    pattern = r"<(/?[bi])>|<a href=\"([^\"]+)\">(.+?)</a>|<code>(.+?)</code>"

    for match in re.finditer(pattern, text):
        # Add text before the tag
        start = match.start()
        plain_text += text[last_end:start]
        current_offset = len(plain_text)

        tag = match.group(1)
        if tag:
            # Simple tags (b, i)
            if not tag.startswith("/"):
                tag_stack.append((tag, current_offset))
            else:
                if not tag_stack:
                    raise ValueError("Unmatched closing tag")
                open_tag, start_offset = tag_stack.pop()
                if open_tag == tag[1:]:
                    entity_type = "bold" if open_tag == "b" else "italic"
                    entities.append({
                        "type": entity_type,
                        "offset": start_offset,
                        "length": current_offset - start_offset
                    })
        elif match.group(2):
            # Link
            url = match.group(2)
            text_content = match.group(3)
            plain_text += text_content
            entities.append({
                "type": "text_link",
                "offset": current_offset,
                "length": len(text_content),
                "url": url
            })
        elif match.group(4):
            # Code
            code_content = match.group(4)
            plain_text += code_content
            entities.append({
                "type": "code",
                "offset": current_offset,
                "length": len(code_content)
            })

        last_end = match.end()

    # Add remaining text
    plain_text += text[last_end:]

    if tag_stack:
        raise ValueError("Unclosed HTML tags")

    return plain_text, entities
