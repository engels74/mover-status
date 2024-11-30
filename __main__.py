#!/usr/bin/env python3

# main.py

"""
MoverStatus application entry point.

This module serves as the main entry point for the MoverStatus application.
It handles command-line argument parsing, configuration loading, logging setup,
and the main monitoring execution loop.

Example:
    $ python -m mover_status --config config.yml
    $ python -m mover_status --debug
"""


import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import List, NoReturn, Optional

import structlog
from structlog.stdlib import LoggerFactory
from structlog.types import Processor

from config.settings import Settings
from core.monitor import MoverMonitor
from utils.version import version_checker

# Initialize structured logging
processors: List[Processor] = [
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.dev.ConsoleRenderer()
]

structlog.configure(
    processors=processors,
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed command-line arguments
    """
    parser = argparse.ArgumentParser(
        description="Monitor Unraid Mover process and send notifications"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file",
        default=None
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without sending notifications"
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Path to log file (enables file logging)",
        default=None
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current mover status and exit"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send test notifications and exit"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information"
    )
    return parser.parse_args()

def setup_logging(debug: bool = False, log_file: Optional[Path] = None) -> None:
    """Configure logging level and format.

    Args:
        debug: Enable debug logging if True
        log_file: Optional path to log file
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Configure structlog
    processors = [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_file:
        # Add file logging
        file_handler = logging.FileHandler(str(log_file))
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        logging.getLogger().addHandler(file_handler)
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    # Configure logging
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )

async def check_version() -> None:
    """Check for available updates from the repository.

    This function checks the current version against the latest available version
    and logs a message if an update is available.

    Raises:
        Exception: If the version check fails, the error is logged as a warning.
    """
    try:
        update_available, latest_version = await version_checker.check_for_updates()
        if update_available:
            logger.info(
                "Update available",
                current_version=str(version_checker.current_version),
                latest_version=latest_version
            )
    except Exception as err:
        logger.warning("Failed to check for updates", error=str(err))

async def shutdown(monitor: MoverMonitor) -> None:
    """Gracefully shutdown the application.

    Args:
        monitor: Active monitor instance to stop
    """
    logger.info("Shutting down...")
    try:
        await monitor.stop()
    except Exception as err:
        logger.error("Error during shutdown", error=str(err))

def handle_signal(monitor: MoverMonitor, loop: asyncio.AbstractEventLoop) -> None:
    """Handle system signals for graceful shutdown.

    Args:
        monitor: Active monitor instance
        loop: Current event loop
    """
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(shutdown(monitor))
        )

async def run_monitor(settings: Settings) -> None:
    """Run the main monitoring loop with signal handling.

    This function initializes and runs the mover monitor, setting up signal handlers
    for graceful shutdown. It runs indefinitely until interrupted or an error occurs.

    Args:
        settings: Application settings including monitoring and notification configuration.

    Raises:
        Exception: If a monitor error occurs, it's logged and the application exits.
    """
    monitor = MoverMonitor(settings)

    # Setup signal handlers
    loop = asyncio.get_running_loop()
    handle_signal(monitor, loop)

    try:
        await monitor.start()
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await monitor.stop()
    except Exception as err:
        logger.error("Monitor error", error=str(err))
        await monitor.stop()
        sys.exit(1)

async def show_status(settings: Settings) -> None:
    """Display current mover status and exit.

    Args:
        settings: Application settings
    """
    monitor = MoverMonitor(settings)
    try:
        is_running = await monitor._process_manager.is_running()
        if is_running:
            print("Mover is currently running")
            if monitor._calculator.stats:
                stats = monitor._calculator.stats
                print(f"Progress: {stats.percent_complete:.1f}%")
                print(f"Remaining: {stats.remaining_formatted}")
                print(f"ETC: {stats.etc_formatted}")
        else:
            print("Mover is not running")
    finally:
        await monitor.stop()

async def test_notifications(settings: Settings) -> None:
    """Send test notifications and exit.

    Args:
        settings: Application settings
    """
    monitor = MoverMonitor(settings)
    try:
        await monitor._setup_providers()
        await monitor._send_notifications(
            monitor._calculator.stats,
            force=True
        )
        print("Test notifications sent successfully")
    except Exception as err:
        print(f"Failed to send test notifications: {err}")
    finally:
        await monitor.stop()

def main() -> NoReturn:
    """Application entry point and main execution flow.

    This function handles the main execution flow including:
    - Command-line argument parsing
    - Configuration loading from YAML (if specified)
    - Logging setup
    - Version checking
    - Monitor initialization and execution

    The function never returns normally, instead exiting with an appropriate
    status code based on execution success or failure.

    Raises:
        SystemExit: With status code 0 for normal exit, 1 for errors.
    """
    args = parse_args()

    # Show version and exit if requested
    if args.version:
        print(f"MoverStatus v{version_checker.current_version}")
        sys.exit(0)

    # Setup logging
    setup_logging(args.debug, args.log_file)
    logger.info(
        "Starting MoverStatus",
        version=str(version_checker.current_version),
        debug=args.debug,
        dry_run=args.dry_run
    )

    try:
        # Load settings
        settings = Settings()
        if args.config:
            if not args.config.exists():
                logger.error(f"Config file not found: {args.config}")
                sys.exit(1)
            try:
                settings = Settings.from_yaml(args.config)
            except Exception as err:
                logger.error(f"Failed to load config: {err}")
                sys.exit(1)

        # Override settings from command line
        settings.logging.debug_mode = args.debug
        settings.dry_run = args.dry_run

        # Handle special commands
        if args.status:
            asyncio.run(show_status(settings))
            sys.exit(0)
        elif args.test:
            asyncio.run(test_notifications(settings))
            sys.exit(0)

        # Run the monitor
        asyncio.run(run_monitor(settings))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as err:
        logger.error("Fatal error", error=str(err))
        sys.exit(1)

if __name__ == "__main__":
    main()
