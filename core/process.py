# core/process.py

"""
Process management utilities for monitoring the Unraid Mover process.
Provides process state tracking and resource monitoring without control capabilities.

Example:
    >>> manager = ProcessManager(settings)
    >>> async with manager:
    ...     is_running = await manager.is_running()
    ...     if is_running:
    ...         stats = manager.last_stats
    ...         print(f"CPU Usage: {stats.total_cpu_percent}%")
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Dict, FrozenSet, Optional, Set

import psutil
from structlog import get_logger

from config.constants import PROCESS_CHECK_INTERVAL
from config.settings import Settings

logger = get_logger(__name__)

class ProcessState(str, Enum):
    """Possible states of the mover process."""
    UNKNOWN = auto()    # Initial state
    RUNNING = auto()    # Process is active
    STOPPED = auto()    # Process has stopped
    ERROR = auto()      # Error occurred
    ZOMBIE = auto()     # Process is zombie/defunct

@dataclass(frozen=True)
class ProcessStats:
    """Statistics for the mover process group."""
    script_pid: int                 # PHP script PID
    related_pids: FrozenSet[int]    # PIDs of related processes
    total_cpu_percent: float        # Combined CPU usage
    total_memory_percent: float     # Combined memory usage
    io_read_bytes: int             # Combined read bytes
    io_write_bytes: int            # Combined write bytes
    start_time: datetime           # Process start time
    command_line: str              # Main process command line
    nice_level: Optional[int]      # Nice level if set
    io_class: Optional[str]        # IO class if set

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
    """
    Monitors the Unraid Mover process and related child processes.
    Provides status information and resource usage statistics.
    """

    def __init__(self, settings: Settings):
        """Initialize process manager.

        Args:
            settings: Application settings instance
        """
        self._settings = settings
        self._mover_paths = {
            'script': Path("/usr/local/sbin/mover"),
            'php': Path("/usr/local/emhttp/plugins/unraid.mover/mover.php"),
            'age_mover': Path("/usr/local/emhttp/plugins/unraid.mover/age.mover")
        }
        self._current_state = ProcessState.UNKNOWN
        self._process_groups: Dict[int, Set[int]] = {}
        self._last_stats: Optional[ProcessStats] = None
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> 'ProcessManager':
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()

    @asynccontextmanager
    async def _process_access(self, proc: psutil.Process):
        """Context manager for safe process access.

        Args:
            proc: Process to access

        Yields:
            psutil.Process: Process object for safe access

        Raises:
            ProcessAccessError: If process access fails
        """
        try:
            yield proc
        except psutil.NoSuchProcess as err:
            raise ProcessNotFoundError(f"Process {proc.pid} no longer exists") from err
        except psutil.AccessDenied as err:
            raise ProcessAccessError(f"Access denied to process {proc.pid}") from err
        except psutil.TimeoutError as err:
            raise ProcessError(f"Timeout accessing process {proc.pid}") from err
        except Exception as err:
            raise ProcessError(f"Error accessing process {proc.pid}: {err}") from err

    async def _is_mover_related(self, proc: psutil.Process) -> bool:
        """Check if a process is related to the mover operation.

        Args:
            proc: Process to check

        Returns:
            bool: True if process is mover-related
        """
        try:
            async with self._process_access(proc):
                cmdline = proc.cmdline()
                cmdline_str = ' '.join(cmdline)

                # Check for main mover processes
                if any(str(path) in cmdline_str for path in self._mover_paths.values()):
                    return True

                # Check for utility processes
                if proc.name() in {'ionice', 'nice'}:
                    return any(str(path) in cmdline_str for path in self._mover_paths.values())

                # Check for file operation processes
                if proc.name() in {'mv', 'cp', 'rsync'}:
                    parent = proc
                    for _ in range(3):  # Check up to 3 levels up
                        try:
                            parent = parent.parent()
                            if parent and parent.pid in self._process_groups:
                                return True
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            break
                        if not parent:
                            break

        except ProcessError:
            return False

        return False

    async def _get_process_stats(self, script_pid: int, related_pids: Set[int]) -> ProcessStats:
        """Collect statistics for mover-related processes.

        Args:
            script_pid: PID of main PHP script
            related_pids: PIDs of related processes

        Returns:
            ProcessStats: Collected process statistics

        Raises:
            ProcessError: If stats collection fails
        """
        total_cpu = 0.0
        total_memory = 0.0
        total_read = 0
        total_write = 0
        nice_level = None
        io_class = None
        start_time = None
        command_line = ""

        try:
            # Get main script stats
            main_proc = psutil.Process(script_pid)
            async with self._process_access(main_proc):
                with main_proc.oneshot():
                    command_line = " ".join(main_proc.cmdline())
                    start_time = datetime.fromtimestamp(main_proc.create_time())
                    total_cpu += main_proc.cpu_percent()
                    total_memory += main_proc.memory_percent()
                    nice_level = main_proc.nice()

                    if hasattr(main_proc, 'ionice'):
                        io_class = str(main_proc.ionice().ioclass)

                    if hasattr(main_proc, 'io_counters'):
                        io = main_proc.io_counters()
                        total_read += io.read_bytes
                        total_write += io.write_bytes

            # Add stats from related processes
            for pid in related_pids:
                try:
                    proc = psutil.Process(pid)
                    async with self._process_access(proc):
                        with proc.oneshot():
                            total_cpu += proc.cpu_percent()
                            total_memory += proc.memory_percent()
                            if hasattr(proc, 'io_counters'):
                                io = proc.io_counters()
                                total_read += io.read_bytes
                                total_write += io.write_bytes
                except ProcessError:
                    continue

            return ProcessStats(
                script_pid=script_pid,
                related_pids=frozenset(related_pids),
                total_cpu_percent=round(total_cpu, 2),
                total_memory_percent=round(total_memory, 2),
                io_read_bytes=total_read,
                io_write_bytes=total_write,
                start_time=start_time or datetime.now(),
                command_line=command_line,
                nice_level=nice_level,
                io_class=io_class
            )

        except Exception as err:
            raise ProcessError(f"Failed to collect process stats: {err}") from err

    async def _find_mover_processes(self) -> Optional[tuple[int, Set[int]]]:
        """Find running mover processes.

        Returns:
            Optional[tuple[int, Set[int]]]: Tuple of (main_pid, related_pids) if found

        Raises:
            ProcessError: If process search fails
        """
        main_pid = None
        related_pids: Set[int] = set()

        try:
            async with self._lock:
                for proc in psutil.process_iter(['name', 'cmdline']):
                    try:
                        if await self._is_mover_related(proc):
                            cmdline = ' '.join(proc.cmdline())
                            if str(self._mover_paths['php']) in cmdline:
                                main_pid = proc.pid
                            else:
                                related_pids.add(proc.pid)
                    except ProcessError:
                        continue

                if main_pid:
                    return main_pid, related_pids
                return None

        except Exception as err:
            logger.error("Error searching for mover processes", error=str(err))
            self._current_state = ProcessState.ERROR
            raise ProcessError(f"Process search failed: {err}") from err

    async def _update_state(self) -> None:
        """Update process state and statistics."""
        try:
            process_info = await self._find_mover_processes()

            if not process_info:
                if self._current_state == ProcessState.RUNNING:
                    logger.info("Mover process completed")
                self._current_state = ProcessState.STOPPED
                self._process_groups.clear()
                self._last_stats = None
                return

            main_pid, related_pids = process_info

            # Verify main process is still responsive
            try:
                proc = psutil.Process(main_pid)
                if proc.status() == psutil.STATUS_ZOMBIE:
                    self._current_state = ProcessState.ZOMBIE
                    return
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self._current_state = ProcessState.ERROR
                return

            # Update process tracking
            self._process_groups[main_pid] = related_pids
            self._current_state = ProcessState.RUNNING

            # Collect new statistics
            self._last_stats = await self._get_process_stats(main_pid, related_pids)

        except ProcessError as err:
            logger.error("Process state update failed", error=str(err))
            self._current_state = ProcessState.ERROR
        except Exception as err:
            logger.error("Unexpected error in state update", error=str(err))
            self._current_state = ProcessState.ERROR

    async def start(self) -> None:
        """Start process monitoring."""
        if self._monitor_task is not None:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Process monitoring started")

    async def stop(self) -> None:
        """Stop process monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        self._process_groups.clear()
        self._last_stats = None
        logger.info("Process monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._update_state()
                await asyncio.sleep(PROCESS_CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as err:
                logger.error("Monitoring loop error", error=str(err))
                await asyncio.sleep(PROCESS_CHECK_INTERVAL)

    async def is_running(self) -> bool:
        """Check if mover process is currently running.

        Returns:
            bool: True if process is running
        """
        return self._current_state == ProcessState.RUNNING

    @property
    def current_state(self) -> ProcessState:
        """Get current process state."""
        return self._current_state

    @property
    def last_stats(self) -> Optional[ProcessStats]:
        """Get most recent process statistics."""
        return self._last_stats
