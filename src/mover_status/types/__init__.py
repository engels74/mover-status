"""Type definitions and protocols for mover-status application.

This package provides:
- Data models (immutable dataclasses)
- Protocol definitions (structural subtyping interfaces)
- Type aliases (PEP 695 modern syntax)
"""

from mover_status.types.aliases import (
    NotificationEvent,
    ProviderConfig,
    ProviderRegistry,
)
from mover_status.types.models import (
    DiskSample,
    HealthStatus,
    NotificationData,
    NotificationResult,
    ProgressData,
    Response,
)
from mover_status.types.protocols import (
    HTTPClient,
    MessageFormatter,
    NotificationProvider,
)

__all__ = [
    # Type aliases
    "NotificationEvent",
    "ProviderConfig",
    "ProviderRegistry",
    # Data models
    "DiskSample",
    "HealthStatus",
    "NotificationData",
    "NotificationResult",
    "ProgressData",
    "Response",
    # Protocols
    "HTTPClient",
    "MessageFormatter",
    "NotificationProvider",
]
