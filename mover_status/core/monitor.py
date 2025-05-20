"""
Monitor module for the Mover Status Monitor.

This module provides the core monitoring functionality for tracking the
progress of the mover process in Unraid systems.
"""

import time
import logging

from mover_status.utils.process import is_mover_running
from mover_status.utils.data import get_directory_size
from mover_status.core.calculation.progress import calculate_progress

# Get logger for this module
logger = logging.getLogger(__name__)


class MonitorSession:
    """
    Class for tracking the state of a mover process monitoring session.

    This class maintains the state of a monitoring session, including the
    initial size of the cache directory, the current progress, and the
    timing information needed for ETA calculations.

    Attributes:
        is_monitoring: Whether monitoring is currently active.
        mover_path: Path to the mover executable.
        cache_path: Path to the cache directory being monitored.
        exclusions: List of paths to exclude from size calculations.
        notification_increment: Percentage increment for notifications.
        poll_interval: Time in seconds between checks for mover process.
        max_wait_time: Maximum time in seconds to wait for mover process to start.
        initial_size: Initial size of the cache directory in bytes.
        start_time: Timestamp when monitoring started.
        last_check_time: Timestamp of the last progress check.
        last_size: Size of the cache directory at the last check.
        last_progress: Progress percentage at the last check.
        last_notification_progress: Progress percentage at the last notification.
    """

    def __init__(
        self,
        mover_path: str = "/usr/local/sbin/mover",
        cache_path: str = "/mnt/cache",
        exclusions: list[str] | None = None,
        notification_increment: int = 25,
        poll_interval: float = 1.0,
        max_wait_time: int = 300
    ) -> None:
        """
        Initialize a new monitoring session.

        Args:
            mover_path: Path to the mover executable. Defaults to "/usr/local/sbin/mover".
            cache_path: Path to the cache directory to monitor. Defaults to "/mnt/cache".
            exclusions: List of paths to exclude from size calculations. Defaults to None.
            notification_increment: Percentage increment for notifications. Defaults to 25.
            poll_interval: Time in seconds between checks for mover process. Defaults to 1.0.
            max_wait_time: Maximum time in seconds to wait for mover process to start. Defaults to 300.
        """
        # Configuration parameters
        self.mover_path: str = mover_path
        self.cache_path: str = cache_path
        self.exclusions: list[str] = exclusions or []
        self.notification_increment: int = notification_increment
        self.poll_interval: float = poll_interval
        self.max_wait_time: int = max_wait_time

        # Monitoring state
        self.is_monitoring: bool = False
        self.initial_size: int | None = None
        self.start_time: float | None = None
        self.last_check_time: float | None = None
        self.last_size: int | None = None
        self.last_progress: int | None = None
        self.last_notification_progress: int = -1  # Initialize to -1 to ensure 0% notification

    def start_monitoring(self) -> None:
        """
        Start monitoring the mover process.

        This method initializes the monitoring session by checking if the mover
        process is running and calculating the initial size of the cache directory.

        Raises:
            RuntimeError: If the mover process is not running.
            FileNotFoundError: If the cache directory does not exist.
            RuntimeError: If the directory size calculation fails.
        """
        # Check if mover is running
        if not is_mover_running(self.mover_path):
            logger.error(f"Mover process not found at {self.mover_path}")
            raise RuntimeError("Mover process is not running")

        # Calculate initial size
        initial_size = get_directory_size(self.cache_path, self.exclusions)
        current_time = time.time()

        # Initialize monitoring state
        self.is_monitoring = True
        self.initial_size = initial_size
        self.start_time = current_time
        self.last_check_time = current_time
        self.last_size = initial_size
        self.last_progress = 0

        logger.info(f"Started monitoring mover process. Initial cache size: {initial_size} bytes")

    def stop_monitoring(self) -> None:
        """
        Stop monitoring the mover process.

        This method stops the monitoring session but preserves the current state
        for final calculations and notifications.
        """
        self.is_monitoring = False
        logger.info("Stopped monitoring mover process")

    def reset_monitoring(self) -> None:
        """
        Reset the monitoring session to its initial state.

        This method clears all monitoring state variables, allowing the session
        to be reused for a new monitoring cycle.
        """
        self.is_monitoring = False
        self.initial_size = None
        self.start_time = None
        self.last_check_time = None
        self.last_size = None
        self.last_progress = None
        self.last_notification_progress = -1

        logger.info("Reset monitoring session")

    def update_progress(self) -> None:
        """
        Update the progress of the monitoring session.

        This method calculates the current size of the cache directory and
        updates the progress percentage.

        Raises:
            RuntimeError: If the monitoring session is not active.
            FileNotFoundError: If the cache directory does not exist.
            RuntimeError: If the directory size calculation fails.
        """
        if not self.is_monitoring:
            raise RuntimeError("Monitoring session is not active")

        if self.initial_size is None:
            raise RuntimeError("Initial size not set")

        # Get current size and time
        current_size = get_directory_size(self.cache_path, self.exclusions)
        current_time = time.time()

        # Calculate progress
        progress = calculate_progress(self.initial_size, current_size)

        # Update state
        self.last_size = current_size
        self.last_progress = progress
        self.last_check_time = current_time

        logger.debug(f"Updated progress: {progress}%, current size: {current_size} bytes")

    def should_send_notification(self) -> bool:
        """
        Determine if a notification should be sent based on the current progress.

        This method checks if the current progress has reached a notification
        threshold based on the notification increment.

        Returns:
            bool: True if a notification should be sent, False otherwise.

        Raises:
            RuntimeError: If the monitoring session is not active.
        """
        if not self.is_monitoring:
            raise RuntimeError("Monitoring session is not active")

        if self.last_progress is None:
            raise RuntimeError("Progress not calculated")

        # Always notify at 0% (initial) and 100% (completion)
        if self.last_progress == 0 and self.last_notification_progress == -1:
            return True

        if self.last_progress == 100 and self.last_notification_progress < 100:
            return True

        # Calculate the progress rounded down to the nearest increment
        progress_increment = (self.last_progress // self.notification_increment) * self.notification_increment

        # Notify if we've reached a new increment threshold
        if progress_increment > self.last_notification_progress:
            return True

        return False

    def wait_for_mover_start(self) -> bool:
        """
        Wait for the mover process to start.

        This method polls for the mover process at regular intervals until
        it is detected or the maximum wait time is reached.

        Returns:
            bool: True if the mover process was detected, False if the wait timed out.
        """
        logger.info(f"Waiting for mover process to start (max wait: {self.max_wait_time}s)")

        start_wait_time = time.time()

        while True:
            # Check if mover is running
            if is_mover_running(self.mover_path):
                logger.info("Mover process detected")
                return True

            # Check if we've exceeded the maximum wait time
            current_time = time.time()
            if current_time - start_wait_time > self.max_wait_time:
                logger.warning(f"Timed out waiting for mover process after {self.max_wait_time}s")
                return False

            # Wait before checking again
            time.sleep(self.poll_interval)

    def is_mover_process_ended(self) -> bool:
        """
        Check if the mover process has ended.

        Returns:
            bool: True if the mover process is no longer running, False otherwise.
        """
        # Check if mover is still running
        is_running = is_mover_running(self.mover_path)

        # Return the opposite (True if not running)
        return not is_running

    def calculate_initial_size(self) -> int:
        """
        Calculate the initial size of the cache directory.

        This method is used to determine the starting point for progress tracking
        when the mover process begins.

        Returns:
            int: The size of the cache directory in bytes.

        Raises:
            FileNotFoundError: If the cache directory does not exist.
            RuntimeError: If the directory size calculation fails.
        """
        logger.info(f"Calculating initial size of {self.cache_path}")

        # Get the directory size
        initial_size = get_directory_size(self.cache_path, self.exclusions)

        logger.info(f"Initial cache size: {initial_size} bytes")
        return initial_size
