"""
Monitor module for the Mover Status Monitor.

This module provides backward compatibility for the core monitoring functionality.
The actual implementation has been moved to mover_status.core.monitoring for
better separation of concerns.
"""

import logging
import time  # pyright: ignore[reportUnusedImport]

from mover_status.core.monitoring.session import MonitorSession as CoreMonitorSession
from mover_status.core.monitoring.tracker import ProgressTracker
from mover_status.notification.manager import NotificationManager

# Import functions that tests expect to be available for mocking
from mover_status.utils.process import is_mover_running  # pyright: ignore[reportUnusedImport]
from mover_status.utils.data import get_directory_size  # pyright: ignore[reportUnusedImport]
from mover_status.core.calculation.progress import calculate_progress  # pyright: ignore[reportUnusedImport]
from mover_status.core.calculation.time import calculate_eta  # pyright: ignore[reportUnusedImport]

# Get logger for this module
logger = logging.getLogger(__name__)


class MonitorSession:
    """
    Monitor session class (backward compatibility wrapper).

    This class provides backward compatibility for the original MonitorSession
    interface while delegating to the new core monitoring implementation.
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
        # Create the core monitoring session
        self._core_session: CoreMonitorSession = CoreMonitorSession(
            mover_path=mover_path,
            cache_path=cache_path,
            exclusions=exclusions,
            notification_increment=notification_increment,
            poll_interval=poll_interval,
            max_wait_time=max_wait_time
        )

        # Create the progress tracker
        self._tracker: ProgressTracker = ProgressTracker(self._core_session)

    # Delegate properties to the core session
    @property
    def is_monitoring(self) -> bool:
        """Whether monitoring is currently active."""
        return self._core_session.is_monitoring

    @is_monitoring.setter
    def is_monitoring(self, value: bool) -> None:
        """Set monitoring state."""
        self._core_session.is_monitoring = value

    @property
    def mover_path(self) -> str:
        """Path to the mover executable."""
        return self._core_session.mover_path

    @property
    def cache_path(self) -> str:
        """Path to the cache directory being monitored."""
        return self._core_session.cache_path

    @property
    def exclusions(self) -> list[str]:
        """List of paths to exclude from size calculations."""
        return self._core_session.exclusions

    @property
    def notification_increment(self) -> int:
        """Percentage increment for notifications."""
        return self._core_session.notification_increment

    @notification_increment.setter
    def notification_increment(self, value: int) -> None:
        """Set the notification increment (for testing)."""
        self._core_session.notification_increment = value

    @property
    def poll_interval(self) -> float:
        """Time in seconds between checks for mover process."""
        return self._core_session.poll_interval

    @property
    def max_wait_time(self) -> int:
        """Maximum time in seconds to wait for mover process to start."""
        return self._core_session.max_wait_time

    @property
    def initial_size(self) -> int | None:
        """Initial size of the cache directory in bytes."""
        return self._core_session.initial_size

    @initial_size.setter
    def initial_size(self, value: int | None) -> None:
        """Set the initial size (for testing)."""
        self._core_session.initial_size = value

    @property
    def start_time(self) -> float | None:
        """Timestamp when monitoring started."""
        return self._core_session.start_time

    @start_time.setter
    def start_time(self, value: float | None) -> None:
        """Set the start time (for testing)."""
        self._core_session.start_time = value

    @property
    def last_check_time(self) -> float | None:
        """Timestamp of the last progress check."""
        return self._core_session.last_check_time

    @property
    def last_size(self) -> int | None:
        """Size of the cache directory at the last check."""
        return self._core_session.last_size

    @property
    def last_progress(self) -> int | None:
        """Progress percentage at the last check."""
        return self._core_session.last_progress

    @last_progress.setter
    def last_progress(self, value: int | None) -> None:
        """Set the last progress (for testing)."""
        self._core_session.last_progress = value

    @property
    def last_notification_progress(self) -> int:
        """Progress percentage at the last notification."""
        return self._core_session.last_notification_progress

    @last_notification_progress.setter
    def last_notification_progress(self, value: int) -> None:
        """Set the last notification progress."""
        self._core_session.last_notification_progress = value

    @property
    def progress_history(self) -> list[tuple[float, int]]:
        """List of (timestamp, progress) tuples tracking progress over time."""
        return self._core_session.progress_history

    @property
    def total_data_moved(self) -> int:
        """Total bytes moved from cache to array."""
        return self._core_session.total_data_moved

    # Delegate methods to the core session
    def start_monitoring(self) -> None:
        """Start the monitoring session."""
        return self._core_session.start_monitoring()

    def stop_monitoring(self) -> None:
        """Stop the monitoring session."""
        return self._core_session.stop_monitoring()

    def reset_monitoring(self) -> None:
        """Reset the monitoring session."""
        return self._core_session.reset_monitoring()

    def update_progress(self) -> None:
        """Update the progress of the monitoring session."""
        return self._core_session.update_progress()

    def should_send_notification(self) -> bool:
        """Determine if a notification should be sent."""
        return self._core_session.should_send_notification()

    def wait_for_mover_start(self) -> bool:
        """Wait for the mover process to start."""
        return self._core_session.wait_for_mover_start()

    def is_mover_process_ended(self) -> bool:
        """Check if the mover process has ended."""
        return self._core_session.is_mover_process_ended()

    def calculate_initial_size(self) -> int:
        """Calculate the initial size of the cache directory."""
        return self._core_session.calculate_initial_size()

    def get_estimated_completion_time(self) -> float | None:
        """Get the estimated completion time."""
        return self._core_session.get_estimated_completion_time()

    def get_progress_rate(self) -> float:
        """Calculate the progress rate."""
        return self._core_session.get_progress_rate()

    def get_notification_thresholds(self) -> list[int]:
        """Get the notification thresholds."""
        return self._core_session.get_notification_thresholds()

    # Methods that use NotificationManager (backward compatibility)
    def handle_process_completion(self, notification_manager: NotificationManager) -> None:
        """Handle the completion of the mover process."""
        def notification_callback(message: str, **kwargs: object) -> bool:
            return notification_manager.send_notification(message, **kwargs)

        self._tracker.handle_process_completion(notification_callback)

    def send_progress_notification(self, notification_manager: NotificationManager) -> None:
        """Send a progress notification if needed."""
        if self.should_send_notification():
            def notification_callback(message: str, **kwargs: object) -> bool:
                return notification_manager.send_notification(message, **kwargs)

            self._tracker.send_progress_notification(notification_callback)
            self.last_notification_progress = self.last_progress or 0

    def run_monitoring_loop(
        self,
        notification_manager: NotificationManager,
        max_cycles: int | None = None,
        restart_delay: float = 10.0
    ) -> None:
        """Run the main monitoring loop."""
        def notification_callback(message: str, **kwargs: object) -> bool:
            return notification_manager.send_notification(message, **kwargs)

        self._tracker.run_monitoring_loop(
            notification_callback=notification_callback,
            max_cycles=max_cycles,
            restart_delay=restart_delay
        )