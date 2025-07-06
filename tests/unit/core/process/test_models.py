"""Test suite for process models."""

from __future__ import annotations

import pytest
from datetime import datetime
from typing import TYPE_CHECKING

from mover_status.core.process.models import ProcessInfo, ProcessStatus

if TYPE_CHECKING:
    pass


class TestProcessStatus:
    """Test the ProcessStatus enum."""

    def test_process_status_values(self) -> None:
        """Test that ProcessStatus has expected values."""
        assert ProcessStatus.RUNNING.value == "running"
        assert ProcessStatus.STOPPED.value == "stopped"
        assert ProcessStatus.UNKNOWN.value == "unknown"

    def test_process_status_from_string(self) -> None:
        """Test creating ProcessStatus from string."""
        assert ProcessStatus.from_string("running") == ProcessStatus.RUNNING
        assert ProcessStatus.from_string("stopped") == ProcessStatus.STOPPED
        assert ProcessStatus.from_string("unknown") == ProcessStatus.UNKNOWN

    def test_process_status_from_string_case_insensitive(self) -> None:
        """Test ProcessStatus.from_string is case insensitive."""
        assert ProcessStatus.from_string("RUNNING") == ProcessStatus.RUNNING
        assert ProcessStatus.from_string("Running") == ProcessStatus.RUNNING
        assert ProcessStatus.from_string("rUnNiNg") == ProcessStatus.RUNNING

    def test_process_status_from_string_invalid(self) -> None:
        """Test ProcessStatus.from_string with invalid input."""
        with pytest.raises(ValueError, match="Invalid process status: 'invalid'"):
            _ = ProcessStatus.from_string("invalid")

    def test_process_status_string_representation(self) -> None:
        """Test string representation of ProcessStatus."""
        assert str(ProcessStatus.RUNNING) == "running"
        assert str(ProcessStatus.STOPPED) == "stopped"
        assert str(ProcessStatus.UNKNOWN) == "unknown"


class TestProcessInfo:
    """Test the ProcessInfo model."""

    def test_process_info_creation(self) -> None:
        """Test creating a ProcessInfo instance."""
        start_time = datetime.now()
        
        process = ProcessInfo(
            pid=123,
            command="/usr/local/sbin/mover",
            start_time=start_time,
            name="mover"
        )
        
        assert process.pid == 123
        assert process.command == "/usr/local/sbin/mover"
        assert process.start_time == start_time
        assert process.name == "mover"
        assert process.status == ProcessStatus.UNKNOWN  # default

    def test_process_info_with_all_fields(self) -> None:
        """Test creating ProcessInfo with all fields."""
        start_time = datetime.now()
        
        process = ProcessInfo(
            pid=456,
            command="/bin/bash script.sh",
            start_time=start_time,
            name="bash",
            status=ProcessStatus.RUNNING,
            cpu_percent=25.5,
            memory_mb=128.0,
            working_directory="/home/user",
            user="root"
        )
        
        assert process.pid == 456
        assert process.command == "/bin/bash script.sh"
        assert process.start_time == start_time
        assert process.name == "bash"
        assert process.status == ProcessStatus.RUNNING
        assert process.cpu_percent == 25.5
        assert process.memory_mb == 128.0
        assert process.working_directory == "/home/user"
        assert process.user == "root"

    def test_process_info_optional_fields_default_to_none(self) -> None:
        """Test that optional fields default to None."""
        process = ProcessInfo(
            pid=789,
            command="test",
            start_time=datetime.now(),
            name="test"
        )
        
        assert process.cpu_percent is None
        assert process.memory_mb is None
        assert process.working_directory is None
        assert process.user is None

    def test_process_info_equality(self) -> None:
        """Test ProcessInfo equality comparison."""
        start_time = datetime.now()
        
        process1 = ProcessInfo(
            pid=123,
            command="/usr/local/sbin/mover",
            start_time=start_time,
            name="mover"
        )
        
        process2 = ProcessInfo(
            pid=123,
            command="/usr/local/sbin/mover",
            start_time=start_time,
            name="mover"
        )
        
        process3 = ProcessInfo(
            pid=456,
            command="/usr/local/sbin/mover",
            start_time=start_time,
            name="mover"
        )
        
        assert process1 == process2
        assert process1 != process3

    def test_process_info_hash(self) -> None:
        """Test ProcessInfo hashing."""
        start_time = datetime.now()
        
        process1 = ProcessInfo(
            pid=123,
            command="/usr/local/sbin/mover",
            start_time=start_time,
            name="mover"
        )
        
        process2 = ProcessInfo(
            pid=123,
            command="/usr/local/sbin/mover",
            start_time=start_time,
            name="mover"
        )
        
        # Same objects should have same hash
        assert hash(process1) == hash(process2)
        
        # Should be usable in sets
        process_set = {process1, process2}
        assert len(process_set) == 1

    def test_process_info_string_representation(self) -> None:
        """Test string representation of ProcessInfo."""
        start_time = datetime.now()
        
        process = ProcessInfo(
            pid=123,
            command="/usr/local/sbin/mover",
            start_time=start_time,
            name="mover"
        )
        
        str_repr = str(process)
        assert "ProcessInfo" in str_repr
        assert "pid=123" in str_repr
        assert "name='mover'" in str_repr

    def test_process_info_repr(self) -> None:
        """Test repr of ProcessInfo."""
        start_time = datetime.now()
        
        process = ProcessInfo(
            pid=123,
            command="/usr/local/sbin/mover",
            start_time=start_time,
            name="mover"
        )
        
        repr_str = repr(process)
        assert "ProcessInfo" in repr_str
        assert "pid=123" in repr_str

    def test_process_info_is_mover_process(self) -> None:
        """Test the is_mover_process method."""
        start_time = datetime.now()
        
        # Test mover process
        mover_process = ProcessInfo(
            pid=123,
            command="/usr/local/sbin/mover",
            start_time=start_time,
            name="mover"
        )
        assert mover_process.is_mover_process()
        
        # Test non-mover process  
        other_process = ProcessInfo(
            pid=456,
            command="/bin/bash",
            start_time=start_time,
            name="bash"
        )
        assert not other_process.is_mover_process()
        
        # Test process with mover in command but not name
        script_process = ProcessInfo(
            pid=789,
            command="/usr/local/sbin/mover --dry-run",
            start_time=start_time,
            name="python"
        )
        assert script_process.is_mover_process()

    def test_process_info_age_seconds(self) -> None:
        """Test the age_seconds property."""
        import time
        
        start_time = datetime.now()
        process = ProcessInfo(
            pid=123,
            command="test",
            start_time=start_time,
            name="test"
        )
        
        # Sleep a bit to ensure age > 0
        time.sleep(0.1)
        
        age = process.age_seconds
        assert age > 0
        assert age < 1  # Should be less than 1 second

    def test_process_info_validation(self) -> None:
        """Test ProcessInfo validation."""
        start_time = datetime.now()
        
        # Test invalid PID
        with pytest.raises(ValueError, match="PID must be positive"):
            _ = ProcessInfo(
                pid=-1,
                command="test",
                start_time=start_time,
                name="test"
            )
        
        with pytest.raises(ValueError, match="PID must be positive"):
            _ = ProcessInfo(
                pid=0,
                command="test",
                start_time=start_time,
                name="test"
            )
        
        # Test empty command
        with pytest.raises(ValueError, match="Command cannot be empty"):
            _ = ProcessInfo(
                pid=123,
                command="",
                start_time=start_time,
                name="test"
            )
        
        # Test empty name
        with pytest.raises(ValueError, match="Name cannot be empty"):
            _ = ProcessInfo(
                pid=123,
                command="test",
                start_time=start_time,
                name=""
            )

    def test_process_info_cpu_percent_validation(self) -> None:
        """Test CPU percent validation."""
        start_time = datetime.now()
        
        # Valid CPU percent
        process = ProcessInfo(
            pid=123,
            command="test",
            start_time=start_time,
            name="test",
            cpu_percent=50.0
        )
        assert process.cpu_percent == 50.0
        
        # Invalid CPU percent
        with pytest.raises(ValueError, match="CPU percent must be non-negative"):
            _ = ProcessInfo(
                pid=123,
                command="test",
                start_time=start_time,
                name="test",
                cpu_percent=-1.0
            )

    def test_process_info_memory_mb_validation(self) -> None:
        """Test memory MB validation."""
        start_time = datetime.now()
        
        # Valid memory
        process = ProcessInfo(
            pid=123,
            command="test",
            start_time=start_time,
            name="test",
            memory_mb=256.0
        )
        assert process.memory_mb == 256.0
        
        # Invalid memory
        with pytest.raises(ValueError, match="Memory MB must be non-negative"):
            _ = ProcessInfo(
                pid=123,
                command="test",
                start_time=start_time,
                name="test",
                memory_mb=-1.0
            )