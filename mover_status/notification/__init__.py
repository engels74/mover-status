"""
Notification system for the Mover Status Monitor.

This package provides the notification system for the Mover Status Monitor.
It includes an abstract base class for notification providers and concrete
implementations for various notification platforms.
"""

from mover_status.notification.base import NotificationProvider

__all__ = ["NotificationProvider"]