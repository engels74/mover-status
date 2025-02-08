# config/providers/telegram/types.py

"""
Type definitions and utility functions for Telegram bot integration.
This module provides type hints, data structures, and validation functions
specific to the Telegram Bot API implementation.

Components:
- Enums: MessagePriority and BotPermissions for configuration
- TypedDict classes: Request/response structures for API calls
- Utility functions: Chat ID validation and keyboard creation
- Rate limiting configuration

Example:
    >>> from config.providers.telegram.types import ChatType, SendMessageRequest
    >>> request = SendMessageRequest(
    ...     chat_id="-1001234567890",
    ...     text="Hello World",
    ...     parse_mode="HTML",
    ...     disable_notification=True
    ... )
"""

from enum import IntEnum
from typing import List, TypedDict, Union

from config.constants import JsonDict
from shared.providers.telegram import (
    ChatType as SharedChatType,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from shared.providers.telegram import (
    MessageLimit as SharedMessageLimit,
    ApiLimit,
)

# Use shared types to avoid duplication
ChatType = SharedChatType
MessageLimit = SharedMessageLimit


class MessagePriority(IntEnum):
    """Message priority levels for controlling notification behavior.

    Defines the notification behavior when sending messages:
    - SILENT: Message is delivered without any notification
    - NORMAL: Standard notification with default system settings
    - URGENT: High-priority notification that bypasses mute settings
    """
    SILENT = 0     # No notification
    NORMAL = 1     # Default notification
    URGENT = 2     # Priority notification (bypasses mute)


class BotPermissions(IntEnum):
    """Required bot permissions for different Telegram API features.

    Defines the permission flags needed for various bot operations:
    - Basic messaging: SEND_MESSAGES, EDIT_MESSAGES, DELETE_MESSAGES
    - Channel management: CREATE_POSTS, INVITE_USERS, PIN_MESSAGES
    - Forum features: MANAGE_TOPICS
    """
    SEND_MESSAGES = 1
    EDIT_MESSAGES = 2
    DELETE_MESSAGES = 4
    CREATE_POSTS = 8
    INVITE_USERS = 16
    PIN_MESSAGES = 32
    MANAGE_TOPICS = 64


class SendMessageRequest(TypedDict, total=False):
    """Type definition for Telegram sendMessage API request.

    Attributes:
        chat_id (Union[int, str]): Unique identifier for the target chat
        text (str): Message text to send (1-4096 characters)
        parse_mode (Optional[ParseMode]): Text formatting mode (HTML/Markdown)
        entities (Optional[List[MessageEntity]]): Special entities in message
        disable_web_page_preview (Optional[bool]): Disable link previews
        disable_notification (Optional[bool]): Send silently
        protect_content (Optional[bool]): Prevent forwarding/saving
        message_thread_id (Optional[int]): Thread ID for forum topics
        reply_markup (Optional[InlineKeyboardMarkup]): Inline keyboard

    Example:
        >>> msg = SendMessageRequest(
        ...     chat_id="@channel",
        ...     text="Status update",
        ...     parse_mode="HTML",
        ...     protect_content=True
        ... )
    """


class EditMessageRequest(TypedDict, total=False):
    """Type definition for Telegram editMessageText API request.

    Attributes:
        chat_id (Union[int, str]): Chat containing message to edit
        message_id (int): Identifier of message to edit
        text (str): New text content (1-4096 characters)
        parse_mode (Optional[ParseMode]): Text formatting mode
        entities (Optional[List[MessageEntity]]): Special entities
        disable_web_page_preview (Optional[bool]): Disable link previews
        reply_markup (Optional[InlineKeyboardMarkup]): Updated keyboard
    """


class DeleteMessageRequest(TypedDict, total=False):
    """Type definition for Telegram deleteMessage API request.

    Attributes:
        chat_id (Union[int, str]): Chat containing message to delete
        message_id (int): Identifier of message to delete

    Note:
        Messages can only be deleted if they were sent less than 48 hours ago.
        Bots can delete their own messages in groups and channels.
    """


class ProviderError(TypedDict, total=False):
    """Type definition for Telegram API error responses.

    Attributes:
        code (int): Error code from Telegram API
        message (str): Human-readable error description
        retry_after (Optional[int]): Seconds to wait before retry
        parameters (Optional[JsonDict]): Additional error details

    Note:
        Common error codes:
        - 400: Bad Request (invalid parameters)
        - 401: Unauthorized (invalid token)
        - 429: Too Many Requests (rate limit)
    """


class BotCommand(TypedDict, total=False):
    """Type definition for Telegram bot command configuration.

    Attributes:
        command (str): Command name without leading slash
        description (str): Command description (3-256 characters)
        permissions (Optional[List[BotPermissions]]): Required permissions

    Example:
        >>> cmd = BotCommand(
        ...     command="start",
        ...     description="Start the bot",
        ...     permissions=[BotPermissions.SEND_MESSAGES]
        ... )
    """


# Provider-specific rate limiting configuration
RATE_LIMIT = {
    "max_retries": 5,  # Maximum number of retry attempts
    "retry_delay": 1,  # Delay between retries in seconds
    "per_second": MessageLimit.MESSAGES_PER_SECOND,  # Messages per second limit
    "per_minute": MessageLimit.MESSAGES_PER_MINUTE   # Messages per minute limit
}


def create_progress_keyboard(percent: float) -> InlineKeyboardMarkup:
    """Create an inline keyboard with a visual progress indicator.

    Generates a keyboard with a progress bar using Unicode block characters
    and percentage display. The keyboard can be attached to messages to show
    progress updates.

    Args:
        percent (float): Progress percentage between 0 and 100

    Returns:
        InlineKeyboardMarkup: Keyboard markup with progress bar

    Raises:
        ValueError: If percent is outside the valid range [0, 100]

    Example:
        >>> keyboard = create_progress_keyboard(75.5)
        >>> message = SendMessageRequest(
        ...     chat_id="@channel",
        ...     text="Processing...",
        ...     reply_markup=keyboard
        ... )
    """
    if not 0 <= percent <= 100:
        raise ValueError(f"Invalid percentage value: {percent}")

    # Create progress bar
    total_slots = MessageLimit.BUTTONS_PER_ROW
    filled = int(percent * total_slots / 100)
    empty = total_slots - filled

    # Build keyboard layout with proper typing
    keyboard: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="█" * filled + "░" * empty, callback_data=f"progress_{percent}")
        ],
        [
            InlineKeyboardButton(text=f"{percent:.1f}%", callback_data="percent"),
            InlineKeyboardButton(text="Cancel", callback_data="cancel")
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def validate_chat_id(chat_id: Union[int, str]) -> bool:
    """Validate Telegram chat ID format according to API specifications.

    Checks if a chat ID matches one of the following formats:
    - Numeric ID for private chats, groups, and channels
    - Username for public channels (starting with @)
    - Negative ID for supergroups and channels
    - Special format for private channels (-100 prefix)

    Args:
        chat_id (Union[int, str]): Chat identifier to validate

    Returns:
        bool: True if chat ID format is valid, False otherwise

    Example:
        >>> validate_chat_id("-1001234567890")  # Channel ID
        True
        >>> validate_chat_id("@channelname")    # Public username
        True
        >>> validate_chat_id("invalid.name")    # Invalid format
        False
    """
    if isinstance(chat_id, int):
        return True

    if isinstance(chat_id, str):
        # Channel username format
        if chat_id.startswith("@"):
            username = chat_id[1:]
            return (
                len(username) <= ApiLimit.USERNAME_LENGTH and
                username.isalnum()
            )

        # Group/channel ID format
        if chat_id.startswith("-100"):
            try:
                int(chat_id)
                return True
            except ValueError:
                return False

        # Private chat ID format
        try:
            int(chat_id)
            return True
        except ValueError:
            return False

    return False
