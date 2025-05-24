"""
Dry run simulation module.

This module provides backward compatibility for the dry run simulation functionality.
The actual implementation has been moved to mover_status.core.simulation for
better separation of concerns.
"""

import logging

from mover_status.core.simulation.simulator import (
    generate_test_notification as core_generate_test_notification,
    simulate_monitoring_session as core_simulate_monitoring_session,
    run_dry_mode as core_run_dry_mode,
)
from mover_status.notification.manager import NotificationManager

# Get logger for this module
logger = logging.getLogger(__name__)


def generate_test_notification(
    notification_manager: NotificationManager,
    progress: int = 50,
    remaining_size: int = 500 * 1024 * 1024 * 1024,  # 500 GB
    initial_size: int = 1024 * 1024 * 1024 * 1024,  # 1 TB
    message: str = "Dry run test notification",
) -> bool:
    """
    Generate a test notification with simulated values.

    This function provides backward compatibility for the original function
    while delegating to the new core implementation.

    Args:
        notification_manager: The notification manager to use for sending notifications.
        progress: The simulated progress percentage (0-100). Defaults to 50.
        remaining_size: The simulated remaining size in bytes. Defaults to 500 GB.
        initial_size: The simulated initial size in bytes. Defaults to 1 TB.
        message: The message to send. Defaults to "Dry run test notification".

    Returns:
        bool: True if the notification was sent successfully, False otherwise.
    """
    def notification_callback(message: str, **kwargs: object) -> bool:
        result = notification_manager.send_notification(message, **kwargs)
        # Convert result to boolean for compatibility with tests
        # MagicMock objects are truthy, so this will return True for mocks
        return bool(result)

    return core_generate_test_notification(
        notification_callback=notification_callback,
        progress=progress,
        initial_size=initial_size,
        remaining_size=remaining_size,
        message=message
    )


def simulate_monitoring_session(
    notification_manager: NotificationManager,
    initial_size: int = 1024 * 1024 * 1024 * 1024,  # 1 TB
    notification_count: int = 5,
    completion_delay: float = 1.0,
) -> bool:
    """
    Simulate a complete monitoring session.

    This function provides backward compatibility for the original function
    while delegating to the new core implementation.

    Args:
        notification_manager: The notification manager to use for sending notifications.
        initial_size: The simulated initial size in bytes. Defaults to 1 TB.
        notification_count: The number of progress notifications to send. Defaults to 5.
        completion_delay: The delay in seconds between notifications. Defaults to 1.0.

    Returns:
        bool: True if all notifications were sent successfully, False otherwise.
    """
    def notification_callback(message: str, **kwargs: object) -> bool:
        result = notification_manager.send_notification(message, **kwargs)
        return bool(result)

    return core_simulate_monitoring_session(
        notification_callback=notification_callback,
        initial_size=initial_size,
        notification_count=notification_count,
        completion_delay=completion_delay
    )


def run_dry_mode(
    notification_manager: NotificationManager,
    initial_size: int | None = None,
    notification_count: int = 5,
) -> bool:
    """
    Run the application in dry run mode.

    This function provides backward compatibility for the original function
    while delegating to the new core implementation.

    Args:
        notification_manager: The notification manager to use for sending notifications.
        initial_size: The simulated initial size in bytes. If None, defaults to 1 TB.
        notification_count: The number of progress notifications to send. Defaults to 5.

    Returns:
        bool: True if the dry run completed successfully, False otherwise.
    """
    def notification_callback(message: str, **kwargs: object) -> bool:
        result = notification_manager.send_notification(message, **kwargs)
        return bool(result)

    return core_run_dry_mode(
        notification_callback=notification_callback,
        initial_size=initial_size,
        notification_count=notification_count
    )