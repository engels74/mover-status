"""Base notification provider classes and interfaces."""

from __future__ import annotations

from .provider import NotificationProvider, with_retry
from .retry import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
    RetryTimeoutError,
    with_advanced_retry,
    with_timeout
)
from .registry import (
    ProviderRegistry,
    ProviderRegistryError,
    ProviderMetadata,
    ProviderDiscovery,
    ProviderLifecycleManager,
    get_global_registry,
    reset_global_registry
)
from .config_validator import (
    ConfigValidator,
    ConfigValidationError,
    CredentialValidator,
    SchemaValidator,
    EnvironmentValidator,
    ValidationResult,
    ValidationSeverity,
    ValidationIssue,
)

__all__ = [
    # Provider classes
    "NotificationProvider",
    "with_retry",
    # Retry and circuit breaker
    "CircuitBreaker",
    "CircuitBreakerError",
    "CircuitBreakerState",
    "RetryTimeoutError",
    "with_advanced_retry",
    "with_timeout",
    # Registry system
    "ProviderRegistry",
    "ProviderRegistryError",
    "ProviderMetadata",
    "ProviderDiscovery",
    "ProviderLifecycleManager",
    "get_global_registry",
    "reset_global_registry",
    # Configuration validation
    "ConfigValidator",
    "ConfigValidationError",
    "CredentialValidator",
    "SchemaValidator",
    "EnvironmentValidator",
    "ValidationResult",
    "ValidationSeverity",
    "ValidationIssue",
]


