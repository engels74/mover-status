"""
Tests for the CLI module.

This module contains tests for the command line interface functionality,
including argument parsing, help/version commands, and provider-specific options.
"""

import pytest
from unittest.mock import patch

from mover_status.cli import CLIParser, CLIError


class TestCLIParser:
    """Test cases for the CLIParser class."""

    def test_parse_basic_arguments(self) -> None:
        """Test case: Parse command line arguments."""
        parser = CLIParser()

        # Test basic arguments
        args = parser.parse_args(["-c", "config.yaml", "--debug"])
        assert args.config == "config.yaml"  # pyright: ignore[reportAny]
        assert args.debug is True  # pyright: ignore[reportAny]
        assert args.dry_run is False  # pyright: ignore[reportAny]

        # Test dry run argument
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True  # pyright: ignore[reportAny]
        assert args.debug is False  # pyright: ignore[reportAny]

    def test_handle_version_command(self) -> None:
        """Test case: Handle version command."""
        parser = CLIParser()

        with patch('builtins.print') as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                _ = parser.parse_args(["--version"])

        assert exc_info.value.code == 0
        mock_print.assert_called_once()
        # Check that version information is printed
        printed_text = str(mock_print.call_args[0][0])  # pyright: ignore[reportAny]
        assert "Mover Status Monitor" in printed_text

    def test_handle_help_command(self) -> None:
        """Test case: Handle help command."""
        parser = CLIParser()

        with patch('builtins.print') as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                _ = parser.parse_args(["--help"])

        assert exc_info.value.code == 0
        mock_print.assert_called_once()
        # Check that help information is printed
        printed_text = str(mock_print.call_args[0][0])  # pyright: ignore[reportAny]
        assert "usage:" in printed_text.lower()

    def test_support_provider_specific_options(self) -> None:
        """Test case: Support provider-specific options."""
        parser = CLIParser()

        # Register a provider-specific option
        parser.register_provider_option(
            "telegram",
            "--telegram-token",
            help="Telegram bot token",
            dest="telegram_token"
        )

        # Test parsing provider-specific option
        args = parser.parse_args(["--telegram-token", "test-token"])
        assert hasattr(args, 'telegram_token')
        assert args.telegram_token == "test-token"  # pyright: ignore[reportAny]

    def test_register_provider_specific_cli_options(self) -> None:
        """Test case: Register provider-specific CLI options."""
        parser = CLIParser()

        # Test registering multiple provider options
        parser.register_provider_option(
            "discord",
            "--discord-webhook",
            help="Discord webhook URL",
            dest="discord_webhook"
        )

        parser.register_provider_option(
            "telegram",
            "--telegram-chat-id",
            help="Telegram chat ID",
            dest="telegram_chat_id"
        )

        # Test that options are registered
        args = parser.parse_args([
            "--discord-webhook", "https://discord.com/api/webhooks/test",
            "--telegram-chat-id", "123456789"
        ])

        assert args.discord_webhook == "https://discord.com/api/webhooks/test"  # pyright: ignore[reportAny]
        assert args.telegram_chat_id == "123456789"  # pyright: ignore[reportAny]

    def test_parse_provider_specific_options(self) -> None:
        """Test case: Parse provider-specific options."""
        parser = CLIParser()

        # Register provider options
        parser.register_provider_option(
            "telegram",
            "--telegram-enabled",
            action="store_true",
            help="Enable Telegram notifications"
        )

        # Test parsing boolean provider option
        args = parser.parse_args(["--telegram-enabled"])
        assert args.telegram_enabled is True  # pyright: ignore[reportAny]

    def test_pass_options_to_provider_initialization(self) -> None:
        """Test case: Pass options to provider initialization."""
        parser = CLIParser()

        # Register provider options
        parser.register_provider_option(
            "telegram",
            "--telegram-token",
            help="Telegram bot token"
        )
        parser.register_provider_option(
            "telegram",
            "--telegram-chat-id",
            help="Telegram chat ID"
        )

        # Parse arguments
        args = parser.parse_args([
            "--telegram-token", "test-token",
            "--telegram-chat-id", "123456789"
        ])

        # Test extracting provider-specific options
        telegram_options = parser.get_provider_options(args, "telegram")
        expected_options: dict[str, object] = {
            "telegram_token": "test-token",
            "telegram_chat_id": "123456789"
        }

        assert telegram_options == expected_options

    def test_cli_error_handling(self) -> None:
        """Test case: Handle CLI errors properly."""
        parser = CLIParser()

        # Test invalid argument
        with pytest.raises(SystemExit):
            _ = parser.parse_args(["--invalid-argument"])

    def test_default_values(self) -> None:
        """Test case: Verify default values for arguments."""
        parser = CLIParser()

        # Test default values
        args = parser.parse_args([])
        assert args.config is None  # pyright: ignore[reportAny]
        assert args.debug is False  # pyright: ignore[reportAny]
        assert args.dry_run is False  # pyright: ignore[reportAny]
        assert args.version is False  # pyright: ignore[reportAny]
        assert args.help is False  # pyright: ignore[reportAny]

    def test_duplicate_provider_option_registration(self) -> None:
        """Test case: Handle duplicate provider option registration."""
        parser = CLIParser()

        # Register an option
        parser.register_provider_option(
            "telegram",
            "--telegram-token",
            help="Telegram bot token"
        )

        # Try to register the same option again
        with pytest.raises(CLIError):
            parser.register_provider_option(
                "telegram",
                "--telegram-token",
                help="Duplicate telegram bot token"
            )

    def test_get_provider_options_for_nonexistent_provider(self) -> None:
        """Test case: Get provider options for non-existent provider."""
        parser = CLIParser()
        args = parser.parse_args([])

        # Test getting options for a provider that has no registered options
        options = parser.get_provider_options(args, "nonexistent")
        assert options == {}
