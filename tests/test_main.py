"""
Tests for the main application entry point.

This module contains tests for the command line interface and application
initialization functionality in the main module.
"""

import sys
import argparse
import pytest
from typing import Any, cast
from unittest.mock import patch, MagicMock, call

# Import the module directly to allow for better patching
import mover_status.__main__
from mover_status.__main__ import (
    parse_args,
    handle_version_command,
    handle_help_command,
    main,
    initialize_app,
)
from mover_status import __version__
from mover_status.utils.logger import LogLevel, LogFormat
from mover_status.notification.providers.telegram.provider import TelegramProvider
from mover_status.notification.providers.discord.provider import DiscordProvider


class TestCommandLineInterface:
    """Tests for the command line interface functionality."""

    def test_parse_args_default(self) -> None:
        """Test parsing command line arguments with default values."""
        with patch.object(sys, 'argv', ['mover-status']):
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
            args = parse_args()
            assert args.version
            assert not args.help
            assert not args.dry_run
            assert not args.debug

    def test_parse_args_help(self) -> None:
        """Test parsing command line arguments with help flag."""
        with patch.object(sys, 'argv', ['mover-status', '--help']):
            args = parse_args()
            assert args.help
            assert not args.version
            assert not args.dry_run
            assert not args.debug

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
        with patch('mover_status.__main__.ConfigManager') as mock_config_manager, \
             patch('mover_status.__main__.setup_logger') as mock_setup_logger, \
             patch('mover_status.__main__.NotificationManager') as mock_notification_manager, \
             patch('mover_status.__main__.check_for_updates') as mock_check_updates:

            # Setup mocks
            mock_config_instance = MagicMock()
            mock_config_manager.return_value = mock_config_instance
            mock_config_instance.load.return_value = mock_config_instance
            mock_config_instance.config.get_nested_value.return_value = []

            # Mock check_for_updates to avoid network calls
            mock_check_updates.return_value = False

            # Create a mock for the notification manager
            mock_notification_instance = MagicMock()
            mock_notification_manager.return_value = mock_notification_instance

            # Call the function
            config_manager, notification_manager = initialize_app(None, False)

            # Verify ConfigManager was initialized correctly
            mock_config_manager.assert_called_once_with(None)
            mock_config_instance.load.assert_called_once()

            # Verify logger was set up correctly
            mock_setup_logger.assert_called_once()
            logger_config = mock_setup_logger.call_args[0][1]
            assert logger_config.console_enabled is True
            assert logger_config.level == LogLevel.INFO
            assert logger_config.format == LogFormat.SIMPLE

            # Verify NotificationManager was initialized
            mock_notification_manager.assert_called_once()
            assert notification_manager == mock_notification_instance

            # Verify no providers were registered (default behavior)
            assert mock_notification_instance.register_provider.call_count == 0

    def test_initialize_app_with_config(self) -> None:
        """Test initializing the application with a config file path."""
        with patch('mover_status.__main__.ConfigManager') as mock_config_manager, \
             patch('mover_status.__main__.setup_logger') as mock_setup_logger, \
             patch('mover_status.__main__.NotificationManager') as mock_notification_manager, \
             patch('mover_status.__main__.TelegramProvider') as mock_telegram_provider, \
             patch('mover_status.__main__.DiscordProvider') as mock_discord_provider, \
             patch('mover_status.__main__.check_for_updates') as mock_check_updates:

            # Setup mocks
            mock_config_instance = MagicMock()
            mock_config_manager.return_value = mock_config_instance
            mock_config_instance.load.return_value = mock_config_instance

            # Mock check_for_updates to avoid network calls
            mock_check_updates.return_value = False

            # Create a mock for the notification manager
            mock_notification_instance = MagicMock()
            mock_notification_manager.return_value = mock_notification_instance

            # Mock the validate_config method to return empty list (no errors)
            mock_telegram_provider_instance = MagicMock()
            mock_telegram_provider_instance.validate_config.return_value = []
            mock_telegram_provider_instance.enabled = True
            mock_telegram_provider.return_value = mock_telegram_provider_instance

            mock_discord_provider_instance = MagicMock()
            mock_discord_provider_instance.validate_config.return_value = []
            mock_discord_provider_instance.enabled = True
            mock_discord_provider.return_value = mock_discord_provider_instance

            # Mock enabled providers list with valid configurations
            mock_config_instance.config.get_nested_value.side_effect = lambda key: {
                "notification.enabled_providers": ["telegram", "discord"],
                "notification.providers.telegram": {
                    "enabled": True,
                    "bot_token": "test_token",
                    "chat_id": "test_id",
                    "message_template": "test message",
                    "parse_mode": "HTML",
                    "disable_notification": False
                },
                "notification.providers.discord": {
                    "enabled": True,
                    "webhook_url": "https://discord.com/api/webhooks/test",
                    "username": "Test Bot",
                    "message_template": "test message",
                    "use_embeds": True,
                    "embed_title": "Test Title",
                    "embed_colors": {
                        "low_progress": 123,
                        "mid_progress": 456,
                        "high_progress": 789,
                        "complete": 101112
                    }
                }
            }.get(key, [])

            # Call the function
            config_manager, notification_manager = initialize_app("test_config.yaml", False)

            # Verify ConfigManager was initialized correctly
            mock_config_manager.assert_called_once_with("test_config.yaml")
            mock_config_instance.load.assert_called_once()

            # Verify logger was set up correctly
            mock_setup_logger.assert_called_once()

            # Verify NotificationManager was initialized
            mock_notification_manager.assert_called_once()
            assert notification_manager == mock_notification_instance

            # Verify providers were registered
            assert mock_notification_instance.register_provider.call_count == 2
            mock_telegram_provider.assert_called_once()
            mock_discord_provider.assert_called_once()

    def test_initialize_app_with_debug(self) -> None:
        """Test initializing the application with debug mode enabled."""
        with patch('mover_status.__main__.ConfigManager') as mock_config_manager, \
             patch('mover_status.__main__.setup_logger') as mock_setup_logger, \
             patch('mover_status.__main__.NotificationManager') as mock_notification_manager, \
             patch('mover_status.__main__.check_for_updates') as mock_check_updates:

            # Setup mocks
            mock_config_instance = MagicMock()
            mock_config_manager.return_value = mock_config_instance
            mock_config_instance.load.return_value = mock_config_instance
            mock_config_instance.config.get_nested_value.return_value = []

            # Mock check_for_updates to avoid network calls
            mock_check_updates.return_value = False

            # Create a mock for the notification manager
            mock_notification_instance = MagicMock()
            mock_notification_manager.return_value = mock_notification_instance

            # Call the function with debug=True
            config_manager, notification_manager = initialize_app(None, True)

            # Verify logger was set up with debug settings
            mock_setup_logger.assert_called_once()
            logger_config = mock_setup_logger.call_args[0][1]
            assert logger_config.level == LogLevel.DEBUG
            assert logger_config.format == LogFormat.DETAILED

            # Verify NotificationManager was initialized
            mock_notification_manager.assert_called_once()
            assert notification_manager == mock_notification_instance


class TestMainFunction:
    """Tests for the main function."""

    def test_main_version(self) -> None:
        """Test main function with version flag."""
        with patch.object(sys, 'argv', ['mover-status', '--version']), \
             patch('mover_status.__main__.handle_version_command') as mock_version:
            main()
            mock_version.assert_called_once()

    def test_main_help(self) -> None:
        """Test main function with help flag."""
        with patch.object(sys, 'argv', ['mover-status', '--help']), \
             patch('mover_status.__main__.handle_help_command') as mock_help:
            main()
            mock_help.assert_called_once()

    def test_main_dry_run(self) -> None:
        """Test main function with dry run flag."""
        with patch.object(sys, 'argv', ['mover-status', '--dry-run']), \
             patch('mover_status.__main__.initialize_app') as mock_init, \
             patch('mover_status.__main__.run_dry_mode') as mock_dry_run:

            # Setup mocks
            mock_config = MagicMock()
            mock_notification = MagicMock()
            mock_init.return_value = (mock_config, mock_notification)

            # Call the function
            main()

            # Verify mocks were called correctly
            mock_init.assert_called_once()
            mock_dry_run.assert_called_once_with(mock_notification)

    def test_main_normal_run(self) -> None:
        """Test main function with normal run."""
        with patch.object(sys, 'argv', ['mover-status']), \
             patch('mover_status.__main__.initialize_app') as mock_init, \
             patch('mover_status.__main__.MonitorSession') as mock_monitor_session:

            # Setup mocks
            mock_config = MagicMock()
            mock_notification = MagicMock()
            mock_init.return_value = (mock_config, mock_notification)

            # Mock config values
            mock_config.config.get_nested_value.side_effect = lambda key: {
                "monitoring.mover_executable": "/test/mover",
                "monitoring.cache_directory": "/test/cache",
                "paths.exclude": ["/test/exclude"],
                "notification.notification_increment": 20,
                "monitoring.poll_interval": 2.5
            }.get(key, None)

            # Mock monitor session
            mock_session = MagicMock()
            mock_monitor_session.return_value = mock_session

            # Call the function
            main()

            # Verify mocks were called correctly
            mock_init.assert_called_once()
            mock_monitor_session.assert_called_once_with(
                mover_path="/test/mover",
                cache_path="/test/cache",
                exclusions=["/test/exclude"],
                notification_increment=20,
                poll_interval=2.5
            )
            mock_session.run_monitoring_loop.assert_called_once_with(mock_notification)

    def test_main_keyboard_interrupt(self) -> None:
        """Test main function handling keyboard interrupt."""
        with patch.object(sys, 'argv', ['mover-status']), \
             patch('mover_status.__main__.initialize_app') as mock_init, \
             patch('mover_status.__main__.MonitorSession') as mock_monitor_session, \
             patch('mover_status.__main__.logger') as mock_logger:

            # Setup mocks
            mock_config = MagicMock()
            mock_notification = MagicMock()
            mock_init.return_value = (mock_config, mock_notification)

            # Mock config values
            mock_config.config.get_nested_value.return_value = "/test/path"

            # Mock monitor session to raise KeyboardInterrupt
            mock_session = MagicMock()
            mock_session.run_monitoring_loop.side_effect = KeyboardInterrupt()
            mock_monitor_session.return_value = mock_session

            # Call the function
            main()

            # Verify logger was called with the expected message
            mock_logger.info.assert_any_call("Received keyboard interrupt, shutting down")

    def test_main_exception_handling(self) -> None:
        """Test main function handling exceptions."""
        with patch.object(sys, 'argv', ['mover-status']), \
             patch('mover_status.__main__.initialize_app') as mock_init, \
             patch('mover_status.__main__.MonitorSession') as mock_monitor_session, \
             patch('mover_status.__main__.logger') as mock_logger:

            # Setup mocks
            mock_config = MagicMock()
            mock_notification = MagicMock()
            mock_init.return_value = (mock_config, mock_notification)

            # Mock config values
            mock_config.config.get_nested_value.return_value = "/test/path"

            # Mock monitor session to raise an exception
            mock_session = MagicMock()
            mock_session.run_monitoring_loop.side_effect = RuntimeError("Test error")
            mock_monitor_session.return_value = mock_session

            # Call the function
            main()

            # Verify logger was called with the expected message
            mock_logger.error.assert_called_once()
