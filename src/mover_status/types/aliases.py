"""Type aliases using modern PEP 695 syntax.

This module defines complex type aliases for common type patterns
throughout the application, using Python 3.13+ type statement syntax.
"""

from collections.abc import Mapping

from mover_status.types.models import NotificationData

# Provider configuration type
# Generic mapping type for provider-specific configuration data
# Supports plugin-based architecture where providers define their own config schemas
# Each provider validates its own configuration using Pydantic at load time
type ProviderConfig = Mapping[str, object]

# Notification event type alias
# Represents notification event data sent to providers
# Currently aliases the NotificationData dataclass
type NotificationEvent = NotificationData
