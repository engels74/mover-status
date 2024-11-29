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
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Dict,
    Final,
    Generic,
    List,
    Optional,
    TypeVar,
)

from pydantic import BaseModel
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


class MessagePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3


class NotificationError(Exception):
    """Base exception for notification-related errors."""


class NotificationState(BaseModel):
    """Tracks notification provider state."""

    def __init__(self):
        self.last_notification: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.error_count: int = 0
        self.notification_count: int = 0
        self.success_count: int = 0
        self.history: List[Dict[str, Any]] = []
        self._priority_counts: Dict[MessagePriority, int] = {
            MessagePriority.LOW: 0,
            MessagePriority.NORMAL: 0,
            MessagePriority.HIGH: 0
        }

    def add_notification(
        self,
        message: str,
        success: bool = True,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> None:
        """Add notification to history.

        Args:
            message: Notification message
            success: Whether notification was successful
            priority: Message priority level
        """
        if success:
            self.success_count += 1
            self._priority_counts[priority] += 1

        self.notification_count += 1
        if len(self.history) >= MAX_HISTORY_SIZE:
            self.history.pop(0)

        self.history.append({
            "message": message,
            "success": success,
            "priority": priority,
            "timestamp": datetime.now()
        })
        self.last_notification = datetime.now()

    @property
    def priority_counts(self) -> Dict[MessagePriority, int]:
        """Get counts of messages by priority level."""
        return self._priority_counts.copy()


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
        self._priority_rate_limits = {
            MessagePriority.LOW: self._rate_limit // 2,
            MessagePriority.NORMAL: self._rate_limit,
            MessagePriority.HIGH: self._rate_limit * 2
        }
        self._priority_retry_attempts = {
            MessagePriority.LOW: max(0, self._retry_attempts - 1),
            MessagePriority.NORMAL: self._retry_attempts,
            MessagePriority.HIGH: self._retry_attempts + 1
        }

        self._state = NotificationState()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> NotificationState:
        """Get provider state."""
        return self._state

    def _get_priority_from_level(self, level: NotificationLevel) -> MessagePriority:
        """Convert notification level to message priority.

        Args:
            level: Notification level

        Returns:
            MessagePriority: Corresponding message priority
        """
        priority_map = {
            NotificationLevel.DEBUG: MessagePriority.LOW,
            NotificationLevel.INFO: MessagePriority.NORMAL,
            NotificationLevel.WARNING: MessagePriority.HIGH,
            NotificationLevel.ERROR: MessagePriority.HIGH,
            NotificationLevel.CRITICAL: MessagePriority.HIGH
        }
        return priority_map.get(level, MessagePriority.NORMAL)

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
        priority = self._get_priority_from_level(level)
        retry_attempts = self._priority_retry_attempts[priority]

        async with self._lock:
            try:
                # Check rate limit
                now = datetime.now()
                if self._state.last_notification:
                    elapsed = (now - self._state.last_notification).total_seconds()
                    if elapsed < MIN_NOTIFICATION_INTERVAL:
                        # Allow high priority messages to bypass rate limit
                        if priority != MessagePriority.HIGH:
                            logger.debug(
                                "Rate limited",
                                elapsed=f"{elapsed:.2f}s",
                                min_interval=MIN_NOTIFICATION_INTERVAL,
                                priority=priority.value
                            )
                            return False

                # Attempt notification with priority-based retries
                for attempt in range(retry_attempts + 1):
                    try:
                        success = await self.send_notification(
                            message,
                            level=level,
                            priority=priority,
                            **kwargs
                        )
                        if success:
                            self._state.add_notification(message, priority=priority)
                            return True

                        if attempt < retry_attempts:
                            # Adjust retry delay based on priority
                            delay = self._retry_delay * (2 if priority == MessagePriority.HIGH else 1)
                            await asyncio.sleep(delay)
                            continue

                        self._state.add_notification(message, success=False, priority=priority)
                        return False

                    except Exception as err:
                        if attempt < retry_attempts:
                            logger.warning(
                                "Notification failed, retrying",
                                error=str(err),
                                attempt=attempt + 1,
                                max_attempts=retry_attempts,
                                priority=priority.value
                            )
                            await asyncio.sleep(self._retry_delay)
                            continue

                        raise

            except Exception as err:
                self._state.last_error = str(err)
                self._state.add_notification(message, success=False, priority=priority)
                logger.error(
                    "Notification failed",
                    error=str(err),
                    error_type=type(err).__name__,
                    priority=priority.value
                )
                return False

    @abstractmethod
    async def send_notification(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        priority: MessagePriority = MessagePriority.NORMAL,
        **kwargs
    ) -> bool:
        """Send notification to provider.

        Args:
            message: Message to send
            level: Notification priority level
            priority: Message priority level
            **kwargs: Additional provider-specific arguments

        Returns:
            bool: True if notification was sent successfully

        Raises:
            NotImplementedError: Must be implemented by provider
        """
        raise NotImplementedError
