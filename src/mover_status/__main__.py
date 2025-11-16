"""Application entry point and CLI for mover-status.

This module implements the main entry point for the mover-status application,
providing CLI argument parsing, configuration loading, logging setup, and
orchestrator lifecycle management with graceful shutdown handling.

Requirements:
- 1.1-1.5: Mover process lifecycle monitoring through orchestrator
- 4.1-4.4: Configuration validation and environment variable resolution

Architecture:
- No provider-specific code or references (maintains plugin isolation)
- Uses generic terminology only ("providers", "notification services")
- Configuration and orchestrator handle all provider concerns
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import NoReturn

from mover_status.core.config import (
    ConfigurationError,
    EnvironmentVariableError,
    load_main_config,
)
from mover_status.core.orchestrator import Orchestrator
from mover_status.utils.logging import configure_logging

__all__ = ["main"]

# Default configuration paths
DEFAULT_CONFIG_PATH: Path = Path("config/mover-status.yaml")
DEFAULT_MONITORED_PATHS: tuple[Path, ...] = (Path("/mnt/cache"),)

# Exit codes
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_RUNTIME_ERROR = 1


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for mover-status application.

    Returns:
        Parsed arguments namespace containing configuration options

    CLI Arguments:
        --config, -c: Path to main configuration file
        --dry-run: Enable dry-run mode (log notifications without sending)
        --log-level: Override log level from config
        --no-syslog: Disable syslog integration
        --monitored-paths: Comma-separated list of paths to monitor
    """
    parser = argparse.ArgumentParser(
        prog="mover-status",
        description="Monitor Unraid Mover process and send real-time progress notifications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mover-status
  mover-status --config /path/to/config.yaml
  mover-status --dry-run --log-level DEBUG
  mover-status --no-syslog --monitored-paths /mnt/cache,/mnt/cache2

For more information, see: https://github.com/engels74/mover-status
        """,
    )

    _ = parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to main configuration file (default: {DEFAULT_CONFIG_PATH})",
        metavar="PATH",
    )

    _ = parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run mode: log notifications without sending (overrides config)",
    )

    _ = parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override log level from configuration",
        metavar="LEVEL",
    )

    _ = parser.add_argument(
        "--no-syslog",
        action="store_true",
        help="Disable syslog integration (useful for development)",
    )

    _ = parser.add_argument(
        "--monitored-paths",
        type=str,
        help="Comma-separated list of paths to monitor (overrides config)",
        metavar="PATHS",
    )

    return parser.parse_args()


def parse_monitored_paths(paths_str: str) -> tuple[Path, ...]:
    """Parse comma-separated path string into tuple of Path objects.

    Args:
        paths_str: Comma-separated string of file paths

    Returns:
        Tuple of Path objects

    Example:
        >>> parse_monitored_paths("/mnt/cache,/mnt/cache2")
        (Path('/mnt/cache'), Path('/mnt/cache2'))
    """
    return tuple(Path(p.strip()) for p in paths_str.split(",") if p.strip())


async def async_main(
    *,
    config_path: Path,
    dry_run: bool = False,
    log_level: str | None = None,
    enable_syslog: bool = True,
    monitored_paths: tuple[Path, ...] | None = None,
) -> None:
    """Async main function implementing application lifecycle.

    Args:
        config_path: Path to main configuration file
        dry_run: Enable dry-run mode (override config setting)
        log_level: Override log level from config
        enable_syslog: Enable syslog integration
        monitored_paths: Paths to monitor (override config setting)

    Raises:
        ConfigurationError: If configuration is invalid
        EnvironmentVariableError: If required environment variable is missing
        RuntimeError: If orchestrator fails to start
    """
    # Load and validate configuration
    # Requirement 4.1: Load and validate main YAML configuration file
    logger = logging.getLogger(__name__)
    logger.info("Loading configuration", extra={"config_path": str(config_path)})

    config = load_main_config(config_path)

    # Apply CLI overrides to configuration
    if dry_run:
        config.application.dry_run = True
        logger.info("Dry-run mode enabled via CLI override")

    if log_level is not None:
        config.application.log_level = log_level
        logger.info("Log level overridden via CLI", extra={"log_level": log_level})

    # Configure logging with final settings
    # Requirement 4.1: Configuration loaded and validated
    configure_logging(
        log_level=config.application.log_level,
        enable_syslog=enable_syslog and config.application.syslog_enabled,
        enable_console=True,
    )

    logger = logging.getLogger(__name__)
    logger.info("Mover-status application starting")

    # Determine monitored paths (CLI override or config default)
    paths: tuple[Path, ...] = monitored_paths or DEFAULT_MONITORED_PATHS
    logger.info(
        "Monitoring paths configured",
        extra={"paths": [str(p) for p in paths]},
    )

    # Create orchestrator instance
    # Requirements 1.1-1.5: Orchestrator handles mover lifecycle monitoring
    logger.info("Initializing orchestrator")
    orchestrator = Orchestrator(
        config=config,
        monitored_paths=paths,
    )

    # Setup shutdown handler
    shutdown_requested = False

    def request_shutdown() -> None:
        """Request graceful shutdown of orchestrator."""
        nonlocal shutdown_requested
        if not shutdown_requested:
            shutdown_requested = True
            logger.info("Shutdown signal received, requesting graceful shutdown")
            orchestrator.request_shutdown()

    # Register signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        _ = loop.add_signal_handler(sig, request_shutdown)

    try:
        # Start orchestrator (blocks until shutdown requested)
        # Requirement 1.4: Baseline capture triggered when mover starts
        # Requirement 1.5: Process state tracking maintained
        logger.info("Starting orchestrator")
        await orchestrator.start()

    except Exception as exc:
        logger.exception(
            "Orchestrator failed during execution",
            extra={"error": str(exc)},
        )
        raise

    finally:
        # Cleanup: Remove signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            _ = loop.remove_signal_handler(sig)

        logger.info("Mover-status application shutdown complete")


def main() -> NoReturn:
    """Main entry point for mover-status application.

    Parses command-line arguments, loads configuration, sets up logging,
    creates and runs the orchestrator, and handles graceful shutdown.

    Exit Codes:
        0: Clean shutdown
        1: Configuration error or runtime error

    Requirements:
        - 1.1-1.5: Mover lifecycle monitoring via orchestrator
        - 4.1: Load and validate main configuration
        - 4.2: Provider configs loaded by orchestrator
        - 4.3: Fail-fast validation with actionable errors
        - 4.4: Environment variable resolution
    """
    # Parse command-line arguments
    args = parse_arguments()

    # Parse monitored paths if provided
    cli_monitored_paths: tuple[Path, ...] | None = None
    monitored_paths_arg: str | None = args.monitored_paths  # pyright: ignore[reportAny]  # argparse boundary
    if monitored_paths_arg:
        cli_monitored_paths = parse_monitored_paths(monitored_paths_arg)

    try:
        # Run async main function
        # Requirement 4.3: Fail-fast validation with actionable errors
        # Extract args with type annotations to avoid reportAny at argparse boundary
        config_path_arg: Path = args.config  # pyright: ignore[reportAny]  # argparse boundary
        dry_run_arg: bool = args.dry_run  # pyright: ignore[reportAny]  # argparse boundary
        log_level_arg: str | None = args.log_level  # pyright: ignore[reportAny]  # argparse boundary
        no_syslog_arg: bool = args.no_syslog  # pyright: ignore[reportAny]  # argparse boundary

        asyncio.run(
            async_main(
                config_path=config_path_arg,
                dry_run=dry_run_arg,
                log_level=log_level_arg,
                enable_syslog=not no_syslog_arg,
                monitored_paths=cli_monitored_paths,
            )
        )

    except ConfigurationError as exc:
        # Requirement 4.3: Display actionable error messages
        print(f"Configuration error:\n{exc}", file=sys.stderr)
        sys.exit(EXIT_CONFIG_ERROR)

    except EnvironmentVariableError as exc:
        # Requirement 4.4: Environment variable resolution errors
        print(f"Environment variable error:\n{exc}", file=sys.stderr)
        sys.exit(EXIT_CONFIG_ERROR)

    except RuntimeError as exc:
        # Orchestrator or runtime failure
        print(f"Runtime error: {exc}", file=sys.stderr)
        sys.exit(EXIT_RUNTIME_ERROR)

    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C (already handled by signal handler)
        print("\nShutdown complete", file=sys.stderr)
        sys.exit(EXIT_SUCCESS)

    except Exception as exc:
        # Unexpected error with stack trace
        print(f"Unexpected error: {exc}", file=sys.stderr)
        logging.exception("Unexpected error during application execution")
        sys.exit(EXIT_RUNTIME_ERROR)

    # Normal exit
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
