"""Abstract process detector interface for process detection and monitoring."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ProcessInfo


class ProcessDetector(ABC):
    """Abstract base class for process detection functionality.
    
    This class defines the interface contract for process detection operations
    including discovery, filtering, and monitoring of processes.
    """
    
    @abstractmethod
    def detect_mover(self) -> ProcessInfo | None:
        """Detect running mover process.
        
        Returns:
            ProcessInfo for the mover process if found, None otherwise
        """
        pass
    
    @abstractmethod
    def is_process_running(self, pid: int) -> bool:
        """Check if a process is still running.
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if process is running, False otherwise
        """
        pass
    
    @abstractmethod
    def get_process_info(self, pid: int) -> ProcessInfo | None:
        """Get detailed information about a specific process.
        
        Args:
            pid: Process ID to get information for
            
        Returns:
            ProcessInfo if process exists, None otherwise
        """
        pass
    
    @abstractmethod
    def list_processes(self) -> list[ProcessInfo]:
        """List all processes accessible to the detector.
        
        Returns:
            List of ProcessInfo objects for all accessible processes
        """
        pass
    
    @abstractmethod
    def find_processes(self, pattern: str) -> list[ProcessInfo]:
        """Find processes matching a pattern.
        
        Args:
            pattern: Pattern to match against process names/commands
            
        Returns:
            List of ProcessInfo objects matching the pattern
        """
        pass


class ProcessFilter(ABC):
    """Abstract base class for process filtering operations."""
    
    @abstractmethod
    def match(self, process: ProcessInfo) -> bool:
        """Check if a process matches the filter criteria.
        
        Args:
            process: ProcessInfo to check
            
        Returns:
            True if process matches filter, False otherwise
        """
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get a human-readable description of the filter.
        
        Returns:
            String description of what the filter matches
        """
        pass


class ProcessMonitor(ABC):
    """Abstract base class for process monitoring operations."""
    
    @abstractmethod
    def start_monitoring(self, process: ProcessInfo) -> None:
        """Start monitoring a process.
        
        Args:
            process: Process to monitor
        """
        pass
    
    @abstractmethod
    def stop_monitoring(self, pid: int) -> None:
        """Stop monitoring a process.
        
        Args:
            pid: Process ID to stop monitoring
        """
        pass
    
    @abstractmethod
    def get_monitored_processes(self) -> list[ProcessInfo]:
        """Get list of currently monitored processes.
        
        Returns:
            List of ProcessInfo objects for monitored processes
        """
        pass
    
    @abstractmethod
    def is_monitoring(self, pid: int) -> bool:
        """Check if a process is being monitored.
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if process is being monitored, False otherwise
        """
        pass