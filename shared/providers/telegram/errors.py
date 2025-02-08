# shared/providers/telegram/errors.py

"""Telegram-specific error types."""

from typing import Any, Dict, Optional


class TelegramError(Exception):
    """Base class for Telegram-related errors."""

    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.context = context or {}
        super().__init__(message)


class TelegramApiError(TelegramError):
    """Raised when Telegram API returns an error."""
    pass


class TelegramRateLimitError(TelegramError):
    """Raised when hitting Telegram API rate limits."""
    pass


class TelegramValidationError(TelegramError):
    """Raised when Telegram-specific validation fails."""
    pass
