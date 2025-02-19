"""Tests for the monitor module."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Set, Optional

import pytest
from structlog.testing import capture_logs

from config.constants import MonitorEvent, MonitorState
from config.settings import FileSystemSettings, MonitoringSettings, Settings
from core.calculator import TransferStats
from core.monitor import DirectoryScanner, MonitorStats, MoverMonitor
from core.process import ProcessState

# Test data
TEST_PATHS = {
    Path("/test/path1"),
    Path("/test/path2"),
    Path("/test/excluded")
}

@pytest.fixture
def excluded_paths() -> Set[Path]:
    """Fixture for test excluded paths."""
    return {Path("/test/excluded")}

@pytest.fixture
def directory_scanner(excluded_paths: Set[Path]) -> DirectoryScanner:
    """Fixture for DirectoryScanner instance."""
    return DirectoryScanner(excluded_paths, cache_ttl=1.0)

@pytest.fixture
def monitor_stats() -> MonitorStats:
    """Fixture for MonitorStats instance."""
    return MonitorStats()

@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Fixture for test settings."""
    # Create excluded directory
    excluded_dir = tmp_path / "excluded"
    excluded_dir.mkdir()
    
    return Settings(
        monitoring=MonitoringSettings(polling_interval=1.0),
        filesystem=FileSystemSettings(excluded_paths={excluded_dir}),
        check_version=False
    )

@pytest.fixture
async def mover_monitor(settings: Settings) -> AsyncGenerator[MoverMonitor, None]:
    """Fixture for MoverMonitor instance."""
    monitor = MoverMonitor(settings)
    yield monitor
    await monitor.stop()

class TestDirectoryScanner:
    """Tests for the DirectoryScanner class."""

    def test_initialization(self, directory_scanner: DirectoryScanner):
        """Test scanner initialization."""
        assert directory_scanner._excluded_paths == {Path("/test/excluded")}
        assert directory_scanner._cache_ttl == 1.0
        assert isinstance(directory_scanner._cache, dict)
        assert isinstance(directory_scanner._lock, asyncio.Lock)

    def test_should_exclude(self, directory_scanner: DirectoryScanner):
        """Test path exclusion logic."""
        # Test excluded path
        assert directory_scanner._should_exclude(Path("/test/excluded"))
        assert directory_scanner._should_exclude(Path("/test/excluded/subdir"))

        # Test non-excluded paths
        assert not directory_scanner._should_exclude(Path("/test/path1"))
        assert not directory_scanner._should_exclude(Path("/other/path"))

    @pytest.mark.asyncio
    async def test_get_size(self, directory_scanner: DirectoryScanner, tmp_path: Path):
        """Test directory size calculation."""
        # Create test files
        test_file1 = tmp_path / "file1.txt"
        test_file1.write_text("test data 1")
        test_file2 = tmp_path / "file2.txt"
        test_file2.write_text("test data 2")

        # Create excluded directory
        excluded_dir = tmp_path / "excluded"
        excluded_dir.mkdir()
        excluded_file = excluded_dir / "excluded.txt"
        excluded_file.write_text("excluded data")

        # Update excluded paths
        directory_scanner._excluded_paths = {excluded_dir}

        # Test size calculation
        size = await directory_scanner.get_size(tmp_path)
        expected_size = len("test data 1") + len("test data 2")
        assert size == expected_size

    @pytest.mark.asyncio
    async def test_clear_cache(self, directory_scanner: DirectoryScanner):
        """Test cache clearing."""
        # Add test data to cache
        test_path = Path("/test/path")
        async with directory_scanner._lock:
            directory_scanner._cache[test_path] = (1000, datetime.now().timestamp())

        # Clear cache
        await directory_scanner.clear_cache()
        assert not directory_scanner._cache

class TestMonitorStats:
    """Tests for the MonitorStats class."""

    def test_initialization(self, monitor_stats: MonitorStats):
        """Test stats initialization."""
        assert monitor_stats.start_time is None
        assert monitor_stats.error_count == 0
        assert monitor_stats.process_state is None
        assert monitor_stats.transfer_stats is None

    def test_state_updates(self, monitor_stats: MonitorStats):
        """Test state update functionality."""
        # Update process state
        monitor_stats.process_state = None  # Reset first
        monitor_stats.process_state = ProcessState("running")  # Set using string value
        assert monitor_stats.process_state == ProcessState.RUNNING

        # Update error count
        monitor_stats.error_count += 1
        assert monitor_stats.error_count == 1

        # Update transfer stats
        transfer_stats = TransferStats(
            current_size=1000,
            initial_size=2000,
            bytes_transferred=1000,
            bytes_remaining=1000,
            percent_complete=50.0,
            transfer_rate=100.0,
            elapsed_time=10.0,
            remaining_time=10.0
        )
        monitor_stats.transfer_stats = transfer_stats
        assert monitor_stats.transfer_stats == transfer_stats

class TestMoverMonitor:
    """Tests for the MoverMonitor class."""

    @pytest.mark.asyncio
    async def test_initialization(self, mover_monitor: MoverMonitor):
        """Test monitor initialization."""
        assert mover_monitor.state == MonitorState.STOPPED
        assert isinstance(mover_monitor.stats, MonitorStats)
        assert not mover_monitor._providers
        assert not mover_monitor._event_handlers
        assert not mover_monitor._tasks

    @pytest.mark.asyncio
    async def test_event_subscription(self, mover_monitor: MoverMonitor):
        """Test event subscription system."""
        test_event = MonitorEvent.MONITOR_ERROR
        event_data = {}

        # Test event handler
        async def test_handler(event: MonitorEvent, **kwargs):
            event_data["event"] = event
            event_data["kwargs"] = kwargs

        # Subscribe to event
        mover_monitor.subscribe(test_event, test_handler)
        assert test_event in mover_monitor._event_handlers
        assert test_handler in mover_monitor._event_handlers[test_event]

        # Test event notification
        await mover_monitor._notify_event(test_event, test_data="test")
        assert event_data["event"] == test_event
        assert event_data["kwargs"]["test_data"] == "test"

        # Test unsubscribe
        mover_monitor.unsubscribe(test_event, test_handler)
        assert not mover_monitor._event_handlers[test_event]

    @pytest.mark.asyncio
    async def test_monitor_lifecycle(self, mover_monitor: MoverMonitor):
        """Test monitor start/stop lifecycle."""
        # Test start
        await mover_monitor.start()
        assert mover_monitor.state == MonitorState.MONITORING
        assert mover_monitor._tasks

        # Test stop
        await mover_monitor.stop()
        assert mover_monitor.state == MonitorState.STOPPED
        assert not mover_monitor._tasks

    @pytest.mark.asyncio
    async def test_monitoring_error_handling(self, mover_monitor: MoverMonitor):
        """Test error handling during monitoring."""
        with capture_logs() as logs:
            # Simulate error in monitoring loop
            async def failing_update():
                raise Exception("Test error")

            mover_monitor._update_monitoring = failing_update
            await mover_monitor.start()
            await asyncio.sleep(0.1)  # Allow error to occur
            await mover_monitor.stop()

            # Verify error was logged
            error_logs = [log for log in logs if log["log_level"] == "error"]
            assert error_logs
            assert "Test error" in str(error_logs[0]["error"])

    @pytest.mark.asyncio
    async def test_async_context_manager(self, settings: Settings):
        """Test async context manager functionality."""
        async with MoverMonitor(settings) as monitor:
            assert monitor.state == MonitorState.STOPPED
            await monitor.start()
            assert monitor.state == MonitorState.MONITORING

        # Verify cleanup after context
        assert monitor.state == MonitorState.STOPPED
        assert not monitor._tasks 