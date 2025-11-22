"""Unraid mover process simulator for E2E testing.

This module simulates the Unraid mover process behavior for end-to-end testing.
It creates a PID file, progressively moves files from source to destination,
and cleans up the PID file on completion, mimicking the real mover workflow.

Key behaviors:
- Creates PID file at start (mimics /var/run/mover.pid)
- Progressively moves files from cache to array in chunks
- Simulates realistic timing with configurable duration
- Deletes PID file on completion or error
- Supports graceful shutdown on SIGTERM/SIGINT
"""

import argparse
import asyncio
import logging
import os
import shutil
import signal
import sys
from pathlib import Path
from typing import Literal, NoReturn, Protocol, cast

logger = logging.getLogger(__name__)


class SimulatorArgs(Protocol):
    """Type protocol for parsed command-line arguments."""

    source_dir: Path
    dest_dir: Path
    pid_file: Path
    duration: float
    chunk_interval: float
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    create_test_data: bool
    test_data_size: int


class MoverSimulator:
    """Simulates Unraid mover process for E2E testing.

    This class creates a realistic simulation of the Unraid mover process,
    which transfers files from cache drives to the array. It manages PID file
    lifecycle and file movement operations.

    Attributes:
        source_dir: Source directory (simulates /mnt/cache)
        dest_dir: Destination directory (simulates /mnt/user or array)
        pid_file: Path to PID file (simulates /var/run/mover.pid)
        total_duration: Total time to complete move operation (seconds)
        chunk_interval: Time between move operations (seconds)
        create_test_data: Whether to create test data files
        test_data_size_mb: Size of test data to create in MB
    """

    def __init__(
        self,
        source_dir: Path,
        dest_dir: Path,
        pid_file: Path,
        *,
        total_duration: float = 45.0,
        chunk_interval: float = 3.0,
        create_test_data: bool = False,
        test_data_size_mb: int = 100,
    ) -> None:
        """Initialize mover simulator.

        Args:
            source_dir: Directory containing files to move
            dest_dir: Destination directory for moved files
            pid_file: Path where PID file should be created
            total_duration: Total duration of move operation in seconds
            chunk_interval: Seconds between each chunk move operation
            create_test_data: Whether to create test data files in source_dir
            test_data_size_mb: Total size of test data to create in MB
        """
        self.source_dir: Path = source_dir
        self.dest_dir: Path = dest_dir
        self.pid_file: Path = pid_file
        self.total_duration: float = total_duration
        self.chunk_interval: float = chunk_interval
        self.create_test_data: bool = create_test_data
        self.test_data_size_mb: int = test_data_size_mb
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._pid_file_created: bool = False

    def _create_pid_file(self) -> None:
        """Create PID file with current process ID.

        Mimics Unraid mover's PID file creation at /var/run/mover.pid.
        The PID file contains the current process ID as a string.
        """
        try:
            # Ensure parent directory exists
            self.pid_file.parent.mkdir(parents=True, exist_ok=True)

            # Write current process ID
            pid = os.getpid()
            _ = self.pid_file.write_text(f"{pid}\n")
            self._pid_file_created = True
            logger.info(f"Created PID file: {self.pid_file} with PID {pid}")
        except OSError as e:
            logger.error(f"Failed to create PID file: {e}")
            raise

    def _delete_pid_file(self) -> None:
        """Delete PID file on completion.

        Removes the PID file to signal mover process completion,
        matching Unraid's cleanup behavior.
        """
        if self._pid_file_created and self.pid_file.exists():
            try:
                self.pid_file.unlink()
                logger.info(f"Deleted PID file: {self.pid_file}")
            except OSError as e:
                logger.warning(f"Failed to delete PID file: {e}")

    async def _create_test_data_files(self) -> None:
        """Create test data files in source directory.

        Creates test files with random data for E2E testing.
        The files are created with realistic sizes to simulate cache usage.
        """
        # Ensure source directory exists
        self.source_dir.mkdir(parents=True, exist_ok=True)

        # Calculate file parameters
        num_files = 20
        file_size_bytes = (self.test_data_size_mb * 1024 * 1024) // num_files

        logger.info(f"Creating {num_files} test files ({self.test_data_size_mb}MB total) in {self.source_dir}")

        # Create files in thread pool to avoid blocking event loop
        def create_file(file_path: Path, size: int) -> None:
            """Create a single file with random data."""
            with file_path.open("wb") as f:
                # Write in chunks to avoid memory issues
                chunk_size = 1024 * 1024  # 1MB chunks
                for _ in range(size // chunk_size):
                    _ = f.write(os.urandom(chunk_size))
                # Write remaining bytes
                remainder = size % chunk_size
                if remainder:
                    _ = f.write(os.urandom(remainder))

        # Create files concurrently
        tasks: list[asyncio.Task[None]] = []
        for i in range(num_files):
            file_path = self.source_dir / f"testfile_{i:03d}.dat"
            task = asyncio.create_task(asyncio.to_thread(create_file, file_path, file_size_bytes))
            tasks.append(task)

        _ = await asyncio.gather(*tasks)
        logger.info(f"Test data created: {num_files} files, {self.test_data_size_mb}MB")

    def _get_files_to_move(self) -> list[Path]:
        """Get list of files from source directory.

        Returns:
            List of file paths to move, sorted by name for consistency
        """
        if not self.source_dir.exists():
            logger.warning(f"Source directory does not exist: {self.source_dir}")
            return []

        files = [f for f in self.source_dir.rglob("*") if f.is_file() and not f.name.startswith(".")]
        return sorted(files)

    async def _move_file(self, file_path: Path) -> None:
        """Move a single file from source to destination.

        Args:
            file_path: Path to file to move

        Note:
            Uses asyncio.to_thread to avoid blocking the event loop
            during file I/O operations.
        """
        try:
            # Calculate relative path and destination
            rel_path = file_path.relative_to(self.source_dir)
            dest_path = self.dest_dir / rel_path

            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file (run in thread pool to avoid blocking)
            _ = await asyncio.to_thread(shutil.move, str(file_path), str(dest_path))
            logger.debug(f"Moved: {rel_path}")
        except Exception as e:
            logger.error(f"Failed to move {file_path}: {e}")

    async def _progressive_move(self) -> None:
        """Progressively move files from source to destination.

        Divides files into chunks and moves them at regular intervals
        to simulate realistic mover behavior with measurable progress.
        """
        files = self._get_files_to_move()
        if not files:
            logger.warning("No files to move")
            return

        total_files = len(files)
        num_chunks = max(1, int(self.total_duration / self.chunk_interval))
        chunk_size = max(1, total_files // num_chunks)

        logger.info(f"Moving {total_files} files in {num_chunks} chunks")

        for i in range(0, total_files, chunk_size):
            if self._shutdown_event.is_set():
                logger.info("Shutdown requested, stopping file moves")
                break

            chunk = files[i : i + chunk_size]
            logger.info(
                f"Moving chunk {i // chunk_size + 1}/{num_chunks}: {len(chunk)} files ({i + len(chunk)}/{total_files} total)"
            )

            # Move files in current chunk concurrently
            _ = await asyncio.gather(*[self._move_file(f) for f in chunk])

            # Wait before next chunk (unless this is the last chunk)
            if i + chunk_size < total_files and not self._shutdown_event.is_set():
                await asyncio.sleep(self.chunk_interval)

        logger.info("File move completed")

    async def run(self) -> int:
        """Run mover simulation.

        Returns:
            Exit code: 0 on success, 1 on error
        """
        try:
            # Create test data if requested
            if self.create_test_data:
                logger.info("Creating test data files...")
                await self._create_test_data_files()

            # Create PID file to signal mover start
            self._create_pid_file()

            # Small delay to ensure monitoring detects PID file
            await asyncio.sleep(0.5)

            # Progressively move files
            await self._progressive_move()

            # Small delay before cleanup to ensure final sampling
            await asyncio.sleep(1.0)

            return 0

        except Exception as e:
            logger.error(f"Mover simulation failed: {e}")
            return 1

        finally:
            # Always clean up PID file
            self._delete_pid_file()

    def request_shutdown(self) -> None:
        """Request graceful shutdown of mover simulation."""
        logger.info("Shutdown requested")
        self._shutdown_event.set()


def _setup_logging(log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]) -> None:
    """Configure logging for simulator.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    level_map: dict[str, int] = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    logging.basicConfig(
        level=level_map[log_level],
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )


def _parse_args() -> SimulatorArgs:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Simulate Unraid mover process for E2E testing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    _ = parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("/mnt/cache"),
        help="Source directory containing files to move",
    )
    _ = parser.add_argument(
        "--dest-dir",
        type=Path,
        default=Path("/mnt/user"),
        help="Destination directory for moved files",
    )
    _ = parser.add_argument(
        "--pid-file",
        type=Path,
        default=Path("/var/run/mover.pid"),
        help="Path to PID file",
    )
    _ = parser.add_argument(
        "--duration",
        type=float,
        default=45.0,
        help="Total duration of move operation (seconds)",
    )
    _ = parser.add_argument(
        "--chunk-interval",
        type=float,
        default=3.0,
        help="Interval between chunk moves (seconds)",
    )
    _ = parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    _ = parser.add_argument(
        "--create-test-data",
        action="store_true",
        help="Create test data files before moving",
    )
    _ = parser.add_argument(
        "--test-data-size",
        type=int,
        default=100,
        help="Size of test data to create in MB",
    )
    # Two-step cast needed for argparse.Namespace (untyped at runtime)
    return cast(SimulatorArgs, cast(object, parser.parse_args()))


async def _async_main() -> int:
    """Async main entry point.

    Returns:
        Exit code: 0 on success, non-zero on error
    """
    args = _parse_args()
    _setup_logging(args.log_level)

    # Create simulator
    simulator = MoverSimulator(
        source_dir=args.source_dir,
        dest_dir=args.dest_dir,
        pid_file=args.pid_file,
        total_duration=args.duration,
        chunk_interval=args.chunk_interval,
        create_test_data=args.create_test_data,
        test_data_size_mb=args.test_data_size,
    )

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    def signal_handler() -> None:
        simulator.request_shutdown()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Run simulation
    return await simulator.run()


def main() -> NoReturn:
    """Main entry point for mover simulator.

    Raises:
        SystemExit: Always exits with return code from simulation
    """
    try:
        exit_code = asyncio.run(_async_main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
