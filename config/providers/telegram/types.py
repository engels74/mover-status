# config/providers/telegram/types.py

"""
Type definitions specific to Telegram provider configuration.
Extends shared types with provider-specific structures and constraints.

Example:
    >>> from config.providers.telegram.types import ChatType, SendMessageRequest
    >>> request = SendMessageRequest(chat_id="123", text="Hello", parse_mode="HTML")
"""

from enum import IntEnum
from typing import List, Optional, TypedDict, Union

from config.constants import Errors, JsonDict
from shared.providers.telegram import (
    ChatType as SharedChatType,
)
from shared.providers.telegram import (
    InlineKeyboardMarkup,
    MessageEntity,
    ParseMode,
)
from shared.providers.telegram import (
    MessageLimit as SharedMessageLimit,
)

# Use shared types to avoid duplication
ChatType = SharedChatType
MessageLimit = SharedMessageLimit


class MessagePriority(IntEnum):
    """Message priority levels for notifications."""
    SILENT = 0     # No notification
    NORMAL = 1     # Default notification
    URGENT = 2     # Priority notification (bypasses mute)


class BotPermissions(IntEnum):
    """Required bot permissions for different features."""
    SEND_MESSAGES = 1
    EDIT_MESSAGES = 2
    DELETE_MESSAGES = 4
    CREATE_POSTS = 8
    INVITE_USERS = 16
    PIN_MESSAGES = 32
    MANAGE_TOPICS = 64


class SendMessageRequest(TypedDict, total=False):
    """Telegram sendMessage request structure."""
    chat_id: Union[int, str]
    text: str
    parse_mode: Optional[ParseMode]
    entities: Optional[List[MessageEntity]]
    disable_web_page_preview: Optional[bool]
    disable_notification: Optional[bool]
    protect_content: Optional[bool]
    message_thread_id: Optional[int]
    reply_markup: Optional[InlineKeyboardMarkup]


class EditMessageRequest(TypedDict, total=False):
    """Telegram editMessageText request structure."""
    chat_id: Union[int, str]
    message_id: int
    text: str
    parse_mode: Optional[ParseMode]
    entities: Optional[List[MessageEntity]]
    disable_web_page_preview: Optional[bool]
    reply_markup: Optional[InlineKeyboardMarkup]


class DeleteMessageRequest(TypedDict, total=False):
    """Telegram deleteMessage request structure."""
    chat_id: Union[int, str]
    message_id: int


class ProviderError(TypedDict, total=False):
    """Provider error response structure."""
    code: int
    message: str
    retry_after: Optional[int]
    parameters: Optional[JsonDict]


class BotCommand(TypedDict, total=False):
    """Bot command configuration structure."""
    command: str
    description: str
    permissions: Optional[List[BotPermissions]]


# Provider-specific rate limiting configuration
RATE_LIMIT = {
    "max_retries": 5,
    "retry_delay": 1,
    "per_second": MessageLimit.MESSAGES_PER_SECOND,
    "per_minute": MessageLimit.MESSAGES_PER_MINUTE
}


def create_progress_keyboard(percent: float) -> InlineKeyboardMarkup:
    """Create inline keyboard with progress information.

    Args:
        percent: Progress percentage (0-100)

    Returns:
        InlineKeyboardMarkup: Progress keyboard markup

    Raises:
        ValueError: If percent is not between 0 and 100
    """
    if not 0 <= percent <= 100:
        raise ValueError(Errors.INVALID_PERCENTAGE.format(value=percent))

    # Create progress bar
    total_slots = MessageLimit.BUTTONS_PER_ROW
    filled = int(percent * total_slots / 100)
    empty = total_slots - filled

    # Build keyboard layout
    keyboard: List[List[JsonDict]] = [
        [
            {"text": "█" * filled + "░" * empty, "callback_data": f"progress_{percent}"}
        ],
        [
            {"text": f"{percent:.1f}%", "callback_data": "percent"},
            {"text": "Cancel", "callback_data": "cancel"}
        ]
    ]

    return {"inline_keyboard": keyboard}


def validate_chat_id(chat_id: Union[int, str]) -> bool:
    """Validate Telegram chat ID format.

    Args:
        chat_id: Chat ID to validate

    Returns:
        bool: True if chat ID is valid

    Example:
        >>> validate_chat_id("-1001234567890")
        True
        >>> validate_chat_id("@channelname")
        True
    """
    if isinstance(chat_id, int):
        return True

    if isinstance(chat_id, str):
        # Channel username format
        if chat_id.startswith("@"):
            username = chat_id[1:]
            return (
                len(username) <= MessageLimit.USERNAME_LENGTH and
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
