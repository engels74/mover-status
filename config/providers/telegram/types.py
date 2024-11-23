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

from shared.types.telegram import (
    InlineKeyboardMarkup,
    MessageEntity,
    ParseMode,
)


class ChatType(StrEnum):
    """Telegram chat types for configuration."""
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"


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


# Provider-specific rate limiting configuration
RATE_LIMIT = {
    "max_retries": 3,      # Maximum retry attempts
    "retry_delay": 5,      # Delay between retries in seconds
    "rate_limit": 20,      # Maximum requests per period
    "rate_period": 60,     # Rate limit period in seconds
}

# Default message templates for provider
DEFAULT_TEMPLATES = {
    "progress": (
        "📊 <b>Mover Status</b>\n\n"
        "Progress: <b>{percent}%</b>\n"
        "{progress_bar}\n"
        "Remaining: {remaining_data}\n"
        "Elapsed: {elapsed_time}\n"
        "ETC: {etc}"
    ),
    "completion": "✅ <b>Transfer Complete</b>\n\nAll data has been successfully moved.",
    "error": "❌ <b>Error</b>\n\n{error_message}",
    "warning": "⚠️ <b>Warning</b>\n\n{warning_message}"
}

# Provider configuration defaults
DEFAULT_CONFIG = {
    "parse_mode": ParseMode.HTML,
    "disable_notification": False,
    "protect_content": False,
    "message_thread_id": None,
    "api_base_url": "https://api.telegram.org"
}

# Provider capabilities and requirements
PROVIDER_CAPS = {
    "supports_edit": True,           # Can edit sent messages
    "supports_delete": True,         # Can delete sent messages
    "supports_formatting": True,     # Supports message formatting
    "supports_inline_buttons": True, # Supports inline keyboard buttons
    "required_permissions": [        # Required bot permissions
        BotPermissions.SEND_MESSAGES,
        BotPermissions.EDIT_MESSAGES
    ]
}

def create_progress_keyboard(percent: float) -> InlineKeyboardMarkup:
    """Create inline keyboard with progress information.

    Args:
        percent: Progress percentage (0-100)

    Returns:
        InlineKeyboardMarkup: Progress keyboard markup

    Example:
        >>> keyboard = create_progress_keyboard(75.5)
        >>> keyboard["inline_keyboard"]
        [[{"text": "▓▓▓▓▓▓▓▒▒▒ 75.5%", "callback_data": "progress"}]]
    """
    progress_blocks = 10
    filled = int(percent / 100 * progress_blocks)
    bar = "▓" * filled + "▒" * (progress_blocks - filled)

    return {
        "inline_keyboard": [[{
            "text": f"{bar} {percent:.1f}%",
            "callback_data": "progress"
        }]]
    }

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
            return chat_id[4:].isdigit() and len(chat_id[4:]) in (9, 10)

        # Private chat ID format: positive integer
        return chat_id.isdigit()

    return False

def get_error_message(error: ProviderError) -> str:
    """Get human-readable error message from provider error.

    Args:
        error: Provider error structure

    Returns:
        str: Formatted error message

    Example:
        >>> error = {"code": 429, "message": "Too Many Requests", "retry_after": 30}
        >>> get_error_message(error)
        'Rate limit exceeded. Please wait 30 seconds.'
    """
    if error["code"] == 429:
        retry_after = error.get("retry_after", 60)
        return f"Rate limit exceeded. Please wait {retry_after} seconds."

    return error.get("message", "Unknown error occurred")
