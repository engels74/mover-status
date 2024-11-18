# notifications\telegram\types.py

"""
Type definitions and constants for Telegram bot notifications.
Defines message structure, API limits, and formatting options for Telegram bot API.

Example:
    >>> from notifications.telegram.types import ParseMode, MessageLimit
    >>> MAX_LENGTH = MessageLimit.MESSAGE_TEXT
    >>> mode = ParseMode.HTML
"""

from enum import Enum, IntEnum
from typing import List, Optional, TypedDict, Union


class ParseMode(str, Enum):
    """Telegram message parsing modes."""
    HTML = "HTML"
    MARKDOWN = "MarkdownV2"
    PLAIN = None


class ChatType(str, Enum):
    """Telegram chat types."""
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"


class MessageEntityType(str, Enum):
    """Telegram message entity types for text formatting."""
    BOLD = "bold"
    ITALIC = "italic"
    CODE = "code"
    PRE = "pre"
    TEXT_LINK = "text_link"
    MENTION = "mention"
    HASHTAG = "hashtag"
    URL = "url"


class MessagePriority(IntEnum):
    """Message priority levels affecting notification behavior."""
    SILENT = 0     # No notification
    NORMAL = 1     # Default notification
    PRIORITY = 2   # Urgent notification (bypasses mute)


class MessageLimit(IntEnum):
    """Telegram API message limits."""
    MESSAGE_TEXT = 4096      # Maximum message text length
    CAPTION_TEXT = 1024      # Maximum media caption length
    MESSAGE_ENTITIES = 100   # Maximum message entities
    MESSAGES_PER_SECOND = 30 # Maximum messages per second
    MESSAGES_PER_MINUTE = 20 # Maximum messages per minute to same chat
    MESSAGE_THREADS = 100    # Maximum message threads per chat


class MessageEntity(TypedDict, total=False):
    """Telegram message entity structure."""
    type: str
    offset: int
    length: int
    url: Optional[str]
    language: Optional[str]


class ReplyMarkup(TypedDict, total=False):
    """Base type for all reply markup options."""
    pass


class InlineKeyboardButton(TypedDict):
    """Telegram inline keyboard button structure."""
    text: str
    url: Optional[str]
    callback_data: Optional[str]


class InlineKeyboardMarkup(ReplyMarkup):
    """Telegram inline keyboard markup structure."""
    inline_keyboard: List[List[InlineKeyboardButton]]


class SendMessageRequest(TypedDict, total=False):
    """Structure for sendMessage API request."""
    chat_id: Union[int, str]
    text: str
    parse_mode: Optional[str]
    entities: Optional[List[MessageEntity]]
    disable_notification: Optional[bool]
    protect_content: Optional[bool]
    reply_markup: Optional[ReplyMarkup]


# Rate Limiting Configuration
RATE_LIMIT = {
    "max_retries": 3,      # Maximum number of retry attempts
    "retry_delay": 5,      # Delay between retries in seconds
    "rate_limit": 20,      # Maximum requests per rate period
    "rate_period": 60,     # Rate limit period in seconds
}

# Default message templates
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

def create_progress_keyboard(percent: float) -> InlineKeyboardMarkup:
    """Create inline keyboard with progress information.

    Args:
        percent: Progress percentage (0-100)

    Returns:
        InlineKeyboardMarkup: Formatted inline keyboard

    Example:
        >>> keyboard = create_progress_keyboard(75.5)
        >>> keyboard["inline_keyboard"]
        [[{"text": "▰▰▰▰▰▰▰▱▱▱ 75.5%", "callback_data": "progress"}]]
    """
    # Create progress bar
    progress_blocks = 10
    filled = int(percent / 100 * progress_blocks)
    bar = "▰" * filled + "▱" * (progress_blocks - filled)

    return {
        "inline_keyboard": [[{
            "text": f"{bar} {percent:.1f}%",
            "callback_data": "progress"
        }]]
    }

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

    Example:
        >>> long_text = "x" * 5000
        >>> validated = validate_message_length(long_text)
        >>> len(validated) <= MessageLimit.MESSAGE_TEXT
        True
    """
    if not text:
        raise ValueError("Message text cannot be empty")

    if len(text) > limit:
        return text[:(limit - 3)] + "..."
    return text
