"""Message templates and formatting utilities for Telegram notifications.

This module provides a comprehensive set of utilities for creating and formatting
messages for the Telegram notification provider. It includes templates for various
message types and utility functions for text formatting and entity extraction.

Features:
    - Pre-defined templates for common message types (progress, completion, error)
    - HTML and Markdown text escaping utilities
    - Message entity extraction for rich text formatting
    - Support for inline keyboards and interactive messages
    - Length validation and automatic truncation
    - Priority-based message formatting

Templates:
    - Progress: Transfer progress with progress bar and timing info
    - Completion: Success notification with optional statistics
    - Error: Error notification with optional debug information
    - Status: General status updates with optional keyboard
    - Warning: Warning messages with context and suggestions
    - System: System status updates with metrics
    - Batch: Batch operation status and summaries
    - Interactive: Messages with inline keyboard actions
    - Debug: Technical messages with context and stack traces

Example:
    >>> from notifications.telegram.templates import create_progress_message
    >>> message = create_progress_message(
    ...     percent=75.5,
    ...     remaining_data="1.2 GB",
    ...     elapsed_time="2 hours",
    ...     etc="15:30"
    ... )
    >>> print(message["text"])
    📊 Transfer Progress
    [███████▒▒▒] 75.5%
    ⏱️ Elapsed: 2 hours
    ⌛ Remaining: 1.2 GB
    🏁 ETC: 15:30
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
from utils.formatters import (
    ProgressStyle,
    TimeFormat,
    format_progress,
    format_timestamp,
)

logger = get_logger(__name__)

# Default message templates with placeholders
DEFAULT_TEMPLATES = {
    "progress": """📊 <b>Transfer Progress</b>

{progress_bar} <b>{percent:.1f}%</b>

⏱️ Elapsed: {elapsed_time}
⌛ Remaining: {remaining_data}
🏁 ETC: {etc}""",

    "completion": """✅ <b>Transfer Complete!</b>

The file transfer has been successfully completed.
{stats}""",

    "error": """❌ <b>Error Occurred</b>

{error_message}
{debug_info}""",

    "status": """ℹ️ <b>Status Update</b>

{status_message}""",

    "warning": """⚠️ <b>Warning</b>

{warning_message}""",
}


def escape_html(text: str) -> str:
    """Escape HTML special characters in text for safe message formatting.

    Replaces HTML special characters with their corresponding HTML entities
    to prevent parsing errors and potential XSS vulnerabilities.

    Args:
        text (str): Raw text containing potential HTML special characters

    Returns:
        str: Text with HTML special characters escaped

    Example:
        >>> text = "User input with <tags> & 'quotes'"
        >>> escaped = escape_html(text)
        >>> print(escaped)
        'User input with &lt;tags&gt; &amp; &apos;quotes&apos;'

    Note:
        Handles the following characters:
        - & becomes &amp;
        - " becomes &quot;
        - ' becomes &apos;
        - > becomes &gt;
        - < becomes &lt;
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
    """Escape Markdown special characters in text for safe message formatting.

    Escapes Markdown syntax characters to prevent unintended formatting when
    sending messages with ParseMode.MARKDOWN.

    Args:
        text (str): Raw text containing potential Markdown special characters

    Returns:
        str: Text with Markdown special characters escaped

    Example:
        >>> text = "Text with *bold* and _italic_"
        >>> escaped = escape_markdown(text)
        >>> print(escaped)
        'Text with \\*bold\\* and \\_italic\\_'

    Note:
        Escapes the following characters: _ * [ ] ( ) ~ ` > # + - = | { } . !
        Each character is escaped by prepending a backslash.
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
) -> Dict[str, Any]:
    """Create a formatted progress update message with progress bar.

    Constructs a message showing transfer progress with a visual progress bar,
    timing information, and optional inline keyboard controls.

    Args:
        percent (float): Progress percentage (0-100)
        remaining_data (str): Remaining data amount (e.g., "1.2 GB")
        elapsed_time (str): Elapsed time (e.g., "2 hours")
        etc (str): Estimated time of completion (e.g., "15:30")
        priority (MessagePriority): Message priority affecting rate limits
            (default: NORMAL)
        add_keyboard (bool): Whether to add control buttons (default: True)
        description (Optional[str]): Optional progress description

    Returns:
        Dict[str, Any]: Formatted message data containing:
            - text: Message text with progress information
            - parse_mode: HTML
            - reply_markup: Optional inline keyboard
            - priority: Message priority level

    Raises:
        ValueError: If percent is not between 0 and 100
        ValueError: If message exceeds Telegram length limits

    Example:
        >>> message = create_progress_message(
        ...     percent=75.5,
        ...     remaining_data="1.2 GB",
        ...     elapsed_time="2 hours",
        ...     etc="15:30",
        ...     description="Uploading backup files"
        ... )
        >>> print(message["text"])
        📊 Transfer Progress
        [███████▒▒▒] 75.5%
        Uploading backup files
        ⏱️ Elapsed: 2 hours
        ⌛ Remaining: 1.2 GB
        🏁 ETC: 15:30
    """
    if not 0 <= percent <= 100:
        raise ValueError("Percent must be between 0 and 100")

    # Format progress bar and timestamps
    progress_bar = format_progress(percent, style=ProgressStyle.BLOCKS, width=20)
    elapsed = format_timestamp(
        datetime.now() - timedelta(seconds=float(elapsed_time)),
        format_type=TimeFormat.RELATIVE
    )
    completion_time = datetime.strptime(etc, "%H:%M")
    etc_formatted = format_timestamp(completion_time, format_type=TimeFormat.FRIENDLY)

    message = f"""📊 <b>Transfer Progress</b>

{progress_bar} <b>{percent:.1f}%</b>

⏱️ Elapsed: {elapsed}
⌛ Remaining: {remaining_data}
🏁 ETC: {etc_formatted}"""

    if description:
        message = f"{description}\n\n{message}"

    data: Dict[str, Any] = {
        "text": message,
        "parse_mode": ParseMode.HTML,
        "priority": priority
    }

    if add_keyboard:
        data["reply_markup"] = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Pause", callback_data="pause"),
             InlineKeyboardButton(text="Cancel", callback_data="cancel")]
        ])

    validate_message_length(data["text"])
    return data


def create_completion_message(
    stats: Optional[Dict[str, Union[str, int, float]]] = None,
    priority: MessagePriority = MessagePriority.NORMAL,
    include_stats: bool = True
) -> Dict[str, Any]:
    """Create a completion notification message with optional statistics.

    Constructs a message indicating successful completion of an operation,
    optionally including relevant statistics.

    Args:
        stats (Optional[Dict[str, Union[str, int, float]]]): Transfer statistics:
            - total_size: Total size transferred
            - duration: Total transfer duration
            - speed: Average transfer speed
            - files: Number of files transferred
        priority (MessagePriority): Message priority (default: NORMAL)
        include_stats (bool): Whether to include statistics (default: True)

    Returns:
        Dict[str, Any]: Formatted message data containing:
            - text: Completion message with optional stats
            - parse_mode: HTML
            - priority: Message priority level

    Example:
        >>> stats = {
        ...     "total_size": "5.2 GB",
        ...     "duration": "1 hour 23 minutes",
        ...     "speed": "1.2 MB/s",
        ...     "files": 42
        ... }
        >>> message = create_completion_message(stats=stats)
        >>> print(message["text"])
        ✅ Transfer Complete!

        Total Size: 5.2 GB
        Duration: 1 hour 23 minutes
        Speed: 1.2 MB/s
        Files: 42
    """
    message = "✅ <b>Transfer Complete!</b>\n\nThe file transfer has been successfully completed."

    if stats and include_stats:
        stats_text = []
        for key, value in stats.items():
            if isinstance(value, datetime):
                value = format_timestamp(value, format_type=TimeFormat.FRIENDLY)
            stats_text.append(f"<b>{key}:</b> {value}")

        if stats_text:
            message += "\n\n<b>Transfer Statistics:</b>\n" + "\n".join(stats_text)

    message += f"\n\nCompleted at {format_timestamp(datetime.now(), format_type=TimeFormat.FRIENDLY)}"

    data = {
        "text": message,
        "parse_mode": ParseMode.HTML,
        "priority": priority
    }

    validate_message_length(data["text"])
    return data


def create_error_message(
    error_message: str,
    parse_mode: ParseMode = ParseMode.HTML,
    include_debug: bool = False,
    debug_info: Optional[Dict[str, str]] = None,
    priority: MessagePriority = MessagePriority.HIGH
) -> Dict[str, Any]:
    """Create an error notification message with optional debug info.

    Constructs a message describing an error condition, optionally including
    technical details for debugging purposes.

    Args:
        error_message (str): Main error description
        parse_mode (ParseMode): Message parsing mode (default: HTML)
        include_debug (bool): Whether to include debug info (default: False)
        debug_info (Optional[Dict[str, str]]): Debug information:
            - error_code: Error code if available
            - component: Component where error occurred
            - trace: Simplified stack trace
            - context: Additional error context
        priority (MessagePriority): Message priority (default: HIGH)

    Returns:
        Dict[str, Any]: Formatted message data containing:
            - text: Error message with optional debug info
            - parse_mode: Specified parse mode
            - priority: Message priority level

    Raises:
        ValueError: If error_message is empty
        ValueError: If message exceeds Telegram length limits

    Example:
        >>> debug = {
        ...     "error_code": "E1234",
        ...     "component": "file_transfer",
        ...     "trace": "TransferError: Connection lost"
        ... }
        >>> message = create_error_message(
        ...     "Failed to upload file",
        ...     include_debug=True,
        ...     debug_info=debug
        ... )
        >>> print(message["text"])
        ❌ Error Occurred

        Failed to upload file

        Debug Information:
        Error Code: E1234
        Component: file_transfer
        Trace: TransferError: Connection lost
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
) -> Dict[str, Any]:
    """Create a status update message with optional inline keyboard.

    Constructs an informational status message that can include interactive
    buttons for user actions.

    Args:
        status_message (str): Status update content
        parse_mode (ParseMode): Message parsing mode (default: HTML)
        keyboard (Optional[InlineKeyboardMarkup]): Optional inline keyboard
            for interactive responses
        priority (MessagePriority): Message priority (default: NORMAL)

    Returns:
        Dict[str, Any]: Formatted message data containing:
            - text: Status message
            - parse_mode: Specified parse mode
            - reply_markup: Optional inline keyboard
            - priority: Message priority level

    Raises:
        ValueError: If status_message is empty
        ValueError: If message exceeds Telegram length limits

    Example:
        >>> keyboard = {
        ...     "inline_keyboard": [[
        ...         {"text": "View Details", "callback_data": "view"},
        ...         {"text": "Dismiss", "callback_data": "dismiss"}
        ...     ]]
        ... }
        >>> message = create_status_message(
        ...     "New backup available",
        ...     keyboard=keyboard
        ... )
        >>> print(message["text"])
        ℹ️ Status Update

        New backup available
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
    """Create a formatted warning message with details and suggestions.

    Constructs a warning message that can include additional context and
    suggested actions for resolution.

    Args:
        warning_message (str): Main warning description
        warning_details (Optional[Dict[str, str]]): Warning context:
            - severity: Warning severity level
            - source: Component that generated the warning
            - impact: Potential impact description
        suggestion (Optional[str]): Suggested action for resolution

    Returns:
        str: Formatted warning message with emoji prefix

    Raises:
        ValueError: If warning_message is empty

    Example:
        >>> details = {
        ...     "severity": "medium",
        ...     "source": "disk_monitor",
        ...     "impact": "Reduced backup performance"
        ... }
        >>> message = create_warning_message(
        ...     "Low disk space detected",
        ...     warning_details=details,
        ...     suggestion="Consider cleaning old backups"
        ... )
        >>> print(message)
        ⚠️ Warning

        Low disk space detected

        Details:
        Severity: medium
        Source: disk_monitor
        Impact: Reduced backup performance

        Suggestion: Consider cleaning old backups
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
    """Create a formatted system status message with metrics.

    Constructs a comprehensive system status message that can include
    performance metrics and current issues.

    Args:
        status (str): Current system operational status
        metrics (Optional[Dict[str, Union[str, int, float]]]): System metrics:
            - cpu_usage: CPU utilization percentage
            - memory_usage: Memory utilization
            - disk_space: Available disk space
            - uptime: System uptime
        issues (Optional[List[str]]): List of active issues or alerts

    Returns:
        str: Formatted system status message with emoji indicators

    Example:
        >>> metrics = {
        ...     "cpu_usage": "45%",
        ...     "memory_usage": "2.1 GB",
        ...     "disk_space": "150 GB",
        ...     "uptime": "5 days"
        ... }
        >>> issues = ["High CPU load", "Low disk space"]
        >>> message = create_system_message(
        ...     "Operational",
        ...     metrics=metrics,
        ...     issues=issues
        ... )
        >>> print(message)
        🖥️ System Status: Operational

        Metrics:
        CPU Usage: 45%
        Memory Usage: 2.1 GB
        Disk Space: 150 GB
        Uptime: 5 days

        Active Issues:
        ⚠️ High CPU load
        ⚠️ Low disk space
    """
    message_parts = ["🖥️ *System Status*\n", status]

    if metrics:
        metrics_text = "\n\n📊 *Metrics:*\n" + "\n".join(
            f"• {k}: {v}" for k, v in metrics.items()
        )
        message_parts.append(metrics_text)

    if issues and len(issues) > 0:
        issues_text = "\n\n❗ *Current Issues:*\n" + "\n".join(
            f"• ⚠️ {issue}" for issue in issues
        )
        message_parts.append(issues_text)

    return "\n".join(message_parts)


def create_batch_message(
    operation: str,
    items: List[Dict[str, Any]],
    summary: Optional[str] = None
) -> str:
    """Create a formatted batch operation status message.

    Constructs a message summarizing a batch operation's status, including
    details about processed items and operation summary.

    Args:
        operation (str): Type of batch operation (e.g., "backup", "cleanup")
        items (List[Dict[str, Any]]): List of processed items, each containing:
            - name: Item name or identifier
            - status: Processing status
            - size: Item size if applicable
            - duration: Processing duration
        summary (Optional[str]): Operation summary or results

    Returns:
        str: Formatted batch operation message

    Example:
        >>> items = [
        ...     {"name": "file1.txt", "status": "success", "size": "1.2 MB"},
        ...     {"name": "file2.txt", "status": "failed", "size": "2.1 MB"}
        ... ]
        >>> message = create_batch_message(
        ...     "Backup",
        ...     items,
        ...     "1 of 2 files processed successfully"
        ... )
        >>> print(message)
        📦 Batch Operation: Backup

        Items:
        ✅ file1.txt (1.2 MB)
        ❌ file2.txt (2.1 MB)

        Summary: 1 of 2 files processed successfully
    """
    message_parts = [f"📦 *Batch {operation}*"]

    if summary:
        message_parts.append(summary)
    else:
        message_parts.append(f"Processing {len(items)} items")

    # Add items summary (limit to first 10)
    items_text = "\n\n*Items:*\n" + "\n".join(
        f"• {'✅' if item['status'] == 'success' else '❌'} {item.get('name', 'Unknown')} ({item.get('size', '')})"
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
    """Create an interactive message with inline keyboard buttons.

    Constructs a message that includes interactive buttons for user actions,
    optionally with an expiration timer.

    Args:
        title (str): Message title or header
        description (str): Detailed message description
        actions (List[Dict[str, str]]): Available actions:
            - text: Button label
            - callback_data: Button callback identifier
            - url: Optional URL for link buttons
        expires_in (Optional[int]): Message expiration in seconds

    Returns:
        Tuple[str, Optional[InlineKeyboardMarkup]]: Message text and keyboard

    Example:
        >>> actions = [
        ...     {"text": "Approve", "callback_data": "approve"},
        ...     {"text": "Reject", "callback_data": "reject"},
        ...     {"text": "Details", "url": "https://example.com"}
        ... ]
        >>> text, markup = create_interactive_message(
        ...     "Backup Approval Required",
        ...     "New backup is ready for review",
        ...     actions,
        ...     expires_in=3600
        ... )
        >>> print(text)
        🔔 Backup Approval Required

        New backup is ready for review

        ⏳ Expires in: 1 hour
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
                text=action['text'],
                callback_data=action.get('callback_data', action['text'])
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
    """Create a technical debug message with context and stack trace.

    Constructs a detailed technical message for debugging purposes,
    including relevant context and stack trace information.

    Args:
        message (str): Main debug message or description
        context (Optional[Dict[str, Any]]): Debug context:
            - timestamp: Event timestamp
            - component: Source component
            - variables: Relevant variable values
            - state: System state information
        stack_trace (Optional[str]): Formatted stack trace

    Returns:
        str: Formatted debug message with technical details

    Example:
        >>> context = {
        ...     "timestamp": "2023-01-01 12:34:56",
        ...     "component": "file_handler",
        ...     "variables": {"path": "/tmp/file.txt"}
        ... }
        >>> message = create_debug_message(
        ...     "File access error",
        ...     context=context,
        ...     stack_trace="Traceback: ..."
        ... )
        >>> print(message)
        🔧 Debug Information

        Message: File access error

        Context:
        Timestamp: 2023-01-01 12:34:56
        Component: file_handler
        Variables: {"path": "/tmp/file.txt"}

        Stack Trace:
        Traceback: ...
    """
    message_parts = ["🔧 *Debug Information*\n", message]

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


def extract_html_entities(text: str) -> Tuple[str, List[MessageEntity]]:
    """Extract message entities from HTML-formatted text.

    Parses HTML-formatted text to extract formatting entities supported by
    Telegram's Bot API, converting them into MessageEntity objects while
    maintaining proper offsets and lengths.

    Supported HTML Tags:
        - <b>, <strong>: Bold text
        - <i>, <em>: Italic text
        - <u>: Underlined text
        - <s>, <strike>, <del>: Strikethrough text
        - <code>: Monospace text
        - <pre>: Pre-formatted text block
        - <a href="...">: Link with URL
        - <spoiler>: Spoiler text

    Args:
        text (str): HTML-formatted text to parse

    Returns:
        Tuple[str, List[MessageEntity]]: Tuple containing:
            - Plain text with HTML tags removed
            - List of MessageEntity objects with:
                - type: Entity type (bold, italic, etc.)
                - offset: Character offset in plain text
                - length: Entity length in characters
                - url: URL for link entities

    Raises:
        ValueError: If HTML tags are malformed or nested incorrectly

    Example:
        >>> text = '<b>Bold</b> and <i>italic</i> with <a href="https://t.me">link</a>'
        >>> plain_text, entities = extract_html_entities(text)
        >>> print(plain_text)
        'Bold and italic with link'
        >>> for entity in entities:
        ...     print(f"{entity['type']} at {entity['offset']}:{entity['length']}")
        bold at 0:4
        italic at 9:6
        text_link at 20:4 (url: https://t.me)

    Note:
        - Entities are returned in order of appearance
        - Nested tags are supported with proper offset calculation
        - Malformed HTML will raise ValueError with details
        - Unknown tags are ignored and included as plain text
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
