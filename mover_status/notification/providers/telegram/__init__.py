"""
Telegram notification provider package.

This package provides the implementation of the Telegram notification provider.
"""

from .defaults import TELEGRAM_DEFAULTS
from .formatter import (
    format_html_text,
    format_telegram_eta,
    format_telegram_message,
    format_timestamp_for_telegram,
)
from .provider import TelegramProvider

__all__ = [
    "TELEGRAM_DEFAULTS",
    "TelegramProvider",
    "format_html_text",
    "format_telegram_eta",
    "format_telegram_message",
    "format_timestamp_for_telegram",
]