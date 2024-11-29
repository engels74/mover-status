# notifications/providers/telegram/types.py

"""
Type definitions and constants for Telegram bot notifications.
Defines message structure, API limits, and formatting options for Telegram bot API.

Example:
    >>> from notifications.providers.telegram.types import MessagePriority, validate_message_length
    >>> priority = MessagePriority.NORMAL
    >>> text = validate_message_length("Hello, World!")
"""

from enum import IntEnum
from typing import Dict, List, Optional, TypedDict, Union

from config.constants import ErrorMessages
from shared.providers.telegram import (
    MessageEntity,
    MessageLimit,
    ParseMode,
)


class MessagePriority(IntEnum):
    """Message priority levels affecting notification behavior."""
    LOW = 0      # Low priority, can be delayed/dropped
    NORMAL = 1   # Default notification priority
    HIGH = 2     # High priority, immediate delivery


class NotificationState(TypedDict, total=False):
    """Telegram notification state tracking."""
    message_id: int
    chat_id: Union[int, str]
    thread_id: Optional[int]
    priority: MessagePriority
    retry_count: int
    last_error: Optional[str]
    last_update: float


class InlineKeyboardButton(TypedDict, total=False):
    """Telegram inline keyboard button structure."""
    text: str                       # Button text (required)
    url: Optional[str]              # Optional URL to open
    callback_data: Optional[str]    # Optional callback data


class InlineKeyboardMarkup(TypedDict):
    """Telegram inline keyboard markup structure."""
    inline_keyboard: List[List[InlineKeyboardButton]]


class SendMessageRequest(TypedDict, total=False):
    """Structure for sendMessage API request."""
    chat_id: Union[int, str]
    text: str
    parse_mode: Optional[ParseMode]
    entities: Optional[List[MessageEntity]]
    disable_notification: Optional[bool]
    protect_content: Optional[bool]
    message_thread_id: Optional[int]
    reply_markup: Optional[InlineKeyboardMarkup]


class EditMessageRequest(TypedDict, total=False):
    """Structure for editMessageText API request."""
    chat_id: Union[int, str]
    message_id: int
    text: str
    parse_mode: Optional[ParseMode]
    entities: Optional[List[MessageEntity]]
    message_thread_id: Optional[int]
    reply_markup: Optional[InlineKeyboardMarkup]


class DeleteMessageRequest(TypedDict, total=False):
    """Structure for deleteMessage API request."""
    chat_id: Union[int, str]
    message_id: int
    message_thread_id: Optional[int]


# Default message templates with HTML formatting
DEFAULT_TEMPLATES: Dict[str, str] = {
    "progress": (
        "📊 <b>Transfer Progress</b>\n"
        "├ Progress: <b>{percent:.1f}%</b>\n"
        "├ Speed: {speed}/s\n"
        "├ Remaining: {remaining}\n"
        "├ Elapsed: {elapsed}\n"
        "└ ETA: {eta}"
    ),
    "completion": (
        "✅ <b>Transfer Complete</b>\n"
        "├ Total Size: {total_size}\n"
        "├ Duration: {duration}\n"
        "├ Average Speed: {avg_speed}/s\n"
        "└ Files Moved: {files_moved}"
    ),
    "error": (
        "❌ <b>Transfer Error</b>\n"
        "├ Error: {error}\n"
        "├ Details: {details}\n"
        "└ Retry Count: {retry_count}"
    ),
    "warning": (
        "⚠️ <b>Warning</b>\n"
        "{message}"
    )
}


def create_progress_keyboard(percent: float) -> InlineKeyboardMarkup:
    """Create inline keyboard with progress information.

    Args:
        percent: Progress percentage (0-100)

    Returns:
        InlineKeyboardMarkup: Formatted inline keyboard

    Raises:
        ValueError: If percent is not between 0 and 100

    Example:
        >>> keyboard = create_progress_keyboard(75.5)
        >>> keyboard["inline_keyboard"]
        [[{"text": "▰▰▰▰▰▰▰▱▱▱ 75.5%", "callback_data": "progress"}]]
    """
    if not 0 <= percent <= 100:
        raise ValueError(ErrorMessages.INVALID_PERCENTAGE.format(
            value=percent
        ))

    # Create progress bar
    total_slots = MessageLimit.BUTTONS_PER_ROW
    filled = int(percent * total_slots / 100)
    empty = total_slots - filled

    # Build keyboard layout
    keyboard: List[List[InlineKeyboardButton]] = [
        [
            {
                "text": "█" * filled + "░" * empty,
                "callback_data": f"progress_{percent:.1f}"
            }
        ],
        [
            {"text": f"{percent:.1f}%", "callback_data": "percent"},
            {"text": "Cancel", "callback_data": "cancel"}
        ]
    ]

    return {"inline_keyboard": keyboard}


def validate_message_length(
    text: str,
    limit: int = MessageLimit.MESSAGE_TEXT,
    truncate: bool = True
) -> str:
    """Validate and optionally truncate message text.

    Args:
        text: Message text to validate
        limit: Maximum length limit (default: MESSAGE_TEXT)
        truncate: Whether to truncate text if too long (default: True)

    Returns:
        str: Validated message text

    Raises:
        ValueError: If text is empty or too long when truncate is False

    Example:
        >>> long_text = "x" * 5000
        >>> validated = validate_message_length(long_text)
        >>> len(validated) <= MessageLimit.MESSAGE_TEXT
        True
    """
    if not text:
        raise ValueError(ErrorMessages.EMPTY_MESSAGE)

    if len(text) > limit:
        if not truncate:
            raise ValueError(ErrorMessages.MESSAGE_TOO_LONG.format(
                max_length=limit
            ))
        return text[:(limit - 3)] + "..."

    return text
