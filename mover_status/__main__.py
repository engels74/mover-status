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
from mover_status.application import Application
from mover_status.cli import CLIParser
from mover_status.core.dry_run import run_dry_mode

# Get logger for this module
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments using the new CLIParser.

    Returns:
        argparse.Namespace: The parsed command line arguments.
    """
    cli_parser = CLIParser()
    return cli_parser.parse_args()


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


def initialize_app(config_path: str | None, debug: bool) -> Application:
    """
    Initialize the application using the new Application class.

    Args:
        config_path: Path to the configuration file, or None to use defaults.
        debug: Whether to enable debug logging.

    Returns:
        Initialized Application instance.
    """
    # Create and initialize the application
    app = Application(config_path=config_path, debug=debug)

    # Load and register providers
    app.load_and_register_providers()

    logger.info("Application initialized successfully")
    return app


def main() -> None:
    """
    Main application entry point.

    This function parses command line arguments, initializes the application,
    and runs the monitoring loop or dry run mode as specified.
    """
    # Parse command line arguments using the new CLIParser
    args = parse_args()

    # Initialize application using the new Application class
    app = initialize_app(
        getattr(args, 'config', None),
        bool(getattr(args, 'debug', False))
    )

    try:
        # Run in dry run mode if specified
        if getattr(args, 'dry_run', False):
            logger.info("Running in dry run mode")
            _ = run_dry_mode(app.notification_manager)
        else:
            # Start and run the application
            logger.info("Starting monitoring session")
            app.start()
            app.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
    finally:
        # Stop the application
        if hasattr(app, 'stop'):
            app.stop()
        logger.info("Mover Status Monitor shutting down")


if __name__ == "__main__":
    main()