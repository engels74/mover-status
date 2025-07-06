"""Integration test suite for process detection framework.

This module provides comprehensive integration tests that verify the interaction
between all components of the process detection framework, including abstract
interfaces, concrete implementations, pattern matching, and error handling.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, patch

from mover_status.core.process import (
    ProcessInfo,
    ProcessStatus,
    UnraidMoverDetector,
    RegexMatcher,
    WildcardMatcher,
    CustomMatcher,
    ProcessGrouper,
    ErrorHandler,
    PermissionManager,
    RetryManager,
    ProcessPermissionError,
    ProcessNotFoundError,
)

if TYPE_CHECKING:
    pass

# pyright: reportAny=false


# Create proper exception classes for mocking
class MockNoSuchProcess(Exception):
    """Mock exception for psutil.NoSuchProcess."""
    pid: int

    def __init__(self, pid: int = 0) -> None:
        self.pid = pid
        super().__init__(f"process no longer exists (pid={pid})")


class MockAccessDenied(Exception):
    """Mock exception for psutil.AccessDenied."""
    pid: int

    def __init__(self, pid: int = 0) -> None:
        self.pid = pid
        super().__init__(f"access denied (pid={pid})")


class MockZombieProcess(Exception):
    """Mock exception for psutil.ZombieProcess."""
    pid: int

    def __init__(self, pid: int = 0) -> None:
        self.pid = pid
        super().__init__(f"zombie process (pid={pid})")


class TestProcessDetectionFrameworkIntegration:
    """Integration tests for the complete process detection framework."""

    def _setup_mock_psutil(self, mock_psutil: MagicMock) -> None:
        """Set up mock psutil with proper exception classes."""
        mock_psutil.NoSuchProcess = MockNoSuchProcess
        mock_psutil.AccessDenied = MockAccessDenied
        mock_psutil.ZombieProcess = MockZombieProcess

    def test_full_framework_integration_with_successful_detection(self) -> None:
        """Test complete framework integration with successful mover detection."""
        # Create a real UnraidMoverDetector
        detector = UnraidMoverDetector()
        
        # Mock psutil to simulate a running mover process
        with patch('mover_status.core.process.unraid_detector.psutil') as mock_psutil:
            self._setup_mock_psutil(mock_psutil)
            
            # Mock process data - exactly like the working test
            mock_proc: MagicMock = Mock()
            mock_proc.info = {
                'pid': 1234,
                'name': 'mover',
                'cmdline': ['/usr/local/sbin/mover']
            }

            # Mock psutil.Process methods
            mock_proc.pid = 1234
            mock_proc.name.return_value = 'mover'
            mock_proc.cmdline.return_value = ['/usr/local/sbin/mover']
            mock_proc.create_time.return_value = 1735728000.0
            mock_proc.status.return_value = 'running'
            mock_proc.cpu_percent.return_value = 15.5
            mock_memory_info: MagicMock = Mock()
            mock_memory_info.rss = 1024 * 1024 * 50  # 50MB
            mock_proc.memory_info.return_value = mock_memory_info
            mock_proc.cwd.return_value = '/tmp'
            mock_proc.username.return_value = 'root'

            # Mock psutil.process_iter to return our mock process
            mock_psutil.process_iter.return_value = [mock_proc]
            
            # Test mover detection
            mover_process = detector.detect_mover()
            
            assert mover_process is not None
            assert mover_process.pid == 1234
            assert mover_process.name == 'mover'
            assert mover_process.command == '/usr/local/sbin/mover'
            assert mover_process.status == ProcessStatus.RUNNING
            assert mover_process.cpu_percent == 15.5
            assert mover_process.memory_mb == 50.0
            assert mover_process.user == 'root'
            assert mover_process.working_directory == '/tmp'

    def test_framework_integration_with_pattern_matching(self) -> None:
        """Test framework integration with pattern matching capabilities."""
        # Test pattern matching without complex detector mocking
        # Create sample processes
        processes = [
            ProcessInfo(
                pid=123, name="mover", command="/usr/local/sbin/mover",
                start_time=datetime.now(), cpu_percent=15.0
            ),
            ProcessInfo(
                pid=124, name="bash", command="/bin/bash",
                start_time=datetime.now(), cpu_percent=2.0
            ),
            ProcessInfo(
                pid=125, name="mover-backup", command="/usr/local/sbin/mover-backup",
                start_time=datetime.now(), cpu_percent=12.0
            ),
        ]
        
        # Test multiple pattern matchers working together
        regex_matcher = RegexMatcher(r'mover.*', case_sensitive=False)
        wildcard_matcher = WildcardMatcher('*backup*')
        custom_matcher = CustomMatcher(
            lambda p: p.cpu_percent is not None and p.cpu_percent > 10.0,
            "High CPU processes"
        )
        
        # Test each matcher individually
        regex_matches = [p for p in processes if regex_matcher.match(p)]
        wildcard_matches = [p for p in processes if wildcard_matcher.match(p)]
        cpu_matches = [p for p in processes if custom_matcher.match(p)]
        
        # Verify pattern matching results
        assert len(regex_matches) == 2  # mover and mover-backup
        assert len(wildcard_matches) == 1  # mover-backup
        assert len(cpu_matches) == 2  # mover and mover-backup (both > 10% CPU)
        
        # Test combined filtering (all matchers must match)
        combined_matches = [
            p for p in processes 
            if regex_matcher.match(p) and wildcard_matcher.match(p) and custom_matcher.match(p)
        ]
        assert len(combined_matches) == 1  # Only mover-backup matches all criteria
        assert combined_matches[0].name == "mover-backup"

    def test_framework_integration_with_error_handling(self) -> None:
        """Test framework integration with comprehensive error handling."""
        error_handler = ErrorHandler()
        permission_manager = PermissionManager()
        
        # Test error handler and permission manager integration
        with patch('os.getuid', return_value=1000):  # Non-root user
            # Create new permission manager with mocked user ID
            permission_manager = PermissionManager()
            assert permission_manager.is_root is False
            
            # Test permission checking
            with patch('psutil.Process') as mock_process:
                mock_proc = Mock()
                mock_proc.uids.return_value = Mock(real=1000)  # User owns process
                mock_process.return_value = mock_proc
                
                # Should have access to own process
                assert permission_manager.check_process_access(1234) is True
                
            # Test error handling
            try:
                raise ProcessPermissionError(123, "Access denied")
            except ProcessPermissionError as e:
                error_handler.handle_permission_error(e, 123)
                
                # Verify error was recorded
                assert error_handler.error_count == 1
                assert len(error_handler.error_history) == 1
                assert error_handler.error_history[0]["type"] == "permission"
                assert error_handler.error_history[0]["pid"] == 123

    def test_framework_integration_with_process_grouping(self) -> None:
        """Test framework integration with process grouping functionality."""
        # Create sample processes
        processes = [
            ProcessInfo(
                pid=123, name="mover", command="/usr/local/sbin/mover",
                start_time=datetime.now(), cpu_percent=5.0, memory_mb=50.0
            ),
            ProcessInfo(
                pid=124, name="mover", command="/usr/local/sbin/mover --backup",
                start_time=datetime.now(), cpu_percent=15.0, memory_mb=100.0
            ),
            ProcessInfo(
                pid=125, name="bash", command="/bin/bash",
                start_time=datetime.now(), cpu_percent=1.0, memory_mb=10.0
            ),
            ProcessInfo(
                pid=126, name="python", command="/usr/bin/python script.py",
                start_time=datetime.now(), cpu_percent=25.0, memory_mb=200.0
            ),
        ]
        
        grouper = ProcessGrouper()
        
        # Test grouping by name
        name_groups = grouper.group_by_name(processes)
        assert "mover" in name_groups
        assert len(name_groups["mover"]) == 2
        assert "bash" in name_groups
        assert len(name_groups["bash"]) == 1
        
        # Test grouping by resource usage (adjust thresholds to match test data)
        resource_groups = grouper.group_by_resource_usage(processes, cpu_threshold=10.0, memory_threshold=150.0)
        assert "high_cpu" in resource_groups
        assert "normal" in resource_groups
        assert "high_memory" in resource_groups
        assert "high_both" in resource_groups
        # mover --backup (15.0% CPU, 100MB) should be high_cpu only
        assert len(resource_groups["high_cpu"]) == 1  # mover --backup
        # python (25.0% CPU, 200MB) should be high_both (both CPU and memory)
        assert len(resource_groups["high_both"]) == 1  # python
        # mover (5.0% CPU, 50MB) and bash (1.0% CPU, 10MB) should be normal
        assert len(resource_groups["normal"]) == 2   # mover and bash

    def test_framework_integration_with_retry_mechanism(self) -> None:
        """Test framework integration with retry mechanisms for transient failures."""
        retry_manager = RetryManager(max_attempts=3, base_delay=0.01)  # Fast retry for testing
        
        call_count = 0
        
        def failing_operation() -> ProcessInfo | None:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Use a retryable exception (not ProcessNotFoundError which is permanent)
                raise RuntimeError("Temporary failure")
            return ProcessInfo(
                pid=123, name="mover", command="/usr/local/sbin/mover",
                start_time=datetime.now()
            )
        
        # Test retry mechanism
        result = retry_manager.execute_with_retry(failing_operation)
        
        assert result is not None
        assert result.pid == 123
        assert call_count == 3  # Should have retried twice before success
        
        # Test that permanent errors are not retried
        def permanent_failure() -> ProcessInfo | None:
            raise ProcessNotFoundError(456)
        
        try:
            _ = retry_manager.execute_with_retry(permanent_failure)
            assert False, "Should have raised ProcessNotFoundError"
        except ProcessNotFoundError:
            pass  # Expected

    def test_comprehensive_framework_integration(self) -> None:
        """Test comprehensive integration of all framework components."""
        # Test all components working together without complex mocking
        
        # 1. Test ProcessInfo model with validation
        process_info = ProcessInfo(
            pid=123,
            name="mover",
            command="/usr/local/sbin/mover",
            start_time=datetime.now(),
            cpu_percent=15.5,
            memory_mb=50.0,
            user="root",
            working_directory="/tmp"
        )
        
        # 2. Test pattern matching on the process
        regex_matcher = RegexMatcher(r'mover', case_sensitive=False)
        wildcard_matcher = WildcardMatcher('*mover*')
        custom_matcher = CustomMatcher(
            lambda p: p.cpu_percent is not None and p.cpu_percent > 10.0,
            "High CPU processes"
        )
        
        assert regex_matcher.match(process_info)
        assert wildcard_matcher.match(process_info)
        assert custom_matcher.match(process_info)
        
        # 3. Test process grouping
        processes = [
            process_info,
            ProcessInfo(
                pid=124, name="bash", command="/bin/bash",
                start_time=datetime.now(), cpu_percent=2.0
            )
        ]
        
        grouper = ProcessGrouper()
        name_groups = grouper.group_by_name(processes)
        resource_groups = grouper.group_by_resource_usage(processes, cpu_threshold=10.0)
        
        assert "mover" in name_groups
        assert "bash" in name_groups
        assert len(name_groups["mover"]) == 1
        assert len(resource_groups["high_cpu"]) == 1  # mover process
        assert len(resource_groups["normal"]) == 1    # bash process
        
        # 4. Test error handling
        error_handler = ErrorHandler()
        try:
            raise ProcessPermissionError(123, "Test error")
        except ProcessPermissionError as e:
            error_handler.handle_permission_error(e, 123)
            
        assert error_handler.error_count == 1
        assert len(error_handler.error_history) == 1
        
        # 5. Test retry manager
        retry_manager = RetryManager(max_attempts=2, base_delay=0.01)
        call_count = 0
        
        def test_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Temporary failure")
            return "success"
        
        result = retry_manager.execute_with_retry(test_operation)
        assert result == "success"
        assert call_count == 2
