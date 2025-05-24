"""
Progress tracking utilities.

This module provides utilities for tracking progress over time and managing
monitoring state without notification dependencies.
"""

import time
import logging

from mover_status.core.monitoring.session import MonitorSession, NotificationCallback

# Get logger for this module
logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Progress tracking utility class.

    This class provides utilities for tracking progress over time and managing
    the monitoring loop without direct notification dependencies.
    """

    def __init__(self, session: MonitorSession) -> None:
        """
        Initialize the progress tracker.

        Args:
            session: The monitoring session to track.
        """
        self.session: MonitorSession = session

    def run_monitoring_loop(
        self,
        notification_callback: NotificationCallback | None = None,
        max_cycles: int | None = None,
        restart_delay: float = 10.0
    ) -> None:
        """
        Run the main monitoring loop.

        This method continuously monitors the mover process, updating progress
        and calling the notification callback as needed. It can run indefinitely
        or for a specified number of cycles.

        Args:
            notification_callback: Optional callback function for sending notifications.
            max_cycles: Maximum number of monitoring cycles to run. None for unlimited.
            restart_delay: Time in seconds to wait before restarting monitoring after completion.
        """
        cycle_count = 0

        logger.info("Starting main monitoring loop")

        while max_cycles is None or cycle_count < max_cycles:
            try:
                # Wait for mover to start if not already running
                if not self.session.wait_for_mover_start():
                    logger.warning("Mover process did not start within timeout")
                    break

                # Start monitoring
                self.session.start_monitoring()

                # Send initial notification
                if notification_callback and self.session.should_send_notification():
                    self._send_progress_notification(notification_callback)
                    self.session.last_notification_progress = self.session.last_progress or 0

                # Monitor until process completes
                while self.session.is_monitoring and not self.session.is_mover_process_ended():
                    # Update progress
                    self.session.update_progress()

                    # Send notification if threshold reached
                    if notification_callback and self.session.should_send_notification():
                        self._send_progress_notification(notification_callback)
                        self.session.last_notification_progress = self.session.last_progress or 0

                    # Sleep to prevent CPU overuse
                    time.sleep(self.session.poll_interval)

                # Handle process completion
                if self.session.is_monitoring:
                    self.handle_process_completion(notification_callback)

                cycle_count += 1

                # Wait before restarting if not at max cycles
                if max_cycles is None or cycle_count < max_cycles:
                    logger.info("Waiting %s seconds before restarting monitoring", restart_delay)
                    time.sleep(restart_delay)

            except KeyboardInterrupt:
                logger.info("Monitoring interrupted by user")
                break
            except Exception as e:
                logger.error("Error in monitoring loop: %s", e)
                break

        logger.info("Monitoring loop completed")

    def handle_process_completion(self, notification_callback: NotificationCallback | None = None) -> None:
        """
        Handle the completion of the mover process.

        This method handles the completion of the mover process by updating
        the final progress and sending a completion notification.

        Args:
            notification_callback: Optional callback function for sending notifications.
        """
        logger.info("Mover process completed")

        # Update final progress
        self.session.update_progress()

        # Send completion notification
        if notification_callback:
            self._send_completion_notification(notification_callback)

        # Stop monitoring
        self.session.stop_monitoring()

    def _send_progress_notification(self, notification_callback: NotificationCallback) -> None:
        """
        Send a progress notification using the callback.

        Args:
            notification_callback: The callback function for sending notifications.
        """
        if self.session.last_progress is None or self.session.initial_size is None:
            return

        message = f"Mover progress: {self.session.last_progress}%"
        eta = self.session.get_estimated_completion_time()

        _ = notification_callback(
            message,
            raw_values={
                "progress": self.session.last_progress,
                "remaining_size": self.session.last_size,
                "initial_size": self.session.initial_size,
                "eta": eta,
                "total_moved": self.session.total_data_moved
            }
        )

    def send_progress_notification(self, notification_callback: NotificationCallback) -> None:
        """
        Send a progress notification using the callback (public method).

        Args:
            notification_callback: The callback function for sending notifications.
        """
        self._send_progress_notification(notification_callback)

    def _send_completion_notification(self, notification_callback: NotificationCallback) -> None:
        """
        Send a completion notification using the callback.

        Args:
            notification_callback: The callback function for sending notifications.
        """
        message = "Mover process completed"

        _ = notification_callback(
            message,
            raw_values={
                "progress": 100,
                "remaining_size": self.session.last_size,
                "initial_size": self.session.initial_size,
                "eta": None,
                "total_moved": self.session.total_data_moved
            }
        )
