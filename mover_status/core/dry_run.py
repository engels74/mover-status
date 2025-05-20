"""
Dry run simulation module.

This module provides functionality for simulating a monitoring session without
actually monitoring the mover process. It is used for testing and demonstration
purposes.
"""

import time
import logging

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

    This function sends a notification with simulated progress values to test
    the notification system without actually monitoring the mover process.

    Args:
        notification_manager: The notification manager to use for sending notifications.
        progress: The simulated progress percentage (0-100). Defaults to 50.
        remaining_size: The simulated remaining size in bytes. Defaults to 500 GB.
        initial_size: The simulated initial size in bytes. Defaults to 1 TB.
        message: The message to send. Defaults to "Dry run test notification".

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
    result = notification_manager.send_notification(
        message,
        raw_values={
            "progress": progress,
            "remaining_size": remaining_size,
            "initial_size": initial_size,
            "eta": eta,
            "total_moved": total_moved
        }
    )

    # Return True if the notification was sent successfully
    return True if result else False


def simulate_monitoring_session(
    notification_manager: NotificationManager,
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
        notification_manager: The notification manager to use for sending notifications.
        initial_size: The simulated initial size in bytes. Defaults to 1 TB.
        notification_count: The number of progress notifications to send. Defaults to 5.
        completion_delay: The delay in seconds between notifications. Defaults to 1.0.

    Returns:
        bool: True if the simulation completed successfully, False otherwise.
    """
    logger.info("Starting dry run simulation with %d notifications", notification_count)

    # Send initial notification (0% progress)
    success = generate_test_notification(
        notification_manager,
        progress=0,
        remaining_size=initial_size,
        initial_size=initial_size,
        message="Dry run: Starting mover simulation"
    )

    if not success:
        logger.error("Failed to send initial notification")
        return False

    # Send progress notifications
    for i in range(notification_count):
        # Calculate progress percentage
        progress = (i + 1) * (100 // (notification_count + 1))

        # Calculate remaining size based on progress
        remaining_size = initial_size * (100 - progress) // 100

        # Send notification
        success = generate_test_notification(
            notification_manager,
            progress=progress,
            remaining_size=remaining_size,
            initial_size=initial_size,
            message=f"Dry run: Mover progress update {progress}%"
        )

        if not success:
            logger.error("Failed to send progress notification %d", i + 1)
            return False

        # Wait before sending the next notification
        time.sleep(completion_delay)

    # Send completion notification (100% progress)
    success = generate_test_notification(
        notification_manager,
        progress=100,
        remaining_size=0,
        initial_size=initial_size,
        message="Dry run: Mover process completed"
    )

    if not success:
        logger.error("Failed to send completion notification")
        return False

    logger.info("Dry run simulation completed successfully")
    return True


def run_dry_mode(
    notification_manager: NotificationManager,
    initial_size: int | None = None,
    notification_count: int = 5,
) -> bool:
    """
    Run the application in dry run mode.

    This function is the main entry point for running the application in dry run
    mode. It simulates a monitoring session without actually monitoring the mover
    process.

    Args:
        notification_manager: The notification manager to use for sending notifications.
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
        notification_manager,
        initial_size=initial_size,
        notification_count=notification_count
    )
