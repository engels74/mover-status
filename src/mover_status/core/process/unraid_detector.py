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
        "/usr/local/bin/mover",
        "mover-backup",
        "mover.py",
    ]
    
    def __init__(self) -> None:
        """Initialize the Unraid mover detector.
        
        Sets up the detector with Unraid-specific configuration and patterns
        for identifying mover processes.
        """
        logger.debug("Initializing UnraidMoverDetector")
    
    @override
    def detect_mover(self) -> ProcessInfo | None:
        """Detect running mover process on Unraid system.
        
        Searches through all running processes to find the mover process
        using predefined patterns specific to Unraid systems.
        
        Returns:
            ProcessInfo for the mover process if found, None otherwise
        """
        logger.debug("Detecting mover process")
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # Skip processes with no cmdline (kernel threads)
                    if not proc.info['cmdline']:
                        continue
                    
                    # Join command line arguments into a single string
                    cmdline_list = proc.info['cmdline']
                    cmdline = ' '.join(cmdline_list) if cmdline_list else ''
                    process_name = proc.info['name'] or ''
                    
                    # Check if this process matches any mover pattern
                    if self._is_mover_process(cmdline, process_name):
                        logger.debug(f"Found mover process: PID={proc.info['pid']}, cmdline='{cmdline}'")
                        return self._create_process_info(proc)
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                    logger.debug(f"Error accessing process {proc.info.get('pid', 'unknown')}: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Error accessing process {proc.info.get('pid', 'unknown')}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error during mover detection: {e}")
            
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
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
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
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # Skip processes with no cmdline (kernel threads)
                    if not proc.info['cmdline']:
                        continue
                    
                    # Join command line arguments into a single string
                    cmdline_list = proc.info['cmdline']
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
            memory_mb = float(memory_info.rss) / (1024 * 1024)  # Convert bytes to MB
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