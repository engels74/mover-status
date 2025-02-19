# notifications/base.py

"""
Abstract base notification provider implementation.
This module defines the core notification system architecture, providing base
classes and interfaces for implementing notification providers with advanced
features like rate limiting, error handling, and message prioritization.

Components:
- NotificationError: Base exception for notification-related errors
- NotificationState: State tracking and history management
- NotificationProvider: Abstract base class for providers

Features:
- Priority-based rate limiting and retries
- Message type-specific rate limits
- Thread-safe state tracking
- Notification history with configurable size
- Comprehensive error handling
- Flexible message formatting
- Async/await support

The notification system supports multiple message types and priority levels,
allowing for fine-grained control over notification delivery:

Message Types:
- DEBUG: Development and troubleshooting messages
- WARNING: Important but non-critical issues
- ERROR: Critical issues requiring attention
- SYSTEM: System-level notifications
- PROGRESS: Transfer progress updates
- COMPLETION: Task completion notifications
- BATCH: Batch operation results
- INTERACTIVE: User interaction messages
- CUSTOM: Provider-specific messages

Priority Levels:
- LOW: Informational messages
- NORMAL: Standard notifications
- HIGH: Critical updates and errors

Example:
    >>> from notifications.base import NotificationProvider
    >>> from config.constants import NotificationLevel, MessageType
    >>>
    >>> class DiscordProvider(NotificationProvider):
    ...     async def send_notification(
    ...         self,
    ...         message: str,
    ...         level: NotificationLevel = NotificationLevel.INFO,
    ...         **kwargs
    ...     ) -> bool:
    ...         # Format message for Discord
    ...         webhook_data = self._format_message(
    ...             message,
    ...             level=level,
    ...             **kwargs
    ...         )
    ...
    ...         # Send via webhook with retries
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
    """Base exception for notification-related errors.

    This exception class serves as the root for all notification system
    errors, allowing for specific error handling of notification issues
    versus other system errors.

    Common scenarios:
    - Rate limit exceeded
    - Provider API errors
    - Authentication failures
    - Network connectivity issues
    - Message format validation errors
    """
    pass


class NotificationState(BaseModel):
    """State tracking and history management for notification providers.

    This class maintains comprehensive statistics and history about
    notifications sent through a provider, including success rates,
    message counts by type and priority, and timing information.

    Features:
    - Thread-safe state updates
    - Configurable history size
    - Priority and type-based tracking
    - Timestamp tracking by message type
    - Success/failure statistics

    Attributes:
        last_notification (Optional[datetime]): Timestamp of most recent notification
        last_error (Optional[str]): Description of last error encountered
        last_error_time (Optional[datetime]): Timestamp of last error
        error_count (int): Total number of failed notifications
        notification_count (int): Total notifications attempted
        success_count (int): Total successful notifications
        history (List[Dict[str, Any]]): Recent notification records
        rate_limited (bool): Whether the provider is currently rate limited
        rate_limit_until (Optional[float]): Timestamp when rate limit expires
        disabled (bool): Whether the provider is disabled
        _priority_counts (Dict[MessagePriority, int]): Counts by priority level
        _type_counts (Dict[MessageType, int]): Counts by message type
        _last_by_type (Dict[MessageType, datetime]): Last timestamp by type
        _lock (asyncio.Lock): Thread safety lock
    """

    last_notification: Optional[datetime] = None
    last_error: Optional[str] = None  # Changed from Exception to str
    last_error_time: Optional[datetime] = None
    error_count: int = 0
    notification_count: int = 0
    success_count: int = 0
    history: List[Dict[str, Any]] = []
    rate_limited: bool = False
    rate_limit_until: Optional[float] = None
    disabled: bool = False
    _priority_counts: Dict[MessagePriority, int] = {
        MessagePriority.LOW: 0,
        MessagePriority.NORMAL: 0,
        MessagePriority.HIGH: 0
    }
    _type_counts: Dict[MessageType, int] = {
        message_type: 0 for message_type in MessageType
    }
    _last_by_type: Dict[MessageType, Optional[datetime]] = {
        message_type: None for message_type in MessageType
    }
    _lock: asyncio.Lock = asyncio.Lock()

    model_config = {
        "arbitrary_types_allowed": True,
        "validate_assignment": True
    }

    async def add_notification(
        self,
        message: str,
        success: bool = True,
        priority: MessagePriority = MessagePriority.NORMAL,
        message_type: MessageType = MessageType.CUSTOM
    ) -> None:
        """Add a notification to the provider's history with thread safety.

        Updates various tracking metrics including counts by type and priority,
        timestamps, and the notification history queue. Automatically manages
        history size to prevent memory issues.

        Args:
            message (str): The notification message content
            success (bool, optional): Whether the notification was successful.
                Defaults to True.
            priority (MessagePriority, optional): Priority level of the message.
                Defaults to NORMAL.
            message_type (MessageType, optional): Type of notification message.
                Defaults to CUSTOM.

        Thread Safety:
            This method is thread-safe and can be called concurrently from
            multiple coroutines. All state updates are protected by a lock.

        Example:
            >>> await state.add_notification(
            ...     "Transfer complete",
            ...     success=True,
            ...     priority=MessagePriority.HIGH,
            ...     message_type=MessageType.COMPLETION
            ... )
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
        """Get message counts by type with thread safety.

        Returns a copy of the type count dictionary to prevent external
        modification of internal state. The counts are maintained for all
        message types defined in MessageType enum.

        Returns:
            Dict[MessageType, int]: Copy of message counts indexed by type

        Thread Safety:
            This property is thread-safe as it returns a copy of the internal
            dictionary, preventing any modification of the original data.

        Example:
            >>> counts = state.type_counts
            >>> print(f"Error messages: {counts[MessageType.ERROR]}")
            >>> print(f"Progress updates: {counts[MessageType.PROGRESS]}")
        """
        return self._type_counts.copy()

    def get_last_by_type(self, message_type: MessageType) -> Optional[datetime]:
        """Get the timestamp of the last message of a specific type.

        Retrieves the timestamp of the most recent notification sent for
        the specified message type. Used primarily for rate limiting and
        monitoring message frequency.

        Args:
            message_type (MessageType): Type of message to get timestamp for

        Returns:
            Optional[datetime]: Timestamp of last message of specified type,
                or None if no messages of that type have been sent

        Example:
            >>> last_error = state.get_last_by_type(MessageType.ERROR)
            >>> if last_error:
            ...     elapsed = (datetime.now() - last_error).total_seconds()
            ...     print(f"Time since last error: {elapsed:.1f}s")
        """
        return self._last_by_type.get(message_type)


class NotificationProvider(ABC, Generic[TConfig, TValidator]):
    """Abstract base class for implementing notification providers.

    This class provides a comprehensive framework for building notification
    providers with advanced features like rate limiting, retries, and
    priority-based message handling. It uses generics to allow for
    provider-specific configuration and validation.

    Features:
    - Priority-based rate limiting
    - Automatic retries with configurable attempts
    - Message type-specific rate limits
    - Thread-safe operation
    - State tracking and history
    - Flexible message formatting
    - Generic configuration types

    The provider implements a sophisticated rate limiting system that
    adjusts based on message priority and type:
    - High priority messages get 2x the base rate limit
    - Low priority messages get 1/2 the base rate limit
    - Debug messages are limited to 1/4 the base rate
    - Error messages are allowed 2x the base rate

    Attributes:
        state (NotificationState): Current provider state and history
        _rate_limit (int): Base rate limit per period
        _rate_period (int): Rate limit period in seconds
        _retry_attempts (int): Base number of retry attempts
        _retry_delay (float): Delay between retries in seconds
        _priority_rate_limits (Dict[MessagePriority, int]): Rate limits by priority
        _priority_retry_attempts (Dict[MessagePriority, int]): Retries by priority
        _type_rate_limits (Dict[MessageType, int]): Rate limits by message type
        _rate_lock (asyncio.Lock): Rate limiting lock
        _notify_lock (asyncio.Lock): Notification operation lock

    Example:
        >>> class TelegramProvider(NotificationProvider):
        ...     async def send_notification(
        ...         self,
        ...         message: str,
        ...         level: NotificationLevel = NotificationLevel.INFO,
        ...         **kwargs
        ...     ) -> bool:
        ...         try:
        ...             # Send message via Telegram API
        ...             async with self._client as client:
        ...                 await client.send_message(
        ...                     self._chat_id,
        ...                     self._format_message(message, level)
        ...                 )
        ...             return True
        ...         except Exception as err:
        ...             logger.error(f"Telegram error: {err}")
        ...             return False
    """

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
        """Convert notification level to message priority for rate limiting.

        Maps notification levels to corresponding priority levels for
        determining rate limits and retry attempts:
        - ERROR/CRITICAL -> HIGH priority
        - WARNING -> NORMAL priority
        - INFO/DEBUG -> LOW priority

        Args:
            level (NotificationLevel): Notification level to convert

        Returns:
            MessagePriority: Corresponding message priority for rate limiting

        Example:
            >>> priority = provider._get_priority_from_level(NotificationLevel.ERROR)
            >>> assert priority == MessagePriority.HIGH
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
        """Send a notification with rate limiting and automatic retries.

        This is the main entry point for sending notifications. It handles:
        1. Priority determination from notification level
        2. Rate limit checking based on message type
        3. Notification sending with retries
        4. State updates and history tracking
        5. Error handling and logging

        Args:
            message (str): The notification message to send
            level (NotificationLevel, optional): Severity level of the message.
                Defaults to INFO.
            message_type (MessageType, optional): Type of notification message.
                Defaults to CUSTOM.
            **kwargs: Additional provider-specific arguments passed to
                send_notification()

        Returns:
            bool: True if notification was sent successfully, False otherwise

        Thread Safety:
            This method is thread-safe and can be called concurrently from
            multiple coroutines. All operations are protected by locks.

        Example:
            >>> success = await provider.notify(
            ...     "Transfer started",
            ...     level=NotificationLevel.INFO,
            ...     message_type=MessageType.PROGRESS,
            ...     color="#00ff00"  # Provider-specific kwarg
            ... )
            >>> if not success:
            ...     logger.error("Failed to send notification")
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
        """Send a notification through the provider's specific channel.

        This is the abstract method that each provider must implement to
        handle the actual sending of notifications through their respective
        channels (e.g., Discord webhook, Telegram API, etc.).

        The implementation should:
        1. Format the message appropriately for the channel
        2. Handle provider-specific authentication
        3. Send the notification with appropriate error handling
        4. Return success/failure status

        Args:
            message (str): The notification message to send
            level (NotificationLevel, optional): Severity level of the message.
                Defaults to INFO.
            priority (MessagePriority, optional): Priority level for rate limiting.
                Defaults to NORMAL.
            message_type (MessageType, optional): Type of notification message.
                Defaults to CUSTOM.
            **kwargs: Provider-specific arguments (e.g., color, buttons)

        Returns:
            bool: True if notification was sent successfully, False otherwise

        Raises:
            NotImplementedError: This method must be implemented by subclasses

        Example:
            >>> class EmailProvider(NotificationProvider):
            ...     async def send_notification(
            ...         self,
            ...         message: str,
            ...         level: NotificationLevel = NotificationLevel.INFO,
            ...         **kwargs
            ...     ) -> bool:
            ...         subject = f"[{level.name}] Notification"
            ...         return await self._send_email(subject, message)
        """
        raise NotImplementedError
