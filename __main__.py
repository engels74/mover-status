#!/usr/bin/env python3

# main.py

"""
MoverStatus application entry point.
Handles command-line arguments, configuration, logging setup, and main execution loop.

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
from typing import NoReturn

import structlog
from structlog.stdlib import LoggerFactory

from config.settings import Settings
from core.monitor import MoverMonitor
from utils.version import version_checker

# Initialize structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ],
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
        "--version",
        action="store_true",
        help="Show version information"
    )
    return parser.parse_args()

def setup_logging(debug: bool = False) -> None:
    """Configure logging level and format.

    Args:
        debug: Enable debug logging if True
    """
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

async def check_version() -> None:
    """Check for available updates."""
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
    """Run the main monitoring loop.

    Args:
        settings: Application settings
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

def main() -> NoReturn:
    """Application entry point."""
    args = parse_args()

    # Show version and exit if requested
    if args.version:
        print(f"MoverStatus v{version_checker.current_version}")
        sys.exit(0)

    # Setup logging
    setup_logging(args.debug)
    logger.info("Starting MoverStatus")

    try:
        # Load settings
        settings = Settings()
        if args.config:
            settings = Settings.from_yaml(args.config)

        # Override settings from command line
        settings.logging.debug_mode = args.debug
        settings.dry_run = args.dry_run

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
