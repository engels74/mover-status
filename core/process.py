# core/process.py

"""
Process management utilities for monitoring the Unraid Mover process.
This module implements process state tracking and resource monitoring capabilities
for the Unraid Mover process without direct control functionality.

Components:
- ProcessState: Enumeration of possible process states
- ProcessStats: Data structure for process resource usage statistics
- ProcessManager: Main coordinator for process monitoring and statistics

Features:
- Asynchronous process monitoring with configurable check intervals
- Detailed resource usage statistics (CPU, memory, I/O, threads)
- Thread-safe process state tracking
- Automatic process discovery and reconnection
- Error handling for common process monitoring issues

Example:
    >>> from core.process import ProcessManager
    >>> from config.settings import Settings
    >>>
    >>> settings = Settings.from_file("config.yaml")
    >>> manager = ProcessManager(settings)
    >>>
    >>> async with manager:
    ...     # Check if process is running
    ...     is_running = await manager.is_running()
    ...     if is_running:
    ...         # Get resource usage statistics
    ...         stats = manager.last_stats
    ...         print(f"CPU Usage: {stats.total_cpu_percent}%")
    ...         print(f"Memory Usage: {stats.total_memory_percent}%")
    ...         print(f"IO Operations: {stats.io_read_count + stats.io_write_count}")
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Optional

import psutil
from structlog import get_logger

from config.constants import Process
from config.settings import Settings

logger = get_logger(__name__)

class ProcessState(StrEnum):
    """Process state enumeration for the mover process.

    Defines the possible states that the mover process can be in at any given time.
    Used for tracking process lifecycle and health monitoring.

    States:
        UNKNOWN: Initial state or when process state cannot be determined
        RUNNING: Process is currently active and executing
        STOPPED: Process has terminated normally
        ERROR: Process encountered an error condition
        ZOMBIE: Process is in zombie/defunct state (terminated but not cleaned up)
    """
    UNKNOWN = "unknown"    # Initial state
    RUNNING = "running"    # Process is active
    STOPPED = "stopped"    # Process has stopped
    ERROR = "error"        # Error occurred
    ZOMBIE = "zombie"      # Process is zombie/defunct

@dataclass(frozen=True)
class ProcessStats:
    """Process resource usage statistics data structure.

    Collects and stores various metrics about process resource utilization,
    including CPU usage, memory consumption, I/O operations, and thread statistics.
    This class is immutable (frozen) to ensure thread safety.

    Attributes:
        total_cpu_percent (float): CPU usage percentage across all cores
        total_memory_percent (float): Memory usage as percentage of system memory
        total_memory_bytes (int): Actual memory usage in bytes (RSS)
        io_read_bytes (int): Total bytes read from disk
        io_write_bytes (int): Total bytes written to disk
        io_read_count (int): Number of read operations performed
        io_write_count (int): Number of write operations performed
        num_threads (int): Current number of threads in the process
        num_fds (int): Number of open file descriptors
        num_handles (int): Number of open handles (Windows-specific)
        num_ctx_switches (int): Total number of context switches
        process_state (str): Current process state string
    """
    total_cpu_percent: float = 0.0
    total_memory_percent: float = 0.0
    total_memory_bytes: int = 0
    io_read_bytes: int = 0
    io_write_bytes: int = 0
    io_read_count: int = 0
    io_write_count: int = 0
    num_threads: int = 0
    num_fds: int = 0
    num_handles: int = 0
    num_ctx_switches: int = 0
    process_state: str = ""

class ProcessError(Exception):
    """Base exception for process-related errors."""
    pass

class ProcessNotFoundError(ProcessError):
    """Raised when mover process cannot be found."""
    pass

class ProcessAccessError(ProcessError):
    """Raised when process access is denied."""
    pass

class ProcessManager:
    """Process monitoring and statistics collection system.

    This class provides the core functionality for monitoring the Unraid Mover process
    and collecting resource usage statistics. It implements an asynchronous monitoring
    system with automatic process discovery and reconnection capabilities.

    Features:
    - Asynchronous process state monitoring
    - Resource usage statistics collection
    - Thread-safe operations with asyncio locks
    - Automatic process rediscovery on failures
    - Configurable check intervals
    - Error handling and logging

    The manager operates in a non-intrusive manner, only observing the process
    without attempting to control or modify its behavior. This ensures safe
    operation alongside the Unraid system.

    Attributes:
        last_stats (property): Most recently collected process statistics
        _process (Optional[psutil.Process]): Current process reference
        _last_stats (Optional[ProcessStats]): Cached process statistics
        _last_check (Optional[datetime]): Timestamp of last process check
        _lock (asyncio.Lock): Thread safety lock

    Example:
        >>> async with ProcessManager(settings) as manager:
        ...     # Check process state
        ...     if await manager.is_running():
        ...         # Access latest statistics
        ...         stats = manager.last_stats
        ...         print(f"Memory Usage: {stats.total_memory_percent:.1f}%")
    """

    def __init__(self, settings: Settings):
        """Initialize process manager.

        Args:
            settings: Application settings instance
        """
        self._settings = settings
        self._process: Optional[psutil.Process] = None
        self._last_stats: Optional[ProcessStats] = None
        self._last_check: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> 'ProcessManager':
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        pass

    @property
    def last_stats(self) -> Optional[ProcessStats]:
        """Get last recorded process statistics."""
        return self._last_stats

    async def is_running(self) -> bool:
        """Check if mover process is running.

        Returns:
            bool: True if process is running, False otherwise
        """
        async with self._lock:
            try:
                # Check if we need to refresh process status
                now = datetime.now()
                if (
                    self._last_check is None
                    or (now - self._last_check).total_seconds() >= Process.CHECK_INTERVAL
                ):
                    self._last_check = now
                    await self._update_process()

                # Get process statistics if available
                if self._process is not None:
                    try:
                        self._last_stats = await self._get_process_stats()
                        return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        self._process = None
                        self._last_stats = None

                return False

            except Exception as err:
                logger.error(
                    "Process check failed",
                    error=str(err),
                    error_type=type(err).__name__
                )
                return False

    async def _update_process(self) -> None:
        """Update process reference."""
        try:
            # Find mover process
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    if proc.name() == Process.EXECUTABLE:
                        self._process = proc
                        return
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Process not found
            self._process = None

        except Exception as err:
            logger.error(
                "Process update failed",
                error=str(err),
                error_type=type(err).__name__
            )
            self._process = None

    async def _get_process_stats(self) -> ProcessStats:
        """Get process statistics.

        Returns:
            ProcessStats: Current process statistics

        Raises:
            psutil.NoSuchProcess: If process no longer exists
            psutil.AccessDenied: If access to process information is denied
        """
        if self._process is None:
            raise ValueError("No process available")

        # Get process information
        with self._process.oneshot():
            cpu_percent = self._process.cpu_percent()
            memory_info = self._process.memory_info()
            memory_percent = self._process.memory_percent()
            io_counters = self._process.io_counters()
            num_threads = self._process.num_threads()
            num_fds = self._process.num_fds()
            num_handles = self._process.num_handles()
            ctx_switches = self._process.num_ctx_switches()
            status = self._process.status()

        # Create statistics object
        return ProcessStats(
            total_cpu_percent=cpu_percent,
            total_memory_percent=memory_percent,
            total_memory_bytes=memory_info.rss,
            io_read_bytes=io_counters.read_bytes,
            io_write_bytes=io_counters.write_bytes,
            io_read_count=io_counters.read_count,
            io_write_count=io_counters.write_count,
            num_threads=num_threads,
            num_fds=num_fds,
            num_handles=num_handles,
            num_ctx_switches=ctx_switches.voluntary + ctx_switches.involuntary,
            process_state=status
        )
