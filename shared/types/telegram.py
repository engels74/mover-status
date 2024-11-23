# shared/types/telegram.py

"""
Shared type definitions for Telegram integration.
Contains types used by both configuration and notification components.

Example:
    >>> from shared.types.telegram import ParseMode, MessageLimit
    >>> mode = ParseMode.HTML
    >>> max_length = MessageLimit.MESSAGE_TEXT
"""

from enum import IntEnum, StrEnum
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union


class ParseMode(StrEnum):
    """Telegram message parsing modes."""
    HTML = "HTML"
    MARKDOWN = "MarkdownV2"
    NONE = "None"


class MessageEntityType(StrEnum):
    """Telegram message entity types."""
    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    CODE = "code"
    PRE = "pre"
    TEXT_LINK = "text_link"
    TEXT_MENTION = "text_mention"
    URL = "url"
    EMAIL = "email"
    PHONE_NUMBER = "phone_number"
    HASHTAG = "hashtag"
    MENTION = "mention"


class MessageLimit(IntEnum):
    """Telegram API message limits."""
    MESSAGE_TEXT = 4096        # Maximum message text length
    CAPTION_TEXT = 1024        # Maximum media caption length
    ENTITIES = 100            # Maximum message entities per message
    BUTTONS_PER_ROW = 8       # Maximum inline keyboard buttons per row
    KEYBOARD_ROWS = 10        # Maximum rows in inline keyboard
    CALLBACK_DATA = 64        # Maximum callback data length
    BUTTON_TEXT = 64          # Maximum button text length
    MESSAGES_PER_SECOND = 30  # Maximum messages per second (bot API)
    MESSAGES_PER_MINUTE = 20  # Maximum messages per minute per chat


class ApiLimits(IntEnum):
    """Telegram Bot API limits."""
    FILE_UPLOAD = 50 * 1024 * 1024  # Maximum file upload size (50MB)
    RETRY_AFTER = 60                # Maximum retry after time in seconds
    WEBHOOK_SIZE = 2 * 1024         # Maximum webhook payload size in bytes
    USERNAME_LENGTH = 32            # Maximum bot username length
    CHAT_ID_LENGTH = 14            # Maximum chat ID length


class MessageEntity(TypedDict, total=False):
    """Telegram message entity structure."""
    type: MessageEntityType
    offset: int
    length: int
    url: Optional[str]
    user: Optional[Dict]
    language: Optional[str]


class InlineKeyboardButton(TypedDict, total=False):
    """Telegram inline keyboard button structure."""
    text: str
    url: Optional[str]
    callback_data: Optional[str]
    web_app: Optional[Dict]
    login_url: Optional[Dict]
    switch_inline_query: Optional[str]
    switch_inline_query_current_chat: Optional[str]
    callback_game: Optional[Dict]
    pay: Optional[bool]


class InlineKeyboardMarkup(TypedDict):
    """Telegram inline keyboard markup structure."""
    inline_keyboard: List[List[InlineKeyboardButton]]


class User(TypedDict, total=False):
    """Telegram user structure."""
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str]
    username: Optional[str]
    language_code: Optional[str]


class Chat(TypedDict, total=False):
    """Telegram chat structure."""
    id: int
    type: Literal["private", "group", "supergroup", "channel"]
    title: Optional[str]
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]


class Message(TypedDict, total=False):
    """Telegram message structure."""
    message_id: int
    from_user: Optional[User]
    chat: Chat
    date: int
    text: Optional[str]
    entities: Optional[List[MessageEntity]]
    reply_markup: Optional[InlineKeyboardMarkup]


class Response(TypedDict):
    """Telegram API response structure."""
    ok: bool
    result: Optional[Union[Message, bool, List[Any]]]
    error_code: Optional[int]
    description: Optional[str]


# Rate limiting configuration
RATE_LIMIT = {
    "max_retries": 3,      # Maximum number of retry attempts
    "retry_delay": 5,      # Delay between retries in seconds
    "rate_limit": 20,      # Maximum requests per rate period
    "rate_period": 60,     # Rate limit period in seconds
}

# Default templates for message formatting
DEFAULT_TEMPLATES = {
    "progress": (
        "📊 <b>Transfer Progress</b>\n"
        "├ Progress: <b>{percent}%</b>\n"
        "├ Remaining: {remaining_data}\n"
        "├ Elapsed: {elapsed_time}\n"
        "└ ETC: {etc}"
    ),
    "completion": "✅ <b>Transfer Complete!</b>\nAll data has been successfully moved.",
    "error": "❌ <b>Transfer Error</b>\n{error_message}"
}

def format_progress_bar(percent: float, width: int = 10) -> str:
    """Create progress bar string for Telegram messages.

    Args:
        percent: Progress percentage (0-100)
        width: Width of progress bar in characters

    Returns:
        str: Formatted progress bar string

    Example:
        >>> format_progress_bar(75.5)
        '▓▓▓▓▓▓▓▒▒▒'
    """
    filled = int(width * percent / 100)
    return "▓" * filled + "▒" * (width - filled)


def validate_message_length(
    text: str,
    limit: MessageLimit = MessageLimit.MESSAGE_TEXT
) -> str:
    """Validate and truncate message if needed.

    Args:
        text: Message text to validate
        limit: Maximum length limit to apply

    Returns:
        str: Validated message text

    Raises:
        ValueError: If text is empty
    """
    if not text:
        raise ValueError("Message text cannot be empty")

    if len(text) > limit:
        return text[:(limit - 3)] + "..."
    return text
