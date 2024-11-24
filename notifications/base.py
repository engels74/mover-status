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
from typing import Any, Dict, Generic, List, Optional, Protocol, Type, TypeVar

from structlog import get_logger

from config.constants import (
    NOTIFICATION_RETRY_ATTEMPTS,
    NOTIFICATION_RETRY_DELAY,
)
from core.calculator import TransferStats
from utils.formatters import format_duration, format_size, format_template
from utils.validators import BaseProviderValidator, ValidationContext

logger = get_logger(__name__)

# Type variable for provider-specific config types
TConfig = TypeVar('TConfig')
TValidator = TypeVar('TValidator', bound=BaseProviderValidator)


class NotificationError(Exception):
    """Base exception for notification-related errors."""
    def __init__(self, message: str, code: Optional[int] = None):
        """Initialize error with optional status code.

        Args:
            message: Error description
            code: Optional error code
        """
        super().__init__(message)
        self.code = code


class RateLimitExceeded(NotificationError):
    """Raised when rate limit is exceeded."""


class MessageFormatError(NotificationError):
    """Raised when message formatting fails."""


class ConfigurationError(NotificationError):
    """Raised when provider configuration is invalid."""


class ValidationError(NotificationError):
    """Raised when validation fails."""
    def __init__(self, message: str, context: Optional[ValidationContext] = None):
        """Initialize validation error with optional context.

        Args:
            message: Error description
            context: Optional validation context with metrics
        """
        super().__init__(message)
        self.context = context


class MessageFormatterProtocol(Protocol):
    """Protocol defining message formatting interface."""

    def _format_message(self, message: str) -> Dict[str, Any]:
        """Format message for provider-specific requirements.

        Args:
            message: Raw message string

        Returns:
            Dict[str, Any]: Formatted message data

        Raises:
            MessageFormatError: If formatting fails
        """
        ...


class NotificationProvider(ABC, MessageFormatterProtocol, Generic[TConfig, TValidator]):
    """
    Abstract base class for notification providers.
    Implements common functionality and defines required interface.

    Type Parameters:
        TConfig: Provider-specific configuration type
        TValidator: Provider-specific validator type
    """

    # Class-level validator instance for config validation
    _validator_class: Type[TValidator]

    @classmethod
    def validate_config(
        cls,
        config: Dict[str, Any],
        required_fields: Optional[List[str]] = None,
        context: Optional[ValidationContext] = None,
    ) -> TConfig:
        """Validate provider configuration using the provider's validator.

        This implementation uses the provider's validator class to validate the config.
        Providers should specify their validator class and override this method if needed.

        Args:
            config: Configuration dictionary to validate
            required_fields: Optional list of required field names
            context: Optional validation context for metrics

        Returns:
            TConfig: Validated configuration object

        Raises:
            ValidationError: If validation fails
            ConfigurationError: If configuration is invalid or validator is not set

        Example:
            >>> config = {"webhook_url": "https://example.com", "username": "bot"}
            >>> validated = DiscordProvider.validate_config(config)
        """
        if not hasattr(cls, '_validator_class'):
            raise ConfigurationError(
                f"No validator class set for provider {cls.__name__}"
            )

        try:
            validator = cls._validator_class()
            return validator.validate(config, context=context)
        except Exception as e:
            raise ValidationError(
                f"Configuration validation failed: {str(e)}",
                context=context
            ) from e

    def __init__(
        self,
        config: TConfig,
        rate_limit: int = 1,
        rate_period: int = 60,
        retry_attempts: int = NOTIFICATION_RETRY_ATTEMPTS,
        retry_delay: int = NOTIFICATION_RETRY_DELAY,
    ):
        """Initialize notification provider.

        Args:
            config: Validated provider configuration
            rate_limit: Maximum number of notifications per period
            rate_period: Time period for rate limit in seconds
            retry_attempts: Number of retry attempts for failed notifications
            retry_delay: Delay between retry attempts in seconds

        Raises:
            ValueError: If provided values are invalid
            ValidationError: If config validation fails
        """
        # Validate config using provider validator
        try:
            self.config = self.validate_config(config)
        except ValidationError as e:
            logger.error(
                "Provider configuration validation failed",
                provider=self.__class__.__name__,
                error=str(e),
                context=e.context
            )
            raise

        if rate_limit < 1:
            raise ValueError("Rate limit must be at least 1")
        if rate_period < 1:
            raise ValueError("Rate period must be at least 1 second")
        if retry_attempts < 0:
            raise ValueError("Retry attempts cannot be negative")
        if retry_delay < 0:
            raise ValueError("Retry delay cannot be negative")

        self._rate_limit = rate_limit
        self._rate_period = rate_period
        self._retry_attempts = retry_attempts
        self._retry_delay = retry_delay
        self._notification_history: List[datetime] = []
        self._last_error: Optional[NotificationError] = None
        self._last_notification_time: Optional[datetime] = None

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
            ValueError: If template string is invalid
        """
        if not template:
            raise ValueError("Template string cannot be empty")

        if not await self._check_rate_limit():
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
        last_error = None
        for attempt in range(self._retry_attempts + 1):
            try:
                if await self.send_notification(message):
                    self._last_notification_time = datetime.now()
                    self._notification_history.append(self._last_notification_time)
                    self._last_error = None
                    return True

            except NotificationError as err:
                last_error = err
                logger.warning(
                    "Notification attempt failed",
                    attempt=attempt + 1,
                    max_attempts=self._retry_attempts + 1,
                    error=str(err),
                    retry_delay=self._retry_delay,
                )
                if attempt < self._retry_attempts:
                    await asyncio.sleep(self._retry_delay)

        self._last_error = last_error
        raise NotificationError(
            f"Failed to send notification after {self._retry_attempts + 1} attempts"
        ) from last_error

    async def _check_rate_limit(self) -> bool:
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

        # Check if sending would exceed limit
        if len(self._notification_history) >= self._rate_limit:
            return False

        return True

    @property
    def last_error(self) -> Optional[NotificationError]:
        """Get last notification error if any."""
        return self._last_error

    @property
    def last_notification_time(self) -> Optional[datetime]:
        """Get timestamp of last successful notification."""
        return self._last_notification_time

    def reset_rate_limit(self) -> None:
        """Reset rate limiting history."""
        self._notification_history.clear()
