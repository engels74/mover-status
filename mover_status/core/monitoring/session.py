"""
Core monitoring session module.

This module provides the MonitorSession class for tracking the state of the
mover process monitoring without notification dependencies.
"""

import time
import logging
from typing import Protocol

from mover_status.utils.process import is_mover_running
from mover_status.utils.data import get_directory_size
from mover_status.core.calculation.progress import calculate_progress
from mover_status.core.calculation.time import calculate_eta

# Get logger for this module
logger = logging.getLogger(__name__)


class NotificationCallback(Protocol):
    """Protocol for notification callbacks."""
    def __call__(self, message: str, **kwargs: object) -> bool: ...


class MonitorSession:
    """
    Core monitoring session class.

    This class tracks the state of the mover process monitoring without
    dependencies on the notification system. It provides pure monitoring
    functionality that can be used independently.

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
        progress_history: List of (timestamp, progress) tuples tracking progress over time.
        total_data_moved: Total bytes moved from cache to array.
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
        self.last_notification_progress: int = -1
        self.progress_history: list[tuple[float, int]] = []
        self.total_data_moved: int = 0

    def start_monitoring(self) -> None:
        """
        Start the monitoring session.

        This method initializes the monitoring session by checking if the mover
        process is running, calculating the initial size of the cache directory,
        and setting up the monitoring state.

        Raises:
            RuntimeError: If the mover process is not running.
        """
        logger.info("Starting monitoring session")

        # Check if mover is running
        if not is_mover_running(self.mover_path):
            raise RuntimeError("Mover process is not running")

        # Calculate initial size
        self.initial_size = get_directory_size(self.cache_path, self.exclusions)
        logger.info("Initial cache size: %d bytes", self.initial_size)

        # Initialize monitoring state
        current_time = time.time()
        self.is_monitoring = True
        self.start_time = current_time
        self.last_check_time = current_time
        self.last_size = self.initial_size
        self.last_progress = 0
        self.progress_history = [(current_time, 0)]
        self.total_data_moved = 0

        logger.info("Monitoring session started")

    def stop_monitoring(self) -> None:
        """
        Stop the monitoring session.

        This method stops the monitoring session but preserves the monitoring
        state for analysis.
        """
        logger.info("Stopping monitoring session")
        self.is_monitoring = False

    def reset_monitoring(self) -> None:
        """
        Reset the monitoring session.

        This method resets all monitoring state to initial values.
        """
        logger.info("Resetting monitoring session")
        self.is_monitoring = False
        self.initial_size = None
        self.start_time = None
        self.last_check_time = None
        self.last_size = None
        self.last_progress = None
        self.last_notification_progress = -1
        self.progress_history = []
        self.total_data_moved = 0

    def update_progress(self) -> None:
        """
        Update the progress of the monitoring session.

        This method calculates the current progress by checking the current size
        of the cache directory and updating the monitoring state.

        Raises:
            RuntimeError: If the monitoring session is not active.
        """
        if not self.is_monitoring:
            raise RuntimeError("Monitoring session is not active")

        # Get current size
        current_size = get_directory_size(self.cache_path, self.exclusions)
        current_time = time.time()

        # Calculate progress
        if self.initial_size is not None:
            progress = calculate_progress(self.initial_size, current_size)
            total_moved = self.initial_size - current_size

            # Update state
            self.last_size = current_size
            self.last_progress = progress
            self.last_check_time = current_time
            self.total_data_moved = total_moved

            # Add to progress history
            self.progress_history.append((current_time, progress))

            logger.debug("Progress updated: %d%% (%d bytes remaining)", progress, current_size)

    def should_send_notification(self) -> bool:
        """
        Determine if a notification should be sent based on progress thresholds.

        Returns:
            bool: True if a notification should be sent, False otherwise.
        """
        if self.last_progress is None:
            return False

        # Always send notification for 100% completion
        if self.last_progress == 100:
            return True

        # Check if we've reached a notification threshold
        if self.last_progress >= self.last_notification_progress + self.notification_increment:
            return True

        # Send initial notification at 0%
        if self.last_notification_progress == -1 and self.last_progress == 0:
            return True

        return False

    def wait_for_mover_start(self) -> bool:
        """
        Wait for the mover process to start.

        This method polls for the mover process to start up to the maximum wait time.

        Returns:
            bool: True if the mover process started, False if it timed out.
        """
        logger.info("Waiting for mover process to start")
        start_time = time.time()

        while time.time() - start_time < self.max_wait_time:
            if is_mover_running(self.mover_path):
                logger.info("Mover process started")
                return True

            time.sleep(self.poll_interval)

        logger.warning("Timed out waiting for mover process to start")
        return False

    def is_mover_process_ended(self) -> bool:
        """
        Check if the mover process has ended.

        Returns:
            bool: True if the mover process has ended, False otherwise.
        """
        return not is_mover_running(self.mover_path)

    def calculate_initial_size(self) -> int:
        """
        Calculate the initial size of the cache directory.

        Returns:
            int: The initial size in bytes.
        """
        return get_directory_size(self.cache_path, self.exclusions)

    def get_estimated_completion_time(self) -> float | None:
        """
        Get the estimated completion time based on current progress.

        Returns:
            float | None: The estimated completion time as a timestamp, or None if it cannot be calculated.
        """
        if not self.is_monitoring or self.start_time is None or self.last_progress is None:
            return None

        current_time = time.time()
        return calculate_eta(self.start_time, current_time, self.last_progress)

    def get_progress_rate(self) -> float:
        """
        Calculate the current progress rate in percentage per second.

        Returns:
            float: The progress rate in percentage per second.
        """
        if len(self.progress_history) < 2:
            return 0.0

        # Calculate rate based on the entire history
        start_time, start_progress = self.progress_history[0]
        end_time, end_progress = self.progress_history[-1]

        time_diff = end_time - start_time
        progress_diff = end_progress - start_progress

        if time_diff <= 0:
            return 0.0

        return progress_diff / time_diff

    def get_notification_thresholds(self) -> list[int]:
        """
        Get the list of progress thresholds for notifications.

        Returns:
            list[int]: A list of progress percentages where notifications should be sent.
        """
        if self.notification_increment <= 0:
            # Default to 25% if invalid increment
            increment = 25
        else:
            increment = self.notification_increment

        thresholds: list[int] = []
        for i in range(0, 101, increment):
            thresholds.append(i)

        # Always include 100% completion
        if 100 not in thresholds:
            thresholds.append(100)

        return sorted(thresholds)
