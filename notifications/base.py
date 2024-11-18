# notifications/base.py

"""
Abstract base notification provider implementation.
Defines the interface and common functionality for all notification providers.
Handles rate limiting, error handling, and message formatting.

Example:
    class DiscordProvider(NotificationProvider):
        async def send_notification(self, message: str) -> bool:
            # Discord-specific implementation
            webhook_data = self._format_message(message)
            return await self._send_webhook(webhook_data)
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from structlog import get_logger

from config.constants import (
    NOTIFICATION_RETRY_ATTEMPTS,
    NOTIFICATION_RETRY_DELAY,
)
from core.calculator import TransferStats
from utils.formatters import format_duration, format_size, format_template

logger = get_logger(__name__)


class NotificationError(Exception):
    """Base exception for notification-related errors."""


class RateLimitExceeded(NotificationError):
    """Raised when rate limit is exceeded."""


class MessageFormatError(NotificationError):
    """Raised when message formatting fails."""


class NotificationProvider(ABC):
    """
    Abstract base class for notification providers.
    Implements common functionality and defines required interface.
    """

    def __init__(
        self,
        rate_limit: int = 1,
        rate_period: int = 60,
        retry_attempts: int = NOTIFICATION_RETRY_ATTEMPTS,
        retry_delay: int = NOTIFICATION_RETRY_DELAY,
    ):
        """Initialize notification provider.

        Args:
            rate_limit: Maximum number of notifications per period
            rate_period: Time period for rate limit in seconds
            retry_attempts: Number of retry attempts for failed notifications
            retry_delay: Delay between retry attempts in seconds
        """
        self._rate_limit = rate_limit
        self._rate_period = rate_period
        self._retry_attempts = retry_attempts
        self._retry_delay = retry_delay
        self._notification_history: List[datetime] = []
        self._last_error: Optional[Exception] = None

    @abstractmethod
    async def send_notification(self, message: str) -> bool:
        """Send notification to the provider.

        Args:
            message: Message to send

        Returns:
            bool: True if notification was sent successfully

        Raises:
            NotificationError: If notification fails
        """

    @abstractmethod
    def _format_message(self, message: str) -> Dict[str, Any]:
        """Format message for provider-specific requirements.

        Args:
            message: Raw message string

        Returns:
            Dict[str, Any]: Formatted message data

        Raises:
            MessageFormatError: If formatting fails
        """

    async def notify(
        self,
        template: str,
        stats: Optional[TransferStats] = None,
        **kwargs,
    ) -> bool:
        """Send notification with retry and rate limiting.

        Args:
            template: Message template string
            stats: Optional transfer statistics
            **kwargs: Additional template variables

        Returns:
            bool: True if notification was sent successfully

        Raises:
            RateLimitExceeded: If rate limit is exceeded
            NotificationError: If notification fails after retries
        """
        if not self._check_rate_limit():
            raise RateLimitExceeded(
                f"Rate limit exceeded: {self._rate_limit} per {self._rate_period}s"
            )

        # Prepare template variables
        template_vars = kwargs.copy()
        if stats:
            template_vars.update({
                "percent": f"{stats.percent_complete:.1f}",
                "remaining_data": format_size(stats.current_size),
                "total_data": format_size(stats.initial_size),
                "elapsed_time": format_duration(
                    (datetime.now() - stats.start_time).total_seconds()
                ),
            })
            if stats.estimated_completion:
                template_vars["etc"] = stats.estimated_completion.strftime(
                    "%H:%M on %b %d"
                )

        try:
            message = format_template(template, **template_vars)
        except ValueError as err:
            raise MessageFormatError(f"Failed to format message: {err}") from err

        # Attempt notification with retries
        for attempt in range(self._retry_attempts):
            try:
                if await self.send_notification(message):
                    self._notification_history.append(datetime.now())
                    self._last_error = None
                    return True

            except Exception as err:
                self._last_error = err
                logger.warning(
                    "Notification attempt failed",
                    attempt=attempt + 1,
                    error=str(err),
                )
                if attempt < self._retry_attempts - 1:
                    await asyncio.sleep(self._retry_delay)

        raise NotificationError(
            f"Failed to send notification after {self._retry_attempts} attempts"
        )

    def _check_rate_limit(self) -> bool:
        """Check if sending notification would exceed rate limit.

        Returns:
            bool: True if within rate limit
        """
        now = datetime.now()
        cutoff = now - timedelta(seconds=self._rate_period)

        # Remove old notifications from history
        self._notification_history = [
            t for t in self._notification_history if t > cutoff
        ]

        return len(self._notification_history) < self._rate_limit

    @property
    def last_error(self) -> Optional[Exception]:
        """Get last notification error if any."""
        return self._last_error

    def reset_rate_limit(self) -> None:
        """Reset rate limiting history."""
        self._notification_history.clear()
