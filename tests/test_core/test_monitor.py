"""
Tests for the core module reorganization.

This module contains tests for the reorganized core module structure,
ensuring that imports work correctly and backward compatibility is maintained.
"""

# pyright: reportUnusedParameter=false
# pyright: reportAny=false

import time
import pytest
from unittest.mock import patch, MagicMock, call

from mover_status.core.monitor import MonitorSession
from mover_status.notification.manager import NotificationManager


class TestCoreModuleStructure:
    """Tests for the reorganized core module structure."""

    def test_import_reorganized_modules(self) -> None:
        """Test case: Import and use reorganized modules."""
        # Test importing from the new structure
        from mover_status.core.monitoring import MonitorSession as NewMonitorSession
        from mover_status.core.simulation import simulate_monitoring_session
        from mover_status.core.version import get_current_version
        from mover_status.core.calculation import format_bytes

        # Verify that the imports work
        assert NewMonitorSession is not None
        assert simulate_monitoring_session is not None
        assert get_current_version is not None
        assert format_bytes is not None

        # Test that we can create instances
        session = NewMonitorSession()
        assert session is not None
        assert hasattr(session, 'is_monitoring')

    def test_backward_compatibility(self) -> None:
        """Test case: Backward compatibility."""
        # Test that old imports still work
        from mover_status.core.monitor import MonitorSession
        from mover_status.core.dry_run import simulate_monitoring_session as old_simulate
        from mover_status.core.version import get_current_version
        from mover_status.core.calculation import format_bytes

        # Verify that the old imports still work
        assert MonitorSession is not None
        assert old_simulate is not None
        assert get_current_version is not None
        assert format_bytes is not None

        # Test that we can create instances with the old interface
        session = MonitorSession()
        assert session is not None
        assert hasattr(session, 'is_monitoring')


class TestMonitorSession:
    """Tests for the MonitorSession class."""

    def test_init_default_values(self) -> None:
        """Test that MonitorSession initializes with default values."""
        session = MonitorSession()

        # Check default values
        assert session.is_monitoring is False
        assert session.mover_path == "/usr/local/sbin/mover"
        assert session.cache_path == "/mnt/cache"
        assert session.exclusions == []
        assert session.initial_size is None
        assert session.start_time is None
        assert session.last_check_time is None
        assert session.last_size is None
        assert session.last_progress is None
        assert session.last_notification_progress == -1
        assert session.poll_interval == 1.0
        assert session.max_wait_time == 300
        assert session.progress_history == []
        assert session.total_data_moved == 0

    def test_init_custom_values(self) -> None:
        """Test that MonitorSession initializes with custom values."""
        session = MonitorSession(
            mover_path="/custom/mover",
            cache_path="/custom/cache",
            exclusions=["/custom/cache/exclude1", "/custom/cache/exclude2"],
            notification_increment=10,
            poll_interval=5.0,
            max_wait_time=600
        )

        # Check custom values
        assert session.is_monitoring is False
        assert session.mover_path == "/custom/mover"
        assert session.cache_path == "/custom/cache"
        assert session.exclusions == ["/custom/cache/exclude1", "/custom/cache/exclude2"]
        assert session.notification_increment == 10
        assert session.initial_size is None
        assert session.start_time is None
        assert session.last_check_time is None
        assert session.last_size is None
        assert session.last_progress is None
        assert session.last_notification_progress == -1
        assert session.poll_interval == 5.0
        assert session.max_wait_time == 600
        assert session.progress_history == []
        assert session.total_data_moved == 0

    @patch("mover_status.core.monitor.is_mover_running")
    @patch("mover_status.core.monitor.get_directory_size")
    def test_start_monitoring(self, mock_get_dir_size: MagicMock, mock_is_mover_running: MagicMock) -> None:
        """Test starting the monitoring session."""
        # Setup mocks
        mock_is_mover_running.return_value = True
        mock_get_dir_size.return_value = 1000

        # Create session and start monitoring
        session = MonitorSession()
        session.start_monitoring()

        # Check that monitoring started
        assert session.is_monitoring is True
        assert session.initial_size == 1000
        assert session.start_time is not None
        assert session.last_check_time is not None
        assert session.last_size == 1000
        assert session.last_progress == 0
        assert session.progress_history == [(session.start_time, 0)]
        assert session.total_data_moved == 0

        # Verify mocks were called correctly
        mock_is_mover_running.assert_called_once_with("/usr/local/sbin/mover")
        mock_get_dir_size.assert_called_once_with("/mnt/cache", [])

    @patch("mover_status.core.monitor.is_mover_running")
    def test_start_monitoring_no_mover(self, mock_is_mover_running: MagicMock) -> None:
        """Test starting monitoring when mover is not running."""
        # Setup mock
        mock_is_mover_running.return_value = False

        # Create session and try to start monitoring
        session = MonitorSession()

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Mover process is not running"):
            session.start_monitoring()

        # Check that monitoring did not start
        assert session.is_monitoring is False
        assert session.initial_size is None
        assert session.start_time is None

    def test_stop_monitoring(self) -> None:
        """Test stopping the monitoring session."""
        # Create session with monitoring values set
        session = MonitorSession()
        session.is_monitoring = True
        session.initial_size = 1000
        session.start_time = time.time()
        session.last_check_time = time.time()
        session.last_size = 500
        session.last_progress = 50
        session.progress_history = [(session.start_time, 0), (session.last_check_time, 50)]
        session.total_data_moved = 500

        # Stop monitoring
        session.stop_monitoring()

        # Check that monitoring stopped but values are preserved
        assert session.is_monitoring is False
        assert session.initial_size == 1000
        assert session.start_time is not None
        assert session.last_check_time is not None
        assert session.last_size == 500
        assert session.last_progress == 50
        assert len(session.progress_history) == 2
        assert session.total_data_moved == 500

    def test_reset_monitoring(self) -> None:
        """Test resetting the monitoring session."""
        # Create session with monitoring values set
        session = MonitorSession()
        session.is_monitoring = True
        session.initial_size = 1000
        session.start_time = time.time()
        session.last_check_time = time.time()
        session.last_size = 500
        session.last_progress = 50
        session.last_notification_progress = 50
        session.progress_history = [(session.start_time, 0), (session.last_check_time, 50)]
        session.total_data_moved = 500

        # Reset monitoring
        session.reset_monitoring()

        # Check that all values are reset
        assert session.is_monitoring is False
        assert session.initial_size is None
        assert session.start_time is None
        assert session.last_check_time is None
        assert session.last_size is None
        assert session.last_progress is None
        assert session.last_notification_progress == -1
        assert session.progress_history == []
        assert session.total_data_moved == 0

    @patch("mover_status.core.monitor.get_directory_size")
    @patch("mover_status.core.monitor.calculate_progress")
    def test_update_progress(self, mock_calculate_progress: MagicMock, mock_get_dir_size: MagicMock) -> None:
        """Test updating the progress of the monitoring session."""
        # Setup mocks
        mock_get_dir_size.return_value = 500
        mock_calculate_progress.return_value = 50

        # Create session with monitoring values set
        session = MonitorSession()
        session.is_monitoring = True
        session.initial_size = 1000
        session.start_time = time.time()
        session.last_check_time = time.time() - 10  # 10 seconds ago
        session.last_size = 600
        session.last_progress = 40
        session.progress_history = [(session.start_time, 0), (session.last_check_time, 40)]
        session.total_data_moved = 400

        # Update progress
        session.update_progress()

        # Check that progress was updated
        assert session.last_size == 500
        assert session.last_progress == 50
        assert session.last_check_time is not None
        assert len(session.progress_history) == 3
        assert session.progress_history[2][1] == 50
        assert session.total_data_moved == 500

        # Verify mocks were called correctly
        mock_get_dir_size.assert_called_once_with("/mnt/cache", [])
        mock_calculate_progress.assert_called_once_with(1000, 500)

    def test_update_progress_not_monitoring(self) -> None:
        """Test updating progress when not monitoring."""
        # Create session that is not monitoring
        session = MonitorSession()
        session.is_monitoring = False

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Monitoring session is not active"):
            session.update_progress()

    def test_should_send_notification(self) -> None:
        """Test notification threshold logic."""
        # Create session with notification increment of 25%
        session = MonitorSession(notification_increment=25)
        session.is_monitoring = True
        session.last_notification_progress = -1

        # Test initial notification (0%)
        session.last_progress = 0
        assert session.should_send_notification() is True
        session.last_notification_progress = 0

        # Test progress below next threshold
        session.last_progress = 10
        assert session.should_send_notification() is False

        # Test progress at next threshold
        session.last_progress = 25
        assert session.should_send_notification() is True
        session.last_notification_progress = 25

        # Test progress between thresholds
        session.last_progress = 40
        assert session.should_send_notification() is False

        # Test progress at next threshold
        session.last_progress = 50
        assert session.should_send_notification() is True
        session.last_notification_progress = 50

        # Test 100% completion
        session.last_progress = 100
        assert session.should_send_notification() is True

    @patch("mover_status.core.monitor.is_mover_running")
    @patch("mover_status.core.monitor.time.sleep")
    def test_wait_for_mover_start_success(self, mock_sleep: MagicMock, mock_is_mover_running: MagicMock) -> None:
        """Test waiting for mover process to start successfully."""
        # Setup mock to return False initially, then True
        mock_is_mover_running.side_effect = [False, False, True]

        # Create session
        session = MonitorSession(poll_interval=1.0)

        # Call the method
        result = session.wait_for_mover_start()

        # Verify the result
        assert result is True

        # Verify mocks were called correctly
        assert mock_is_mover_running.call_count == 3
        mock_sleep.assert_has_calls([call(1.0), call(1.0)])

    @patch("mover_status.core.monitor.is_mover_running")
    @patch("mover_status.core.monitor.time.sleep")
    @patch("mover_status.core.monitor.time.time")
    def test_wait_for_mover_start_timeout(self, mock_time: MagicMock, mock_sleep: MagicMock,
                                         mock_is_mover_running: MagicMock) -> None:
        """Test waiting for mover process to start with timeout."""
        # Setup mock to always return False (mover never starts)
        mock_is_mover_running.return_value = False

        # Setup time mock to simulate timeout
        mock_time.side_effect = [0, 10, 100, 200, 300, 400]  # Start, then exceed max_wait_time

        # Create session with short max wait time
        session = MonitorSession(max_wait_time=300)

        # Call the method
        result = session.wait_for_mover_start()

        # Verify the result
        assert result is False

        # Verify mocks were called correctly
        assert mock_is_mover_running.call_count > 0
        assert mock_sleep.call_count > 0

    @patch("mover_status.core.monitor.is_mover_running")
    def test_is_mover_process_ended(self, mock_is_mover_running: MagicMock) -> None:
        """Test checking if mover process has ended."""
        # Setup mock
        mock_is_mover_running.return_value = False

        # Create session
        session = MonitorSession()

        # Call the method
        result = session.is_mover_process_ended()

        # Verify the result
        assert result is True

        # Verify mock was called correctly
        mock_is_mover_running.assert_called_once_with("/usr/local/sbin/mover")

        # Test when mover is still running
        mock_is_mover_running.reset_mock()
        mock_is_mover_running.return_value = True

        result = session.is_mover_process_ended()

        assert result is False
        mock_is_mover_running.assert_called_once_with("/usr/local/sbin/mover")

    @patch("mover_status.core.monitor.get_directory_size")
    def test_calculate_initial_size(self, mock_get_dir_size: MagicMock) -> None:
        """Test calculating the initial size of the cache directory."""
        # Setup mock
        mock_get_dir_size.return_value = 5000

        # Create session
        session = MonitorSession(cache_path="/custom/cache", exclusions=["/custom/cache/exclude"])

        # Call the method
        size = session.calculate_initial_size()

        # Verify the result
        assert size == 5000

        # Verify mock was called correctly
        mock_get_dir_size.assert_called_once_with("/custom/cache", ["/custom/cache/exclude"])

    @patch("mover_status.core.monitor.time.time")
    @patch("mover_status.core.monitor.calculate_eta")
    def test_track_progress_over_time(self, mock_calculate_eta: MagicMock, mock_time: MagicMock) -> None:
        """Test tracking progress over time."""
        # Setup mocks
        current_time = 1000.0
        mock_time.return_value = current_time
        mock_calculate_eta.return_value = current_time + 300  # ETA is 5 minutes from now

        # Create session with monitoring values set
        session = MonitorSession()
        session.is_monitoring = True
        session.initial_size = 1000
        session.start_time = current_time - 300  # Started 5 minutes ago
        session.last_check_time = current_time - 60  # Last check was 1 minute ago
        session.last_size = 600
        session.last_progress = 40
        session.progress_history = [
            (session.start_time, 0),
            (session.start_time + 60, 10),
            (session.start_time + 120, 20),
            (session.start_time + 180, 30),
            (session.last_check_time, 40)
        ]
        session.total_data_moved = 400

        # Call the method
        eta = session.get_estimated_completion_time()

        # Verify the result
        assert eta == current_time + 300

        # Verify mocks were called correctly
        mock_calculate_eta.assert_called_once_with(session.start_time, current_time, 40)

    def test_get_progress_rate(self) -> None:
        """Test calculating the progress rate."""
        # Create session with progress history
        session = MonitorSession()
        session.is_monitoring = True
        session.start_time = 1000.0
        session.progress_history = [
            (1000.0, 0),    # Start time, 0%
            (1060.0, 10),   # 1 minute later, 10%
            (1120.0, 20),   # 2 minutes later, 20%
            (1180.0, 30),   # 3 minutes later, 30%
            (1240.0, 40)    # 4 minutes later, 40%
        ]

        # Call the method
        rate = session.get_progress_rate()

        # Verify the result (40% in 4 minutes = 10% per minute = 0.167% per second)
        assert 0.16 <= rate <= 0.17

        # Test with empty history
        session.progress_history = []
        assert session.get_progress_rate() == 0.0

        # Test with only one entry
        session.progress_history = [(1000.0, 0)]
        assert session.get_progress_rate() == 0.0

    def test_get_notification_thresholds(self) -> None:
        """Test determining notification thresholds."""
        # Create session with notification increment of 25%
        session = MonitorSession(notification_increment=25)

        # Call the method
        thresholds = session.get_notification_thresholds()

        # Verify the result
        assert thresholds == [0, 25, 50, 75, 100]

        # Test with different increment
        session.notification_increment = 10
        thresholds = session.get_notification_thresholds()
        assert thresholds == [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

        # Test with invalid increment (should default to 25%)
        session.notification_increment = 0
        thresholds = session.get_notification_thresholds()
        assert thresholds == [0, 25, 50, 75, 100]

        session.notification_increment = -10
        thresholds = session.get_notification_thresholds()
        assert thresholds == [0, 25, 50, 75, 100]

    @patch("mover_status.core.monitor.is_mover_running")
    @patch("mover_status.core.monitor.get_directory_size")
    @patch("mover_status.core.monitor.time.sleep")
    def test_run_monitoring_loop_single_cycle(
        self, mock_sleep: MagicMock, mock_get_dir_size: MagicMock, mock_is_mover_running: MagicMock
    ) -> None:
        """Test running the monitoring loop for a single cycle."""
        # Setup mocks
        # First call to is_mover_running returns False, then True for a while, then False again
        mock_is_mover_running.side_effect = [False, True, True, True, True, False]

        # Directory size decreases over time
        mock_get_dir_size.side_effect = [1000, 800, 600, 400, 200, 0]

        # Create notification manager mock
        notification_manager = MagicMock(spec=NotificationManager)

        # Create session
        session = MonitorSession(poll_interval=0.1)

        # Run the monitoring loop with max_cycles=1 to ensure it exits after one cycle
        session.run_monitoring_loop(notification_manager, max_cycles=1)

        # Verify that monitoring was started and stopped
        assert mock_is_mover_running.call_count >= 3
        assert mock_get_dir_size.call_count >= 2

        # MagicMock attributes are dynamically generated
        assert notification_manager.send_notification.call_count >= 2  # At least initial and completion

        # Verify that sleep was called to prevent CPU overuse
        assert mock_sleep.call_count > 0

    @patch("mover_status.core.monitor.is_mover_running")
    @patch("mover_status.core.monitor.get_directory_size")
    @patch("mover_status.core.monitor.time.sleep")
    def test_handle_process_completion(
        self, mock_sleep: MagicMock, mock_get_dir_size: MagicMock, mock_is_mover_running: MagicMock
    ) -> None:
        """Test handling process completion in the monitoring loop."""
        # Setup mocks
        # Mover starts, runs for a while, then completes
        mock_is_mover_running.side_effect = [True, True, True, False]

        # Directory size decreases over time
        mock_get_dir_size.side_effect = [1000, 500, 0]

        # Create notification manager mock
        notification_manager = MagicMock(spec=NotificationManager)

        # Create session
        session = MonitorSession(poll_interval=0.1)

        # Start monitoring manually to set up the state
        session.start_monitoring()

        # Run the monitoring loop with process_ended=True to simulate completion
        session.handle_process_completion(notification_manager)

        # Verify that a completion notification was sent
        notification_manager.send_notification.assert_called_with(
            "Mover process completed",
            raw_values={
                "progress": 100,
                "remaining_size": session.last_size,
                "initial_size": session.initial_size,
                "eta": None,
                "total_moved": session.total_data_moved
            }
        )

        # Verify that monitoring was stopped
        assert session.is_monitoring is False

    @patch("mover_status.core.monitor.is_mover_running")
    @patch("mover_status.core.monitor.get_directory_size")
    @patch("mover_status.core.monitor.time.sleep")
    def test_restart_monitoring(
        self, mock_sleep: MagicMock, mock_get_dir_size: MagicMock, mock_is_mover_running: MagicMock
    ) -> None:
        """Test restarting monitoring after completion."""
        # Setup mocks
        # First cycle: mover starts, runs, completes
        # Second cycle: mover starts again, runs, completes
        mock_is_mover_running.side_effect = [
            # First cycle
            False, True, True, False,
            # Second cycle
            False, True, True, False
        ]

        # Directory size decreases over time for both cycles
        mock_get_dir_size.side_effect = [
            # First cycle
            1000, 500, 0,
            # Second cycle
            2000, 1000, 0
        ]

        # Create notification manager mock
        notification_manager = MagicMock(spec=NotificationManager)

        # Create session
        session = MonitorSession(poll_interval=0.1)

        # Run the monitoring loop with max_cycles=2 to test restart
        session.run_monitoring_loop(notification_manager, max_cycles=2)

        # Verify that monitoring was started, stopped, and restarted
        assert mock_is_mover_running.call_count >= 6
        assert mock_get_dir_size.call_count >= 4
        assert notification_manager.send_notification.call_count >= 4  # At least initial and completion for both cycles

        # Verify that sleep was called between cycles
        assert mock_sleep.call_count > 0
