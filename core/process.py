# core/process.py

"""
Process management utilities for monitoring the Unraid Mover process.
Tracks the mover.php script and its related processes (ionice, nice, file operations).
Provides monitoring and statistics collection without process control capabilities.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

import psutil
from structlog import get_logger

from config.constants import MOVER_EXECUTABLE, PROCESS_CHECK_INTERVAL
from config.settings import Settings

logger = get_logger(__name__)

class ProcessState(str, Enum):
    """Possible states of the mover process."""
    UNKNOWN = "unknown"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"

@dataclass
class ProcessStats:
    """Statistics for the mover process group."""
    script_pid: int              # PHP script PID
    related_pids: List[int]      # PIDs of related processes (ionice, nice, etc.)
    total_cpu_percent: float     # Combined CPU usage
    total_memory_percent: float  # Combined memory usage
    io_read_bytes: int          # Combined read bytes
    io_write_bytes: int         # Combined write bytes
    start_time: datetime        # Process start time
    command_line: str           # Main process command line
    nice_level: Optional[int]   # Nice level if set
    io_class: Optional[str]     # IO class if set

class ProcessManager:
    """
    Monitors the Unraid Mover process and its related child processes.
    Provides status information and resource usage statistics.
    """

    def __init__(self, settings: Settings):
        """Initialize process manager.

        Args:
            settings: Application settings instance
        """
        self._settings = settings
        self._mover_paths = {
            'script': Path(MOVER_EXECUTABLE),
            'php': Path("/usr/local/emhttp/plugins/ca.mover.tuning/mover.php"),
            'age_mover': Path("/usr/local/emhttp/plugins/ca.mover.tuning/age_mover")
        }
        self._current_state = ProcessState.UNKNOWN
        self._process_groups: Dict[int, Set[int]] = {}  # main_pid -> related_pids
        self._last_stats: Optional[ProcessStats] = None
        self._running = False

    def _is_mover_related(self, proc: psutil.Process) -> bool:
        """Check if a process is related to the mover operation.

        Args:
            proc: Process to check

        Returns:
            bool: True if process is mover-related
        """
        try:
            cmdline = proc.cmdline()
            cmdline_str = ' '.join(cmdline)

            # Check for main PHP script
            if any(str(path) in cmdline_str for path in self._mover_paths.values()):
                return True

            # Check for ionice/nice wrapper processes
            if proc.name() in ['ionice', 'nice']:
                return any(str(path) in cmdline_str for path in self._mover_paths.values())

            # Check for actual file operation processes
            if proc.name() in ['mv', 'cp', 'rsync']:
                # Verify it's a descendant of a known mover process
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

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return False

    def _get_process_stats(self, script_pid: int, related_pids: Set[int]) -> ProcessStats:
        """Collect statistics for all mover-related processes.

        Args:
            script_pid: PID of the main PHP script
            related_pids: PIDs of related processes

        Returns:
            ProcessStats: Collected process statistics
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
                    with proc.oneshot():
                        total_cpu += proc.cpu_percent()
                        total_memory += proc.memory_percent()
                        if hasattr(proc, 'io_counters'):
                            io = proc.io_counters()
                            total_read += io.read_bytes
                            total_write += io.write_bytes
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return ProcessStats(
                script_pid=script_pid,
                related_pids=list(related_pids),
                total_cpu_percent=total_cpu,
                total_memory_percent=total_memory,
                io_read_bytes=total_read,
                io_write_bytes=total_write,
                start_time=start_time or datetime.now(),
                command_line=command_line,
                nice_level=nice_level,
                io_class=io_class
            )

        except (psutil.NoSuchProcess, psutil.AccessDenied) as err:
            logger.warning(
                "Failed to collect process stats",
                error=str(err),
                script_pid=script_pid
            )
            raise

    async def _find_mover_processes(self) -> Optional[tuple[int, Set[int]]]:
        """Find running mover processes.

        Returns:
            Optional[tuple[int, Set[int]]]: Tuple of (main_pid, related_pids) if found
        """
        main_pid = None
        related_pids = set()

        try:
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    if self._is_mover_related(proc):
                        cmdline = ' '.join(proc.cmdline())
                        # Main PHP script
                        if str(self._mover_paths['php']) in cmdline:
                            main_pid = proc.pid
                        else:
                            related_pids.add(proc.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if main_pid:
                return main_pid, related_pids
            return None

        except Exception as err:
            logger.error("Error searching for mover processes", error=str(err))
            self._current_state = ProcessState.ERROR
            return None

    async def _update_state(self) -> None:
        """Update process state and statistics."""
        process_info = await self._find_mover_processes()

        if not process_info:
            if self._current_state == ProcessState.RUNNING:
                logger.info("Mover process completed")
            self._current_state = ProcessState.STOPPED
            self._process_groups.clear()
            self._last_stats = None
            return

        main_pid, related_pids = process_info
        try:
            # Update process group tracking
            self._process_groups[main_pid] = related_pids
            self._current_state = ProcessState.RUNNING

            # Collect new statistics
            self._last_stats = self._get_process_stats(main_pid, related_pids)

        except (psutil.NoSuchProcess, psutil.AccessDenied) as err:
            logger.warning(
                "Failed to update process state",
                error=str(err),
                main_pid=main_pid
            )
            self._current_state = ProcessState.ERROR

    async def monitor(self) -> None:
        """Start continuous process monitoring."""
        self._running = True
        logger.info("Starting mover process monitoring")

        while self._running:
            try:
                await self._update_state()
                await asyncio.sleep(PROCESS_CHECK_INTERVAL)
            except Exception as err:
                logger.error("Monitoring error", error=str(err))
                self._current_state = ProcessState.ERROR
                await asyncio.sleep(PROCESS_CHECK_INTERVAL)

    def stop(self) -> None:
        """Stop process monitoring."""
        self._running = False
        logger.info("Stopping mover process monitoring")

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
