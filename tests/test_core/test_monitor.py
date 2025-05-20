"""
Tests for the monitor module.

This module contains tests for the MonitorSession class, which is responsible
for tracking the state of the mover process monitoring.
"""

import time
import pytest
from unittest.mock import patch, MagicMock, call

from mover_status.core.monitor import MonitorSession


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

        # Stop monitoring
        session.stop_monitoring()

        # Check that monitoring stopped but values are preserved
        assert session.is_monitoring is False
        assert session.initial_size == 1000
        assert session.start_time is not None
        assert session.last_check_time is not None
        assert session.last_size == 500
        assert session.last_progress == 50

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

        # Update progress
        session.update_progress()

        # Check that progress was updated
        assert session.last_size == 500
        assert session.last_progress == 50
        assert session.last_check_time is not None

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
