"""Protocol definitions for component interfaces.

This module defines structural subtyping protocols that establish
contracts for core application components without requiring inheritance.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol, runtime_checkable

from mover_status.types.models import (
    HealthStatus,
    NotificationData,
    NotificationResult,
    Response,
)


@runtime_checkable
class NotificationProvider(Protocol):
    """Protocol for notification delivery providers.

    Defines the interface for sending notifications to external platforms
    (e.g., webhook services, chat platforms) with health monitoring capabilities.
    """

    async def send_notification(self, data: NotificationData) -> NotificationResult:
        """Deliver notification to provider platform.

        Args:
            data: Notification payload containing transfer progress information

        Returns:
            Result of the delivery attempt including timing and error details
        """
        ...

    def validate_config(self) -> bool:
        """Validate provider configuration.

        Returns:
            True if configuration is valid and provider can be initialized
        """
        ...

    async def health_check(self) -> HealthStatus:
        """Verify provider connectivity and health.

        Returns:
            Current health status including failure tracking information
        """
        ...


class MessageFormatter(Protocol):
    """Protocol for platform-specific message formatting.

    Defines the interface for formatting notification messages with
    platform-specific rich content and timestamp representations.
    """

    def format_message(
        self, template: str, placeholders: Mapping[str, object]
    ) -> str:
        """Format message with platform-specific formatting.

        Args:
            template: Message template string
            placeholders: Key-value pairs for template substitution

        Returns:
            Formatted message with platform-specific rich content
        """
        ...

    def format_time(self, timestamp: datetime) -> str:
        """Convert timestamp to platform-specific format.

        Args:
            timestamp: Datetime to format

        Returns:
            Platform-specific time representation
            (e.g., Unix timestamps, ISO 8601 strings, human-readable formats)
        """
        ...


class HTTPClient(Protocol):
    """Protocol for HTTP client operations.

    Defines the interface for making HTTP requests with timeout
    and retry capabilities for reliable notification delivery.
    """

    async def post(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        timeout: float,
    ) -> Response:
        """Send HTTP POST request with timeout.

        Args:
            url: Target URL for the POST request
            payload: Request body data
            timeout: Request timeout in seconds (keyword-only)

        Returns:
            HTTP response with status, body, and headers
        """
        ...

    async def post_with_retry(
        self,
        url: str,
        payload: Mapping[str, object],
    ) -> Response:
        """Send HTTP POST with exponential backoff retry.

        Implements retry logic for transient failures with:
        - Maximum 5 retry attempts
        - Exponential backoff with configurable maximum interval
        - Random jitter (±20%) to prevent thundering herd

        Args:
            url: Target URL for the POST request
            payload: Request body data

        Returns:
            HTTP response with status, body, and headers

        Raises:
            Exception: If all retry attempts are exhausted
        """
        ...
