"""
Tests for the main application entry point.

This module contains tests for the command line interface and application
initialization functionality in the main module.
"""

# pyright: reportAny=false

import sys
import argparse
import pytest
from unittest.mock import patch, MagicMock

# Import the module directly to allow for better patching
from mover_status.__main__ import (
    parse_args,
    handle_version_command,
    handle_help_command,
    main,
    initialize_app,
)
from mover_status import __version__
# We're using the mock_types module for type checking in comments
# but not directly in the code, so we don't need to import it


class TestCommandLineInterface:
    """Tests for the command line interface functionality."""

    def test_parse_args_default(self) -> None:
        """Test parsing command line arguments with default values."""
        with patch.object(sys, 'argv', ['mover-status']):
            # We need to cast the result to our type for type checking
            args = parse_args()
            assert args.config is None
            assert not args.version
            assert not args.help
            assert not args.dry_run
            assert not args.debug

    def test_parse_args_config(self) -> None:
        """Test parsing command line arguments with config file path."""
        with patch.object(sys, 'argv', ['mover-status', '--config', 'test_config.yaml']):
            args = parse_args()
            assert args.config == 'test_config.yaml'
            assert not args.version
            assert not args.help
            assert not args.dry_run
            assert not args.debug

    def test_parse_args_version(self) -> None:
        """Test parsing command line arguments with version flag."""
        with patch.object(sys, 'argv', ['mover-status', '--version']):
            # The new CLIParser exits directly when version is requested
            with pytest.raises(SystemExit) as exc_info:
                _ = parse_args()
            assert exc_info.value.code == 0

    def test_parse_args_help(self) -> None:
        """Test parsing command line arguments with help flag."""
        with patch.object(sys, 'argv', ['mover-status', '--help']):
            # The new CLIParser exits directly when help is requested
            with pytest.raises(SystemExit) as exc_info:
                _ = parse_args()
            assert exc_info.value.code == 0

    def test_parse_args_dry_run(self) -> None:
        """Test parsing command line arguments with dry run flag."""
        with patch.object(sys, 'argv', ['mover-status', '--dry-run']):
            args = parse_args()
            assert args.dry_run
            assert not args.version
            assert not args.help
            assert not args.debug

    def test_parse_args_debug(self) -> None:
        """Test parsing command line arguments with debug flag."""
        with patch.object(sys, 'argv', ['mover-status', '--debug']):
            args = parse_args()
            assert args.debug
            assert not args.version
            assert not args.help
            assert not args.dry_run

    def test_parse_args_multiple(self) -> None:
        """Test parsing command line arguments with multiple flags."""
        with patch.object(sys, 'argv', ['mover-status', '--config', 'test_config.yaml', '--dry-run', '--debug']):
            args = parse_args()
            assert args.config == 'test_config.yaml'
            assert args.dry_run
            assert args.debug
            assert not args.version
            assert not args.help

    def test_handle_version_command(self) -> None:
        """Test handling version command."""
        with patch('builtins.print') as mock_print:
            with patch('sys.exit') as mock_exit:
                handle_version_command()
                mock_print.assert_called_once_with(f"Mover Status Monitor v{__version__}")
                mock_exit.assert_called_once_with(0)

    def test_handle_help_command(self) -> None:
        """Test handling help command."""
        parser = argparse.ArgumentParser(description="Test parser")
        with patch('builtins.print') as mock_print:
            with patch('sys.exit') as mock_exit:
                handle_help_command(parser)
                mock_print.assert_called_once()
                mock_exit.assert_called_once_with(0)


class TestApplicationInitialization:
    """Tests for the application initialization functionality."""

    def test_initialize_app_default(self) -> None:
        """Test initializing the application with default settings."""
        with patch('mover_status.__main__.Application') as mock_application:

            # Setup mocks
            mock_app_instance = MagicMock()
            mock_application.return_value = mock_app_instance

            # Call the function
            app = initialize_app(None, False)

            # Verify Application was initialized correctly
            mock_application.assert_called_once_with(config_path=None, debug=False)

            # Verify load_and_register_providers was called
            mock_app_instance.load_and_register_providers.assert_called_once()

            # Verify we got the application instance back
            assert app == mock_app_instance

    def test_initialize_app_with_config(self) -> None:
        """Test initializing the application with a config file path."""
        with patch('mover_status.__main__.Application') as mock_application:

            # Setup mocks
            mock_app_instance = MagicMock()
            mock_application.return_value = mock_app_instance

            # Call the function
            app = initialize_app("test_config.yaml", False)

            # Verify Application was initialized correctly
            mock_application.assert_called_once_with(config_path="test_config.yaml", debug=False)

            # Verify load_and_register_providers was called
            mock_app_instance.load_and_register_providers.assert_called_once()

            # Verify we got the application instance back
            assert app == mock_app_instance

    def test_initialize_app_with_debug(self) -> None:
        """Test initializing the application with debug mode enabled."""
        with patch('mover_status.__main__.Application') as mock_application:

            # Setup mocks
            mock_app_instance = MagicMock()
            mock_application.return_value = mock_app_instance

            # Call the function with debug=True
            app = initialize_app(None, True)

            # Verify Application was initialized correctly with debug=True
            mock_application.assert_called_once_with(config_path=None, debug=True)

            # Verify load_and_register_providers was called
            mock_app_instance.load_and_register_providers.assert_called_once()

            # Verify we got the application instance back
            assert app == mock_app_instance


class TestMainFunction:
    """Tests for the main function."""

    def test_main_version(self) -> None:
        """Test main function with version flag."""
        with patch.object(sys, 'argv', ['mover-status', '--version']):
            # The new CLIParser exits directly when version is requested
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_help(self) -> None:
        """Test main function with help flag."""
        with patch.object(sys, 'argv', ['mover-status', '--help']):
            # The new CLIParser exits directly when help is requested
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_dry_run(self) -> None:
        """Test main function with dry run flag."""
        with patch.object(sys, 'argv', ['mover-status', '--dry-run']), \
             patch('mover_status.__main__.initialize_app') as mock_init, \
             patch('mover_status.__main__.run_dry_mode') as mock_dry_run:

            # Setup mocks
            mock_app = MagicMock()
            mock_app.notification_manager = MagicMock()
            mock_init.return_value = mock_app

            # Call the function
            main()

            # Verify mocks were called correctly
            mock_init.assert_called_once()
            mock_dry_run.assert_called_once_with(mock_app.notification_manager)

    def test_main_normal_run(self) -> None:
        """Test main function with normal run."""
        with patch.object(sys, 'argv', ['mover-status']), \
             patch('mover_status.__main__.initialize_app') as mock_init:

            # Setup mocks
            mock_app = MagicMock()
            mock_init.return_value = mock_app

            # Call the function
            main()

            # Verify mocks were called correctly
            mock_init.assert_called_once()
            mock_app.start.assert_called_once()
            mock_app.run.assert_called_once()

    def test_main_keyboard_interrupt(self) -> None:
        """Test main function handling keyboard interrupt."""
        with patch.object(sys, 'argv', ['mover-status']), \
             patch('mover_status.__main__.initialize_app') as mock_init, \
             patch('mover_status.__main__.logger') as mock_logger:

            # Setup mocks
            mock_app = MagicMock()
            mock_app.run.side_effect = KeyboardInterrupt()
            mock_init.return_value = mock_app

            # Call the function
            main()

            # Verify logger was called with the expected message
            mock_logger.info.assert_any_call("Received keyboard interrupt, shutting down")

    def test_main_exception_handling(self) -> None:
        """Test main function handling exceptions."""
        with patch.object(sys, 'argv', ['mover-status']), \
             patch('mover_status.__main__.initialize_app') as mock_init, \
             patch('mover_status.__main__.logger') as mock_logger:

            # Setup mocks
            mock_app = MagicMock()
            mock_app.run.side_effect = RuntimeError("Test error")
            mock_init.return_value = mock_app

            # Call the function
            main()

            # Verify logger was called with the expected message
            mock_logger.error.assert_called_once()


class TestMainEntryPointRefactored:
    """Tests for the refactored main entry point using new architecture."""

    def test_initialize_application_with_new_architecture(self) -> None:
        """Test initializing application using the new Application class."""
        with patch('mover_status.__main__.Application') as mock_application, \
             patch('mover_status.__main__.CLIParser') as mock_cli_parser:

            # Setup mocks
            mock_app_instance = MagicMock()
            mock_application.return_value = mock_app_instance

            mock_parser_instance = MagicMock()
            mock_cli_parser.return_value = mock_parser_instance

            # Mock parsed arguments
            mock_args = MagicMock()
            mock_args.config = None
            mock_args.debug = False
            mock_args.dry_run = False
            mock_parser_instance.parse_args.return_value = mock_args

            # Call main function
            main()

            # Verify Application was initialized correctly
            mock_application.assert_called_once_with(config_path=None, debug=False)

            # Verify application lifecycle methods were called
            mock_app_instance.load_and_register_providers.assert_called_once()
            mock_app_instance.start.assert_called_once()
            mock_app_instance.run.assert_called_once()

    def test_handle_command_line_arguments_with_new_cli(self) -> None:
        """Test handling command line arguments using the new CLIParser."""
        with patch('mover_status.__main__.Application') as mock_application, \
             patch('mover_status.__main__.CLIParser') as mock_cli_parser:

            # Setup mocks
            mock_app_instance = MagicMock()
            mock_application.return_value = mock_app_instance

            mock_parser_instance = MagicMock()
            mock_cli_parser.return_value = mock_parser_instance

            # Mock parsed arguments with config and debug
            mock_args = MagicMock()
            mock_args.config = "/test/config.yaml"
            mock_args.debug = True
            mock_args.dry_run = False
            mock_parser_instance.parse_args.return_value = mock_args

            # Call main function
            main()

            # Verify CLIParser was used
            mock_cli_parser.assert_called_once()
            mock_parser_instance.parse_args.assert_called_once()

            # Verify Application was initialized with correct arguments
            mock_application.assert_called_once_with(config_path="/test/config.yaml", debug=True)

    def test_run_application_with_new_architecture(self) -> None:
        """Test running application with the new architecture."""
        with patch('mover_status.__main__.Application') as mock_application, \
             patch('mover_status.__main__.CLIParser') as mock_cli_parser, \
             patch('mover_status.__main__.run_dry_mode') as mock_dry_run:

            # Setup mocks
            mock_app_instance = MagicMock()
            mock_application.return_value = mock_app_instance

            mock_parser_instance = MagicMock()
            mock_cli_parser.return_value = mock_parser_instance

            # Mock parsed arguments for dry run mode
            mock_args = MagicMock()
            mock_args.config = None
            mock_args.debug = False
            mock_args.dry_run = True
            mock_parser_instance.parse_args.return_value = mock_args

            # Call main function
            main()

            # Verify Application was initialized
            mock_application.assert_called_once_with(config_path=None, debug=False)

            # Verify providers were loaded but application wasn't started for dry run
            mock_app_instance.load_and_register_providers.assert_called_once()
            mock_app_instance.start.assert_not_called()
            mock_app_instance.run.assert_not_called()

            # Verify dry run mode was executed
            mock_dry_run.assert_called_once_with(mock_app_instance.notification_manager)
