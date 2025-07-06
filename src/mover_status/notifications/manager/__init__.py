"""Notification manager for coordinating notification providers."""

from __future__ import annotations

from .dispatcher import (
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

__all__ = [
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
]
