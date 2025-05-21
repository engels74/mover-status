"""
Main application entry point for the Mover Status Monitor.

This module provides the command line interface and main application loop
for the Mover Status Monitor. It handles command line arguments, initializes
the application components, and runs the monitoring loop.
"""

import sys
import argparse
import logging

from mover_status import __version__
from mover_status.config.config_manager import ConfigManager
from mover_status.utils.logger import setup_logger, LoggerConfig, LogLevel, LogFormat
from mover_status.notification.manager import NotificationManager
from mover_status.core.monitor import MonitorSession
from mover_status.core.dry_run import run_dry_mode

# Get logger for this module
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: The parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Mover Status Monitor - Track Unraid mover progress and send notifications",
        add_help=False  # Disable built-in help to handle it manually
    )

    # Configuration options
    _ = parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        type=str,
        default=None
    )

    # Mode options
    _ = parser.add_argument(
        "--dry-run",
        help="Run in dry run mode (test notifications without monitoring)",
        action="store_true",
        default=False
    )

    _ = parser.add_argument(
        "--debug",
        help="Enable debug logging",
        action="store_true",
        default=False
    )

    # Information options
    _ = parser.add_argument(
        "-v", "--version",
        help="Show version information and exit",
        action="store_true",
        default=False
    )

    _ = parser.add_argument(
        "-h", "--help",
        help="Show this help message and exit",
        action="store_true",
        default=False
    )

    return parser.parse_args()


def handle_version_command() -> None:
    """
    Handle the version command.

    This function prints the version information and exits.
    """
    print(f"Mover Status Monitor v{__version__}")
    sys.exit(0)


def handle_help_command(parser: argparse.ArgumentParser) -> None:
    """
    Handle the help command.

    This function prints the help message and exits.

    Args:
        parser: The argument parser to get help from.
    """
    print(parser.format_help())
    sys.exit(0)


def initialize_app(config_path: str | None, debug: bool) -> tuple[ConfigManager, NotificationManager]:
    """
    Initialize the application components.

    This function initializes the configuration manager, sets up logging,
    and initializes the notification manager.

    Args:
        config_path: Path to the configuration file, or None to use defaults.
        debug: Whether to enable debug logging.

    Returns:
        Tuple containing the initialized ConfigManager and NotificationManager.
    """
    # Initialize configuration manager
    config_manager = ConfigManager(config_path)
    _ = config_manager.load()

    # Set up logging
    log_config = LoggerConfig(
        console_enabled=True,
        level=LogLevel.DEBUG if debug else LogLevel.INFO,
        format=LogFormat.DETAILED if debug else LogFormat.SIMPLE
    )
    _ = setup_logger("mover_status", log_config)
    logger.info("Mover Status Monitor starting up")
    logger.info(f"Version: {__version__}")

    # Initialize notification manager
    notification_manager = NotificationManager()
    logger.info("Notification manager initialized")

    return config_manager, notification_manager


def main() -> None:
    """
    Main application entry point.

    This function parses command line arguments, initializes the application,
    and runs the monitoring loop or dry run mode as specified.
    """
    # Parse command line arguments
    args = parse_args()

    # Create parser for help command
    parser = argparse.ArgumentParser(
        description="Mover Status Monitor - Track Unraid mover progress and send notifications",
        add_help=False
    )
    _ = parser.add_argument("-c", "--config", help="Path to configuration file")
    _ = parser.add_argument("--dry-run", help="Run in dry run mode (test notifications without monitoring)", action="store_true")
    _ = parser.add_argument("--debug", help="Enable debug logging", action="store_true")
    _ = parser.add_argument("-v", "--version", help="Show version information and exit", action="store_true")
    _ = parser.add_argument("-h", "--help", help="Show this help message and exit", action="store_true")

    # Handle information commands
    if getattr(args, 'version', False):
        handle_version_command()
    if getattr(args, 'help', False):
        handle_help_command(parser)

    # Initialize application
    config_manager, notification_manager = initialize_app(
        getattr(args, 'config', None),
        bool(getattr(args, 'debug', False))
    )

    try:
        # Run in dry run mode if specified
        if getattr(args, 'dry_run', False):
            logger.info("Running in dry run mode")
            _ = run_dry_mode(notification_manager)
        else:
            # Create and run monitor session
            logger.info("Starting monitoring session")

            # Get configuration values with proper type casting
            mover_path = str(config_manager.config.get_nested_value("monitoring.mover_executable"))
            cache_path = str(config_manager.config.get_nested_value("monitoring.cache_directory"))

            # Handle exclusions list
            exclusions_obj = config_manager.config.get_nested_value("paths.exclude")
            exclusions: list[str] | None = None
            if isinstance(exclusions_obj, list):
                # Convert to a list of strings, filtering out non-string items
                exclusions = []
                # Cast to satisfy the type checker
                exclusions_list = exclusions_obj  # pyright: ignore[reportUnknownVariableType]

                # Process each item, checking its type
                for item in exclusions_list:  # pyright: ignore[reportUnknownVariableType]
                    if isinstance(item, str):
                        exclusions.append(item)

            # Get numeric values with safe conversion
            notification_increment_obj = config_manager.config.get_nested_value("notification.notification_increment")
            notification_increment = 25  # Default value
            if isinstance(notification_increment_obj, (int, float, str)):
                try:
                    notification_increment = int(notification_increment_obj)
                except (ValueError, TypeError):
                    pass

            poll_interval_obj = config_manager.config.get_nested_value("monitoring.poll_interval")
            poll_interval = 1.0  # Default value
            if isinstance(poll_interval_obj, (int, float, str)):
                try:
                    poll_interval = float(poll_interval_obj)
                except (ValueError, TypeError):
                    pass

            # Create and run monitor session
            monitor_session = MonitorSession(
                mover_path=mover_path,
                cache_path=cache_path,
                exclusions=exclusions,
                notification_increment=notification_increment,
                poll_interval=poll_interval,
            )
            monitor_session.run_monitoring_loop(notification_manager)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
    finally:
        logger.info("Mover Status Monitor shutting down")


if __name__ == "__main__":
    main()