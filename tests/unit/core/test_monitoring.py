"""Unit tests for PID file monitoring module.

Tests cover:
- PID file reading with various content formats
- PID file state checking (exists/not exists, valid/invalid PID)
- PID file watching with event detection
- Event emission for creation, modification, deletion
- Polling interval timing
- Error handling for filesystem errors
- Async generator behavior and cancellation
"""

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from mover_status.core.monitoring import (
    PIDFileEvent,
    check_pid_file_state,
    read_pid_from_file,
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


class TestWatchPidFile:
    """Test PID file watching and event emission."""

    @pytest.mark.asyncio
    async def test_file_creation_emits_created_event(self, tmp_path: Path) -> None:
        """Creating PID file should emit created event."""
        pid_file = tmp_path / "mover.pid"

        async def create_file_after_delay() -> None:
            """Create PID file after 0.5 seconds."""
            await asyncio.sleep(0.5)
            _ = pid_file.write_text("12345")

        # Start file creation task
        _ = asyncio.create_task(create_file_after_delay())

        # Watch for events
        events: list[PIDFileEvent] = []
        async for event in watch_pid_file(pid_file, check_interval=1):
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
            """Delete PID file after 0.5 seconds."""
            await asyncio.sleep(0.5)
            _ = pid_file.unlink()

        # Start file deletion task
        _ = asyncio.create_task(delete_file_after_delay())

        # Watch for events
        events: list[PIDFileEvent] = []
        async for event in watch_pid_file(pid_file, check_interval=1):
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
            """Modify PID file after 0.5 seconds."""
            await asyncio.sleep(0.5)
            _ = pid_file.write_text("67890")

        # Start file modification task
        _ = asyncio.create_task(modify_file_after_delay())

        # Watch for events
        events: list[PIDFileEvent] = []
        async for event in watch_pid_file(pid_file, check_interval=1):
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
            async with asyncio.timeout(2):
                async for event in watch_pid_file(pid_file, check_interval=1):
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
            await asyncio.sleep(0.5)
            _ = pid_file.write_text("12345")  # Create

            await asyncio.sleep(1.5)
            _ = pid_file.write_text("67890")  # Modify

            await asyncio.sleep(1.5)
            _ = pid_file.unlink()  # Delete

        # Start lifecycle simulation
        _ = asyncio.create_task(simulate_lifecycle())

        # Collect events
        events: list[PIDFileEvent] = []
        async for event in watch_pid_file(pid_file, check_interval=1):
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
        check_interval = 2  # 2 seconds

        async def create_file_after_delay() -> None:
            """Create PID file after 0.5 seconds."""
            await asyncio.sleep(0.5)
            _ = pid_file.write_text("12345")

        # Start file creation task
        _ = asyncio.create_task(create_file_after_delay())

        # Measure time to detect file creation
        start_time = asyncio.get_event_loop().time()

        # Watch for events
        async for event in watch_pid_file(pid_file, check_interval=check_interval):
            if event.event_type == "created":
                elapsed = asyncio.get_event_loop().time() - start_time
                break

        # Event should be detected around check_interval time
        # Allow generous margin for test timing variability
        assert elapsed < (check_interval + 2)

    @pytest.mark.asyncio
    async def test_watcher_cancellation(self, tmp_path: Path) -> None:
        """Watcher should handle cancellation gracefully."""
        pid_file = tmp_path / "mover.pid"

        async def watch_and_cancel() -> None:
            """Start watching and cancel after 1 second."""
            watcher = watch_pid_file(pid_file, check_interval=1)
            task = asyncio.create_task(anext(watcher))

            await asyncio.sleep(1)
            _ = task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected

        # Should complete without error
        await watch_and_cancel()

    @pytest.mark.asyncio
    async def test_invalid_pid_content_emits_event_with_none(
        self, tmp_path: Path
    ) -> None:
        """File with invalid PID should emit event with pid=None."""
        pid_file = tmp_path / "mover.pid"

        async def create_invalid_file() -> None:
            """Create file with invalid PID content."""
            await asyncio.sleep(0.5)
            _ = pid_file.write_text("invalid_pid")

        # Start file creation task
        _ = asyncio.create_task(create_invalid_file())

        # Watch for events
        events: list[PIDFileEvent] = []
        async for event in watch_pid_file(pid_file, check_interval=1):
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
            async with asyncio.timeout(2):
                async for event in watch_pid_file(pid_file, check_interval=1):
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
            await asyncio.sleep(0.5)
            _ = pid_file.write_text("200")

            await asyncio.sleep(1.5)
            _ = pid_file.write_text("300")

        # Start modifications
        _ = asyncio.create_task(rapid_modifications())

        # Collect events
        events: list[PIDFileEvent] = []
        event_count = 0
        async for event in watch_pid_file(pid_file, check_interval=1):
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
