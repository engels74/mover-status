"""Unit tests for PID file monitoring module.

Tests cover:
- PID file reading with various content formats
- PID file state checking (exists/not exists, valid/invalid PID)
- Process validation in process table
- Process executable path retrieval
- Async process validation with timeout
- PID file watching with event detection
- Event emission for creation, modification, deletion
- Polling interval timing
- Error handling for filesystem errors
- Async generator behavior and cancellation
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mover_status.core.monitoring import (
    MoverLifecycleEvent,
    MoverLifecycleStateMachine,
    MoverState,
    PIDFileEvent,
    check_pid_file_state,
    get_process_executable,
    is_process_running,
    monitor_mover_lifecycle,
    read_pid_from_file,
    validate_process_with_timeout,
    watch_pid_file,
)


class TestReadPidFromFile:
    """Test PID file reading with various content and error scenarios."""

    def test_valid_pid_file(self, tmp_path: Path) -> None:
        """Valid PID file should return integer PID."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("12345\n")

        result = read_pid_from_file(pid_file)

        assert result == 12345

    def test_pid_without_newline(self, tmp_path: Path) -> None:
        """PID file without trailing newline should work."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("67890")

        result = read_pid_from_file(pid_file)

        assert result == 67890

    def test_pid_with_extra_whitespace(self, tmp_path: Path) -> None:
        """PID file with extra whitespace should be stripped."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("  54321  \n")

        result = read_pid_from_file(pid_file)

        assert result == 54321

    def test_nonexistent_file_returns_none(self, tmp_path: Path) -> None:
        """Nonexistent PID file should return None."""
        pid_file = tmp_path / "does_not_exist.pid"

        result = read_pid_from_file(pid_file)

        assert result is None

    def test_empty_file_returns_none(self, tmp_path: Path) -> None:
        """Empty PID file should return None."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("")

        result = read_pid_from_file(pid_file)

        assert result is None

    def test_invalid_content_returns_none(self, tmp_path: Path) -> None:
        """PID file with non-numeric content should return None."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("not_a_number")

        result = read_pid_from_file(pid_file)

        assert result is None

    def test_negative_pid_returns_none(self, tmp_path: Path) -> None:
        """PID file with negative number should return None."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("-12345")

        result = read_pid_from_file(pid_file)

        assert result is None

    def test_zero_pid_returns_none(self, tmp_path: Path) -> None:
        """PID file with zero should return None."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("0")

        result = read_pid_from_file(pid_file)

        assert result is None

    def test_floating_point_returns_none(self, tmp_path: Path) -> None:
        """PID file with floating point number should return None."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("123.45")

        result = read_pid_from_file(pid_file)

        assert result is None

    def test_multiple_lines_returns_none(self, tmp_path: Path) -> None:
        """PID file with multiple lines should return None."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("12345\n67890")

        result = read_pid_from_file(pid_file)

        assert result is None

    def test_permission_error_returns_none(self, tmp_path: Path) -> None:
        """PID file with permission error should return None."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("12345")
        _ = pid_file.chmod(0o000)

        try:
            result = read_pid_from_file(pid_file)
            assert result is None
        finally:
            # Restore permissions for cleanup
            _ = pid_file.chmod(0o644)


class TestCheckPidFileState:
    """Test async PID file state checking."""

    @pytest.mark.asyncio
    async def test_file_exists_with_valid_pid(self, tmp_path: Path) -> None:
        """Existing file with valid PID should return (True, pid)."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("12345")

        exists, pid = await check_pid_file_state(pid_file)

        assert exists is True
        assert pid == 12345

    @pytest.mark.asyncio
    async def test_file_does_not_exist(self, tmp_path: Path) -> None:
        """Nonexistent file should return (False, None)."""
        pid_file = tmp_path / "does_not_exist.pid"

        exists, pid = await check_pid_file_state(pid_file)

        assert exists is False
        assert pid is None

    @pytest.mark.asyncio
    async def test_file_exists_with_invalid_content(self, tmp_path: Path) -> None:
        """Existing file with invalid content should return (True, None)."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("invalid")

        exists, pid = await check_pid_file_state(pid_file)

        assert exists is True
        assert pid is None


class TestProcessValidation:
    """Test process validation functions for verifying process existence."""

    def test_current_process_exists_in_table(self) -> None:
        """Current process should exist in process table."""
        current_pid = os.getpid()

        result = is_process_running(current_pid)

        assert result is True

    def test_nonexistent_process_returns_false(self) -> None:
        """Non-existent PID should return False."""
        # Use a very high PID that's unlikely to exist
        fake_pid = 999999

        result = is_process_running(fake_pid)

        assert result is False

    def test_negative_pid_returns_false(self) -> None:
        """Negative PID should return False."""
        result = is_process_running(-1)

        assert result is False

    def test_zero_pid_returns_false(self) -> None:
        """PID 0 should return False."""
        result = is_process_running(0)

        assert result is False

    def test_get_executable_for_current_process(self) -> None:
        """Should retrieve executable path for current process."""
        current_pid = os.getpid()

        exe_path = get_process_executable(current_pid)

        assert exe_path is not None
        assert isinstance(exe_path, str)
        assert len(exe_path) > 0
        # Verify it's a valid path
        assert Path(exe_path).exists()

    def test_get_executable_for_nonexistent_process(self) -> None:
        """Non-existent process should return None."""
        fake_pid = 999999

        exe_path = get_process_executable(fake_pid)

        assert exe_path is None

    def test_get_executable_for_invalid_pid(self) -> None:
        """Invalid PID should return None."""
        exe_path = get_process_executable(-1)

        assert exe_path is None

    @pytest.mark.asyncio
    async def test_validate_process_with_timeout_success(self) -> None:
        """Valid process should validate successfully before timeout."""
        current_pid = os.getpid()

        result = await validate_process_with_timeout(current_pid, timeout=0.1)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_process_with_timeout_nonexistent(self) -> None:
        """Non-existent process should return False."""
        fake_pid = 999999

        result = await validate_process_with_timeout(fake_pid, timeout=0.1)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_process_with_custom_timeout(self) -> None:
        """Should respect custom timeout parameter."""
        current_pid = os.getpid()

        # Test with different timeout values
        result_short = await validate_process_with_timeout(current_pid, timeout=0.05)
        result_long = await validate_process_with_timeout(current_pid, timeout=0.2)

        assert result_short is True
        assert result_long is True


class TestWatchPidFile:
    """Test PID file watching and event emission."""

    @pytest.mark.asyncio
    async def test_file_creation_emits_created_event(self, tmp_path: Path) -> None:
        """Creating PID file should emit created event."""
        pid_file = tmp_path / "mover.pid"

        async def create_file_after_delay() -> None:
            """Create PID file after 0.01 seconds."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text("12345")

        # Start file creation task
        _ = asyncio.create_task(create_file_after_delay())

        # Watch for events
        events: list[PIDFileEvent] = []
        async for event in watch_pid_file(pid_file, check_interval=0.01):
            events.append(event)
            if event.event_type == "created":
                break

        # Verify created event
        assert len(events) == 1
        assert events[0].event_type == "created"
        assert events[0].pid == 12345
        assert isinstance(events[0].timestamp, datetime)

    @pytest.mark.asyncio
    async def test_file_deletion_emits_deleted_event(self, tmp_path: Path) -> None:
        """Deleting PID file should emit deleted event."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("12345")

        async def delete_file_after_delay() -> None:
            """Delete PID file after 0.01 seconds."""
            await asyncio.sleep(0.01)
            _ = pid_file.unlink()

        # Start file deletion task
        _ = asyncio.create_task(delete_file_after_delay())

        # Watch for events
        events: list[PIDFileEvent] = []
        async for event in watch_pid_file(pid_file, check_interval=0.01):
            events.append(event)
            if event.event_type == "deleted":
                break

        # Verify deleted event
        assert len(events) == 1
        assert events[0].event_type == "deleted"
        assert events[0].pid is None
        assert isinstance(events[0].timestamp, datetime)

    @pytest.mark.asyncio
    async def test_file_modification_emits_modified_event(self, tmp_path: Path) -> None:
        """Modifying PID in file should emit modified event."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("12345")

        async def modify_file_after_delay() -> None:
            """Modify PID file after 0.01 seconds."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text("67890")

        # Start file modification task
        _ = asyncio.create_task(modify_file_after_delay())

        # Watch for events
        events: list[PIDFileEvent] = []
        async for event in watch_pid_file(pid_file, check_interval=0.01):
            events.append(event)
            if event.event_type == "modified":
                break

        # Verify modified event
        assert len(events) == 1
        assert events[0].event_type == "modified"
        assert events[0].pid == 67890
        assert isinstance(events[0].timestamp, datetime)

    @pytest.mark.asyncio
    async def test_no_event_when_file_unchanged(self, tmp_path: Path) -> None:
        """No events should be emitted when file is unchanged."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("12345")

        # Watch for events with timeout
        events: list[PIDFileEvent] = []
        try:
            async with asyncio.timeout(0.1):
                async for event in watch_pid_file(pid_file, check_interval=0.01):
                    events.append(event)
        except TimeoutError:
            pass

        # No events should be emitted
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_multiple_events_in_sequence(self, tmp_path: Path) -> None:
        """Multiple state changes should emit multiple events."""
        pid_file = tmp_path / "mover.pid"

        async def simulate_lifecycle() -> None:
            """Simulate mover lifecycle: create, modify, delete."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text("12345")  # Create

            await asyncio.sleep(0.03)
            _ = pid_file.write_text("67890")  # Modify

            await asyncio.sleep(0.03)
            _ = pid_file.unlink()  # Delete

        # Start lifecycle simulation
        _ = asyncio.create_task(simulate_lifecycle())

        # Collect events
        events: list[PIDFileEvent] = []
        async for event in watch_pid_file(pid_file, check_interval=0.01):
            events.append(event)
            if event.event_type == "deleted":
                break

        # Verify event sequence
        assert len(events) == 3

        assert events[0].event_type == "created"
        assert events[0].pid == 12345

        assert events[1].event_type == "modified"
        assert events[1].pid == 67890

        assert events[2].event_type == "deleted"
        assert events[2].pid is None

    @pytest.mark.asyncio
    async def test_polling_interval_respected(self, tmp_path: Path) -> None:
        """Watcher should respect check_interval parameter."""
        pid_file = tmp_path / "mover.pid"
        check_interval = 0.02  # 20 milliseconds

        async def create_file_after_delay() -> None:
            """Create PID file after 0.01 seconds."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text("12345")

        # Start file creation task
        _ = asyncio.create_task(create_file_after_delay())

        # Measure time to detect file creation
        start_time = asyncio.get_event_loop().time()
        elapsed: float = 0.0

        # Watch for events
        async for event in watch_pid_file(pid_file, check_interval=check_interval):
            if event.event_type == "created":
                elapsed = asyncio.get_event_loop().time() - start_time
                break

        # Event should be detected around check_interval time
        # Allow generous margin for test timing variability
        assert elapsed < (check_interval + 0.1)

    @pytest.mark.asyncio
    async def test_watcher_cancellation(self, tmp_path: Path) -> None:
        """Watcher should handle cancellation gracefully."""
        pid_file = tmp_path / "mover.pid"

        async def watch_and_cancel() -> None:
            """Start watching and cancel after 0.01 seconds."""
            watcher = watch_pid_file(pid_file, check_interval=0.01)
            task = asyncio.create_task(anext(watcher))

            await asyncio.sleep(0.01)
            _ = task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected

        # Should complete without error
        await watch_and_cancel()

    @pytest.mark.asyncio
    async def test_invalid_pid_content_emits_event_with_none(self, tmp_path: Path) -> None:
        """File with invalid PID should emit event with pid=None."""
        pid_file = tmp_path / "mover.pid"

        async def create_invalid_file() -> None:
            """Create file with invalid PID content."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text("invalid_pid")

        # Start file creation task
        _ = asyncio.create_task(create_invalid_file())

        # Watch for events
        events: list[PIDFileEvent] = []
        async for event in watch_pid_file(pid_file, check_interval=0.01):
            events.append(event)
            if event.event_type == "created":
                break

        # Verify created event with None PID
        assert len(events) == 1
        assert events[0].event_type == "created"
        assert events[0].pid is None

    @pytest.mark.asyncio
    async def test_file_exists_at_start_no_initial_event(self, tmp_path: Path) -> None:
        """If file exists when watcher starts, no initial event should emit."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("12345")

        # Watch for events with timeout
        events: list[PIDFileEvent] = []
        try:
            async with asyncio.timeout(0.1):
                async for event in watch_pid_file(pid_file, check_interval=0.01):
                    events.append(event)
        except TimeoutError:
            pass

        # No events should be emitted (file unchanged)
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_rapid_changes_detected(self, tmp_path: Path) -> None:
        """Rapid PID changes should be detected."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("100")

        async def rapid_modifications() -> None:
            """Make rapid PID modifications."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text("200")

            await asyncio.sleep(0.03)
            _ = pid_file.write_text("300")

        # Start modifications
        _ = asyncio.create_task(rapid_modifications())

        # Collect events
        events: list[PIDFileEvent] = []
        event_count = 0
        async for event in watch_pid_file(pid_file, check_interval=0.01):
            events.append(event)
            event_count += 1
            if event_count >= 2:  # Expect 2 modification events
                break

        # Verify both modifications detected
        assert len(events) == 2
        assert events[0].event_type == "modified"
        assert events[0].pid == 200
        assert events[1].event_type == "modified"
        assert events[1].pid == 300

    @pytest.mark.asyncio
    async def test_created_event_validates_process(self, tmp_path: Path) -> None:
        """PID file creation should trigger process validation."""
        pid_file = tmp_path / "mover.pid"
        # Use current process PID as a valid test subject
        current_pid = os.getpid()

        async def create_file_with_valid_pid() -> None:
            """Create PID file with current process PID."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text(str(current_pid))

        # Start file creation task
        _ = asyncio.create_task(create_file_with_valid_pid())

        # Watch for events
        events: list[PIDFileEvent] = []
        async for event in watch_pid_file(pid_file, check_interval=0.01):
            events.append(event)
            if event.event_type == "created":
                break

        # Verify event was emitted with correct PID
        assert len(events) == 1
        assert events[0].event_type == "created"
        assert events[0].pid == current_pid
        # Process should have been validated (logged internally)
        # The event is emitted regardless of validation outcome


class TestPIDFileEvent:
    """Test PIDFileEvent dataclass properties."""

    def test_event_is_frozen(self) -> None:
        """PIDFileEvent should be immutable (frozen)."""
        event = PIDFileEvent(
            event_type="created",
            pid=12345,
            timestamp=datetime.now(),
        )

        with pytest.raises(AttributeError):
            event.pid = 67890  # pyright: ignore[reportAttributeAccessIssue]  # Testing immutability

    def test_event_has_slots(self) -> None:
        """PIDFileEvent should use __slots__ for memory efficiency."""
        event = PIDFileEvent(
            event_type="created",
            pid=12345,
            timestamp=datetime.now(),
        )

        assert hasattr(event, "__slots__")
        assert not hasattr(event, "__dict__")

    def test_event_type_literal(self) -> None:
        """event_type should accept literal values."""
        created = PIDFileEvent(
            event_type="created",
            pid=12345,
            timestamp=datetime.now(),
        )
        assert created.event_type == "created"

        modified = PIDFileEvent(
            event_type="modified",
            pid=67890,
            timestamp=datetime.now(),
        )
        assert modified.event_type == "modified"

        deleted = PIDFileEvent(
            event_type="deleted",
            pid=None,
            timestamp=datetime.now(),
        )
        assert deleted.event_type == "deleted"


class TestMoverState:
    """Test MoverState enum properties and values."""

    def test_all_states_exist(self) -> None:
        """All expected lifecycle states should exist."""
        assert hasattr(MoverState, "WAITING")
        assert hasattr(MoverState, "STARTED")
        assert hasattr(MoverState, "MONITORING")
        assert hasattr(MoverState, "COMPLETED")

    def test_state_values(self) -> None:
        """State values should be lowercase strings."""
        assert MoverState.WAITING.value == "waiting"
        assert MoverState.STARTED.value == "started"
        assert MoverState.MONITORING.value == "monitoring"
        assert MoverState.COMPLETED.value == "completed"

    def test_state_equality(self) -> None:
        """States should be comparable."""
        state1 = MoverState.WAITING
        state2 = MoverState.WAITING
        state3 = MoverState.STARTED

        assert state1 == state2
        assert state1 != state3

    def test_state_is_enum(self) -> None:
        """MoverState should be an Enum."""
        from enum import Enum

        assert issubclass(MoverState, Enum)


class TestMoverLifecycleEvent:
    """Test MoverLifecycleEvent dataclass properties."""

    def test_event_is_frozen(self) -> None:
        """MoverLifecycleEvent should be immutable (frozen)."""
        event = MoverLifecycleEvent(
            previous_state=MoverState.WAITING,
            new_state=MoverState.STARTED,
            pid=12345,
            timestamp=datetime.now(),
            message="Test message",
        )

        with pytest.raises(AttributeError):
            event.pid = 67890  # pyright: ignore[reportAttributeAccessIssue]  # Testing immutability

    def test_event_has_slots(self) -> None:
        """MoverLifecycleEvent should use __slots__ for memory efficiency."""
        event = MoverLifecycleEvent(
            previous_state=MoverState.WAITING,
            new_state=MoverState.STARTED,
            pid=12345,
            timestamp=datetime.now(),
            message="Test message",
        )

        assert hasattr(event, "__slots__")
        assert not hasattr(event, "__dict__")

    def test_event_with_all_fields(self) -> None:
        """Event should accept all required fields."""
        timestamp = datetime.now()
        event = MoverLifecycleEvent(
            previous_state=MoverState.WAITING,
            new_state=MoverState.STARTED,
            pid=12345,
            timestamp=timestamp,
            message="Mover process started",
        )

        assert event.previous_state == MoverState.WAITING
        assert event.new_state == MoverState.STARTED
        assert event.pid == 12345
        assert event.timestamp == timestamp
        assert event.message == "Mover process started"

    def test_event_with_none_pid(self) -> None:
        """Event should accept None for PID."""
        event = MoverLifecycleEvent(
            previous_state=MoverState.COMPLETED,
            new_state=MoverState.WAITING,
            pid=None,
            timestamp=datetime.now(),
            message="Ready for next cycle",
        )

        assert event.pid is None


class TestMoverLifecycleStateMachine:
    """Test lifecycle state machine transitions and validation."""

    def test_initial_state_is_waiting(self) -> None:
        """State machine should initialize in WAITING state."""
        sm = MoverLifecycleStateMachine()

        assert sm.current_state == MoverState.WAITING
        assert sm.current_pid is None

    def test_transition_to_started_from_waiting(self) -> None:
        """Should successfully transition from WAITING to STARTED."""
        sm = MoverLifecycleStateMachine()

        event = sm.transition_to_started(12345)

        assert sm.current_state == MoverState.STARTED
        assert sm.current_pid == 12345
        assert event.previous_state == MoverState.WAITING
        assert event.new_state == MoverState.STARTED
        assert event.pid == 12345
        assert "started" in event.message.lower()

    def test_transition_to_started_from_completed(self) -> None:
        """Should allow STARTED transition from COMPLETED (new cycle)."""
        sm = MoverLifecycleStateMachine()
        _ = sm.transition_to_started(100)
        _ = sm.transition_to_completed()

        # Now in COMPLETED, should allow new START
        event = sm.transition_to_started(200)

        assert sm.current_state == MoverState.STARTED
        assert sm.current_pid == 200
        assert event.previous_state == MoverState.COMPLETED
        assert event.new_state == MoverState.STARTED

    def test_transition_to_started_from_invalid_state_raises(self) -> None:
        """Should raise ValueError when transitioning to STARTED from invalid states."""
        sm = MoverLifecycleStateMachine()
        _ = sm.transition_to_started(100)

        # Already in STARTED - cannot transition to STARTED again
        with pytest.raises(ValueError, match="Invalid transition"):
            _ = sm.transition_to_started(200)

    def test_transition_to_monitoring_from_started(self) -> None:
        """Should successfully transition from STARTED to MONITORING."""
        sm = MoverLifecycleStateMachine()
        _ = sm.transition_to_started(12345)

        event = sm.transition_to_monitoring()

        assert sm.current_state == MoverState.MONITORING
        assert sm.current_pid == 12345  # PID preserved
        assert event.previous_state == MoverState.STARTED
        assert event.new_state == MoverState.MONITORING
        assert event.pid == 12345
        assert "monitoring" in event.message.lower()

    def test_transition_to_monitoring_from_invalid_state_raises(self) -> None:
        """Should raise ValueError when transitioning to MONITORING from invalid states."""
        sm = MoverLifecycleStateMachine()

        # Cannot go from WAITING to MONITORING directly
        with pytest.raises(ValueError, match="Invalid transition"):
            _ = sm.transition_to_monitoring()

    def test_transition_to_completed_from_started(self) -> None:
        """Should successfully transition from STARTED to COMPLETED."""
        sm = MoverLifecycleStateMachine()
        _ = sm.transition_to_started(12345)

        event = sm.transition_to_completed(reason="Test completion")

        assert sm.current_state == MoverState.COMPLETED
        assert sm.current_pid == 12345  # PID preserved until reset
        assert event.previous_state == MoverState.STARTED
        assert event.new_state == MoverState.COMPLETED
        assert event.pid == 12345
        assert "Test completion" in event.message

    def test_transition_to_completed_from_monitoring(self) -> None:
        """Should successfully transition from MONITORING to COMPLETED."""
        sm = MoverLifecycleStateMachine()
        _ = sm.transition_to_started(12345)
        _ = sm.transition_to_monitoring()

        event = sm.transition_to_completed()

        assert sm.current_state == MoverState.COMPLETED
        assert event.previous_state == MoverState.MONITORING
        assert event.new_state == MoverState.COMPLETED
        assert "terminated normally" in event.message.lower()

    def test_transition_to_completed_from_waiting_raises(self) -> None:
        """Should raise ValueError when transitioning to COMPLETED from WAITING."""
        sm = MoverLifecycleStateMachine()

        with pytest.raises(ValueError, match="Invalid transition"):
            _ = sm.transition_to_completed()

    def test_transition_to_completed_from_completed_raises(self) -> None:
        """Should raise ValueError when already in COMPLETED state."""
        sm = MoverLifecycleStateMachine()
        _ = sm.transition_to_started(100)
        _ = sm.transition_to_completed()

        with pytest.raises(ValueError, match="Invalid transition"):
            _ = sm.transition_to_completed()

    def test_reset_from_completed(self) -> None:
        """Should successfully reset from COMPLETED to WAITING."""
        sm = MoverLifecycleStateMachine()
        _ = sm.transition_to_started(12345)
        _ = sm.transition_to_completed()

        event = sm.reset()

        assert sm.current_state == MoverState.WAITING
        assert sm.current_pid is None
        assert event.previous_state == MoverState.COMPLETED
        assert event.new_state == MoverState.WAITING
        assert event.pid is None
        assert "ready" in event.message.lower()

    def test_reset_from_invalid_state_raises(self) -> None:
        """Should raise ValueError when resetting from non-COMPLETED state."""
        sm = MoverLifecycleStateMachine()

        # Cannot reset from WAITING
        with pytest.raises(ValueError, match="Cannot reset"):
            _ = sm.reset()

        # Cannot reset from STARTED
        _ = sm.transition_to_started(100)
        with pytest.raises(ValueError, match="Cannot reset"):
            _ = sm.reset()

    def test_full_lifecycle_sequence(self) -> None:
        """Should successfully complete full lifecycle: WAITING → STARTED → MONITORING → COMPLETED → WAITING."""
        sm = MoverLifecycleStateMachine()

        # Initial state
        assert sm.current_state == MoverState.WAITING

        # Start
        _ = sm.transition_to_started(12345)
        assert sm.current_state == MoverState.STARTED

        # Monitor
        _ = sm.transition_to_monitoring()
        assert sm.current_state == MoverState.MONITORING

        # Complete
        _ = sm.transition_to_completed()
        assert sm.current_state == MoverState.COMPLETED

        # Reset
        _ = sm.reset()
        assert sm.current_state == MoverState.WAITING
        assert sm.current_pid is None

    def test_edge_case_unexpected_termination_from_started(self) -> None:
        """Should handle unexpected termination from STARTED state."""
        sm = MoverLifecycleStateMachine()
        _ = sm.transition_to_started(12345)

        # Process crashes before monitoring begins
        event = sm.transition_to_completed(reason="Process crashed unexpectedly")

        assert sm.current_state == MoverState.COMPLETED
        assert "crashed unexpectedly" in event.message

    def test_custom_completion_reason(self) -> None:
        """Should accept custom completion reason."""
        sm = MoverLifecycleStateMachine()
        _ = sm.transition_to_started(12345)

        event = sm.transition_to_completed(reason="PID file deleted")

        assert "PID file deleted" in event.message

    def test_multiple_cycles(self) -> None:
        """Should support multiple mover cycles."""
        sm = MoverLifecycleStateMachine()

        # Cycle 1
        _ = sm.transition_to_started(100)
        _ = sm.transition_to_monitoring()
        _ = sm.transition_to_completed()
        _ = sm.reset()

        # Cycle 2
        _ = sm.transition_to_started(200)
        _ = sm.transition_to_monitoring()
        _ = sm.transition_to_completed()
        _ = sm.reset()

        # Cycle 3
        _ = sm.transition_to_started(300)

        assert sm.current_state == MoverState.STARTED
        assert sm.current_pid == 300


class TestMonitorMoverLifecycle:
    """Test high-level lifecycle monitoring integration."""

    @pytest.mark.asyncio
    async def test_lifecycle_detects_process_start(self, tmp_path: Path) -> None:
        """Should detect process start and transition to STARTED."""
        pid_file = tmp_path / "mover.pid"
        current_pid = os.getpid()  # Use valid PID

        async def create_pid_file() -> None:
            """Create PID file after delay."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text(str(current_pid))

        # Start file creation
        _ = asyncio.create_task(create_pid_file())

        # Monitor lifecycle
        events: list[MoverLifecycleEvent] = []
        async for event in monitor_mover_lifecycle(pid_file, check_interval=0.01):
            events.append(event)
            if event.new_state == MoverState.STARTED:
                break

        # Verify STARTED event
        assert len(events) == 1
        assert events[0].new_state == MoverState.STARTED
        assert events[0].previous_state == MoverState.WAITING
        assert events[0].pid == current_pid

    @pytest.mark.asyncio
    async def test_lifecycle_detects_process_termination(self, tmp_path: Path) -> None:
        """Should detect process termination and transition to COMPLETED."""
        pid_file = tmp_path / "mover.pid"
        current_pid = os.getpid()
        _ = pid_file.write_text(str(current_pid))

        async def delete_pid_file() -> None:
            """Delete PID file after delay."""
            await asyncio.sleep(0.01)
            _ = pid_file.unlink()

        # Start file deletion
        _ = asyncio.create_task(delete_pid_file())

        # Monitor lifecycle
        events: list[MoverLifecycleEvent] = []
        async for event in monitor_mover_lifecycle(pid_file, check_interval=0.01):
            events.append(event)
            if event.new_state == MoverState.WAITING:
                break

        # Should get STARTED (file exists at start), COMPLETED, and WAITING (auto-reset)
        assert len(events) == 3
        assert events[0].new_state == MoverState.STARTED
        assert events[0].previous_state == MoverState.WAITING
        assert events[0].pid == current_pid
        assert events[1].new_state == MoverState.COMPLETED
        assert events[1].previous_state == MoverState.STARTED
        assert events[2].new_state == MoverState.WAITING
        assert events[2].previous_state == MoverState.COMPLETED

    @pytest.mark.asyncio
    async def test_lifecycle_handles_pid_change(self, tmp_path: Path) -> None:
        """Should handle PID file modification (process restart)."""
        pid_file = tmp_path / "mover.pid"
        current_pid = os.getpid()
        _ = pid_file.write_text(str(current_pid))

        async def change_pid() -> None:
            """Modify PID file after delay."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text(str(current_pid + 1))

        # Start PID change (note: new PID won't be running, so won't start)
        _ = asyncio.create_task(change_pid())

        # Monitor lifecycle
        events: list[MoverLifecycleEvent] = []
        try:
            async with asyncio.timeout(0.1):
                async for event in monitor_mover_lifecycle(pid_file, check_interval=0.01):
                    events.append(event)
                    # Wait for COMPLETED and WAITING from PID change
                    if len(events) >= 2 and event.new_state == MoverState.WAITING:
                        break
        except TimeoutError:
            pass

        # Should complete previous process and reset
        assert len(events) >= 2
        # Find COMPLETED event
        completed_events = [e for e in events if e.new_state == MoverState.COMPLETED]
        assert len(completed_events) > 0
        assert "changed unexpectedly" in completed_events[0].message.lower()

    @pytest.mark.asyncio
    async def test_lifecycle_handles_invalid_pid_gracefully(self, tmp_path: Path) -> None:
        """Should handle PID file with invalid content gracefully."""
        pid_file = tmp_path / "mover.pid"

        async def create_invalid_pid_file() -> None:
            """Create PID file with invalid content."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text("invalid_pid")

        # Start file creation
        _ = asyncio.create_task(create_invalid_pid_file())

        # Monitor lifecycle
        events: list[MoverLifecycleEvent] = []
        try:
            async with asyncio.timeout(0.1):
                async for event in monitor_mover_lifecycle(pid_file, check_interval=0.01):
                    events.append(event)
        except TimeoutError:
            pass

        # Should not emit any lifecycle events (PID invalid, process not validated)
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_lifecycle_full_cycle(self, tmp_path: Path) -> None:
        """Should handle complete lifecycle: start → complete → reset."""
        pid_file = tmp_path / "mover.pid"
        current_pid = os.getpid()

        async def simulate_mover_cycle() -> None:
            """Simulate complete mover cycle."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text(str(current_pid))  # Start

            await asyncio.sleep(0.03)
            _ = pid_file.unlink()  # Complete

        # Start simulation
        _ = asyncio.create_task(simulate_mover_cycle())

        # Monitor lifecycle
        events: list[MoverLifecycleEvent] = []
        async for event in monitor_mover_lifecycle(pid_file, check_interval=0.01):
            events.append(event)
            if event.new_state == MoverState.WAITING and len(events) > 1:
                break

        # Verify complete cycle: STARTED → COMPLETED → WAITING
        assert len(events) == 3
        assert events[0].new_state == MoverState.STARTED
        assert events[1].new_state == MoverState.COMPLETED
        assert events[2].new_state == MoverState.WAITING

    @pytest.mark.asyncio
    async def test_lifecycle_respects_check_interval(self, tmp_path: Path) -> None:
        """Should respect check_interval parameter."""
        pid_file = tmp_path / "mover.pid"
        current_pid = os.getpid()
        check_interval = 0.02

        async def create_pid_file() -> None:
            """Create PID file after delay."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text(str(current_pid))

        # Start file creation
        _ = asyncio.create_task(create_pid_file())

        # Monitor lifecycle with custom interval
        start_time = asyncio.get_event_loop().time()
        events: list[MoverLifecycleEvent] = []
        async for event in monitor_mover_lifecycle(pid_file, check_interval=check_interval):
            events.append(event)
            if event.new_state == MoverState.STARTED:
                break

        elapsed = asyncio.get_event_loop().time() - start_time

        # Should detect within check_interval time (with margin)
        assert elapsed < (check_interval + 0.1)

    @pytest.mark.asyncio
    async def test_lifecycle_cancellation(self, tmp_path: Path) -> None:
        """Should handle cancellation gracefully."""
        pid_file = tmp_path / "mover.pid"

        async def monitor_and_cancel() -> None:
            """Start monitoring and cancel."""
            monitor = monitor_mover_lifecycle(pid_file, check_interval=0.01)
            task = asyncio.create_task(anext(monitor))

            await asyncio.sleep(0.01)
            _ = task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected

        # Should complete without error
        await monitor_and_cancel()


class TestPIDFileWatchingWithMocks:
    """Test PID file watching with mocked filesystem to simulate errors."""

    @pytest.mark.asyncio
    async def test_watch_handles_file_deletion_race_condition(self, tmp_path: Path) -> None:
        """Should handle file deleted between exists check and read."""
        pid_file = tmp_path / "mover.pid"
        _ = pid_file.write_text("12345")

        # Simulate race: file exists returns True, but read fails
        original_read = read_pid_from_file
        exists_call_count = 0

        def mock_exists(_: Path) -> bool:
            """Mock exists that returns True."""
            nonlocal exists_call_count
            exists_call_count += 1
            return exists_call_count == 1

        def mock_read(path: Path) -> int | None:
            """Mock read that returns None (file disappeared)."""
            if exists_call_count == 1:
                return None  # File disappeared between exists and read
            return original_read(path)

        with (
            patch.object(Path, "exists", mock_exists),
            patch("mover_status.core.monitoring.read_pid_from_file", side_effect=mock_read),
        ):
            events: list[PIDFileEvent] = []
            try:
                async with asyncio.timeout(0.1):
                    async for event in watch_pid_file(pid_file, check_interval=0.01):
                        events.append(event)
            except TimeoutError:
                pass

        # Should handle race condition gracefully
        assert exists_call_count >= 1


class TestProcessValidationWithMocks:
    """Test process validation with mocked /proc filesystem."""

    def test_is_process_running_with_mock_proc(self) -> None:
        """Should check /proc/{pid} directory existence."""
        test_pid = 99999

        with patch.object(Path, "exists", return_value=True):
            result = is_process_running(test_pid)
            assert result is True

        with patch.object(Path, "exists", return_value=False):
            result = is_process_running(test_pid)
            assert result is False

    def test_process_disappears_during_validation(self) -> None:
        """Should handle process disappearing between checks."""
        test_pid = 99999

        # First check: exists, second check: gone
        call_count = 0

        def mock_exists_then_gone(_: Path) -> bool:
            """Mock that returns True then False."""
            nonlocal call_count
            call_count += 1
            return call_count == 1

        with patch.object(Path, "exists", mock_exists_then_gone):
            # First call
            result1 = is_process_running(test_pid)
            assert result1 is True

            # Second call
            result2 = is_process_running(test_pid)
            assert result2 is False


class TestStateMachineProperties:
    """Property-based tests for state machine invariants using Hypothesis."""

    @given(pid=st.integers(min_value=1, max_value=2147483647))
    def test_pid_always_positive_in_started_state(self, pid: int) -> None:
        """State machine should only accept positive PIDs for STARTED state."""
        sm = MoverLifecycleStateMachine()
        event = sm.transition_to_started(pid)

        assert sm.current_pid == pid
        assert sm.current_pid is not None
        assert sm.current_pid > 0
        assert event.pid == pid

    @given(
        pid1=st.integers(min_value=1, max_value=100000),
        pid2=st.integers(min_value=1, max_value=100000),
    )
    def test_multiple_cycles_preserve_state_invariants(self, pid1: int, pid2: int) -> None:
        """Multiple cycles should maintain state machine invariants."""
        sm = MoverLifecycleStateMachine()

        # Cycle 1
        _ = sm.transition_to_started(pid1)
        assert sm.current_state == MoverState.STARTED
        assert sm.current_pid == pid1

        _ = sm.transition_to_monitoring()
        assert sm.current_state == MoverState.MONITORING
        assert sm.current_pid == pid1

        _ = sm.transition_to_completed()
        assert sm.current_state == MoverState.COMPLETED
        assert sm.current_pid == pid1

        _ = sm.reset()
        assert sm.current_state == MoverState.WAITING
        assert sm.current_pid is None

        # Cycle 2
        _ = sm.transition_to_started(pid2)
        assert sm.current_state == MoverState.STARTED
        assert sm.current_pid == pid2

    @given(reason=st.text(min_size=1, max_size=200))
    def test_completion_reason_preserved_in_message(self, reason: str) -> None:
        """Completion reason should be preserved in event message."""
        sm = MoverLifecycleStateMachine()
        _ = sm.transition_to_started(12345)

        event = sm.transition_to_completed(reason=reason)

        assert reason in event.message

    def test_state_transitions_are_ordered(self) -> None:
        """State transitions must follow specific order."""
        sm = MoverLifecycleStateMachine()

        # Valid sequence
        valid_transitions = [
            (MoverState.WAITING, lambda: sm.transition_to_started(100)),
            (MoverState.STARTED, lambda: sm.transition_to_monitoring()),
            (MoverState.MONITORING, lambda: sm.transition_to_completed()),
            (MoverState.COMPLETED, lambda: sm.reset()),
        ]

        for expected_prev_state, transition_fn in valid_transitions:
            assert sm.current_state == expected_prev_state
            _ = transition_fn()

    def test_no_invalid_state_transitions_possible(self) -> None:
        """Invalid state transitions should always raise ValueError."""
        # From WAITING
        sm = MoverLifecycleStateMachine()
        with pytest.raises(ValueError):
            _ = sm.transition_to_monitoring()
        with pytest.raises(ValueError):
            _ = sm.transition_to_completed()
        with pytest.raises(ValueError):
            _ = sm.reset()

        # From STARTED
        _ = sm.transition_to_started(100)
        with pytest.raises(ValueError):
            _ = sm.transition_to_started(200)  # Already started

        # From MONITORING
        _ = sm.transition_to_monitoring()
        with pytest.raises(ValueError):
            _ = sm.transition_to_started(300)
        with pytest.raises(ValueError):
            _ = sm.transition_to_monitoring()  # Already monitoring

        # From COMPLETED
        _ = sm.transition_to_completed()
        with pytest.raises(ValueError):
            _ = sm.transition_to_monitoring()
        with pytest.raises(ValueError):
            _ = sm.transition_to_completed()  # Already completed

    @given(st.lists(st.integers(min_value=1, max_value=100000), min_size=1, max_size=10))
    def test_event_timestamps_are_monotonic(self, pids: list[int]) -> None:
        """Event timestamps should be monotonically increasing."""
        sm = MoverLifecycleStateMachine()
        events: list[MoverLifecycleEvent] = []

        for pid in pids:
            # Complete cycle for each PID
            events.append(sm.transition_to_started(pid))
            events.append(sm.transition_to_monitoring())
            events.append(sm.transition_to_completed())
            events.append(sm.reset())

        # Verify timestamps are monotonic
        for i in range(len(events) - 1):
            assert events[i].timestamp <= events[i + 1].timestamp


class TestEdgeCasesParametrized:
    """Parametrized tests for edge cases and boundary conditions."""

    @pytest.mark.parametrize(
        "invalid_pid_content",
        [
            "",
            "   ",
            "not_a_number",
            "-1",
            "0",
            "123.456",
            "1.0",
            "1e5",
            "0x123",
            "12345\n67890",
            "12345 67890",
            "\n",
            "\t",
            "NaN",
            "Infinity",
            "None",
            "null",
            "true",
            "false",
            "{}",
            "[]",
        ],
    )
    def test_read_pid_handles_invalid_content(self, tmp_path: Path, invalid_pid_content: str) -> None:
        """Should return None for various invalid PID content formats."""
        pid_file = tmp_path / "test.pid"
        _ = pid_file.write_text(invalid_pid_content)

        result = read_pid_from_file(pid_file)

        assert result is None

    @pytest.mark.parametrize(
        "valid_pid,expected",
        [
            ("1", 1),  # Minimum valid PID
            ("99999", 99999),
            ("2147483647", 2147483647),  # Max 32-bit signed int
            ("  12345  ", 12345),  # Whitespace
            ("12345\n", 12345),  # Trailing newline
            ("\n12345\n", 12345),  # Leading and trailing newline
            ("\t12345\t", 12345),  # Tabs
        ],
    )
    def test_read_pid_handles_valid_content(self, tmp_path: Path, valid_pid: str, expected: int) -> None:
        """Should correctly parse various valid PID formats."""
        pid_file = tmp_path / "test.pid"
        _ = pid_file.write_text(valid_pid)

        result = read_pid_from_file(pid_file)

        assert result == expected

    @pytest.mark.parametrize(
        "invalid_pid",
        [
            -1,
            0,
            -999999,
            -2147483648,  # Min 32-bit signed int
        ],
    )
    def test_process_validation_rejects_invalid_pids(self, invalid_pid: int) -> None:
        """Should return False for invalid PID values."""
        result = is_process_running(invalid_pid)
        assert result is False

        exe = get_process_executable(invalid_pid)
        assert exe is None

    @pytest.mark.parametrize(
        "state_sequence,should_succeed",
        [
            # Valid sequences
            ([("start", 100), ("monitor", None), ("complete", None), ("reset", None)], True),
            ([("start", 100), ("complete", None), ("reset", None)], True),  # Skip monitor
            ([("start", 100)], True),  # Partial sequence
            # Invalid sequences
            ([("monitor", None)], False),  # Can't monitor from WAITING
            ([("complete", None)], False),  # Can't complete from WAITING
            ([("reset", None)], False),  # Can't reset from WAITING
            ([("start", 100), ("start", 200)], False),  # Double start
        ],
    )
    def test_state_machine_sequence_validation(
        self,
        state_sequence: list[tuple[str, int | None]],
        should_succeed: bool,
    ) -> None:
        """Should validate state transition sequences."""
        sm = MoverLifecycleStateMachine()
        exception_raised = False

        try:
            for action, pid in state_sequence:
                if action == "start":
                    assert pid is not None
                    _ = sm.transition_to_started(pid)
                elif action == "monitor":
                    _ = sm.transition_to_monitoring()
                elif action == "complete":
                    _ = sm.transition_to_completed()
                elif action == "reset":
                    _ = sm.reset()
        except ValueError:
            exception_raised = True

        if should_succeed:
            assert not exception_raised
        else:
            assert exception_raised

    @pytest.mark.asyncio
    @pytest.mark.parametrize("check_interval", [0.01, 0.05])
    async def test_watch_respects_different_intervals(self, tmp_path: Path, check_interval: float) -> None:
        """Should respect various check interval values."""
        pid_file = tmp_path / "mover.pid"
        current_pid = os.getpid()

        async def create_file_after_delay() -> None:
            """Create PID file after short delay."""
            await asyncio.sleep(0.005)
            _ = pid_file.write_text(str(current_pid))

        _ = asyncio.create_task(create_file_after_delay())

        start_time = asyncio.get_event_loop().time()
        events: list[PIDFileEvent] = []
        async for event in watch_pid_file(pid_file, check_interval=check_interval):
            events.append(event)
            if event.event_type == "created":
                break

        elapsed = asyncio.get_event_loop().time() - start_time

        # Should detect within interval (with generous margin for test timing)
        assert elapsed < (check_interval + 0.1)
        assert len(events) == 1

    @pytest.mark.parametrize(
        "completion_reason",
        [
            "Process terminated normally",
            "PID file deleted",
            "Process crashed unexpectedly",
            "Signal received",
            "Timeout exceeded",
            pytest.param("", id="empty-reason"),
            pytest.param("A" * 500, id="very-long-reason-500chars"),
        ],
    )
    def test_completion_with_various_reasons(self, completion_reason: str) -> None:
        """Should handle various completion reasons."""
        sm = MoverLifecycleStateMachine()
        _ = sm.transition_to_started(12345)

        event = sm.transition_to_completed(reason=completion_reason)

        assert event.new_state == MoverState.COMPLETED
        if completion_reason:
            assert completion_reason in event.message


class TestLifecycleIntegration:
    """Integration tests for multi-cycle monitoring scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_complete_cycles(self, tmp_path: Path) -> None:
        """Should handle multiple complete mover cycles."""
        pid_file = tmp_path / "mover.pid"
        current_pid = os.getpid()

        async def simulate_three_cycles() -> None:
            """Simulate 3 complete mover cycles."""
            for _cycle in range(3):
                await asyncio.sleep(0.01)
                _ = pid_file.write_text(str(current_pid))
                await asyncio.sleep(0.01)
                _ = pid_file.unlink()
                await asyncio.sleep(0.01)

        _ = asyncio.create_task(simulate_three_cycles())

        events: list[MoverLifecycleEvent] = []
        cycle_count = 0

        async for event in monitor_mover_lifecycle(pid_file, check_interval=0.01):
            events.append(event)
            if event.new_state == MoverState.WAITING and len(events) > 1:
                cycle_count += 1
                if cycle_count >= 3:
                    break

        # Should have 3 complete cycles: STARTED → COMPLETED → WAITING each
        assert cycle_count == 3
        assert len(events) >= 9  # At least 3 events per cycle

    @pytest.mark.asyncio
    async def test_resource_cleanup_after_cancellation(self, tmp_path: Path) -> None:
        """Should clean up resources when monitoring is cancelled."""
        pid_file = tmp_path / "mover.pid"

        async def monitor_with_cancellation() -> None:
            """Start monitoring and cancel after delay."""
            monitor = monitor_mover_lifecycle(pid_file, check_interval=0.01)
            task = asyncio.create_task(anext(monitor))

            await asyncio.sleep(0.02)
            _ = task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected

        # Should complete without hanging or leaking resources
        await asyncio.wait_for(monitor_with_cancellation(), timeout=0.5)

    @pytest.mark.asyncio
    async def test_recovery_from_invalid_pid_then_valid(self, tmp_path: Path) -> None:
        """Should recover from invalid PID and detect valid one later."""
        pid_file = tmp_path / "mover.pid"
        current_pid = os.getpid()

        async def simulate_invalid_then_valid() -> None:
            """Create invalid PID, then valid PID."""
            await asyncio.sleep(0.01)
            _ = pid_file.write_text("invalid")
            await asyncio.sleep(0.01)
            _ = pid_file.unlink()
            await asyncio.sleep(0.01)
            _ = pid_file.write_text(str(current_pid))

        _ = asyncio.create_task(simulate_invalid_then_valid())

        events: list[MoverLifecycleEvent] = []
        async for event in monitor_mover_lifecycle(pid_file, check_interval=0.01):
            events.append(event)
            if event.new_state == MoverState.STARTED:
                break

        # Should eventually detect valid PID
        assert len(events) >= 1
        assert events[-1].new_state == MoverState.STARTED
        assert events[-1].pid == current_pid

    @pytest.mark.asyncio
    async def test_rapid_sequential_state_changes(self, tmp_path: Path) -> None:
        """Should handle rapid state changes correctly."""
        pid_file = tmp_path / "mover.pid"
        current_pid = os.getpid()

        async def rapid_changes() -> None:
            """Rapidly create and delete PID file."""
            for _ in range(3):
                _ = pid_file.write_text(str(current_pid))
                await asyncio.sleep(0.01)
                _ = pid_file.unlink()
                await asyncio.sleep(0.01)

        _ = asyncio.create_task(rapid_changes())

        events: list[MoverLifecycleEvent] = []
        try:
            async with asyncio.timeout(0.5):
                async for event in monitor_mover_lifecycle(pid_file, check_interval=0.01):
                    events.append(event)
        except TimeoutError:
            pass

        # Should detect multiple cycles
        started_events = [e for e in events if e.new_state == MoverState.STARTED]
        assert len(started_events) >= 1

    @pytest.mark.asyncio
    async def test_state_machine_integration_with_watcher(self, tmp_path: Path) -> None:
        """Should integrate state machine with PID file watcher correctly."""
        pid_file = tmp_path / "mover.pid"
        current_pid = os.getpid()
        _ = pid_file.write_text(str(current_pid))

        # Track all state transitions
        states_seen: list[MoverState] = []

        async def delete_after_delay() -> None:
            """Delete PID file after delay."""
            await asyncio.sleep(0.01)
            _ = pid_file.unlink()

        _ = asyncio.create_task(delete_after_delay())

        async for event in monitor_mover_lifecycle(pid_file, check_interval=0.01):
            states_seen.append(event.new_state)
            if event.new_state == MoverState.WAITING and len(states_seen) > 1:
                break

        # Should see expected state progression
        assert MoverState.STARTED in states_seen
        assert MoverState.COMPLETED in states_seen
        assert MoverState.WAITING in states_seen

    @pytest.mark.asyncio
    async def test_concurrent_monitoring_tasks(self, tmp_path: Path) -> None:
        """Should handle multiple concurrent monitoring tasks on different PID files."""
        pid_file1 = tmp_path / "mover1.pid"
        pid_file2 = tmp_path / "mover2.pid"
        current_pid = os.getpid()

        async def monitor_file(pid_file: Path) -> list[MoverLifecycleEvent]:
            """Monitor a PID file and collect events."""
            events: list[MoverLifecycleEvent] = []
            try:
                async with asyncio.timeout(0.3):
                    async for event in monitor_mover_lifecycle(pid_file, check_interval=0.01):
                        events.append(event)
                        if event.new_state == MoverState.STARTED:
                            break
            except TimeoutError:
                pass
            return events

        async def create_pid_files() -> None:
            """Create both PID files with delays."""
            await asyncio.sleep(0.01)
            _ = pid_file1.write_text(str(current_pid))
            await asyncio.sleep(0.01)
            _ = pid_file2.write_text(str(current_pid))

        _ = asyncio.create_task(create_pid_files())

        # Monitor both files concurrently
        results = await asyncio.gather(
            monitor_file(pid_file1),
            monitor_file(pid_file2),
        )

        # Both monitors should detect their respective files
        assert len(results[0]) >= 1
        assert len(results[1]) >= 1
