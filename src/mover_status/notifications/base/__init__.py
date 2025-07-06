"""Base notification provider classes and interfaces."""

from __future__ import annotations

from .provider import NotificationProvider, with_retry

__all__ = [
    "NotificationProvider",
    "with_retry",
]
