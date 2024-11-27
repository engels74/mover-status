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
    NOTIFICATION_RETRY_ATTEMPTS,
    NOTIFICATION_RETRY_DELAY,
    NotificationLevel,
)
from core.calculator import TransferStats
from utils.formatters import format_duration, format_size, format_template
from utils.validators import BaseProviderValidator, ValidationContext

logger = get_logger(__name__)

# Type variables for provider-specific config types
TConfig = TypeVar('TConfig', bound=Dict[str, Any])
TValidator = TypeVar('TValidator', bound=BaseProviderValidator)

# Constants
MAX_HISTORY_SIZE: Final[int] = 100
MIN_NOTIFICATION_INTERVAL: Final[float] = 0.1  # seconds

class NotificationError(Exception):
    """Base exception for notification-related errors."""
    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize error with optional status code and details.

        Args:
            message: Error description
            code: Optional error code
            details: Optional error details
        """
        super().__init__(message)
        self.code = code
        self.details = details or {}
        self.timestamp = datetime.now()


class RateLimitExceeded(NotificationError):
    """Raised when rate limit is exceeded."""
    pass


class MessageFormatError(NotificationError):
    """Raised when message formatting fails."""
    pass


class ConfigurationError(NotificationError):
    """Raised when provider configuration is invalid."""
    pass


class ValidationError(NotificationError):
    """Raised when validation fails."""
    def __init__(
        self,
        message: str,
        context: Optional[ValidationContext] = None,
        field: Optional[str] = None
    ):
        """Initialize validation error with context.

        Args:
            message: Error description
            context: Optional validation context with metrics
            field: Optional field name that failed validation
        """
        super().__init__(message)
        self.context = context
        self.field = field


class NotificationState(BaseModel):
    """Current state of notification provider."""
    enabled: bool = Field(default=True)
    last_notification: Optional[datetime] = None
    last_error: Optional[NotificationError] = None
    error_count: int = Field(default=0)
    success_count: int = Field(default=0)
    rate_limited_count: int = Field(default=0)


class MessageFormatterProtocol(Protocol):
    """Protocol defining message formatting interface."""

    def _format_message(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO
    ) -> Dict[str, Any]:
        """Format message for provider-specific requirements.

        Args:
            message: Raw message string
            level: Message importance level

        Returns:
            Dict[str, Any]: Formatted message data

        Raises:
            MessageFormatError: If formatting fails
        """
        ...


class NotificationProvider(ABC, MessageFormatterProtocol, Generic[TConfig, TValidator]):
    """Abstract base class for notification providers.

    Type Parameters:
        TConfig: Provider-specific configuration type
        TValidator: Provider-specific validator type
    """

    # Class-level validator instance
    _validator_class: Type[TValidator]

    @classmethod
    def validate_config(
        cls,
        config: Dict[str, Any],
        required_fields: Optional[Set[str]] = None,
        context: Optional[ValidationContext] = None
    ) -> TConfig:
        """Validate provider configuration using the provider's validator.

        Args:
            config: Configuration dictionary to validate
            required_fields: Optional set of required field names
            context: Optional validation context for metrics

        Returns:
            TConfig: Validated configuration object

        Raises:
            ValidationError: If validation fails
            ConfigurationError: If configuration is invalid
        """
        if not hasattr(cls, '_validator_class'):
            raise ConfigurationError(
                f"No validator class set for provider {cls.__name__}"
            )

        try:
            validator = cls._validator_class()
            return validator.validate(
                config,
                required_fields=required_fields,
                context=context
            )
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
        # Validate rate limiting parameters
        if rate_limit < 1:
            raise ValueError("Rate limit must be at least 1")
        if rate_period < 1:
            raise ValueError("Rate period must be at least 1 second")
        if retry_attempts < 0:
            raise ValueError("Retry attempts cannot be negative")
        if retry_delay < 0:
            raise ValueError("Retry delay cannot be negative")

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

        self._rate_limit = rate_limit
        self._rate_period = rate_period
        self._retry_attempts = retry_attempts
        self._retry_delay = retry_delay
        self._notification_history: List[datetime] = []
        self._state = NotificationState()
        self._lock = asyncio.Lock()

    @abstractmethod
    async def send_notification(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO
    ) -> bool:
        """Send notification to the provider.

        Args:
            message: Message to send
            level: Message importance level

        Returns:
            bool: True if notification was sent successfully

        Raises:
            NotificationError: If notification fails
        """
        pass

    async def notify(
        self,
        template: str,
        stats: Optional[TransferStats] = None,
        level: NotificationLevel = NotificationLevel.INFO,
        **kwargs: Any
    ) -> bool:
        """Send notification with retry and rate limiting.

        Args:
            template: Message template string
            stats: Optional transfer statistics
            level: Message importance level
            **kwargs: Additional template variables

        Returns:
            bool: True if notification was sent successfully

        Raises:
            RateLimitExceeded: If rate limit is exceeded
            NotificationError: If notification fails after retries
            ValueError: If template string is invalid
        """
        if not self._state.enabled:
            logger.warning("Provider is disabled, skipping notification")
            return False

        async with self._lock:
            # Check rate limit
            if not await self._check_rate_limit():
                self._state.rate_limited_count += 1
                raise RateLimitExceeded(
                    f"Rate limit exceeded: {self._rate_limit} per {self._rate_period}s"
                )

            # Prepare message
            try:
                message = await self._prepare_message(template, stats, **kwargs)
            except (ValueError, MessageFormatError) as err:
                self._update_state_error(
                    NotificationError(str(err), details={"template": template})
                )
                raise

            # Attempt to send
            error = await self._attempt_send(message, level)
            if error is None:
                self._update_state_success()
                return True

            self._update_state_error(error)
            raise NotificationError(
                f"Failed to send notification after {self._retry_attempts + 1} attempts"
            ) from error

    async def _prepare_message(
        self,
        template: str,
        stats: Optional[TransferStats] = None,
        **kwargs: Any
    ) -> str:
        """Prepare message for sending.

        Args:
            template: Message template string
            stats: Optional transfer statistics
            **kwargs: Additional template variables

        Returns:
            str: Prepared message string

        Raises:
            ValueError: If template string is invalid
            MessageFormatError: If message formatting fails
        """
        if not template:
            raise ValueError("Template string cannot be empty")

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

        return message

    async def _attempt_send(
        self,
        message: str,
        level: NotificationLevel
    ) -> Optional[NotificationError]:
        """Attempt to send notification with retries.

        Args:
            message: Prepared message string
            level: Message importance level

        Returns:
            Optional[NotificationError]: Error if sending fails, otherwise None
        """
        last_error = None
        for attempt in range(self._retry_attempts + 1):
            try:
                if await self.send_notification(message, level):
                    return None

            except NotificationError as err:
                last_error = err
                logger.warning(
                    "Notification attempt failed",
                    attempt=attempt + 1,
                    max_attempts=self._retry_attempts + 1,
                    error=str(err),
                    retry_delay=self._retry_delay
                )
                if attempt < self._retry_attempts:
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))  # Exponential backoff

        return last_error

    async def _check_rate_limit(self) -> bool:
        """Check if sending notification would exceed rate limit.

        Returns:
            bool: True if within rate limit
        """
        now = datetime.now()
        cutoff = now - timedelta(seconds=self._rate_period)

        # Remove old notifications from history
        self._notification_history = [
            t for t in self._notification_history
            if t > cutoff
        ][-MAX_HISTORY_SIZE:]  # Keep history size bounded

        # Check if sending would exceed limit
        return len(self._notification_history) < self._rate_limit

    def _update_state_success(self) -> None:
        """Update state after successful notification."""
        now = datetime.now()
        self._notification_history.append(now)
        self._state.last_notification = now
        self._state.success_count += 1
        self._state.error_count = 0
        self._state.last_error = None

    def _update_state_error(self, error: Optional[NotificationError]) -> None:
        """Update state after failed notification.

        Args:
            error: The error that occurred
        """
        self._state.error_count += 1
        self._state.last_error = error
        if self._state.error_count >= 3:
            self._state.enabled = False
            logger.error(
                "Provider disabled due to repeated errors",
                provider=self.__class__.__name__,
                error_count=self._state.error_count
            )

    @property
    def state(self) -> NotificationState:
        """Get current provider state."""
        return self._state

    def reset_state(self) -> None:
        """Reset provider state."""
        self._state = NotificationState()
        self._notification_history.clear()