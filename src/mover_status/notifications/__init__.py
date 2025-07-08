"""Notification system for the mover status monitor."""

from __future__ import annotations

from .base import (
    NotificationProvider,
    with_retry,
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
    RetryTimeoutError,
    with_advanced_retry,
    with_timeout,
    ProviderRegistry,
    ProviderRegistryError,
    ProviderMetadata,
    ProviderDiscovery,
    ProviderLifecycleManager,
    get_global_registry,
    reset_global_registry,
    ConfigValidator,
    ConfigValidationError,
    CredentialValidator,
    EnvironmentValidator,
    ValidationResult,
    ValidationSeverity,
    ValidationIssue,
)
from .manager import (
    AsyncDispatcher,
    BatchProcessor,
    DeliveryTracker,
    DispatchResult,
    DispatchStatus,
    MessageQueue,
    ProviderResult,
    QueuedMessage,
    WorkerPool,
)
from .models import Message

__all__ = [
    # Base provider classes
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
    "EnvironmentValidator",
    "ValidationResult",
    "ValidationSeverity",
    "ValidationIssue",
    # Async dispatch infrastructure
    "AsyncDispatcher",
    "BatchProcessor",
    "DeliveryTracker",
    "DispatchResult",
    "DispatchStatus",
    "MessageQueue",
    "ProviderResult",
    "QueuedMessage",
    "WorkerPool",
    # Message models
    "Message",
]