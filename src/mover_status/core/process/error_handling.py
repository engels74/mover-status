"""Comprehensive error handling and permission management for process detection.

This module provides robust error handling, permission management, retry mechanisms,
and graceful degradation strategies for reliable process detection operations.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Callable, TypeVar, TypedDict

import psutil

from .models import ProcessInfo, ProcessStatus

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorRecord(TypedDict):
    """Type definition for error record."""
    type: str
    pid: int | None
    message: str
    timestamp: datetime
    extra_data: dict[str, str | float]


class ProcessDetectionError(Exception):
    """Base exception for process detection errors."""

    def __init__(self, message: str) -> None:
        """Initialize the error.

        Args:
            message: Error message
        """
        super().__init__(message)
        self.message: str = message


class ProcessPermissionError(ProcessDetectionError):
    """Exception for process permission-related errors."""

    def __init__(self, pid: int, message: str) -> None:
        """Initialize the permission error.

        Args:
            pid: Process ID that caused the error
            message: Error message
        """
        super().__init__(f"Permission error for PID {pid}: {message}")
        self.pid: int = pid


class ProcessNotFoundError(ProcessDetectionError):
    """Exception for process not found errors."""

    def __init__(self, pid: int) -> None:
        """Initialize the not found error.

        Args:
            pid: Process ID that was not found
        """
        super().__init__(f"Process with PID {pid} not found")
        self.pid: int = pid


class ProcessAccessDeniedError(ProcessDetectionError):
    """Exception for process access denied errors."""

    def __init__(self, pid: int, resource: str) -> None:
        """Initialize the access denied error.

        Args:
            pid: Process ID that denied access
            resource: Resource that was denied access
        """
        super().__init__(f"Access denied to {resource} for PID {pid}")
        self.pid: int = pid
        self.resource: str = resource


class ProcessTimeoutError(ProcessDetectionError):
    """Exception for process operation timeout errors."""

    def __init__(self, operation: str, timeout_seconds: float) -> None:
        """Initialize the timeout error.

        Args:
            operation: Operation that timed out
            timeout_seconds: Timeout duration in seconds
        """
        super().__init__(f"Operation '{operation}' timed out after {timeout_seconds} seconds")
        self.operation: str = operation
        self.timeout_seconds: float = timeout_seconds


class SystemResourceError(ProcessDetectionError):
    """Exception for system resource-related errors."""

    def __init__(self, resource_type: str, details: str) -> None:
        """Initialize the system resource error.

        Args:
            resource_type: Type of resource (memory, cpu, etc.)
            details: Detailed error information
        """
        super().__init__(f"System resource error ({resource_type}): {details}")
        self.resource_type: str = resource_type
        self.details: str = details


class ErrorHandler:
    """Handles and categorizes process detection errors."""

    def __init__(self) -> None:
        """Initialize the error handler."""
        self.error_count: int = 0
        self.error_history: list[ErrorRecord] = []
        self.max_history_size: int = 100

        logger.debug("Initialized ErrorHandler")
    
    def handle_permission_error(self, error: Exception, pid: int) -> None:
        """Handle permission-related errors.

        Args:
            error: The original error object
            pid: Process ID that caused the error
        """
        self._record_error("permission", pid, str(error))
        logger.warning(f"Permission denied for process {pid}: {error}")

    def handle_process_not_found(self, error: Exception, pid: int) -> None:
        """Handle process not found errors.

        Args:
            error: The original error object
            pid: Process ID that was not found
        """
        self._record_error("not_found", pid, str(error))
        logger.debug(f"Process {pid} not found: {error}")

    def handle_system_resource_error(self, error: Exception, resource_type: str) -> None:
        """Handle system resource errors.

        Args:
            error: The original error object
            resource_type: Type of resource that caused the error
        """
        self._record_error("system_resource", None, str(error), {"resource_type": resource_type})
        logger.error(f"System resource error ({resource_type}): {error}")
    
    def handle_timeout_error(self, operation: str, timeout_seconds: float) -> None:
        """Handle timeout errors.
        
        Args:
            operation: Operation that timed out
            timeout_seconds: Timeout duration
        """
        self._record_error("timeout", None, f"Operation '{operation}' timed out", 
                          {"operation": operation, "timeout": timeout_seconds})
        logger.warning(f"Operation '{operation}' timed out after {timeout_seconds} seconds")
    
    def should_retry(self, error_type: str, attempt: int) -> bool:
        """Determine if an operation should be retried.
        
        Args:
            error_type: Type of error that occurred
            attempt: Current attempt number
            
        Returns:
            True if operation should be retried
        """
        # Don't retry permanent errors
        if error_type in ["permission", "not_found"]:
            return False
        
        # Retry transient errors up to 3 attempts
        return attempt < 3
    
    def get_error_summary(self) -> dict[str, int | dict[str, int] | list[ErrorRecord]]:
        """Get summary of all errors encountered.

        Returns:
            Dictionary containing error statistics and details
        """
        error_types: dict[str, int] = {}
        for error in self.error_history:
            error_type = error["type"]
            error_types[error_type] = error_types.get(error_type, 0) + 1

        return {
            "total_errors": self.error_count,
            "error_types": error_types,
            "recent_errors": self.error_history[-10:] if self.error_history else []
        }
    
    def _record_error(self, error_type: str, pid: int | None, message: str,
                     extra_data: dict[str, str | float] | None = None) -> None:
        """Record an error in the history.

        Args:
            error_type: Type of error
            pid: Process ID (if applicable)
            message: Error message
            extra_data: Additional error data
        """
        self.error_count += 1

        error_record: ErrorRecord = {
            "type": error_type,
            "pid": pid,
            "message": message,
            "timestamp": datetime.now(),
            "extra_data": extra_data or {}
        }

        self.error_history.append(error_record)

        # Limit history size
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size:]


class PermissionManager:
    """Manages process access permissions and privilege requirements."""

    def __init__(self) -> None:
        """Initialize the permission manager."""
        self.current_user: int = os.getuid()
        self.is_root: bool = self.current_user == 0

        logger.debug(f"Initialized PermissionManager (user={self.current_user}, root={self.is_root})")
    
    def check_process_access(self, pid: int) -> bool:
        """Check if current user can access a process.
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if process is accessible
        """
        if self.is_root:
            return True
        
        try:
            process = psutil.Process(pid)
            # Check if we own the process
            return process.uids().real == self.current_user
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    
    def get_accessible_process_info(self, process: psutil.Process) -> dict[str, str | int | list[str] | float] | None:
        """Get accessible information from a process object.

        Args:
            process: psutil.Process object

        Returns:
            Dictionary of accessible process information
        """
        try:
            info: dict[str, str | int | list[str] | float] = {
                "pid": process.pid,
                "name": process.name(),
                "cmdline": process.cmdline(),
            }

            # Try to get additional info if accessible
            try:
                info["status"] = process.status()
                info["create_time"] = process.create_time()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                pass

            try:
                info["cpu_percent"] = process.cpu_percent()
                memory_info = process.memory_info()
                info["memory_rss"] = float(memory_info.rss)  # pyright: ignore[reportAny]
            except (psutil.AccessDenied, psutil.ZombieProcess):
                pass

            return info

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
    
    def requires_elevated_privileges(self, pid: int) -> bool:
        """Check if accessing a process requires elevated privileges.
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if elevated privileges are required
        """
        # System processes (low PIDs) typically require elevated privileges
        if pid < 100:
            return True
        
        try:
            process = psutil.Process(pid)
            # Check if process is owned by root or system user
            return process.uids().real == 0
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return True  # Assume elevated privileges required if we can't check


class RetryManager:
    """Manages retry logic for transient failures."""

    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0) -> None:
        """Initialize the retry manager.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
        """
        self.max_attempts: int = max_attempts
        self.base_delay: float = base_delay

        logger.debug(f"Initialized RetryManager (max_attempts={max_attempts}, base_delay={base_delay})")
    
    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Determine if an operation should be retried.
        
        Args:
            attempt: Current attempt number (1-based)
            error: Exception that occurred
            
        Returns:
            True if operation should be retried
        """
        if attempt >= self.max_attempts:
            return False
        
        # Don't retry certain permanent errors
        if isinstance(error, (ProcessPermissionError, ProcessNotFoundError)):
            return False
        
        return True
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay before next retry using exponential backoff.

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds
        """
        multiplier: float = pow(2.0, attempt - 1)
        return self.base_delay * multiplier
    
    def execute_with_retry(self, operation: Callable[[], T]) -> T:
        """Execute an operation with retry logic.

        Args:
            operation: Function to execute

        Returns:
            Result of the operation

        Raises:
            Last exception if all retries fail
        """
        last_exception: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                result: T = operation()
                return result
            except Exception as e:
                last_exception = e

                if not self.should_retry(attempt, e):
                    break

                if attempt < self.max_attempts:
                    delay = self.calculate_delay(attempt)
                    logger.debug(f"Retry attempt {attempt} failed, waiting {delay}s: {e}")
                    time.sleep(delay)

        # All retries failed, raise the last exception
        if last_exception:
            raise last_exception

        # This should never happen, but satisfy type checker
        raise RuntimeError("Unexpected retry failure")


class GracefulDegradationManager:
    """Manages graceful degradation when full functionality is not available."""

    def __init__(self) -> None:
        """Initialize the graceful degradation manager."""
        self.degradation_level: int = 0
        self.disabled_features: set[str] = set()

        logger.debug("Initialized GracefulDegradationManager")
    
    def handle_permission_denied(self, feature: str) -> str:
        """Handle permission denied by providing limited functionality.
        
        Args:
            feature: Feature that was denied access
            
        Returns:
            Description of fallback behavior
        """
        self.disabled_features.add(feature)
        self.degradation_level += 1
        
        fallback_msg = f"Limited {feature} information available due to permissions"
        logger.info(f"Graceful degradation: {fallback_msg}")
        
        return fallback_msg
    
    def handle_resource_exhaustion(self, resource_type: str) -> str:
        """Handle resource exhaustion by reducing functionality.
        
        Args:
            resource_type: Type of resource that was exhausted
            
        Returns:
            Description of degraded behavior
        """
        self.degradation_level += 2
        
        degradation_msg = f"Reduced functionality due to {resource_type} constraints"
        logger.warning(f"Resource exhaustion degradation: {degradation_msg}")
        
        return degradation_msg
    
    def get_fallback_process_info(self, pid: int) -> ProcessInfo:
        """Get minimal process information when full details are unavailable.
        
        Args:
            pid: Process ID
            
        Returns:
            ProcessInfo with minimal available information
        """
        return ProcessInfo(
            pid=pid,
            command="<unavailable>",
            start_time=datetime.now(),
            name="unknown",
            status=ProcessStatus.UNKNOWN
        )
    
    def is_feature_available(self, feature: str) -> bool:
        """Check if a feature is still available.
        
        Args:
            feature: Feature name to check
            
        Returns:
            True if feature is available
        """
        return feature not in self.disabled_features
    
    def get_degradation_status(self) -> dict[str, int | list[str] | bool]:
        """Get current degradation status.

        Returns:
            Dictionary containing degradation information
        """
        return {
            "level": self.degradation_level,
            "disabled_features": list(self.disabled_features),
            "is_degraded": self.degradation_level > 0
        }
