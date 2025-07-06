"""Test suite for abstract process detector interface."""

from __future__ import annotations

import pytest
from abc import ABC
from typing import TYPE_CHECKING, override

from mover_status.core.process.detector import ProcessDetector
from mover_status.core.process.models import ProcessInfo

if TYPE_CHECKING:
    pass


class TestProcessDetectorInterface:
    """Test the abstract ProcessDetector interface."""

    def test_process_detector_is_abstract(self) -> None:
        """Test that ProcessDetector is an abstract base class."""
        assert issubclass(ProcessDetector, ABC)
        
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            _ = ProcessDetector()  # type: ignore[abstract]

    def test_process_detector_has_required_methods(self) -> None:
        """Test that ProcessDetector defines required abstract methods."""
        abstract_methods = ProcessDetector.__abstractmethods__
        
        expected_methods = {
            'detect_mover',
            'is_process_running',
            'get_process_info',
            'list_processes',
            'find_processes'
        }
        
        assert abstract_methods == expected_methods

    def test_concrete_implementation_must_implement_all_methods(self) -> None:
        """Test that concrete implementations must implement all abstract methods."""
        
        # Check that we get a TypeError when trying to instantiate incomplete implementation
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            
            # Define incomplete detector (missing abstract methods)
            class IncompleteDetector(ProcessDetector):  # type: ignore[misc]
                pass
            
            # This should raise TypeError due to missing abstract methods
            _ = IncompleteDetector()  # type: ignore[abstract]

    def test_concrete_implementation_works_when_complete(self) -> None:
        """Test that concrete implementations work when all methods are implemented."""
        
        class CompleteDetector(ProcessDetector):
            @override
            def detect_mover(self) -> ProcessInfo | None:
                return None
            
            @override
            def is_process_running(self, pid: int) -> bool:
                return False
            
            @override
            def get_process_info(self, pid: int) -> ProcessInfo | None:
                return None
            
            @override
            def list_processes(self) -> list[ProcessInfo]:
                return []
            
            @override
            def find_processes(self, pattern: str) -> list[ProcessInfo]:
                return []
        
        # Should be able to instantiate
        detector = CompleteDetector()
        assert isinstance(detector, ProcessDetector)


class TestProcessDetectorMethods:
    """Test the method signatures and contracts of ProcessDetector."""

    def test_detector_has_required_method_signatures(self) -> None:
        """Test that ProcessDetector has the expected method signatures."""
        # Check that the methods exist
        assert hasattr(ProcessDetector, 'detect_mover')
        assert hasattr(ProcessDetector, 'is_process_running')
        assert hasattr(ProcessDetector, 'get_process_info')
        assert hasattr(ProcessDetector, 'list_processes')
        assert hasattr(ProcessDetector, 'find_processes')
        
        # Check they are callable
        assert callable(ProcessDetector.detect_mover)
        assert callable(ProcessDetector.is_process_running)
        assert callable(ProcessDetector.get_process_info)
        assert callable(ProcessDetector.list_processes)
        assert callable(ProcessDetector.find_processes)


class MockProcessDetector(ProcessDetector):
    """Mock implementation of ProcessDetector for testing."""

    def __init__(self) -> None:
        """Initialize the mock detector."""
        self.processes: dict[int, ProcessInfo] = {}
        self.running_pids: set[int] = set()

    @override
    def detect_mover(self) -> ProcessInfo | None:
        """Mock detect_mover implementation."""
        for process in self.processes.values():
            if 'mover' in process.command.lower():
                return process
        return None

    @override
    def is_process_running(self, pid: int) -> bool:
        """Mock is_process_running implementation."""
        return pid in self.running_pids

    @override
    def get_process_info(self, pid: int) -> ProcessInfo | None:
        """Mock get_process_info implementation."""
        return self.processes.get(pid)

    @override
    def list_processes(self) -> list[ProcessInfo]:
        """Mock list_processes implementation."""
        return list(self.processes.values())

    @override
    def find_processes(self, pattern: str) -> list[ProcessInfo]:
        """Mock find_processes implementation."""
        return [
            proc for proc in self.processes.values()
            if pattern.lower() in proc.command.lower()
        ]


class TestMockProcessDetector:
    """Test the mock process detector implementation."""

    def test_mock_detector_instantiation(self) -> None:
        """Test that the mock detector can be instantiated."""
        detector = MockProcessDetector()
        assert isinstance(detector, ProcessDetector)

    def test_mock_detector_empty_initial_state(self) -> None:
        """Test that the mock detector starts empty."""
        detector = MockProcessDetector()
        
        assert detector.detect_mover() is None
        assert detector.list_processes() == []
        assert detector.find_processes('test') == []
        assert not detector.is_process_running(123)

    def test_mock_detector_with_processes(self) -> None:
        """Test the mock detector with sample processes."""
        detector = MockProcessDetector()
        
        # Add some test processes
        from datetime import datetime
        
        process1 = ProcessInfo(
            pid=123,
            command="/usr/local/sbin/mover",
            start_time=datetime.now(),
            name="mover"
        )
        process2 = ProcessInfo(
            pid=456,
            command="/bin/bash",
            start_time=datetime.now(),
            name="bash"
        )
        
        detector.processes[123] = process1
        detector.processes[456] = process2
        detector.running_pids.add(123)
        detector.running_pids.add(456)
        
        # Test methods
        assert detector.detect_mover() == process1
        assert detector.is_process_running(123)
        assert detector.is_process_running(456)
        assert not detector.is_process_running(999)
        assert detector.get_process_info(123) == process1
        assert detector.get_process_info(999) is None
        assert len(detector.list_processes()) == 2
        assert detector.find_processes('mover') == [process1]
        assert detector.find_processes('bash') == [process2]
        assert detector.find_processes('nonexistent') == []