"""Type definitions and protocols for mover-status application.

This package provides:
- Data models (immutable dataclasses)
- Protocol definitions (structural subtyping interfaces)
"""

from mover_status.types.models import (
    HealthStatus,
    NotificationData,
    NotificationResult,
    Response,
)
from mover_status.types.protocols import (
    HTTPClient,
    MessageFormatter,
    NotificationProvider,
)

__all__ = [
    # Data models
    "HealthStatus",
    "NotificationData",
    "NotificationResult",
    "Response",
    # Protocols
    "HTTPClient",
    "MessageFormatter",
    "NotificationProvider",
]
