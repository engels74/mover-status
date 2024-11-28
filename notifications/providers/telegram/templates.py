# notifications/providers/telegram/templates.py

"""
Message templates and formatting utilities for Telegram notifications.
Provides template management and message construction for the Telegram provider.

Example:
    >>> from notifications.telegram.templates import create_progress_message
    >>> message = create_progress_message(
    ...     percent=75.5,
    ...     remaining="1.2 GB",
    ...     elapsed="2 hours",
    ...     etc="15:30"
    ... )
"""

import re
from typing import Dict, List, Optional, Union

from structlog import get_logger

from config.constants import MessagePriority
from shared.providers.telegram.types import (
    InlineKeyboardMarkup,
    MessageEntity,
    ParseMode,
    validate_message_length,
)

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
    remaining: str,
    elapsed: str,
    etc: str,
    parse_mode: ParseMode = ParseMode.HTML,
    add_keyboard: bool = True,
    description: Optional[str] = None,
    priority: MessagePriority = MessagePriority.NORMAL,
) -> Dict[str, Union[str, List[MessageEntity], InlineKeyboardMarkup]]:
    """Create formatted progress update message.

    Args:
        percent: Progress percentage (0-100)
        remaining: Remaining data amount
        elapsed: Elapsed time
        etc: Estimated time of completion
        parse_mode: Message parsing mode
        add_keyboard: Whether to add inline keyboard
        description: Optional description
        priority: Message priority level

    Returns:
        Dict: Formatted message data

    Raises:
        ValueError: If percent is out of range or message exceeds length limits
    """
    if not 0 <= percent <= 100:
        raise ValueError("Percent must be between 0 and 100")

    # Escape special characters based on parse mode
    escape_func = escape_html if parse_mode == ParseMode.HTML else escape_markdown
    escaped_values = {
        "percent": escape_func(f"{percent:.1f}"),
        "remaining_data": escape_func(remaining),
        "elapsed_time": escape_func(elapsed),
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
    parse_mode: ParseMode = ParseMode.HTML,
    include_stats: bool = True,
    stats: Optional[Dict[str, str]] = None,
    priority: MessagePriority = MessagePriority.NORMAL,
) -> Dict[str, Union[str, List[MessageEntity]]]:
    """Create completion notification message.

    Args:
        parse_mode: Message parsing mode
        include_stats: Whether to include transfer statistics
        stats: Optional transfer statistics
        priority: Message priority level

    Returns:
        Dict: Formatted message data

    Raises:
        ValueError: If message exceeds length limits
    """
    escape_func = escape_html if parse_mode == ParseMode.HTML else escape_markdown
    stats_text = ""

    # Add statistics if requested and available
    if include_stats and stats:
        stats_text = "\n\n📊 Transfer Statistics:"
        for key, value in stats.items():
            stats_text += f"\n• {escape_func(key)}: {escape_func(value)}"

    # Format and validate message
    message = DEFAULT_TEMPLATES["completion"].format(stats=stats_text)
    message = validate_message_length(message)

    return {
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": priority == MessagePriority.LOW,
    }

def create_error_message(
    error_message: str,
    parse_mode: ParseMode = ParseMode.HTML,
    include_debug: bool = False,
    debug_info: Optional[Dict[str, str]] = None,
    priority: MessagePriority = MessagePriority.HIGH,
) -> Dict[str, Union[str, List[MessageEntity]]]:
    """Create error notification message.

    Args:
        error_message: Error description
        parse_mode: Message parsing mode
        include_debug: Whether to include debug information
        debug_info: Optional debug information
        priority: Message priority level

    Returns:
        Dict: Formatted message data

    Raises:
        ValueError: If error_message is empty or message exceeds length limits
    """
    if not error_message.strip():
        raise ValueError("Error message cannot be empty")

    escape_func = escape_html if parse_mode == ParseMode.HTML else escape_markdown
    debug_text = ""

    # Add debug information if requested
    if include_debug and debug_info:
        debug_text = "\n\n🔍 Debug Information:"
        for key, value in debug_info.items():
            debug_text += f"\n• {escape_func(key)}: {escape_func(value)}"

    # Format and validate message
    message = DEFAULT_TEMPLATES["error"].format(
        error_message=escape_func(error_message),
        debug_info=debug_text
    )
    message = validate_message_length(message)

    return {
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": False,  # Error messages always notify
    }

def create_status_message(
    status_message: str,
    parse_mode: ParseMode = ParseMode.HTML,
    keyboard: Optional[InlineKeyboardMarkup] = None,
    priority: MessagePriority = MessagePriority.NORMAL,
) -> Dict[str, Union[str, List[MessageEntity], InlineKeyboardMarkup]]:
    """Create status update message.

    Args:
        status_message: Status update text
        parse_mode: Message parsing mode
        keyboard: Optional inline keyboard
        priority: Message priority level

    Returns:
        Dict: Formatted message data

    Raises:
        ValueError: If status_message is empty or message exceeds length limits
    """
    if not status_message.strip():
        raise ValueError("Status message cannot be empty")

    escape_func = escape_html if parse_mode == ParseMode.HTML else escape_markdown
    message = DEFAULT_TEMPLATES["status"].format(
        status_message=escape_func(status_message)
    )

    # Validate and prepare response
    message = validate_message_length(message)
    response_data = {
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": priority == MessagePriority.LOW,
    }

    if keyboard:
        response_data["reply_markup"] = keyboard

    return response_data

def create_warning_message(
    warning_message: str,
    parse_mode: ParseMode = ParseMode.HTML,
    keyboard: Optional[InlineKeyboardMarkup] = None,
    priority: MessagePriority = MessagePriority.HIGH,
) -> Dict[str, Union[str, List[MessageEntity], InlineKeyboardMarkup]]:
    """Create warning notification message.

    Args:
        warning_message: Warning description
        parse_mode: Message parsing mode
        keyboard: Optional inline keyboard
        priority: Message priority level

    Returns:
        Dict: Formatted message data

    Raises:
        ValueError: If warning_message is empty or message exceeds length limits
    """
    if not warning_message.strip():
        raise ValueError("Warning message cannot be empty")

    escape_func = escape_html if parse_mode == ParseMode.HTML else escape_markdown
    message = DEFAULT_TEMPLATES["warning"].format(
        warning_message=escape_func(warning_message)
    )

    # Validate and prepare response
    message = validate_message_length(message)
    response_data = {
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": False,  # Warning messages always notify
    }

    if keyboard:
        response_data["reply_markup"] = keyboard

    return response_data

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
