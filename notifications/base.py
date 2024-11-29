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
    MessagePriority,
    MessageType,
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
        self._type_counts: Dict[MessageType, int] = {
            message_type: 0 for message_type in MessageType
        }
        self._last_by_type: Dict[MessageType, Optional[datetime]] = {
            message_type: None for message_type in MessageType
        }
        self._lock = asyncio.Lock()

    async def add_notification(
        self,
        message: str,
        success: bool = True,
        priority: MessagePriority = MessagePriority.NORMAL,
        message_type: MessageType = MessageType.CUSTOM
    ) -> None:
        """Add notification to history.

        Args:
            message: Notification message
            success: Whether notification was successful
            priority: Message priority level
            message_type: Type of message
        """
        async with self._lock:
            # Update counts
            self.notification_count += 1
            if success:
                self.success_count += 1
            self._priority_counts[priority] += 1
            self._type_counts[message_type] += 1

            # Update timestamps
            now = datetime.now()
            self.last_notification = now
            self._last_by_type[message_type] = now

            # Add to history
            self.history.append({
                "message": message,
                "success": success,
                "priority": priority,
                "type": message_type,
                "timestamp": now
            })

            # Trim history if needed
            if len(self.history) > MAX_HISTORY_SIZE:
                self.history = self.history[-MAX_HISTORY_SIZE:]

    @property
    def type_counts(self) -> Dict[MessageType, int]:
        """Get counts of messages by type."""
        return self._type_counts.copy()

    def get_last_by_type(self, message_type: MessageType) -> Optional[datetime]:
        """Get timestamp of last message of specific type."""
        return self._last_by_type.get(message_type)


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

        # Priority-based rate limits and retries
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

        # Message type specific settings
        self._type_rate_limits = {
            MessageType.DEBUG: self._rate_limit // 4,     # Lowest rate limit for debug
            MessageType.WARNING: self._rate_limit,        # Normal rate for warnings
            MessageType.ERROR: self._rate_limit * 2,      # Higher rate for errors
            MessageType.SYSTEM: self._rate_limit * 1.5,   # Elevated rate for system
            MessageType.PROGRESS: self._rate_limit // 2,  # Lower rate for progress
            MessageType.COMPLETION: self._rate_limit,     # Normal rate for completion
            MessageType.BATCH: self._rate_limit,          # Normal rate for batch
            MessageType.INTERACTIVE: self._rate_limit,    # Normal rate for interactive
            MessageType.CUSTOM: self._rate_limit,         # Normal rate for custom
        }

        self._state = NotificationState()
        self._rate_lock = asyncio.Lock()
        self._notify_lock = asyncio.Lock()

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
        if level in (NotificationLevel.ERROR, NotificationLevel.CRITICAL):
            return MessagePriority.HIGH
        elif level == NotificationLevel.WARNING:
            return MessagePriority.NORMAL
        return MessagePriority.LOW

    async def notify(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        message_type: MessageType = MessageType.CUSTOM,
        **kwargs
    ) -> bool:
        """Send notification with rate limiting and retries.

        Args:
            message: Message to send
            level: Notification priority level
            message_type: Type of message
            **kwargs: Additional provider-specific arguments

        Returns:
            bool: True if notification was sent successfully
        """
        async with self._notify_lock:
            # Get priority from level
            priority = self._get_priority_from_level(level)

            try:
                # Check rate limits
                async with self._rate_lock:
                    last = self._state.get_last_by_type(message_type)
                    if last:
                        elapsed = (datetime.now() - last).total_seconds()
                        if elapsed < MIN_NOTIFICATION_INTERVAL:
                            return False

                # Send notification with retries
                success = await self.send_notification(
                    message,
                    level=level,
                    priority=priority,
                    message_type=message_type,
                    **kwargs
                )

                # Update state
                await self._state.add_notification(
                    message,
                    success=success,
                    priority=priority,
                    message_type=message_type
                )

                return success

            except Exception as err:
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
        priority: MessagePriority = MessagePriority.NORMAL,
        message_type: MessageType = MessageType.CUSTOM,
        **kwargs
    ) -> bool:
        """Send notification to provider.

        Args:
            message: Message to send
            level: Notification priority level
            priority: Message priority level
            message_type: Type of message
            **kwargs: Additional provider-specific arguments

        Returns:
            bool: True if notification was sent successfully

        Raises:
            NotImplementedError: Must be implemented by provider
        """
        raise NotImplementedError
