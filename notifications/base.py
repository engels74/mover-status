# notifications/base.py

"""
Abstract base notification provider implementation.
Defines the interface and common functionality for all notification providers.
Handles rate limiting, error handling, and message formatting.

Example:
    >>> class DiscordProvider(NotificationProvider):
    ...     async def send_notification(self, message: str) -> bool:
    ...         # Discord-specific implementation
    ...         webhook_data = self._format_message(message)
    ...         return await self._send_webhook(webhook_data)
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import (
    Any,
    Dict,
    Final,
    Generic,
    List,
    Optional,
    Protocol,
    Set,
    Type,
    TypeVar,
)

from pydantic import BaseModel, Field
from structlog import get_logger

from config.constants import (
    API,
    Notification,
    NotificationLevel,
)

logger = get_logger(__name__)

# Type variables for provider-specific config types
TConfig = TypeVar('TConfig', bound=Dict[str, Any])
TValidator = TypeVar('TValidator', bound=BaseModel)

# Constants
MAX_HISTORY_SIZE: Final[int] = Notification.MAX_HISTORY_SIZE
MIN_NOTIFICATION_INTERVAL: Final[float] = API.MIN_NOTIFICATION_INTERVAL  # seconds


class NotificationError(Exception):
    """Base exception for notification-related errors."""


class NotificationState(BaseModel):
    """Tracks notification provider state."""

    last_notification: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    notification_count: int = 0
    success_count: int = 0
    history: List[Dict[str, Any]] = []

    def add_notification(self, message: str, success: bool = True) -> None:
        """Add notification to history.

        Args:
            message: Notification message
            success: Whether notification was successful
        """
        self.history.append({
            'timestamp': datetime.now(),
            'message': message,
            'success': success
        })

        if len(self.history) > MAX_HISTORY_SIZE:
            self.history.pop(0)

        if success:
            self.success_count += 1
        else:
            self.error_count += 1

        self.notification_count += 1
        self.last_notification = datetime.now()


class NotificationProvider(ABC, Generic[TConfig, TValidator]):
    """Abstract base class for notification providers."""

    def __init__(
        self,
        rate_limit: int = API.DEFAULT_RATE_LIMIT,
        rate_period: int = API.DEFAULT_RATE_PERIOD,
        retry_attempts: int = API.DEFAULT_RETRY_ATTEMPTS,
        retry_delay: float = API.DEFAULT_RETRY_DELAY,
    ):
        """Initialize notification provider.

        Args:
            rate_limit: Maximum notifications per rate_period
            rate_period: Rate limit period in seconds
            retry_attempts: Number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self._rate_limit = max(1, rate_limit)
        self._rate_period = max(1, rate_period)
        self._retry_attempts = max(0, retry_attempts)
        self._retry_delay = max(0.1, retry_delay)

        self._state = NotificationState()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> NotificationState:
        """Get provider state."""
        return self._state

    async def notify(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        **kwargs
    ) -> bool:
        """Send notification with rate limiting and retries.

        Args:
            message: Message to send
            level: Notification priority level
            **kwargs: Additional provider-specific arguments

        Returns:
            bool: True if notification was sent successfully
        """
        async with self._lock:
            try:
                # Check rate limit
                now = datetime.now()
                if self._state.last_notification:
                    elapsed = (now - self._state.last_notification).total_seconds()
                    if elapsed < MIN_NOTIFICATION_INTERVAL:
                        logger.debug(
                            "Rate limited",
                            elapsed=f"{elapsed:.2f}s",
                            min_interval=MIN_NOTIFICATION_INTERVAL
                        )
                        return False

                # Attempt notification with retries
                for attempt in range(self._retry_attempts + 1):
                    try:
                        success = await self.send_notification(
                            message,
                            level=level,
                            **kwargs
                        )
                        if success:
                            self._state.add_notification(message)
                            return True

                        if attempt < self._retry_attempts:
                            await asyncio.sleep(self._retry_delay)
                            continue

                        self._state.add_notification(message, success=False)
                        return False

                    except Exception as err:
                        if attempt < self._retry_attempts:
                            logger.warning(
                                "Notification failed, retrying",
                                error=str(err),
                                attempt=attempt + 1,
                                max_attempts=self._retry_attempts
                            )
                            await asyncio.sleep(self._retry_delay)
                            continue

                        raise

            except Exception as err:
                self._state.last_error = str(err)
                self._state.add_notification(message, success=False)
                logger.error(
                    "Notification failed",
                    error=str(err),
                    error_type=type(err).__name__
                )
                return False

    @abstractmethod
    async def send_notification(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        **kwargs
    ) -> bool:
        """Send notification to provider.

        Args:
            message: Message to send
            level: Notification priority level
            **kwargs: Additional provider-specific arguments

        Returns:
            bool: True if notification was sent successfully

        Raises:
            NotImplementedError: Must be implemented by provider
        """
        raise NotImplementedError
