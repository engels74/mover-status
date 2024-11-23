# config/providers/telegram/types.py

"""
Type definitions specific to Telegram provider configuration.
Extends shared types with provider-specific structures and constraints.

Example:
    >>> from config.providers.telegram.types import ChatType, SendMessageRequest
    >>> request = SendMessageRequest(chat_id="123", text="Hello", parse_mode="HTML")
"""

from enum import IntEnum, StrEnum
from typing import Dict, List, Optional, TypedDict, Union

# Fix: Import ParseMode from shared types instead of redefining
from shared.types.telegram import (
    ChatType as SharedChatType,
    InlineKeyboardMarkup,
    MessageEntity,
    MessageLimit as SharedMessageLimit,
    ParseMode,
)

# Fix: Remove duplicate ChatType enum and use the shared one
ChatType = SharedChatType

# Fix: Remove duplicate MessageLimit and use shared version
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
    message_thread_id: Optional[int]
    text: str
    parse_mode: Optional[ParseMode]
    entities: Optional[List[MessageEntity]]
    disable_notification: Optional[bool]
    protect_content: Optional[bool]
    reply_to_message_id: Optional[int]
    allow_sending_without_reply: Optional[bool]
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

class ProviderError(TypedDict):
    """Provider error response structure."""
    code: int
    message: str
    retry_after: Optional[int]
    parameters: Optional[Dict]

class BotCommand(TypedDict):
    """Bot command configuration structure."""
    command: str
    description: str
    permissions: Optional[List[BotPermissions]]

# Fix: Move rate limiting configuration to constants.py
from config.constants import (
    DEFAULT_API_RETRIES,
    DEFAULT_API_RETRY_DELAY,
)

# Provider-specific rate limiting configuration
RATE_LIMIT = {
    "max_retries": DEFAULT_API_RETRIES,
    "retry_delay": DEFAULT_API_RETRY_DELAY,
    "rate_limit": 20,      # Maximum requests per period
    "rate_period": 60,     # Rate limit period in seconds
}

# Fix: Move templates to telegram/templates.py
from notifications.providers.telegram.templates import DEFAULT_TEMPLATES

# Fix: Add proper type annotations for keyboard creation function
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
        raise ValueError("Percentage must be between 0 and 100")

    progress_blocks = 10
    filled = int(percent / 100 * progress_blocks)
    bar = "▓" * filled + "▒" * (progress_blocks - filled)

    return {
        "inline_keyboard": [[{
            "text": f"{bar} {percent:.1f}%",
            "callback_data": "progress"
        }]]
    }

# Fix: Add proper validation for chat IDs
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
        # Channel username format: @username
        if chat_id.startswith("@"):
            return len(chat_id) > 1 and chat_id[1:].isalnum()

        # Group/channel ID format: -100{9-10 digits}
        if chat_id.startswith("-100"):
            remaining = chat_id[4:]
            return remaining.isdigit() and len(remaining) in (9, 10)

        # Private chat ID format: positive integer
        return chat_id.lstrip("-").isdigit()

    return False
