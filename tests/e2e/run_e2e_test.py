"""E2E test orchestration script for mover-status.

This script orchestrates the complete end-to-end test of mover-status in a
Docker environment, including:
- Creating test data files
- Starting Docker Compose services
- Monitoring logs for expected events
- Verifying notifications were sent
- Cleaning up test resources

Exit codes:
    0: Test passed (all notifications sent successfully)
    1: Test failed (missing notifications, errors, or timeout)
    2: Setup/teardown error
"""

import argparse
import logging
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NoReturn, Protocol, cast

logger = logging.getLogger(__name__)


class E2EArgs(Protocol):
    """Type protocol for parsed command-line arguments."""

    skip_build: bool
    keep_running: bool
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]


# Test constants
E2E_DIR = Path(__file__).parent
PROJECT_ROOT = E2E_DIR.parent.parent
COMPOSE_FILE = E2E_DIR / "docker-compose.e2e.yml"
TEST_TIMEOUT = 300  # 5 minutes maximum test duration


@dataclass(slots=True, frozen=True)
class TestResult:
    """Result of E2E test execution.

    Attributes:
        success: Whether test passed
        started_notified: Whether "started" notification was sent
        progress_notified: Whether any progress notification was sent
        completed_notified: Whether "completed" notification was sent
        errors: List of error messages encountered
        logs: Complete log output from services
    """

    success: bool
    started_notified: bool
    progress_notified: bool
    completed_notified: bool
    errors: list[str]
    logs: str


class E2ETestOrchestrator:
    """Orchestrates E2E test execution for mover-status.

    This class manages the complete lifecycle of an E2E test, including
    Docker Compose service orchestration, log monitoring, and verification.
    """

    def __init__(self, *, skip_build: bool = False, keep_running: bool = False) -> None:
        """Initialize test orchestrator.

        Args:
            skip_build: Skip Docker image build (use existing image)
            keep_running: Keep containers running after test (for debugging)
        """
        self.skip_build: bool = skip_build
        self.keep_running: bool = keep_running
        self._temp_dir: Path | None = None

    def _run_command(
        self, cmd: list[str], *, check: bool = True, capture: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """Run shell command with logging.

        Args:
            cmd: Command and arguments to run
            check: Raise exception on non-zero exit code
            capture: Capture stdout/stderr

        Returns:
            Completed process result
        """
        logger.debug(f"Running command: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=capture,
                text=True,
                cwd=PROJECT_ROOT,
            )
            if capture:
                stdout = result.stdout
                stderr = result.stderr
                if stdout:
                    logger.debug(f"Command output: {stdout}")
                if stderr:
                    logger.debug(f"Command stderr: {stderr}")
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e}")
            if capture:
                # CalledProcessError.stdout/stderr are Any, but we know they're str|None with text=True
                stdout: str | None = cast(str | None, e.stdout)
                stderr: str | None = cast(str | None, e.stderr)
                logger.error(f"stdout: {stdout}")
                logger.error(f"stderr: {stderr}")
            raise

    def _create_test_data(self, size_mb: int = 100) -> Path:
        """Create test data directory with files.

        Args:
            size_mb: Total size of test data in MB

        Returns:
            Path to test data directory
        """
        # Create temporary directory for test data
        temp_dir = Path(tempfile.mkdtemp(prefix="mover-e2e-"))
        self._temp_dir = temp_dir
        logger.info(f"Created test data directory: {temp_dir}")

        # Create cache directory
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Create test files
        num_files = 20
        file_size = (size_mb * 1024 * 1024) // num_files

        logger.info(f"Creating {num_files} test files ({size_mb}MB total)")
        for i in range(num_files):
            file_path = cache_dir / f"testfile_{i:03d}.dat"
            # Create file with random data
            _ = self._run_command(
                ["dd", "if=/dev/urandom", f"of={file_path}", f"bs={file_size}", "count=1"],
                capture=False,
            )
            logger.debug(f"Created {file_path}")

        logger.info(f"Test data created: {num_files} files, {size_mb}MB")
        return temp_dir

    def _build_image(self) -> None:
        """Build Docker image for E2E testing."""
        if self.skip_build:
            logger.info("Skipping Docker image build (--skip-build)")
            return

        logger.info("Building Docker image...")
        _ = self._run_command(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "build"],
            capture=False,
        )
        logger.info("Docker image built successfully")

    def _start_services(self) -> None:
        """Start Docker Compose services."""
        logger.info("Starting Docker Compose services...")
        _ = self._run_command(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "up",
                "-d",
            ],
            capture=False,
        )
        logger.info("Services started")

    def _wait_for_completion(self, timeout: int = TEST_TIMEOUT) -> str:
        """Wait for services to complete and return logs.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Combined logs from all services
        """
        logger.info(f"Waiting for test completion (timeout: {timeout}s)...")

        # Wait for simulator to exit
        try:
            _ = self._run_command(
                [
                    "docker",
                    "wait",
                    "mover-simulator-e2e",
                ],
                capture=False,
            )
            logger.info("Mover simulator completed")
        except subprocess.CalledProcessError:
            logger.warning("Simulator did not exit cleanly")

        # Give mover-status time to send final notifications
        logger.info("Waiting for final notifications (5s)...")
        import time

        time.sleep(5)

        # Get logs from all services
        logger.info("Retrieving logs...")
        result = self._run_command(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "logs",
                "--no-color",
            ]
        )

        return result.stdout

    def _parse_logs(self, logs: str) -> TestResult:
        """Parse logs to verify notifications were sent.

        Args:
            logs: Combined logs from all services

        Returns:
            Test result with verification status
        """
        logger.info("Parsing logs for notification events...")

        # Patterns to look for in logs
        started_pattern = re.compile(r"started.*notification", re.IGNORECASE)
        progress_pattern = re.compile(r"progress.*notification", re.IGNORECASE)
        completed_pattern = re.compile(r"completed.*notification", re.IGNORECASE)
        error_pattern = re.compile(r"ERROR|CRITICAL|Failed|Exception", re.IGNORECASE)

        # Check for notification events
        started_notified = bool(started_pattern.search(logs))
        progress_notified = bool(progress_pattern.search(logs))
        completed_notified = bool(completed_pattern.search(logs))

        # Extract errors
        errors: list[str] = []
        for line in logs.splitlines():
            if error_pattern.search(line):
                errors.append(line.strip())

        # Determine overall success
        success = started_notified and completed_notified and not errors

        logger.info("Notification verification:")
        logger.info(f"  - Started notification: {'✓' if started_notified else '✗'}")
        logger.info(f"  - Progress notification: {'✓' if progress_notified else '✗'}")
        logger.info(f"  - Completed notification: {'✓' if completed_notified else '✗'}")
        logger.info(f"  - Errors found: {len(errors)}")

        if errors:
            logger.warning("Errors found in logs:")
            for error in errors[:10]:  # Show first 10 errors
                logger.warning(f"  {error}")

        return TestResult(
            success=success,
            started_notified=started_notified,
            progress_notified=progress_notified,
            completed_notified=completed_notified,
            errors=errors,
            logs=logs,
        )

    def _stop_services(self) -> None:
        """Stop and remove Docker Compose services."""
        if self.keep_running:
            logger.info("Keeping services running (--keep-running)")
            return

        logger.info("Stopping Docker Compose services...")
        try:
            _ = self._run_command(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(COMPOSE_FILE),
                    "down",
                    "-v",
                ],
                capture=False,
            )
            logger.info("Services stopped and cleaned up")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to stop services cleanly: {e}")

    def _cleanup_test_data(self) -> None:
        """Remove temporary test data."""
        if self._temp_dir and self._temp_dir.exists():
            logger.info(f"Cleaning up test data: {self._temp_dir}")
            import shutil

            shutil.rmtree(self._temp_dir, ignore_errors=True)

    def run(self) -> int:
        """Run E2E test.

        Returns:
            Exit code: 0 on success, 1 on failure, 2 on setup error
        """
        try:
            # Verify environment variables are set
            required_env_vars = [
                "E2E_DISCORD_WEBHOOK_URL",
                "E2E_TELEGRAM_BOT_TOKEN",
                "E2E_TELEGRAM_CHAT_ID",
            ]
            missing_vars = [var for var in required_env_vars if not os.getenv(var)]
            if missing_vars:
                logger.error(f"Missing required environment variables: {missing_vars}")
                logger.error("Set these variables before running E2E tests")
                return 2

            # Setup phase
            logger.info("=" * 80)
            logger.info("Starting E2E Test for mover-status")
            logger.info("=" * 80)

            # Build Docker image
            self._build_image()

            # Note: Test data creation is handled by the simulator creating files
            # in the Docker volumes, so we don't need to create external test data

            # Start services
            self._start_services()

            # Wait for completion and get logs
            logs = self._wait_for_completion()

            # Parse logs and verify
            result = self._parse_logs(logs)

            # Report results
            logger.info("=" * 80)
            logger.info("E2E Test Results")
            logger.info("=" * 80)
            logger.info(f"Overall: {'PASSED ✓' if result.success else 'FAILED ✗'}")
            logger.info(f"Started notification: {'✓' if result.started_notified else '✗'}")
            logger.info(f"Progress notification: {'✓' if result.progress_notified else '✗'}")
            logger.info(f"Completed notification: {'✓' if result.completed_notified else '✗'}")
            logger.info(f"Errors: {len(result.errors)}")
            logger.info("=" * 80)

            return 0 if result.success else 1

        except Exception as e:
            logger.exception(f"E2E test failed with exception: {e}")
            return 2

        finally:
            # Cleanup
            self._stop_services()
            self._cleanup_test_data()


def _setup_logging(log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]) -> None:
    """Configure logging for test orchestrator.

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
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )


def _parse_args() -> E2EArgs:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Run E2E tests for mover-status",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    _ = parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip Docker image build (use existing image)",
    )
    _ = parser.add_argument(
        "--keep-running",
        action="store_true",
        help="Keep containers running after test (for debugging)",
    )
    _ = parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    # Two-step cast needed for argparse.Namespace (untyped at runtime)
    return cast(E2EArgs, cast(object, parser.parse_args()))


def main() -> NoReturn:
    """Main entry point for E2E test orchestrator.

    Raises:
        SystemExit: Always exits with appropriate code
    """
    args = _parse_args()
    _setup_logging(args.log_level)

    orchestrator = E2ETestOrchestrator(
        skip_build=args.skip_build,
        keep_running=args.keep_running,
    )

    exit_code = orchestrator.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
