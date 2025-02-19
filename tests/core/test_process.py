"""Tests for the process module."""

import asyncio
from datetime import datetime
import platform
import pytest
import psutil
from unittest.mock import MagicMock
from typing import Any, Callable, Optional, Union

from config.settings import Settings
from config.constants import Process
from core.process import (
    ProcessState,
    ProcessStats,
    ProcessManager,
    ProcessError,
    ProcessNotFoundError,
    ProcessAccessError
)

# Test data
MOCK_PROCESS_PID = 12345

@pytest.fixture
def settings():
    """Fixture for test settings."""
    return Settings()

class MockProcess:
    """Mock process class for testing."""
    def __init__(self, mocker):
        self.mocker = mocker
        self.pid = MOCK_PROCESS_PID
        self._name: Optional[Callable[[], str]] = None
        self._cpu_percent: Union[float, Callable[[], float]] = 10.0
        self._memory_info = mocker.MagicMock(rss=1024*1024)  # 1MB
        self._memory_percent = 5.0
        self._io_counters = mocker.MagicMock(
            read_bytes=1000,
            write_bytes=2000,
            read_count=10,
            write_count=20
        )
        self._num_threads = 4
        self._num_fds = 8
        self._num_handles = 16 if platform.system() == 'Windows' else None
        self._ctx_switches = mocker.MagicMock(
            voluntary=100,
            involuntary=50
        )
        self._status = "running"
    
    def name(self) -> str:
        if callable(self._name):
            return self._name()
        return Process.EXECUTABLE
    
    def cpu_percent(self) -> float:
        if callable(self._cpu_percent):
            return self._cpu_percent()
        return self._cpu_percent
    
    def memory_info(self):
        return self._memory_info
    
    def memory_percent(self):
        return self._memory_percent
    
    def io_counters(self):
        return self._io_counters
    
    def num_threads(self):
        return self._num_threads
    
    def num_fds(self):
        return self._num_fds
    
    def num_handles(self):
        if platform.system() != 'Windows':
            return 0  # Return 0 on non-Windows platforms
        return self._num_handles
    
    def num_ctx_switches(self):
        return self._ctx_switches
    
    def status(self):
        return self._status
    
    def oneshot(self):
        return self

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return None

@pytest.fixture
def mock_process(mocker):
    """Fixture for mocked psutil.Process."""
    return MockProcess(mocker)

class TestProcessState:
    """Tests for the ProcessState enumeration."""
    
    def test_process_state_values(self):
        """Test ProcessState enumeration values."""
        assert ProcessState.UNKNOWN == "unknown"
        assert ProcessState.RUNNING == "running"
        assert ProcessState.STOPPED == "stopped"
        assert ProcessState.ERROR == "error"
        assert ProcessState.ZOMBIE == "zombie"
    
    def test_process_state_conversion(self):
        """Test ProcessState string conversion."""
        assert ProcessState("running") == ProcessState.RUNNING
        assert str(ProcessState.STOPPED) == "stopped"
        
        with pytest.raises(ValueError):
            ProcessState("invalid_state")

class TestProcessStats:
    """Tests for the ProcessStats data class."""
    
    def test_process_stats_initialization(self):
        """Test ProcessStats initialization with default values."""
        stats = ProcessStats()
        assert stats.total_cpu_percent == 0.0
        assert stats.total_memory_percent == 0.0
        assert stats.total_memory_bytes == 0
        assert stats.io_read_bytes == 0
        assert stats.io_write_bytes == 0
        assert stats.io_read_count == 0
        assert stats.io_write_count == 0
        assert stats.num_threads == 0
        assert stats.num_fds == 0
        assert stats.num_handles == 0
        assert stats.num_ctx_switches == 0
        assert stats.process_state == ""
    
    def test_process_stats_custom_values(self):
        """Test ProcessStats initialization with custom values."""
        stats = ProcessStats(
            total_cpu_percent=50.0,
            total_memory_percent=25.0,
            total_memory_bytes=1024*1024,
            io_read_bytes=1000,
            io_write_bytes=2000,
            io_read_count=10,
            io_write_count=20,
            num_threads=4,
            num_fds=8,
            num_handles=16 if platform.system() == 'Windows' else 0,
            num_ctx_switches=150,
            process_state="running"
        )
        
        assert stats.total_cpu_percent == 50.0
        assert stats.total_memory_percent == 25.0
        assert stats.total_memory_bytes == 1024*1024
        assert stats.io_read_bytes == 1000
        assert stats.io_write_bytes == 2000
        assert stats.io_read_count == 10
        assert stats.io_write_count == 20
        assert stats.num_threads == 4
        assert stats.num_fds == 8
        assert stats.num_handles == (16 if platform.system() == 'Windows' else 0)
        assert stats.num_ctx_switches == 150
        assert stats.process_state == "running"

class TestProcessManager:
    """Tests for the ProcessManager class."""
    
    @pytest.fixture
    def process_manager(self, settings):
        """Fixture for ProcessManager instance."""
        return ProcessManager(settings)
    
    async def test_process_manager_initialization(self, process_manager):
        """Test ProcessManager initialization."""
        assert process_manager._process is None
        assert process_manager._last_stats is None
        assert process_manager._last_check is None
        assert isinstance(process_manager._lock, asyncio.Lock)
    
    async def test_process_discovery(self, process_manager, mock_process, mocker):
        """Test process discovery functionality."""
        mocker.patch('psutil.process_iter', return_value=[mock_process])
        
        async with process_manager:
            is_running = await process_manager.is_running()
            assert is_running is True
            assert process_manager._process is not None
    
    async def test_process_stats_collection(self, process_manager, mock_process, mocker):
        """Test process statistics collection."""
        mocker.patch('psutil.process_iter', return_value=[mock_process])
        process_manager._process = mock_process
        
        stats = await process_manager._get_process_stats()
        
        assert isinstance(stats, ProcessStats)
        assert stats.total_cpu_percent == 10.0
        assert stats.total_memory_percent == 5.0
        assert stats.total_memory_bytes == 1024*1024
        assert stats.io_read_bytes == 1000
        assert stats.io_write_bytes == 2000
        assert stats.process_state == "running"
        
        if platform.system() == 'Windows':
            assert stats.num_handles == 16
        else:
            assert stats.num_handles == 0
    
    async def test_process_not_found(self, process_manager, mocker):
        """Test behavior when process is not found."""
        mocker.patch('psutil.process_iter', return_value=[])
        
        async with process_manager:
            is_running = await process_manager.is_running()
            assert is_running is False
            assert process_manager._process is None
    
    async def test_process_access_denied(self, process_manager, mock_process, mocker):
        """Test handling of access denied errors."""
        def raise_access_denied():
            raise psutil.AccessDenied()
        mock_process._name = raise_access_denied
        mocker.patch('psutil.process_iter', return_value=[mock_process])
        
        async with process_manager:
            is_running = await process_manager.is_running()
            assert is_running is False
    
    async def test_process_error_handling(self, process_manager, mock_process, mocker):
        """Test error handling in process operations."""
        def raise_error():
            raise psutil.NoSuchProcess(MOCK_PROCESS_PID)
        mock_process._cpu_percent = raise_error
        process_manager._process = mock_process
        
        with pytest.raises(psutil.NoSuchProcess):
            await process_manager._get_process_stats() 