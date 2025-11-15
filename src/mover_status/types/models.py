"""Data models for mover-status application.

This module defines immutable dataclasses used throughout the application
for type-safe data transfer between components.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class NotificationData:
    """Generic notification data for all providers.

    Represents the data payload sent to notification providers,
    containing transfer progress information and metadata.
    """

    event_type: str  # "started", "progress", "completed"
    percent: float
    remaining_data: str  # Human-readable format
    moved_data: str
    total_data: str
    rate: str
    etc_timestamp: datetime | None
    correlation_id: str


@dataclass(slots=True)
class NotificationResult:
    """Result of notification delivery attempt.

    Captures the outcome of sending a notification to a provider,
    including success status, timing, and error details if applicable.
    """

    success: bool
    provider_name: str
    error_message: str | None
    delivery_time_ms: float


@dataclass(slots=True)
class HealthStatus:
    """Provider health status.

    Tracks the health and connectivity status of a notification provider,
    including failure tracking for circuit breaker patterns.
    """

    is_healthy: bool
    last_check: datetime
    consecutive_failures: int
    error_message: str | None


@dataclass(slots=True)
class Response:
    """HTTP response.

    Represents an HTTP response with status code, body, and headers.
    """

    status: int
    body: Mapping[str, object]
    headers: Mapping[str, str]


@dataclass(slots=True, frozen=True)
class DiskSample:
    """Immutable disk usage sample for tracking data movement over time.

    Represents a point-in-time snapshot of disk usage, used by the progress
    calculator to track data movement rates across sampling intervals.
    """

    timestamp: datetime
    bytes_used: int
    path: str


@dataclass(slots=True, frozen=True)
class ProgressData:
    """Immutable progress calculation result containing all progress metrics.

    Represents the output from progress calculator pure functions, containing
    comprehensive metrics about data movement progress including percentage,
    bytes moved, transfer rate, and estimated time of completion.
    """

    percent: float
    remaining_bytes: int
    moved_bytes: int
    total_bytes: int
    rate_bytes_per_second: float
    etc: datetime | None
