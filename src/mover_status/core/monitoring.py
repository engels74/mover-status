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
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


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


async def watch_pid_file(
    pid_file_path: Path,
    *,
    check_interval: int = 1,
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
