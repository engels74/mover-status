"""
Command line interface for the Mover Status Monitor.

This module provides the CLI functionality for parsing command line arguments,
handling help and version commands, and supporting provider-specific options.
"""

import sys
import argparse
from typing import final
from collections.abc import Sequence

from mover_status import __version__


@final
class CLIError(Exception):
    """
    Exception raised for CLI-related errors.

    This exception is raised for various CLI-related errors such as
    duplicate option registration or invalid argument configurations.
    """
    pass


@final
class CLIParser:
    """
    Command line interface parser for the Mover Status Monitor.

    This class provides functionality to parse command line arguments,
    handle help and version commands, and support provider-specific options.

    Attributes:
        _parser: The underlying ArgumentParser instance.
        _provider_options: Dictionary tracking provider-specific options.
    """

    def __init__(self) -> None:
        """Initialize the CLI parser."""
        self._parser = argparse.ArgumentParser(
            description="Mover Status Monitor - Track Unraid mover progress and send notifications",
            add_help=False  # We handle help manually
        )
        self._provider_options: dict[str, list[str]] = {}

        # Add core arguments
        self._add_core_arguments()

    def _add_core_arguments(self) -> None:
        """Add core command line arguments."""
        # Configuration options
        _ = self._parser.add_argument(
            "-c", "--config",
            help="Path to configuration file",
            type=str,
            default=None,
            dest="config"
        )

        # Mode options
        _ = self._parser.add_argument(
            "--dry-run",
            help="Run in dry run mode (test notifications without monitoring)",
            action="store_true",
            default=False,
            dest="dry_run"
        )

        _ = self._parser.add_argument(
            "--debug",
            help="Enable debug logging",
            action="store_true",
            default=False,
            dest="debug"
        )

        # Information options
        _ = self._parser.add_argument(
            "-v", "--version",
            help="Show version information and exit",
            action="store_true",
            default=False,
            dest="version"
        )

        _ = self._parser.add_argument(
            "-h", "--help",
            help="Show this help message and exit",
            action="store_true",
            default=False,
            dest="help"
        )

    def register_provider_option(
        self,
        provider_name: str,
        option_name: str,
        **kwargs: object
    ) -> None:
        """
        Register a provider-specific CLI option.

        Args:
            provider_name: Name of the provider.
            option_name: Name of the CLI option (e.g., "--telegram-token").
            **kwargs: Additional arguments passed to add_argument.

        Raises:
            CLIError: If the option is already registered.
        """
        # Check for duplicate registration
        if provider_name in self._provider_options:
            if option_name in self._provider_options[provider_name]:
                raise CLIError(f"Option '{option_name}' is already registered for provider '{provider_name}'")
        else:
            self._provider_options[provider_name] = []

        # Add the option to the parser
        _ = self._parser.add_argument(option_name, **kwargs)  # pyright: ignore[reportArgumentType]

        # Track the option for this provider
        self._provider_options[provider_name].append(option_name)

    def parse_args(self, args: Sequence[str] | None = None) -> argparse.Namespace:
        """
        Parse command line arguments.

        Args:
            args: List of arguments to parse. If None, uses sys.argv.

        Returns:
            Parsed arguments namespace.

        Raises:
            SystemExit: For help, version, or invalid arguments.
        """
        try:
            parsed_args = self._parser.parse_args(args)

            # Handle special commands that should exit
            if hasattr(parsed_args, 'version') and bool(parsed_args.version):  # pyright: ignore[reportAny]
                self._handle_version_command()

            if hasattr(parsed_args, 'help') and bool(parsed_args.help):  # pyright: ignore[reportAny]
                self._handle_help_command()

            return parsed_args

        except SystemExit as e:
            # Re-raise SystemExit for help/version or invalid arguments
            raise e

    def _handle_version_command(self) -> None:
        """
        Handle the version command.

        This function prints the version information and exits.
        """
        print(f"Mover Status Monitor v{__version__}")
        sys.exit(0)

    def _handle_help_command(self) -> None:
        """
        Handle the help command.

        This function prints the help message and exits.
        """
        print(self._parser.format_help())
        sys.exit(0)

    def get_provider_options(self, args: argparse.Namespace, provider_name: str) -> dict[str, object]:
        """
        Extract provider-specific options from parsed arguments.

        Args:
            args: Parsed arguments namespace.
            provider_name: Name of the provider.

        Returns:
            Dictionary of provider-specific options and their values.
        """
        provider_options: dict[str, object] = {}

        if provider_name not in self._provider_options:
            return provider_options

        # Extract options for this provider
        for option_name in self._provider_options[provider_name]:
            # Convert option name to attribute name
            # e.g., "--telegram-token" -> "telegram_token"
            attr_name = option_name.lstrip('-').replace('-', '_')

            if hasattr(args, attr_name):
                value = getattr(args, attr_name)  # pyright: ignore[reportAny]
                if value is not None:
                    provider_options[attr_name] = value

        return provider_options
