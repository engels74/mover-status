# notifications/providers/telegram/__init__.py

"""
Telegram bot notification provider package.
Provides functionality for sending notifications via Telegram Bot API.

Example:
    >>> from notifications.telegram import TelegramConfig, TelegramProvider
    >>> config = TelegramConfig(
    ...     bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    ...     chat_id="-1001234567890"
    ... )
    >>> provider = TelegramProvider(config.to_provider_config())
    >>> async with provider:
    ...     await provider.notify_progress(75.5, "1.2 GB", "2 hours", "15:30")
"""

from typing import TYPE_CHECKING

from notifications.providers.telegram.config import TelegramConfig
from notifications.providers.telegram.provider import TelegramError, TelegramProvider
from notifications.providers.telegram.types import ParseMode

if TYPE_CHECKING:
    from notifications.providers.telegram.templates import (
        create_completion_message,
        create_custom_message,
        create_error_message,
        create_progress_message,
    )
    from notifications.providers.telegram.types import (
        ChatType,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        MessageEntity,
        MessageLimit,
        MessagePriority,
        SendMessageRequest,
    )

__all__ = [
    # Main classes
    "TelegramProvider",
    "TelegramConfig",
    # Exceptions
    "TelegramError",
    # Enums and constants
    "ParseMode",
    # Template functions
    "create_completion_message",
    "create_error_message",
    "create_progress_message",
    "create_custom_message",
    # Type definitions
    "MessageEntity",
    "MessageLimit",
    "SendMessageRequest",
    "InlineKeyboardButton",
    "InlineKeyboardMarkup",
    "MessagePriority",
    "ChatType",
]

__version__ = "0.1.0"
__author__ = "engels74"
__description__ = "Telegram bot notification provider for MoverStatus"

# Version information for the provider
VERSION_INFO = {
    "major": 0,
    "minor": 1,
    "patch": 0,
    "release": None,  # e.g., "alpha", "beta", "rc1"
}

def get_version() -> str:
    """Get current version string.

    Returns:
        str: Version string
    """
    version = f"{VERSION_INFO['major']}.{VERSION_INFO['minor']}.{VERSION_INFO['patch']}"
    if VERSION_INFO['release']:
        version += f"-{VERSION_INFO['release']}"
    return version

def is_available() -> bool:
    """Check if provider requirements are met.

    Returns:
        bool: True if provider can be used
    """
    try:
        import aiohttp  # noqa: F401
        return True
    except ImportError:
        return False
