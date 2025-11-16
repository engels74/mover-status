"""PID file monitoring for detecting mover process lifecycle events.

This module provides async PID file watching functionality with support for:
- Async file watching using polling approach
- PID file event detection (creation, modification, deletion)
- Configurable polling intervals
- Robust error handling for filesystem errors
- Indefinite monitoring with proper cancellation support

The monitoring approach uses polling instead of platform-specific file system
events (like inotify) for simplicity, portability, and sufficient performance
for the 5-second detection requirement (Requirements 1.1, 1.2, 1.3).
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


class MoverState(Enum):
    """Lifecycle states for the mover process.

    Represents the distinct phases of mover operation:
    - WAITING: No mover process detected, waiting for PID file creation
    - STARTED: PID file created and process validated, awaiting baseline
    - MONITORING: Actively monitoring disk usage and calculating progress
    - COMPLETED: Mover process terminated, cycle complete

    State transitions:
        WAITING → STARTED: PID file created, process validated
        STARTED → MONITORING: Baseline disk usage captured
        MONITORING → COMPLETED: PID file deleted or process terminated
        COMPLETED → WAITING: Ready for next mover cycle
    """

    WAITING = "waiting"
    STARTED = "started"
    MONITORING = "monitoring"
    COMPLETED = "completed"


@dataclass(slots=True, frozen=True)
class PIDFileEvent:
    """Immutable event emitted when PID file state changes.

    Represents a detected change in the mover PID file state, including
    creation (mover started), modification (PID changed), or deletion
    (mover stopped).
    """

    event_type: Literal["created", "modified", "deleted"]
    pid: int | None
    timestamp: datetime


@dataclass(slots=True, frozen=True)
class MoverLifecycleEvent:
    """Immutable event emitted when mover lifecycle state changes.

    Represents a state transition in the mover lifecycle state machine,
    capturing the previous state, new state, associated PID, and a
    descriptive message for logging and debugging.

    This event is emitted by the lifecycle state machine on all state
    transitions and is used for:
    - Syslog logging of operational events (Requirement 13.1)
    - Orchestrator coordination and decision-making
    - Audit trail of mover lifecycle progression
    """

    previous_state: MoverState
    new_state: MoverState
    pid: int | None
    timestamp: datetime
    message: str


def read_pid_from_file(pid_file_path: Path) -> int | None:
    """Read PID from PID file, returns None on error.

    Safely reads the PID value from the PID file, handling common error
    conditions like file not existing, permission errors, or invalid content.

    Args:
        pid_file_path: Path to the PID file

    Returns:
        PID as integer if successfully read, None on any error

    Examples:
        >>> from pathlib import Path
        >>> pid_file = Path("/var/run/mover.pid")
        >>> pid = read_pid_from_file(pid_file)
        >>> pid is None or isinstance(pid, int)
        True
    """
    try:
        content = pid_file_path.read_text().strip()

        # Validate content is a positive integer
        if not content.isdigit():
            logger.warning(
                "PID file contains invalid content (not a number)",
                extra={"path": str(pid_file_path), "content": content},
            )
            return None

        pid = int(content)

        # Validate PID is positive
        if pid <= 0:
            logger.warning(
                "PID file contains invalid PID (not positive)",
                extra={"path": str(pid_file_path), "pid": pid},
            )
            return None

        return pid

    except FileNotFoundError:
        # File doesn't exist - this is expected when mover is not running
        logger.debug(
            "PID file not found",
            extra={"path": str(pid_file_path)},
        )
        return None

    except PermissionError:
        # Permission denied reading PID file
        logger.warning(
            "Permission denied reading PID file",
            extra={"path": str(pid_file_path)},
        )
        return None

    except OSError as exc:
        # Other filesystem errors (file removed during read, etc.)
        logger.warning(
            "Filesystem error reading PID file",
            extra={"path": str(pid_file_path), "error": str(exc)},
        )
        return None

    except ValueError as exc:
        # Failed to parse content as integer (shouldn't happen after isdigit check)
        logger.warning(
            "Failed to parse PID from file content",
            extra={"path": str(pid_file_path), "error": str(exc)},
        )
        return None


def is_process_running(pid: int) -> bool:
    """Check if process exists in the system process table.

    Uses the /proc filesystem to verify process existence, which is reliable
    and doesn't require subprocess invocation. This is the standard approach
    for process validation on Linux systems.

    Args:
        pid: Process ID to validate

    Returns:
        True if process exists in process table, False otherwise

    Examples:
        >>> import os
        >>> current_pid = os.getpid()
        >>> is_process_running(current_pid)
        True
        >>> is_process_running(999999)
        False
    """
    return Path(f"/proc/{pid}").exists()


def get_process_executable(pid: int) -> str | None:
    """Get executable path for a running process.

    Reads the /proc/{pid}/exe symlink to determine the actual executable
    path for a process. This can be used to verify the process is one of
    the expected mover variants (mover.old or age_mover).

    Args:
        pid: Process ID to query

    Returns:
        Absolute path to the executable, or None if process doesn't exist
        or if the executable path cannot be determined (permission errors, etc.)

    Examples:
        >>> import os
        >>> current_pid = os.getpid()
        >>> exe_path = get_process_executable(current_pid)
        >>> exe_path is not None
        True
        >>> get_process_executable(999999) is None
        True
    """
    try:
        exe_link = Path(f"/proc/{pid}/exe")
        # resolve(strict=True) will raise FileNotFoundError if symlink doesn't exist
        return str(exe_link.resolve(strict=True))
    except (FileNotFoundError, PermissionError, OSError):
        # Process doesn't exist, permission denied, or other OS error
        return None


async def validate_process_with_timeout(
    pid: int,
    *,
    timeout: float = 5.0,
) -> bool:
    """Validate process exists in process table with timeout protection.

    Asynchronously validates that a PID corresponds to a running process,
    with timeout protection to prevent indefinite blocking. Uses thread
    pool to offload I/O operations and preserve context variables.

    This implements Requirement 1.1's 5-second detection requirement by
    providing timeout protection for process validation after PID file
    creation.

    Args:
        pid: Process ID to validate
        timeout: Timeout in seconds (keyword-only, default: 5.0)

    Returns:
        True if process exists, False otherwise

    Raises:
        TimeoutError: If validation takes longer than timeout duration

    Examples:
        >>> import os
        >>> current_pid = os.getpid()
        >>> await validate_process_with_timeout(current_pid, timeout=1.0)
        True
    """
    try:
        async with asyncio.timeout(timeout):
            # Offload to thread pool to avoid blocking event loop
            return await asyncio.to_thread(is_process_running, pid)
    except TimeoutError:
        logger.warning(
            "Process validation timed out",
            extra={"pid": pid, "timeout": timeout},
        )
        raise


async def check_pid_file_state(
    pid_file_path: Path,
) -> tuple[bool, int | None]:
    """Check if PID file exists and read PID.

    Asynchronously checks the PID file state by offloading I/O to thread pool.
    This prevents blocking the event loop during file operations.

    Args:
        pid_file_path: Path to the PID file

    Returns:
        Tuple of (exists: bool, pid: int | None)
        - exists is True if file exists, False otherwise
        - pid is the PID value if successfully read, None otherwise

    Examples:
        >>> from pathlib import Path
        >>> exists, pid = await check_pid_file_state(Path("/var/run/mover.pid"))
        >>> isinstance(exists, bool)
        True
        >>> pid is None or isinstance(pid, int)
        True
    """
    # Check existence using asyncio.to_thread to avoid blocking
    exists = await asyncio.to_thread(pid_file_path.exists)

    if not exists:
        return (False, None)

    # Read PID using asyncio.to_thread
    pid = await asyncio.to_thread(read_pid_from_file, pid_file_path)

    return (True, pid)


class MoverLifecycleStateMachine:
    """State machine for tracking mover process lifecycle.

    Manages state transitions for the mover process lifecycle, tracking
    progression through WAITING → STARTED → MONITORING → COMPLETED states.
    Enforces valid state transitions, logs lifecycle events to syslog, and
    handles edge cases like unexpected termination.

    This implements Requirements 1.1, 1.2, 1.3, 1.5, and 13.1 by:
    - Tracking process state throughout its lifecycle (1.5)
    - Validating state transitions based on process events (1.1, 1.2, 1.3)
    - Logging all lifecycle events to syslog at INFO level (13.1)

    State transitions:
        WAITING → STARTED: PID file created, process validated
        STARTED → MONITORING: Baseline disk usage captured
        MONITORING → COMPLETED: Process terminated normally
        COMPLETED → WAITING: Ready for next mover cycle
        * → COMPLETED: Emergency transition for unexpected termination

    Attributes:
        current_state: Current lifecycle state
        current_pid: PID of tracked process (None if no process)
    """

    def __init__(self) -> None:
        """Initialize state machine in WAITING state."""
        self._state: MoverState = MoverState.WAITING
        self._pid: int | None = None
        logger.info(
            "Lifecycle state machine initialized",
            extra={"state": self._state.value},
        )

    @property
    def current_state(self) -> MoverState:
        """Get current lifecycle state."""
        return self._state

    @property
    def current_pid(self) -> int | None:
        """Get PID of currently tracked process."""
        return self._pid

    def transition_to_started(self, pid: int) -> MoverLifecycleEvent:
        """Transition to STARTED state when mover process is detected.

        Called when PID file is created and process is validated in the
        process table. This implements Requirements 1.1 and 1.2.

        Args:
            pid: Validated PID of the mover process

        Returns:
            MoverLifecycleEvent describing the state transition

        Raises:
            ValueError: If transition from current state to STARTED is invalid
        """
        # Validate transition is allowed
        if self._state not in {MoverState.WAITING, MoverState.COMPLETED}:
            error_msg = f"Invalid transition from {self._state.value} to STARTED"
            logger.error(
                error_msg,
                extra={
                    "current_state": self._state.value,
                    "target_state": MoverState.STARTED.value,
                    "pid": pid,
                },
            )
            raise ValueError(error_msg)

        # Create transition event
        previous_state = self._state
        self._state = MoverState.STARTED
        self._pid = pid

        event = MoverLifecycleEvent(
            previous_state=previous_state,
            new_state=self._state,
            pid=pid,
            timestamp=datetime.now(),
            message=f"Mover process started (PID {pid})",
        )

        # Log to syslog (Requirement 13.1)
        logger.info(
            event.message,
            extra={
                "previous_state": previous_state.value,
                "new_state": self._state.value,
                "pid": pid,
            },
        )

        return event

    def transition_to_monitoring(self) -> MoverLifecycleEvent:
        """Transition to MONITORING state when baseline is captured.

        Called after baseline disk usage is captured and active monitoring
        can begin. This implements Requirement 1.5 (state tracking during
        monitoring phase).

        Returns:
            MoverLifecycleEvent describing the state transition

        Raises:
            ValueError: If transition from current state to MONITORING is invalid
        """
        # Validate transition is allowed
        if self._state != MoverState.STARTED:
            error_msg = f"Invalid transition from {self._state.value} to MONITORING"
            logger.error(
                error_msg,
                extra={
                    "current_state": self._state.value,
                    "target_state": MoverState.MONITORING.value,
                    "pid": self._pid,
                },
            )
            raise ValueError(error_msg)

        # Create transition event
        previous_state = self._state
        self._state = MoverState.MONITORING

        event = MoverLifecycleEvent(
            previous_state=previous_state,
            new_state=self._state,
            pid=self._pid,
            timestamp=datetime.now(),
            message=f"Monitoring mover progress (PID {self._pid})",
        )

        # Log to syslog (Requirement 13.1)
        logger.info(
            event.message,
            extra={
                "previous_state": previous_state.value,
                "new_state": self._state.value,
                "pid": self._pid,
            },
        )

        return event

    def transition_to_completed(
        self,
        *,
        reason: str = "Process terminated normally",
    ) -> MoverLifecycleEvent:
        """Transition to COMPLETED state when mover process terminates.

        Called when PID file is deleted or process terminates. This
        implements Requirement 1.3 (termination detection).

        This transition is allowed from any state to handle edge cases:
        - Normal completion from MONITORING
        - Unexpected termination from STARTED (mover never fully initialized)
        - Process crash before monitoring begins

        Args:
            reason: Description of why completion occurred (keyword-only)

        Returns:
            MoverLifecycleEvent describing the state transition
        """
        # This transition is allowed from any state except WAITING and COMPLETED
        if self._state in {MoverState.WAITING, MoverState.COMPLETED}:
            error_msg = f"Invalid transition from {self._state.value} to COMPLETED"
            logger.error(
                error_msg,
                extra={
                    "current_state": self._state.value,
                    "target_state": MoverState.COMPLETED.value,
                    "reason": reason,
                },
            )
            raise ValueError(error_msg)

        # Create transition event
        previous_state = self._state
        previous_pid = self._pid
        self._state = MoverState.COMPLETED
        # Keep PID until reset to allow final queries

        event = MoverLifecycleEvent(
            previous_state=previous_state,
            new_state=self._state,
            pid=previous_pid,
            timestamp=datetime.now(),
            message=f"Mover process completed: {reason} (PID {previous_pid})",
        )

        # Log to syslog (Requirement 13.1)
        logger.info(
            event.message,
            extra={
                "previous_state": previous_state.value,
                "new_state": self._state.value,
                "pid": previous_pid,
                "reason": reason,
            },
        )

        return event

    def reset(self) -> MoverLifecycleEvent:
        """Reset state machine to WAITING for next mover cycle.

        Called after a completed mover cycle to prepare for the next
        invocation. Clears PID and returns to WAITING state.

        Returns:
            MoverLifecycleEvent describing the state transition

        Raises:
            ValueError: If reset is called from invalid state
        """
        # Reset is only valid from COMPLETED state
        if self._state != MoverState.COMPLETED:
            error_msg = f"Cannot reset from {self._state.value} state"
            logger.error(
                error_msg,
                extra={"current_state": self._state.value},
            )
            raise ValueError(error_msg)

        # Create transition event
        previous_state = self._state
        previous_pid = self._pid
        self._state = MoverState.WAITING
        self._pid = None

        event = MoverLifecycleEvent(
            previous_state=previous_state,
            new_state=self._state,
            pid=None,
            timestamp=datetime.now(),
            message="Ready for next mover cycle",
        )

        # Log to syslog (Requirement 13.1)
        logger.info(
            event.message,
            extra={
                "previous_state": previous_state.value,
                "new_state": self._state.value,
                "previous_pid": previous_pid,
            },
        )

        return event


async def watch_pid_file(
    pid_file_path: Path,
    *,
    check_interval: float = 1.0,
) -> AsyncGenerator[PIDFileEvent, None]:
    """Watch PID file and yield events on state changes.

    Continuously monitors the PID file for changes and yields PIDFileEvent
    instances when the file is created, modified, or deleted. Uses polling
    approach with configurable interval to detect changes.

    The generator runs indefinitely until cancelled. It tracks previous state
    to emit events only when changes occur, avoiding duplicate events.

    Error handling:
    - Permission errors: logged as warnings, monitoring continues
    - Filesystem errors: logged as warnings, monitoring continues
    - Invalid PID content: logged as warnings, event emitted with pid=None
    - Monitoring never crashes, always continues polling

    Args:
        pid_file_path: Path to mover PID file
        check_interval: Polling interval in seconds (keyword-only, default: 1)

    Yields:
        PIDFileEvent for each detected file state change

    Examples:
        >>> from pathlib import Path
        >>> async for event in watch_pid_file(Path("/var/run/mover.pid")):
        ...     print(f"{event.event_type}: PID {event.pid}")
        ...     if event.event_type == "deleted":
        ...         break
    """
    logger.info(
        "Starting PID file watcher",
        extra={
            "pid_file": str(pid_file_path),
            "check_interval": check_interval,
        },
    )

    # Track previous state to detect changes
    # None means we haven't checked yet (initial state)
    previous_exists: bool | None = None
    previous_pid: int | None = None

    try:
        while True:
            # Check current state
            current_exists, current_pid = await check_pid_file_state(pid_file_path)

            # Detect state changes and emit events
            if previous_exists is None:
                # First check - initialize state without emitting event
                logger.debug(
                    "Initial PID file state",
                    extra={
                        "exists": current_exists,
                        "pid": current_pid,
                    },
                )
                previous_exists = current_exists
                previous_pid = current_pid

            elif not previous_exists and current_exists:
                # File created (mover started)
                # Validate process exists in process table (Requirement 1.2)
                if current_pid is not None:
                    try:
                        process_exists = await asyncio.to_thread(
                            is_process_running,
                            current_pid,
                        )

                        if process_exists:
                            # Optionally get executable path for additional validation
                            exe_path = await asyncio.to_thread(
                                get_process_executable,
                                current_pid,
                            )
                            logger.info(
                                "Process validated in process table",
                                extra={
                                    "pid": current_pid,
                                    "executable": exe_path,
                                },
                            )
                        else:
                            logger.warning(
                                "PID file created but process not found in process table",
                                extra={"pid": current_pid, "path": str(pid_file_path)},
                            )
                    except Exception as exc:
                        # Log validation error but continue - let state machine handle
                        logger.error(
                            "Failed to validate process existence",
                            extra={
                                "pid": current_pid,
                                "error": str(exc),
                            },
                        )

                event = PIDFileEvent(
                    event_type="created",
                    pid=current_pid,
                    timestamp=datetime.now(),
                )
                logger.info(
                    "PID file created",
                    extra={
                        "pid": current_pid,
                        "path": str(pid_file_path),
                    },
                )
                yield event

                previous_exists = current_exists
                previous_pid = current_pid

            elif previous_exists and not current_exists:
                # File deleted (mover stopped)
                event = PIDFileEvent(
                    event_type="deleted",
                    pid=None,
                    timestamp=datetime.now(),
                )
                logger.info(
                    "PID file deleted",
                    extra={"path": str(pid_file_path)},
                )
                yield event

                previous_exists = current_exists
                previous_pid = current_pid

            elif previous_exists and current_exists and previous_pid != current_pid:
                # File modified (PID changed - rare but possible)
                event = PIDFileEvent(
                    event_type="modified",
                    pid=current_pid,
                    timestamp=datetime.now(),
                )
                logger.info(
                    "PID file modified",
                    extra={
                        "old_pid": previous_pid,
                        "new_pid": current_pid,
                        "path": str(pid_file_path),
                    },
                )
                yield event

                previous_pid = current_pid

            # Wait for next check interval
            await asyncio.sleep(check_interval)

    except asyncio.CancelledError:
        # Generator cancelled - clean shutdown
        logger.info(
            "PID file watcher cancelled",
            extra={"pid_file": str(pid_file_path)},
        )
        raise

    except Exception as exc:
        # Unexpected error - log but don't crash the watcher
        logger.error(
            "Unexpected error in PID file watcher",
            extra={
                "pid_file": str(pid_file_path),
                "error": str(exc),
            },
        )
        raise


async def monitor_mover_lifecycle(
    pid_file_path: Path,
    *,
    check_interval: float = 1.0,
) -> AsyncGenerator[MoverLifecycleEvent, None]:
    """Monitor mover process lifecycle and yield state transition events.

    High-level interface for monitoring the mover process lifecycle. Watches
    the PID file for changes, manages a lifecycle state machine, and yields
    MoverLifecycleEvent instances on each state transition.

    This function orchestrates the complete lifecycle monitoring by:
    - Creating and managing the lifecycle state machine
    - Watching PID file for process start/stop events
    - Validating process existence
    - Transitioning state machine based on events
    - Yielding lifecycle events for orchestrator consumption

    The generator runs indefinitely until cancelled, automatically handling:
    - Process detection (WAITING → STARTED)
    - Process termination (STARTED/MONITORING → COMPLETED)
    - Cycle reset (COMPLETED → WAITING)
    - Edge cases (unexpected termination, validation failures)

    Note: The STARTED → MONITORING transition is NOT handled here, as it
    requires baseline disk usage capture by the orchestrator. The orchestrator
    must call state_machine.transition_to_monitoring() when ready.

    Args:
        pid_file_path: Path to mover PID file
        check_interval: PID file polling interval in seconds (keyword-only, default: 1)

    Yields:
        MoverLifecycleEvent for each state transition

    Examples:
        >>> from pathlib import Path
        >>> async for event in monitor_mover_lifecycle(Path("/var/run/mover.pid")):
        ...     print(f"{event.new_state.value}: {event.message}")
        ...     if event.new_state == MoverState.COMPLETED:
        ...         break
    """
    logger.info(
        "Starting mover lifecycle monitoring",
        extra={
            "pid_file": str(pid_file_path),
            "check_interval": check_interval,
        },
    )

    # Create state machine instance
    state_machine = MoverLifecycleStateMachine()

    try:
        # Check if PID file already exists at start (handle edge case where
        # mover is already running when monitoring begins)
        exists, pid = await check_pid_file_state(pid_file_path)
        if exists and pid is not None:
            # PID file exists - validate process and transition to STARTED
            process_exists = await asyncio.to_thread(is_process_running, pid)
            if process_exists:
                lifecycle_event = state_machine.transition_to_started(pid)
                yield lifecycle_event
                logger.info(
                    "Mover process already running at monitor start",
                    extra={"pid": pid},
                )

        # Watch PID file for events
        async for pid_event in watch_pid_file(
            pid_file_path,
            check_interval=check_interval,
        ):
            # Handle PID file events and transition state machine
            if pid_event.event_type == "created":
                # PID file created - attempt transition to STARTED
                if pid_event.pid is not None:
                    try:
                        # Validate process exists (already done in watch_pid_file,
                        # but state machine requires valid PID)
                        process_exists = await asyncio.to_thread(
                            is_process_running,
                            pid_event.pid,
                        )

                        if process_exists:
                            # Transition to STARTED state
                            lifecycle_event = state_machine.transition_to_started(
                                pid_event.pid
                            )
                            yield lifecycle_event
                        else:
                            logger.warning(
                                "PID file created but process not running, staying in WAITING",
                                extra={"pid": pid_event.pid},
                            )
                    except ValueError as exc:
                        # Invalid state transition - log and continue
                        logger.error(
                            "Failed to transition to STARTED",
                            extra={
                                "pid": pid_event.pid,
                                "current_state": state_machine.current_state.value,
                                "error": str(exc),
                            },
                        )
                else:
                    logger.warning(
                        "PID file created but PID could not be read",
                        extra={"path": str(pid_file_path)},
                    )

            elif pid_event.event_type == "deleted":
                # PID file deleted - transition to COMPLETED (if not already)
                if state_machine.current_state in {
                    MoverState.STARTED,
                    MoverState.MONITORING,
                }:
                    try:
                        lifecycle_event = state_machine.transition_to_completed(
                            reason="PID file deleted"
                        )
                        yield lifecycle_event

                        # Auto-reset for next cycle
                        reset_event = state_machine.reset()
                        yield reset_event

                    except ValueError as exc:
                        # Invalid state transition - log and continue
                        logger.error(
                            "Failed to transition to COMPLETED",
                            extra={
                                "current_state": state_machine.current_state.value,
                                "error": str(exc),
                            },
                        )

            elif pid_event.event_type == "modified":
                # PID file modified (PID changed) - log warning
                # This is rare and indicates mover restarted with different PID
                logger.warning(
                    "PID file modified during monitoring - process may have restarted",
                    extra={
                        "new_pid": pid_event.pid,
                        "current_state": state_machine.current_state.value,
                        "current_pid": state_machine.current_pid,
                    },
                )

                # If process changed during STARTED/MONITORING, treat as completion
                # followed by new start
                if state_machine.current_state in {
                    MoverState.STARTED,
                    MoverState.MONITORING,
                }:
                    try:
                        # Complete previous process
                        completion_event = state_machine.transition_to_completed(
                            reason="Process PID changed unexpectedly"
                        )
                        yield completion_event

                        # Reset for new process
                        reset_event = state_machine.reset()
                        yield reset_event

                        # Start new process if PID is valid
                        if pid_event.pid is not None:
                            process_exists = await asyncio.to_thread(
                                is_process_running,
                                pid_event.pid,
                            )
                            if process_exists:
                                start_event = state_machine.transition_to_started(
                                    pid_event.pid
                                )
                                yield start_event

                    except ValueError as exc:
                        logger.error(
                            "Failed to handle PID change",
                            extra={
                                "new_pid": pid_event.pid,
                                "error": str(exc),
                            },
                        )

    except asyncio.CancelledError:
        # Generator cancelled - clean shutdown
        logger.info(
            "Mover lifecycle monitoring cancelled",
            extra={
                "pid_file": str(pid_file_path),
                "final_state": state_machine.current_state.value,
            },
        )
        raise

    except Exception as exc:
        # Unexpected error - log and propagate
        logger.error(
            "Unexpected error in lifecycle monitoring",
            extra={
                "pid_file": str(pid_file_path),
                "current_state": state_machine.current_state.value,
                "error": str(exc),
            },
        )
        raise
