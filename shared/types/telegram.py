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
from typing import Dict, List, Literal, Optional, TypedDict, Union


class ParseMode(StrEnum):
    """Telegram message parsing modes."""
    HTML = "HTML"
    MARKDOWN = "MarkdownV2"
    NONE = "None"


class ChatType(StrEnum):
    """Telegram chat types."""
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"


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


class MessageEntity(TypedDict, total=False):
    """Telegram message entity structure."""
    type: MessageEntityType
    offset: int               # In UTF-16 code units
    length: int              # In UTF-16 code units
    url: Optional[str]       # For "text_link" only
    user: Optional[Dict]     # For "text_mention" only
    language: Optional[str]  # For "pre" only
    custom_emoji_id: Optional[str]  # For "custom_emoji" only


class InlineKeyboardButton(TypedDict, total=False):
    """Telegram inline keyboard button structure."""
    text: str
    url: Optional[str]
    callback_data: Optional[str]
    web_app: Optional[Dict[str, str]]
    login_url: Optional[Dict[str, str]]
    switch_inline_query: Optional[str]
    switch_inline_query_current_chat: Optional[str]


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
    is_premium: Optional[bool]
    added_to_attachment_menu: Optional[bool]


class Chat(TypedDict, total=False):
    """Telegram chat structure."""
    id: int
    type: Literal["private", "group", "supergroup", "channel"]
    title: Optional[str]
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    is_forum: Optional[bool]
    active_usernames: Optional[List[str]]


class Message(TypedDict, total=False):
    """Telegram message structure."""
    message_id: int
    message_thread_id: Optional[int]
    from_user: Optional[User]
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


def create_mention(user_id: int, name: str) -> MessageEntity:
    """Create a text_mention entity for a user.

    Args:
        user_id: Telegram user ID
        name: Display name for the mention

    Returns:
        MessageEntity: Formatted text_mention entity

    Example:
        >>> mention = create_mention(123456789, "John")
        >>> message_text = f"Hello {name}!"
        >>> message_entities = [mention]
    """
    return {
        "type": MessageEntityType.TEXT_MENTION,
        "offset": 0,  # Caller must set correct offset
        "length": len(name),
        "user": {"id": user_id, "first_name": name}
    }


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
    limit: MessageLimit = MessageLimit.MESSAGE_TEXT
) -> bool:
    """Validate message length against Telegram limits.

    Args:
        text: Text to validate
        limit: Maximum length limit to check against

    Returns:
        bool: True if text is within limit

    Raises:
        ValueError: If text exceeds limit or is empty
    """
    if not text:
        raise ValueError("Text cannot be empty")

    length = calculate_utf16_length(text)
    if length > limit:
        raise ValueError(f"Text exceeds {limit} UTF-16 code units")

    return True
