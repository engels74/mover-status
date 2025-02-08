# shared/providers/telegram/types.py

"""
Shared type definitions for Telegram integration.
Contains types used by both configuration and notification components.
Provides constants, TypedDict classes, and utility functions for Telegram Bot API.

Example:
    >>> from shared.providers.telegram import ParseMode, MessageLimit
    >>> mode = ParseMode.HTML
    >>> max_length = MessageLimit.MESSAGE_TEXT
"""

from enum import IntEnum, StrEnum
from typing import Dict, List, Optional, TypedDict, Union


class ParseMode(StrEnum):
    """Telegram message parsing modes."""
    HTML = "HTML"
    MARKDOWN = "MarkdownV2"
    MARKDOWN_LEGACY = "Markdown"  # Added for compatibility
    NONE = ""


class ChatType(StrEnum):
    """Telegram chat types."""
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"


class MessageEntityType(StrEnum):
    """Telegram message entity types for formatting."""
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
    CASHTAG = "cashtag"
    MENTION = "mention"
    CUSTOM_EMOJI = "custom_emoji"


class MessageLimit(IntEnum):
    """Telegram API message limits."""
    MESSAGE_TEXT = 4096        # UTF-16 code units
    CAPTION_TEXT = 1024        # UTF-16 code units
    ENTITIES = 100            # Maximum entities per message
    BUTTONS_PER_ROW = 8       # Maximum inline keyboard buttons per row
    KEYBOARD_ROWS = 10        # Maximum rows in inline keyboard
    CALLBACK_DATA = 64        # Maximum callback data length
    BUTTON_TEXT = 64          # Maximum button text length
    MESSAGES_PER_MINUTE = 30  # Rate limit per chat
    MESSAGES_PER_SECOND = 30  # Global rate limit
    MEDIA_GROUP_SIZE = 10     # Maximum media items in group


class ApiLimit(IntEnum):
    """Telegram Bot API limits."""
    FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    CAPTION_LENGTH = 1024
    MEDIA_GROUP_SIZE = 10
    POLL_OPTIONS = 10
    DEEP_LINK_LENGTH = 64
    USERNAME_LENGTH = 32


class User(TypedDict, total=False):
    """Telegram user information."""
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str]
    username: Optional[str]
    language_code: Optional[str]
    is_premium: Optional[bool]
    added_to_attachment_menu: Optional[bool]


class Chat(TypedDict, total=False):
    """Telegram chat information."""
    id: int
    type: ChatType
    title: Optional[str]
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    is_forum: Optional[bool]
    active_usernames: Optional[List[str]]


class MessageEntity(TypedDict, total=False):
    """Telegram message entity for text formatting."""
    type: MessageEntityType
    offset: int               # UTF-16 code units
    length: int              # UTF-16 code units
    url: Optional[str]       # For "text_link" only
    user: Optional[User]     # For "text_mention" only
    language: Optional[str]  # For "pre" only
    custom_emoji_id: Optional[str]  # For "custom_emoji" only


class InlineKeyboardButton(TypedDict, total=False):
    """Telegram inline keyboard button."""
    text: str
    url: Optional[str]
    callback_data: Optional[str]
    web_app: Optional[Dict[str, str]]
    login_url: Optional[Dict[str, str]]
    switch_inline_query: Optional[str]
    switch_inline_query_current_chat: Optional[str]


class InlineKeyboardMarkup(TypedDict):
    """Telegram inline keyboard markup."""
    inline_keyboard: List[List[InlineKeyboardButton]]


class Message(TypedDict, total=False):
    """Telegram message structure."""
    message_id: int
    message_thread_id: Optional[int]
    from_user: Optional[User]  # Changed from 'from' to 'from_user' for Python compat
    sender_chat: Optional[Chat]
    date: int
    chat: Chat
    text: Optional[str]
    entities: Optional[List[MessageEntity]]
    reply_markup: Optional[InlineKeyboardMarkup]


class Response(TypedDict):
    """Telegram API response structure."""
    ok: bool
    result: Optional[Union[Message, bool, List[Dict]]]
    error_code: Optional[int]
    description: Optional[str]
    parameters: Optional[Dict]


def calculate_utf16_length(text: str) -> int:
    """Calculate text length in UTF-16 code units.

    Args:
        text: Text to measure

    Returns:
        int: Length in UTF-16 code units

    Example:
        >>> calculate_utf16_length("Hello 👋")
        7  # 5 BMP chars + 2 surrogate pairs for emoji
    """
    return len(text.encode('utf-16-le')) // 2


def validate_message_length(
    text: str,
    limit: int = MessageLimit.MESSAGE_TEXT,
    truncate: bool = False,
) -> str:
    """Validate message length against Telegram limits.

    Args:
        text: Text to validate
        limit: Maximum length limit to check against
        truncate: Whether to truncate text if too long

    Returns:
        str: Original or truncated text

    Raises:
        ValueError: If text exceeds limit and truncate is False

    Example:
        >>> text = "x" * 5000
        >>> result = validate_message_length(text, truncate=True)
        >>> len(result) <= MessageLimit.MESSAGE_TEXT
        True
    """
    if not text:
        raise ValueError("Text cannot be empty")

    length = calculate_utf16_length(text)
    if length <= limit:
        return text

    if truncate:
        # Find a position that ensures UTF-16 length is within limit
        pos = 0
        while calculate_utf16_length(text[:pos] + "...") <= limit:
            pos += 1
        return text[:pos - 1] + "..."

    raise ValueError(f"Text exceeds {limit} UTF-16 code units")


__all__ = [
    # Enums
    "ParseMode",
    "ChatType",
    "MessageEntityType",
    "MessageLimit",
    "ApiLimit",
    # TypedDicts
    "User",
    "Chat",
    "MessageEntity",
    "InlineKeyboardButton",
    "InlineKeyboardMarkup",
    "Message",
    "Response",
    # Functions
    "calculate_utf16_length",
    "validate_message_length",
]
