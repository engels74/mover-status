"""Test suite for process detection error handling and permission management."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from mover_status.core.process.error_handling import (
    ProcessDetectionError,
    ProcessPermissionError,
    ProcessNotFoundError,
    ProcessAccessDeniedError,
    ProcessTimeoutError,
    SystemResourceError,
    ErrorHandler,
    PermissionManager,
    RetryManager,
    GracefulDegradationManager,
)
from mover_status.core.process.models import ProcessStatus

if TYPE_CHECKING:
    pass


class TestProcessDetectionErrors:
    """Test process detection error classes."""

    def test_process_detection_error_base(self) -> None:
        """Test base ProcessDetectionError."""
        error = ProcessDetectionError("Test error")
        assert str(error) == "Test error"
        assert error.args == ("Test error",)

    def test_process_permission_error(self) -> None:
        """Test ProcessPermissionError with PID."""
        error = ProcessPermissionError(1234, "Access denied")
        assert error.pid == 1234
        assert "PID 1234" in str(error)
        assert "Access denied" in str(error)

    def test_process_not_found_error(self) -> None:
        """Test ProcessNotFoundError."""
        error = ProcessNotFoundError(5678)
        assert error.pid == 5678
        assert "5678" in str(error)
        assert "not found" in str(error).lower()

    def test_process_access_denied_error(self) -> None:
        """Test ProcessAccessDeniedError."""
        error = ProcessAccessDeniedError(9999, "/proc/9999/cmdline")
        assert error.pid == 9999
        assert error.resource == "/proc/9999/cmdline"
        assert "9999" in str(error)
        assert "/proc/9999/cmdline" in str(error)

    def test_process_timeout_error(self) -> None:
        """Test ProcessTimeoutError."""
        error = ProcessTimeoutError("list_processes", 30.0)
        assert error.operation == "list_processes"
        assert error.timeout_seconds == 30.0
        assert "list_processes" in str(error)
        assert "30.0" in str(error)

    def test_system_resource_error(self) -> None:
        """Test SystemResourceError."""
        error = SystemResourceError("memory", "Insufficient memory")
        assert error.resource_type == "memory"
        assert error.details == "Insufficient memory"
        assert "memory" in str(error)
        assert "Insufficient memory" in str(error)


class TestErrorHandler:
    """Test ErrorHandler functionality."""

    def test_error_handler_initialization(self) -> None:
        """Test ErrorHandler initialization."""
        handler = ErrorHandler()
        assert handler.error_count == 0
        assert len(handler.error_history) == 0

    def test_handle_permission_error(self) -> None:
        """Test handling permission errors."""
        handler = ErrorHandler()
        
        # Mock psutil exception
        mock_error = Mock()
        mock_error.pid = 1234
        
        result = handler.handle_permission_error(mock_error, 1234)
        
        assert result is None
        assert handler.error_count == 1
        assert len(handler.error_history) == 1
        assert handler.error_history[0]["type"] == "permission"

    def test_handle_process_not_found(self) -> None:
        """Test handling process not found errors."""
        handler = ErrorHandler()
        
        mock_error = Mock()
        mock_error.pid = 5678
        
        result = handler.handle_process_not_found(mock_error, 5678)
        
        assert result is None
        assert handler.error_count == 1
        assert handler.error_history[0]["type"] == "not_found"

    def test_handle_system_resource_error(self) -> None:
        """Test handling system resource errors."""
        handler = ErrorHandler()
        
        mock_error = Mock()
        mock_error.__str__ = Mock(return_value="Out of memory")
        
        result = handler.handle_system_resource_error(mock_error, "memory")
        
        assert result is None
        assert handler.error_count == 1
        assert handler.error_history[0]["type"] == "system_resource"

    def test_should_retry_logic(self) -> None:
        """Test retry decision logic."""
        handler = ErrorHandler()
        
        # Should retry for transient errors
        assert handler.should_retry("timeout", 1) is True
        assert handler.should_retry("system_resource", 2) is True
        
        # Should not retry for permanent errors
        assert handler.should_retry("permission", 1) is False
        assert handler.should_retry("not_found", 1) is False
        
        # Should not retry after max attempts
        assert handler.should_retry("timeout", 4) is False

    def test_get_error_summary(self) -> None:
        """Test error summary generation."""
        handler = ErrorHandler()
        
        # Add some errors
        handler.handle_permission_error(Mock(pid=1), 1)
        handler.handle_process_not_found(Mock(pid=2), 2)
        
        summary = handler.get_error_summary()

        assert summary["total_errors"] == 2
        error_types = summary["error_types"]
        assert isinstance(error_types, dict)
        assert "permission" in error_types
        assert "not_found" in error_types


class TestPermissionManager:
    """Test PermissionManager functionality."""

    def test_permission_manager_initialization(self) -> None:
        """Test PermissionManager initialization."""
        manager = PermissionManager()
        assert manager.current_user is not None
        assert isinstance(manager.is_root, bool)

    @patch('os.getuid')
    def test_check_process_access_as_root(self, mock_getuid: Mock) -> None:
        """Test process access check as root user."""
        mock_getuid.return_value = 0  # Root user
        
        manager = PermissionManager()
        assert manager.check_process_access(1234) is True

    @patch('os.getuid')
    @patch('psutil.Process')
    def test_check_process_access_as_user(self, mock_process: Mock, mock_getuid: Mock) -> None:
        """Test process access check as regular user."""
        mock_getuid.return_value = 1000  # Regular user
        
        # Mock process that user owns
        mock_proc = Mock()
        mock_proc.uids.return_value = Mock(real=1000)  # pyright: ignore[reportAny]
        mock_process.return_value = mock_proc
        
        manager = PermissionManager()
        assert manager.check_process_access(1234) is True

    def test_get_accessible_process_info(self) -> None:
        """Test getting accessible process information."""
        manager = PermissionManager()

        # Mock process info
        mock_process = Mock()
        mock_process.pid = 1234
        mock_process.name.return_value = "test_process"  # pyright: ignore[reportAny]
        mock_process.cmdline.return_value = ["test", "command"]  # pyright: ignore[reportAny]
        mock_process.status.return_value = "running"  # pyright: ignore[reportAny]
        mock_process.create_time.return_value = 1234567890.0  # pyright: ignore[reportAny]
        mock_process.cpu_percent.return_value = 5.5  # pyright: ignore[reportAny]

        # Mock memory_info with rss attribute
        mock_memory_info = Mock()
        mock_memory_info.rss = 1024000
        mock_process.memory_info.return_value = mock_memory_info  # pyright: ignore[reportAny]

        info = manager.get_accessible_process_info(mock_process)

        assert info is not None
        assert "pid" in info
        assert "name" in info
        assert "cmdline" in info
        assert info["pid"] == 1234
        assert info["name"] == "test_process"
        assert info["cmdline"] == ["test", "command"]

    def test_requires_elevated_privileges(self) -> None:
        """Test elevated privileges requirement check."""
        manager = PermissionManager()
        
        # System processes typically require elevated privileges
        assert manager.requires_elevated_privileges(1) is True  # init process
        assert manager.requires_elevated_privileges(2) is True  # kernel thread
        
        # User processes typically don't
        assert manager.requires_elevated_privileges(1000) is False


class TestRetryManager:
    """Test RetryManager functionality."""

    def test_retry_manager_initialization(self) -> None:
        """Test RetryManager initialization."""
        manager = RetryManager(max_attempts=3, base_delay=0.1)
        assert manager.max_attempts == 3
        assert manager.base_delay == 0.1

    def test_should_retry_decision(self) -> None:
        """Test retry decision logic."""
        manager = RetryManager(max_attempts=3)
        
        # Should retry within limits
        assert manager.should_retry(1, Exception("transient error")) is True
        assert manager.should_retry(2, Exception("transient error")) is True
        
        # Should not retry after max attempts
        assert manager.should_retry(3, Exception("transient error")) is False

    def test_calculate_delay(self) -> None:
        """Test delay calculation with exponential backoff."""
        manager = RetryManager(base_delay=0.1)
        
        # Test exponential backoff
        assert manager.calculate_delay(1) == 0.1
        assert manager.calculate_delay(2) == 0.2
        assert manager.calculate_delay(3) == 0.4

    def test_execute_with_retry_success(self) -> None:
        """Test successful execution with retry."""
        manager = RetryManager(max_attempts=3, base_delay=0.01)
        
        def successful_operation() -> str:
            return "success"
        
        result = manager.execute_with_retry(successful_operation)
        assert result == "success"

    def test_execute_with_retry_eventual_success(self) -> None:
        """Test eventual success after retries."""
        manager = RetryManager(max_attempts=3, base_delay=0.01)
        
        call_count = 0
        def eventually_successful_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = manager.execute_with_retry(eventually_successful_operation)
        assert result == "success"
        assert call_count == 3

    def test_execute_with_retry_max_attempts_exceeded(self) -> None:
        """Test failure after max attempts exceeded."""
        manager = RetryManager(max_attempts=2, base_delay=0.01)
        
        def always_failing_operation() -> str:
            raise Exception("Permanent failure")
        
        with pytest.raises(Exception, match="Permanent failure"):
            _ = manager.execute_with_retry(always_failing_operation)


class TestGracefulDegradationManager:
    """Test GracefulDegradationManager functionality."""

    def test_graceful_degradation_manager_initialization(self) -> None:
        """Test GracefulDegradationManager initialization."""
        manager = GracefulDegradationManager()
        assert manager.degradation_level == 0
        assert len(manager.disabled_features) == 0

    def test_handle_permission_denied(self) -> None:
        """Test handling permission denied scenarios."""
        manager = GracefulDegradationManager()
        
        result = manager.handle_permission_denied("process_details")
        
        assert result is not None
        assert "limited" in result.lower() or "basic" in result.lower()
        assert "process_details" in manager.disabled_features

    def test_handle_resource_exhaustion(self) -> None:
        """Test handling resource exhaustion."""
        manager = GracefulDegradationManager()
        
        result = manager.handle_resource_exhaustion("memory")
        
        assert result is not None
        assert manager.degradation_level > 0

    def test_get_fallback_process_info(self) -> None:
        """Test getting fallback process information."""
        manager = GracefulDegradationManager()
        
        fallback = manager.get_fallback_process_info(1234)
        
        assert fallback.pid == 1234
        assert fallback.name == "unknown"
        assert fallback.status == ProcessStatus.UNKNOWN

    def test_is_feature_available(self) -> None:
        """Test feature availability checking."""
        manager = GracefulDegradationManager()
        
        # Initially all features available
        assert manager.is_feature_available("process_details") is True
        
        # After disabling a feature
        _ = manager.handle_permission_denied("process_details")
        assert manager.is_feature_available("process_details") is False

    def test_get_degradation_status(self) -> None:
        """Test degradation status reporting."""
        manager = GracefulDegradationManager()
        
        # Initial status
        status = manager.get_degradation_status()
        assert status["level"] == 0
        disabled_features = status["disabled_features"]
        assert isinstance(disabled_features, list)
        assert len(disabled_features) == 0

        # After some degradation
        _ = manager.handle_permission_denied("feature1")
        _ = manager.handle_resource_exhaustion("memory")

        status = manager.get_degradation_status()
        level = status["level"]
        assert isinstance(level, int)
        assert level > 0
        disabled_features = status["disabled_features"]
        assert isinstance(disabled_features, list)
        assert len(disabled_features) > 0
