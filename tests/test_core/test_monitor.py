"""
Tests for the monitor module.

This module contains tests for the MonitorSession class, which is responsible
for tracking the state of the mover process monitoring.
"""

import time
import pytest
from unittest.mock import patch, MagicMock

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

    def test_init_custom_values(self) -> None:
        """Test that MonitorSession initializes with custom values."""
        session = MonitorSession(
            mover_path="/custom/mover",
            cache_path="/custom/cache",
            exclusions=["/custom/cache/exclude1", "/custom/cache/exclude2"],
            notification_increment=10
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
