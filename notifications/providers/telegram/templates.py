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

from ..telegram.types import (
    DEFAULT_TEMPLATES,
    InlineKeyboardMarkup,
    MessageEntity,
    ParseMode,
    create_progress_keyboard,
    validate_message_length,
)

logger = get_logger(__name__)


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
) -> Dict[str, Union[str, List[MessageEntity], InlineKeyboardMarkup]]:
    """Create formatted progress update message.

    Args:
        percent: Progress percentage
        remaining: Remaining data amount
        elapsed: Elapsed time
        etc: Estimated time of completion
        parse_mode: Message parsing mode
        add_keyboard: Whether to add inline keyboard
        description: Optional description

    Returns:
        Dict: Formatted message data

    Raises:
        ValueError: If message exceeds length limits
    """
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
    response_data = {"text": message, "parse_mode": parse_mode}

    # Add inline keyboard if requested
    if add_keyboard:
        response_data["reply_markup"] = create_progress_keyboard(percent)

    return response_data


def create_completion_message(
    parse_mode: ParseMode = ParseMode.HTML,
    include_stats: bool = True,
    stats: Optional[Dict[str, str]] = None,
) -> Dict[str, Union[str, List[MessageEntity]]]:
    """Create completion notification message.

    Args:
        parse_mode: Message parsing mode
        include_stats: Whether to include transfer statistics
        stats: Optional transfer statistics

    Returns:
        Dict: Formatted message data
    """
    message = DEFAULT_TEMPLATES["completion"]

    # Add statistics if requested and available
    if include_stats and stats:
        escape_func = escape_html if parse_mode == ParseMode.HTML else escape_markdown
        stats_text = "\n\n📊 Transfer Statistics:"
        for key, value in stats.items():
            stats_text += f"\n• {escape_func(key)}: {escape_func(value)}"
        message += stats_text

    return {
        "text": validate_message_length(message),
        "parse_mode": parse_mode
    }


def create_error_message(
    error_message: str,
    parse_mode: ParseMode = ParseMode.HTML,
    include_debug: bool = False,
    debug_info: Optional[Dict[str, str]] = None,
) -> Dict[str, Union[str, List[MessageEntity]]]:
    """Create error notification message.

    Args:
        error_message: Error description
        parse_mode: Message parsing mode
        include_debug: Whether to include debug information
        debug_info: Optional debug information

    Returns:
        Dict: Formatted message data
    """
    escape_func = escape_html if parse_mode == ParseMode.HTML else escape_markdown
    message = DEFAULT_TEMPLATES["error"].format(
        error_message=escape_func(error_message)
    )

    # Add debug information if requested
    if include_debug and debug_info:
        debug_text = "\n\n🔍 Debug Information:"
        for key, value in debug_info.items():
            debug_text += f"\n• {escape_func(key)}: {escape_func(value)}"
        message += debug_text

    return {
        "text": validate_message_length(message),
        "parse_mode": parse_mode
    }


def create_custom_message(
    template: str,
    values: Dict[str, str],
    parse_mode: ParseMode = ParseMode.HTML,
    keyboard: Optional[InlineKeyboardMarkup] = None,
) -> Dict[str, Union[str, List[MessageEntity], InlineKeyboardMarkup]]:
    """Create message from custom template.

    Args:
        template: Message template string
        values: Values to substitute in template
        parse_mode: Message parsing mode
        keyboard: Optional inline keyboard

    Returns:
        Dict: Formatted message data

    Raises:
        ValueError: If template format is invalid
    """
    try:
        # Escape values based on parse mode
        escape_func = escape_html if parse_mode == ParseMode.HTML else escape_markdown
        escaped_values = {
            key: escape_func(value) for key, value in values.items()
        }

        message = template.format(**escaped_values)
        response_data = {
            "text": validate_message_length(message),
            "parse_mode": parse_mode
        }

        if keyboard:
            response_data["reply_markup"] = keyboard

        return response_data

    except KeyError as err:
        raise ValueError(f"Missing template value: {err}") from err
    except ValueError as err:
        raise ValueError(f"Template formatting error: {err}") from err


def extract_html_entities(
    text: str
) -> tuple[str, List[MessageEntity]]:
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
    """
    entities = []
    plain_text = ""
    current_offset = 0

    # Simple HTML tag pattern
    pattern = r"<(/?[bi])>|<a href=\"([^\"]+)\">(.+?)</a>|<code>(.+?)</code>"

    tag_stack = []
    last_end = 0

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
                if tag_stack:
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

    return plain_text, entities
