# notifications/providers/telegram/types.py

"""
Type definitions and constants for Telegram bot notifications.
Defines message structure, API limits, and formatting options for Telegram bot API.

Example:
    >>> from notifications.providers.telegram.types import validate_message_length
    >>> text = validate_message_length("Hello, World!")
"""

from typing import Dict, List, Optional, TypedDict, Union

from config.constants import ErrorMessages, MessagePriority
from shared.providers.telegram import (
    MessageEntity,
    MessageLimit,
    ParseMode,
)
import asyncio
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NotificationState:
    """Thread-safe Telegram notification state tracking."""
    message_id: Optional[int] = None
    chat_id: Optional[Union[int, str]] = None
    thread_id: Optional[int] = None
    priority: MessagePriority = MessagePriority.NORMAL
    retry_count: int = 0
    last_error: Optional[str] = None
    last_update: float = field(default_factory=lambda: datetime.now().timestamp())
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def update(self, **kwargs) -> None:
        """Thread-safe state update.

        Args:
            **kwargs: State attributes to update
        """
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.last_update = datetime.now().timestamp()

    async def increment_retry(self) -> int:
        """Thread-safe retry count increment.

        Returns:
            int: New retry count
        """
        async with self._lock:
            self.retry_count += 1
            return self.retry_count

    async def reset(self) -> None:
        """Thread-safe state reset."""
        async with self._lock:
            self.message_id = None
            self.retry_count = 0
            self.last_error = None
            self.last_update = datetime.now().timestamp()


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
