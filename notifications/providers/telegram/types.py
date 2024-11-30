# notifications/providers/telegram/types.py

"""
Type definitions and constants for Telegram bot notifications.

This module provides type definitions, data structures, and utility functions
for working with the Telegram Bot API. It includes message formatting options,
API request/response structures, and validation utilities.

Features:
    - Thread-safe notification state tracking
    - Inline keyboard button and markup structures
    - Message request/response type definitions
    - Message length validation and truncation
    - Default message templates with emoji
    - Progress keyboard generation

Classes:
    - NotificationState: Thread-safe state tracking
    - InlineKeyboardButton: Button configuration
    - InlineKeyboardMarkup: Keyboard layout structure
    - SendMessageRequest: Message sending parameters
    - EditMessageRequest: Message editing parameters
    - DeleteMessageRequest: Message deletion parameters

Constants:
    - MessageLimit: API size and count limits
    - ParseMode: Message formatting modes
    - DEFAULT_TEMPLATES: Pre-defined message templates

Example:
    >>> from notifications.providers.telegram.types import (
    ...     SendMessageRequest,
    ...     InlineKeyboardMarkup,
    ...     validate_message_length
    ... )
    >>> keyboard = {"inline_keyboard": [[
    ...     {"text": "OK", "callback_data": "ok"}
    ... ]]}
    >>> request = SendMessageRequest(
    ...     chat_id="123456789",
    ...     text=validate_message_length("Hello, World!"),
    ...     parse_mode="HTML",
    ...     reply_markup=keyboard
    ... )
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, TypedDict, Union

from config.constants import ErrorMessages, MessagePriority
from shared.providers.telegram import (
    MessageEntity,
    MessageLimit,
    ParseMode,
)


@dataclass
class NotificationState:
    """Thread-safe state tracking for Telegram notifications.

    Maintains the current state of a notification including message IDs,
    retry counts, and error information. All operations are protected by
    an asyncio.Lock for thread safety.

    Attributes:
        message_id (Optional[int]): ID of last sent message
        chat_id (Optional[Union[int, str]]): Target chat/channel ID
        thread_id (Optional[int]): Message thread ID if applicable
        priority (MessagePriority): Message priority level
        retry_count (int): Number of retry attempts
        last_error (Optional[str]): Last error message
        last_update (float): Timestamp of last state update
        _lock (asyncio.Lock): Thread synchronization lock

    Example:
        >>> state = NotificationState(chat_id="123456789")
        >>> async with state._lock:
        ...     state.message_id = 42
        ...     state.retry_count += 1
    """

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

        Updates multiple state attributes atomically within a lock.

        Args:
            **kwargs: State attributes to update:
                - message_id: New message ID
                - chat_id: New chat ID
                - thread_id: New thread ID
                - priority: New priority level
                - retry_count: New retry count
                - last_error: New error message

        Example:
            >>> await state.update(
            ...     message_id=42,
            ...     retry_count=1,
            ...     last_error="Network timeout"
            ... )
        """
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.last_update = datetime.now().timestamp()

    async def increment_retry(self) -> int:
        """Thread-safe retry count increment.

        Atomically increments the retry counter and returns new value.

        Returns:
            int: New retry count after increment

        Example:
            >>> count = await state.increment_retry()
            >>> print(f"Retry attempt {count}")
        """
        async with self._lock:
            self.retry_count += 1
            return self.retry_count

    async def reset(self) -> None:
        """Thread-safe state reset.

        Resets all state attributes to their default values atomically.

        Example:
            >>> await state.reset()  # Reset after successful operation
        """
        async with self._lock:
            self.message_id = None
            self.retry_count = 0
            self.last_error = None
            self.last_update = datetime.now().timestamp()


class InlineKeyboardButton(TypedDict, total=False):
    """Telegram inline keyboard button configuration.

    Structure for configuring individual buttons in an inline keyboard.
    At least one of url, callback_data, or other optional fields must
    be specified along with the text.

    Fields:
        text (str): Label text shown on the button
        url (Optional[str]): URL to open when pressed
        callback_data (Optional[str]): Data sent to bot when pressed
        switch_inline_query (Optional[str]): Query for inline mode
        switch_inline_query_current_chat (Optional[str]): Current chat query

    Example:
        >>> button = InlineKeyboardButton(
        ...     text="Visit Website",
        ...     url="https://example.com"
        ... )
        >>> button = InlineKeyboardButton(
        ...     text="Confirm",
        ...     callback_data="action:confirm"
        ... )
    """
    text: str                       # Button text (required)
    url: Optional[str]              # Optional URL to open
    callback_data: Optional[str]    # Optional callback data
    switch_inline_query: Optional[str]  # Query for inline mode
    switch_inline_query_current_chat: Optional[str]  # Current chat query


class InlineKeyboardMarkup(TypedDict):
    """Telegram inline keyboard layout structure.

    Defines the layout of buttons in an inline keyboard. Buttons are
    arranged in rows and columns, with each button being an
    InlineKeyboardButton instance.

    Fields:
        inline_keyboard (List[List[InlineKeyboardButton]]): Grid of buttons:
            - Outer list represents rows
            - Inner lists represent buttons in each row

    Example:
        >>> keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        ...     {"text": "Yes", "callback_data": "yes"},
        ...     {"text": "No", "callback_data": "no"}
        ... ], [
        ...     {"text": "Cancel", "callback_data": "cancel"}
        ... ]])
    """
    inline_keyboard: List[List[InlineKeyboardButton]]


class SendMessageRequest(TypedDict, total=False):
    """Telegram sendMessage API request parameters.

    Structure for sending new messages via Telegram Bot API. All fields
    except chat_id and text are optional.

    Fields:
        chat_id (Union[int, str]): Target chat/channel ID
        text (str): Message text content
        parse_mode (Optional[ParseMode]): Text formatting mode
        entities (Optional[List[MessageEntity]]): Text formatting entities
        disable_notification (Optional[bool]): Mute notification
        protect_content (Optional[bool]): Prevent forwarding
        message_thread_id (Optional[int]): Thread to reply in
        reply_markup (Optional[InlineKeyboardMarkup]): Inline keyboard

    Example:
        >>> request = SendMessageRequest(
        ...     chat_id="123456789",
        ...     text="Hello!",
        ...     parse_mode="HTML",
        ...     disable_notification=True
        ... )
    """
    chat_id: Union[int, str]
    text: str
    parse_mode: Optional[ParseMode]
    entities: Optional[List[MessageEntity]]
    disable_notification: Optional[bool]
    protect_content: Optional[bool]
    message_thread_id: Optional[int]
    reply_markup: Optional[InlineKeyboardMarkup]


class EditMessageRequest(TypedDict, total=False):
    """Telegram editMessageText API request parameters.

    Structure for editing existing messages via Telegram Bot API.
    Both chat_id and message_id are required to identify the message.

    Fields:
        chat_id (Union[int, str]): Chat/channel with message
        message_id (int): ID of message to edit
        text (str): New message text
        parse_mode (Optional[ParseMode]): Text formatting mode
        entities (Optional[List[MessageEntity]]): Text formatting entities
        message_thread_id (Optional[int]): Thread containing message
        reply_markup (Optional[InlineKeyboardMarkup]): New keyboard

    Example:
        >>> request = EditMessageRequest(
        ...     chat_id="123456789",
        ...     message_id=42,
        ...     text="Updated text",
        ...     parse_mode="HTML"
        ... )
    """
    chat_id: Union[int, str]
    message_id: int
    text: str
    parse_mode: Optional[ParseMode]
    entities: Optional[List[MessageEntity]]
    message_thread_id: Optional[int]
    reply_markup: Optional[InlineKeyboardMarkup]


class DeleteMessageRequest(TypedDict, total=False):
    """Telegram deleteMessage API request parameters.

    Structure for deleting messages via Telegram Bot API.
    Both chat_id and message_id are required.

    Fields:
        chat_id (Union[int, str]): Chat/channel with message
        message_id (int): ID of message to delete
        message_thread_id (Optional[int]): Thread containing message

    Example:
        >>> request = DeleteMessageRequest(
        ...     chat_id="123456789",
        ...     message_id=42
        ... )
    """
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
"""Pre-defined message templates with HTML formatting.

Templates use a tree-style format with UTF-8 box drawing characters
and emoji indicators. All templates support HTML formatting tags.

Available Templates:
    progress: Transfer progress updates with:
        - Current progress percentage
        - Transfer speed
        - Remaining amount
        - Elapsed time
        - Estimated completion time

    completion: Transfer completion status with:
        - Total transferred size
        - Operation duration
        - Average transfer speed
        - Number of files processed

    error: Error notification with:
        - Error description
        - Detailed error information
        - Current retry attempt count

    warning: Warning message with:
        - Warning message text

Example:
    >>> from notifications.telegram.templates import DEFAULT_TEMPLATES
    >>> print(DEFAULT_TEMPLATES["progress"].format(
    ...     percent=75.5,
    ...     speed="1.2 MB",
    ...     remaining="500 MB",
    ...     elapsed="10 minutes",
    ...     eta="15:30"
    ... ))
    📊 Transfer Progress
    ├ Progress: 75.5%
    ├ Speed: 1.2 MB/s
    ├ Remaining: 500 MB
    ├ Elapsed: 10 minutes
    └ ETA: 15:30
"""


def create_progress_keyboard(percent: float) -> InlineKeyboardMarkup:
    """Create an inline keyboard showing transfer progress.

    Generates a keyboard with a visual progress bar and percentage
    indicator. The progress bar uses Unicode block characters to
    create a graphical representation of the progress.

    Args:
        percent (float): Progress percentage between 0 and 100

    Returns:
        InlineKeyboardMarkup: Keyboard with progress bar and controls:
            - Progress bar button (non-interactive)
            - Percentage indicator
            - Cancel button

    Raises:
        ValueError: If percent is not between 0 and 100

    Example:
        >>> keyboard = create_progress_keyboard(75.5)
        >>> print(keyboard)
        {
            'inline_keyboard': [
                [{'text': '███████░░░', 'callback_data': 'progress_75.5'}],
                [
                    {'text': '75.5%', 'callback_data': 'percent'},
                    {'text': 'Cancel', 'callback_data': 'cancel'}
                ]
            ]
        }

    Note:
        The progress bar uses:
        - █ (U+2588) for completed segments
        - ░ (U+2591) for remaining segments
        - Total width is limited by BUTTONS_PER_ROW
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
    """Validate and optionally truncate message text length.

    Ensures that message text complies with Telegram's length limits.
    Can either truncate text that exceeds the limit or raise an error.

    Args:
        text (str): Message text to validate
        limit (int): Maximum allowed length (default: MESSAGE_TEXT)
        truncate (bool): Whether to truncate long text (default: True)

    Returns:
        str: Validated (and possibly truncated) message text

    Raises:
        ValueError: If text is empty
        ValueError: If text exceeds limit and truncate is False

    Example:
        >>> # Truncate long message
        >>> text = "A" * 5000
        >>> short = validate_message_length(text, limit=100)
        >>> len(short) <= 100
        True

        >>> # Raise error for long message
        >>> try:
        ...     validate_message_length(text, limit=100, truncate=False)
        ... except ValueError as e:
        ...     print(str(e))
        Message length 5000 exceeds limit of 100

    Note:
        When truncating, the function:
        1. Preserves the first 85% of the limit
        2. Adds "..." separator
        3. Preserves the last 15% of the limit
    """
    if not text:
        raise ValueError(ErrorMessages.EMPTY_MESSAGE)

    text_length = len(text)
    if text_length <= limit:
        return text

    if not truncate:
        raise ValueError(ErrorMessages.MESSAGE_TOO_LONG.format(
            length=text_length,
            limit=limit
        ))

    # Calculate preserved portions
    preserve_start = int(limit * 0.85)
    preserve_end = limit - preserve_start - 3  # 3 for "..."

    return f"{text[:preserve_start]}...{text[-preserve_end:]}"
