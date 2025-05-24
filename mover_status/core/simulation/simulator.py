"""
Dry run simulation module.

This module provides functionality for simulating a monitoring session without
actually monitoring the mover process and without notification dependencies.
"""

import time
import logging
from typing import Protocol

# Get logger for this module
logger = logging.getLogger(__name__)


class NotificationCallback(Protocol):
    """Protocol for notification callbacks."""
    def __call__(self, message: str, **kwargs: object) -> bool: ...


def generate_test_notification(
    notification_callback: NotificationCallback,
    progress: int = 50,
    initial_size: int = 1024 * 1024 * 1024 * 1024,  # 1 TB
    remaining_size: int = 512 * 1024 * 1024 * 1024,  # 512 GB
    message: str = "Test notification"
) -> bool:
    """
    Generate a test notification with simulated progress data.

    This function generates a test notification with the specified progress
    and size values. It is used for testing notification providers without
    running an actual monitoring session.

    Args:
        notification_callback: The callback function for sending notifications.
        progress: The progress percentage to simulate. Defaults to 50.
        initial_size: The simulated initial size in bytes. Defaults to 1 TB.
        remaining_size: The simulated remaining size in bytes. Defaults to 512 GB.
        message: The message to send. Defaults to "Test notification".

    Returns:
        bool: True if the notification was sent successfully, False otherwise.
    """
    logger.info("Generating test notification with progress: %d%%", progress)

    # Calculate total moved based on progress
    total_moved = initial_size - remaining_size

    # Calculate a simulated ETA based on progress
    eta: float | None = None
    if progress < 100 and progress > 0:
        # Simulate an ETA 1 hour in the future
        eta = time.time() + 3600
    elif progress == 100:
        # Completed, so ETA is now
        eta = time.time()
    # else: progress is 0, so eta remains None (calculating)

    # Send the notification
    result = notification_callback(
        message,
        raw_values={
            "progress": progress,
            "remaining_size": remaining_size,
            "initial_size": initial_size,
            "eta": eta,
            "total_moved": total_moved
        }
    )

    logger.info("Test notification sent: %s", "success" if result else "failed")
    return result


def simulate_monitoring_session(
    notification_callback: NotificationCallback,
    initial_size: int = 1024 * 1024 * 1024 * 1024,  # 1 TB
    notification_count: int = 5,
    completion_delay: float = 1.0,
) -> bool:
    """
    Simulate a complete monitoring session.

    This function simulates a monitoring session by sending a series of
    notifications with increasing progress values, followed by a completion
    notification.

    Args:
        notification_callback: The callback function for sending notifications.
        initial_size: The simulated initial size in bytes. Defaults to 1 TB.
        notification_count: The number of progress notifications to send. Defaults to 5.
        completion_delay: The delay in seconds between notifications. Defaults to 1.0.

    Returns:
        bool: True if all notifications were sent successfully, False otherwise.
    """
    logger.info("Starting simulated monitoring session")
    logger.info("Initial size: %d bytes", initial_size)
    logger.info("Notification count: %d", notification_count)

    all_successful = True

    # Calculate progress increments
    if notification_count > 0:
        progress_increment = 100 // notification_count
    else:
        progress_increment = 25  # Default to 25% increments

    # Send initial notification (0% progress)
    remaining_size = initial_size
    result = generate_test_notification(
        notification_callback,
        progress=0,
        initial_size=initial_size,
        remaining_size=remaining_size,
        message="Mover process started"
    )
    if not result:
        all_successful = False

    time.sleep(completion_delay)

    # Send progress notifications
    for i in range(1, notification_count + 1):
        progress = min(i * progress_increment, 99)  # Don't exceed 99% until completion
        remaining_size = initial_size - (initial_size * progress // 100)

        result = generate_test_notification(
            notification_callback,
            progress=progress,
            initial_size=initial_size,
            remaining_size=remaining_size,
            message=f"Mover progress: {progress}%"
        )
        if not result:
            all_successful = False

        time.sleep(completion_delay)

    # Send completion notification (100% progress)
    result = generate_test_notification(
        notification_callback,
        progress=100,
        initial_size=initial_size,
        remaining_size=0,
        message="Mover process completed"
    )
    if not result:
        all_successful = False

    logger.info("Simulated monitoring session completed: %s", "success" if all_successful else "partial failure")
    return all_successful


def run_dry_mode(
    notification_callback: NotificationCallback,
    initial_size: int | None = None,
    notification_count: int = 5,
) -> bool:
    """
    Run the application in dry run mode.

    This function is the main entry point for running the application in dry run
    mode. It simulates a monitoring session without actually monitoring the mover
    process.

    Args:
        notification_callback: The callback function for sending notifications.
        initial_size: The simulated initial size in bytes. If None, defaults to 1 TB.
        notification_count: The number of progress notifications to send. Defaults to 5.

    Returns:
        bool: True if the dry run completed successfully, False otherwise.
    """
    logger.info("Running in dry run mode")

    # Use default initial size if not specified
    if initial_size is None:
        initial_size = 1024 * 1024 * 1024 * 1024  # 1 TB

    # Simulate a monitoring session
    return simulate_monitoring_session(
        notification_callback,
        initial_size=initial_size,
        notification_count=notification_count
    )
