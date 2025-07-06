"""Unraid-specific process detector implementation."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, override

import psutil

from .detector import ProcessDetector
from .models import ProcessInfo, ProcessStatus

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


class UnraidMoverDetector(ProcessDetector):
    """Unraid-specific implementation of ProcessDetector for mover process detection.
    
    This detector is specifically designed for Unraid systems and implements
    the ProcessDetector interface to provide comprehensive process detection
    and monitoring capabilities focused on the Unraid mover process.
    """
    
    MOVER_PATTERNS: list[str] = [
        "mover",
        "/usr/local/sbin/mover",
        "/usr/local/sbin/mover.old",  # Real mover binary
        "/usr/local/bin/mover",
        "/usr/local/emhttp/plugins/ca.mover.tuning/mover.php",  # PHP wrapper
        "/usr/local/emhttp/plugins/ca.mover.tuning/age_mover",  # Enhanced mover
        "mover-backup",
        "mover.py",
    ]
    
    def __init__(self) -> None:
        """Initialize the Unraid mover detector.
        
        Sets up the detector with Unraid-specific configuration and patterns
        for identifying mover processes.
        """
        logger.debug("Initializing UnraidMoverDetector")
    
    def _check_mover_pid_file(self) -> int | None:
        """Check if mover PID file exists and return PID if valid.
        
        Returns:
            PID if file exists and process is running, None otherwise
        """
        try:
            with open('/var/run/mover.pid', 'r') as f:
                pid_str = f.read().strip()
                pid = int(pid_str)
            
            # Check if the process is actually running
            if self.is_process_running(pid):
                logger.debug(f"Found valid mover PID file with PID {pid}")
                return pid
            else:
                logger.debug(f"PID file exists but process {pid} is not running")
                return None
                
        except (FileNotFoundError, ValueError, PermissionError) as e:
            logger.debug(f"Could not read mover PID file: {e}")
            return None
    
    def _detect_mover_hierarchy(self) -> ProcessInfo | None:
        """Detect mover process including ionice/nice wrappers.
        
        Returns:
            ProcessInfo for wrapped mover process if found, None otherwise
        """
        logger.debug("Detecting mover process with hierarchy support")
        
        try:
            # psutil.process_iter returns Iterator[Process] but type checker sees it as partially unknown
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):  # pyright: ignore[reportUnknownMemberType]
                try:
                    # Skip processes with no cmdline (kernel threads)
                    if not proc.info['cmdline']:
                        continue

                    # Join command line arguments into a single string
                    cmdline_list: list[str] = proc.info['cmdline']  # pyright: ignore[reportAny]
                    cmdline = ' '.join(cmdline_list) if cmdline_list else ''

                    # Check for ionice/nice wrapper containing mover
                    if ('ionice' in cmdline and 'nice' in cmdline and 
                        any(pattern in cmdline for pattern in self.MOVER_PATTERNS)):
                        logger.debug(f"Found wrapped mover process: PID={proc.info['pid']}, cmdline='{cmdline}'")
                        return self._create_process_info(proc)

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                    logger.debug(f"Error accessing process {proc.info.get('pid', 'unknown')}: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Error accessing process {proc.info.get('pid', 'unknown')}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error during hierarchy mover detection: {e}")

        logger.debug("No wrapped mover process found")
        return None
    
    def _detect_direct_mover(self) -> ProcessInfo | None:
        """Detect mover process using direct pattern matching.
        
        Returns:
            ProcessInfo for direct mover process if found, None otherwise
        """
        logger.debug("Detecting direct mover process")

        try:
            # psutil.process_iter returns Iterator[Process] but type checker sees it as partially unknown
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):  # pyright: ignore[reportUnknownMemberType]
                try:
                    # Skip processes with no cmdline (kernel threads)
                    if not proc.info['cmdline']:
                        continue

                    # Join command line arguments into a single string
                    cmdline_list: list[str] = proc.info['cmdline']  # pyright: ignore[reportAny]
                    cmdline = ' '.join(cmdline_list) if cmdline_list else ''
                    process_name = proc.info['name'] or ''

                    # Check if this process matches any mover pattern
                    if self._is_mover_process(cmdline, process_name):
                        logger.debug(f"Found direct mover process: PID={proc.info['pid']}, cmdline='{cmdline}'")
                        return self._create_process_info(proc)

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                    logger.debug(f"Error accessing process {proc.info.get('pid', 'unknown')}: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Error accessing process {proc.info.get('pid', 'unknown')}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error during direct mover detection: {e}")

        logger.debug("No direct mover process found")
        return None
    
    @override
    def detect_mover(self) -> ProcessInfo | None:
        """Enhanced mover detection with PID file and hierarchy support.

        Detection strategy:
        1. First check PID file for official mover process
        2. Fall back to process hierarchy detection (ionice/nice wrappers)
        3. Finally use direct process scanning

        Returns:
            ProcessInfo for the mover process if found, None otherwise
        """
        logger.debug("Detecting mover process with enhanced detection")

        # First check PID file
        pid = self._check_mover_pid_file()
        if pid is not None:
            process_info = self.get_process_info(pid)
            if process_info is not None:
                logger.debug(f"Found mover via PID file: {pid}")
                return process_info

        # Fall back to hierarchy detection (ionice/nice wrappers)
        hierarchy_result = self._detect_mover_hierarchy()
        if hierarchy_result is not None:
            logger.debug("Found mover via hierarchy detection")
            return hierarchy_result

        # Finally try direct process scanning
        direct_result = self._detect_direct_mover()
        if direct_result is not None:
            logger.debug("Found mover via direct detection")
            return direct_result

        logger.debug("No mover process found")
        return None
    
    @override
    def is_process_running(self, pid: int) -> bool:
        """Check if a process is still running.
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if process is running, False otherwise
        """
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    
    @override
    def get_process_info(self, pid: int) -> ProcessInfo | None:
        """Get detailed information about a specific process.
        
        Args:
            pid: Process ID to get information for
            
        Returns:
            ProcessInfo if process exists, None otherwise
        """
        try:
            process = psutil.Process(pid)
            return self._create_process_info(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.debug(f"Error accessing process {pid}: {e}")
            return None
    
    @override
    def list_processes(self) -> list[ProcessInfo]:
        """List all processes accessible to the detector.

        Returns:
            List of ProcessInfo objects for all accessible processes
        """
        processes: list[ProcessInfo] = []

        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):  # pyright: ignore[reportUnknownMemberType]
                try:
                    process_info = self._create_process_info(proc)
                    processes.append(process_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error listing processes: {e}")

        return processes
    
    @override
    def find_processes(self, pattern: str) -> list[ProcessInfo]:
        """Find processes matching a pattern.

        Args:
            pattern: Pattern to match against process names/commands

        Returns:
            List of ProcessInfo objects matching the pattern
        """
        matching_processes: list[ProcessInfo] = []
        pattern_lower = pattern.lower()

        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):  # pyright: ignore[reportUnknownMemberType]
                try:
                    # Skip processes with no cmdline (kernel threads)
                    if not proc.info['cmdline']:
                        continue

                    # Join command line arguments into a single string
                    cmdline_list: list[str] = proc.info['cmdline']  # pyright: ignore[reportAny]
                    cmdline = ' '.join(cmdline_list) if cmdline_list else ''
                    process_name = proc.info['name'] or ''

                    # Check if pattern matches command line or process name
                    if (pattern_lower in cmdline.lower() or
                        pattern_lower in process_name.lower()):
                        process_info = self._create_process_info(proc)
                        matching_processes.append(process_info)

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error finding processes with pattern '{pattern}': {e}")

        return matching_processes
    
    def _is_mover_process(self, cmdline: str, process_name: str) -> bool:
        """Check if a process is a mover process based on command line and name.
        
        Args:
            cmdline: Full command line of the process
            process_name: Name of the process
            
        Returns:
            True if this appears to be a mover process
        """
        cmdline_lower = cmdline.lower()
        name_lower = process_name.lower()
        
        return any(
            pattern.lower() in cmdline_lower or pattern.lower() in name_lower
            for pattern in self.MOVER_PATTERNS
        )
    
    def _create_process_info(self, proc: psutil.Process) -> ProcessInfo:
        """Create ProcessInfo object from psutil Process.
        
        Args:
            proc: psutil.Process object to convert
            
        Returns:
            ProcessInfo object with process details
            
        Raises:
            psutil.NoSuchProcess: If process no longer exists
            psutil.AccessDenied: If access to process is denied
            psutil.ZombieProcess: If process is a zombie
        """
        # Get basic process information
        pid = proc.pid
        name = proc.name()
        cmdline = proc.cmdline()
        command = ' '.join(cmdline) if cmdline else name
        
        # Get process timing information
        create_time = proc.create_time()
        start_time = datetime.fromtimestamp(create_time)
        
        # Get process status
        status_str = proc.status()
        status = self._convert_status(status_str)
        
        # Get resource usage (with error handling)
        cpu_percent: float | None = None
        memory_mb: float | None = None
        try:
            cpu_percent = proc.cpu_percent()
            memory_info = proc.memory_info()
            memory_mb = float(memory_info.rss) / (1024 * 1024)  # Convert bytes to MB  # pyright: ignore[reportAny]
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        
        # Get additional process information (with error handling)
        working_directory = None
        user = None
        try:
            working_directory = proc.cwd()
            user = proc.username()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        
        return ProcessInfo(
            pid=pid,
            name=name,
            command=command,
            start_time=start_time,
            status=status,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            working_directory=working_directory,
            user=user
        )
    
    def _convert_status(self, psutil_status: str) -> ProcessStatus:
        """Convert psutil status string to ProcessStatus enum.
        
        Args:
            psutil_status: Status string from psutil
            
        Returns:
            ProcessStatus enum value
        """
        # Map psutil status strings to ProcessStatus enum
        status_mapping = {
            'running': ProcessStatus.RUNNING,
            'sleeping': ProcessStatus.RUNNING,  # Sleeping processes are still running
            'disk-sleep': ProcessStatus.RUNNING,  # Uninterruptible sleep is still running
            'stopped': ProcessStatus.STOPPED,
            'tracing-stop': ProcessStatus.STOPPED,
            'zombie': ProcessStatus.STOPPED,
            'dead': ProcessStatus.STOPPED,
            'wake-kill': ProcessStatus.STOPPED,
            'waking': ProcessStatus.RUNNING,
            'idle': ProcessStatus.RUNNING,
            'locked': ProcessStatus.RUNNING,
            'waiting': ProcessStatus.RUNNING,
        }
        
        return status_mapping.get(psutil_status.lower(), ProcessStatus.UNKNOWN)
    
    def get_execution_context(self, process_info: ProcessInfo) -> str:
        """Determine how mover was executed (cron/manual/web UI).
        
        Args:
            process_info: ProcessInfo object for the mover process
            
        Returns:
            Execution context: 'cron', 'manual', 'web_ui', or 'unknown'
        """
        if not process_info.command:
            return "unknown"
        
        try:
            proc = psutil.Process(process_info.pid)
            parent = proc.parent()
            if parent:
                parent_name = parent.name()
                parent_cmdline = parent.cmdline()
                
                if parent_name == "crond":
                    return "cron"
                elif parent_name in ["bash", "sh"]:
                    return "manual"
                elif parent_cmdline and "emhttp" in parent_cmdline[0]:
                    return "web_ui"
                    
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.debug(f"Could not determine execution context for PID {process_info.pid}: {e}")
        
        return "unknown"