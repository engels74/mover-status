"""
Tests for the Discord notification provider.

This module contains tests for the Discord notification provider, including
the formatter module and the provider implementation.
"""

# pyright: reportTypedDictNotRequiredAccess=false

import time
from unittest.mock import patch, MagicMock

import pytest
import requests

from mover_status.notification.formatter import RawValues
from mover_status.notification.providers.discord.formatter import (
    format_discord_message,
    format_discord_eta,
    format_markdown_text,
    format_timestamp_for_discord,
    create_embed,
)
from mover_status.notification.providers.discord.provider import (
    DiscordProvider,
    DiscordConfig,
)


class TestDiscordFormatter:
    """Test cases for the Discord formatter module."""

    def test_format_markdown_text(self) -> None:
        """Test formatting text with markdown for Discord."""
        # Test basic text formatting
        assert format_markdown_text("Test") == "Test"

        # Test bold formatting
        assert format_markdown_text("Test", bold=True) == "**Test**"

        # Test italic formatting
        assert format_markdown_text("Test", italic=True) == "*Test*"

        # Test combined formatting
        assert format_markdown_text("Test", bold=True, italic=True) == "***Test***"

        # Test code formatting
        assert format_markdown_text("Test", code=True) == "`Test`"

        # Test code block formatting
        assert format_markdown_text("Test", code_block=True) == "```\nTest\n```"

        # Test underline formatting
        assert format_markdown_text("Test", underline=True) == "__Test__"

        # Test strikethrough formatting
        assert format_markdown_text("Test", strikethrough=True) == "~~Test~~"

        # Test complex combinations
        assert format_markdown_text("Test", bold=True, code=True) == "**`Test`**"

    def test_format_discord_eta(self) -> None:
        """Test formatting ETA for Discord."""
        # Test None ETA (still calculating)
        assert format_discord_eta(None) == "Calculating..."

        # Test with a specific timestamp
        # Create a timestamp for testing (e.g., 1 hour from now)
        current_time = time.time()
        future_time = current_time + 3600  # 1 hour in the future

        # Format the expected result for Discord's timestamp format
        expected_format = f"<t:{int(future_time)}:R>"

        # Test the formatter
        assert format_discord_eta(future_time) == expected_format

    def test_format_discord_message_with_raw_values(self) -> None:
        """Test formatting a message with raw values for Discord."""
        # Define a template with markdown formatting
        template = (
            "Moving data from SSD Cache to HDD Array.\n"
            "Progress: **{percent}** complete.\n"
            "Remaining data: {remaining_data}.\n"
            "Estimated completion time: {etc}.\n\n"
            "Note: Services like Plex may run slow or be unavailable during the move."
        )

        # Define raw values
        raw_values: RawValues = {
            "percent": 50,
            "remaining_bytes": 1073741824,  # 1 GB
            "eta": None,
        }

        # Format the message
        formatted_message = format_discord_message(template, raw_values)

        # Check that the message contains expected formatted values
        assert "**50%**" in formatted_message
        assert "1.0 GB" in formatted_message
        assert "Calculating..." in formatted_message
        assert "\n" in formatted_message  # Newline character

    def test_format_timestamp_for_discord(self) -> None:
        """Test formatting a timestamp for Discord."""
        # Create a specific timestamp for testing
        test_timestamp = 1609459200  # 2021-01-01 00:00:00 UTC

        # Format the timestamp with different Discord timestamp styles
        relative_format = format_timestamp_for_discord(test_timestamp, "R")
        short_time_format = format_timestamp_for_discord(test_timestamp, "t")
        long_time_format = format_timestamp_for_discord(test_timestamp, "T")
        short_date_format = format_timestamp_for_discord(test_timestamp, "d")
        long_date_format = format_timestamp_for_discord(test_timestamp, "D")
        short_datetime_format = format_timestamp_for_discord(test_timestamp, "f")
        long_datetime_format = format_timestamp_for_discord(test_timestamp, "F")

        # Check the format of each style
        assert relative_format == f"<t:{test_timestamp}:R>"
        assert short_time_format == f"<t:{test_timestamp}:t>"
        assert long_time_format == f"<t:{test_timestamp}:T>"
        assert short_date_format == f"<t:{test_timestamp}:d>"
        assert long_date_format == f"<t:{test_timestamp}:D>"
        assert short_datetime_format == f"<t:{test_timestamp}:f>"
        assert long_datetime_format == f"<t:{test_timestamp}:F>"

        # Test with default style (relative)
        default_format = format_timestamp_for_discord(test_timestamp)
        assert default_format == f"<t:{test_timestamp}:R>"

    def test_create_embed(self) -> None:
        """Test creating an embed structure for Discord."""
        # Create a basic embed
        embed = create_embed(
            title="Test Title",
            description="Test Description",
            color=12345,
            fields=[{"name": "Field 1", "value": "Value 1"}],
            footer={"text": "Footer Text"},
            timestamp=1609459200,
        )

        # Check the structure of the embed
        assert embed["title"] == "Test Title"
        assert embed["description"] == "Test Description"
        assert embed["color"] == 12345
        assert len(embed["fields"]) == 1
        assert embed["fields"][0]["name"] == "Field 1"
        assert embed["fields"][0]["value"] == "Value 1"
        assert embed["footer"]["text"] == "Footer Text"
        assert embed["timestamp"] == 1609459200

        # Test with minimal required fields
        minimal_embed = create_embed(title="Minimal Title")
        assert minimal_embed["title"] == "Minimal Title"
        assert "description" not in minimal_embed
        assert "color" not in minimal_embed
        assert "fields" not in minimal_embed
        assert "footer" not in minimal_embed
        assert "timestamp" not in minimal_embed

    def test_create_embed_with_raw_values(self) -> None:
        """Test creating an embed with raw values for Discord."""
        # Define raw values
        raw_values: RawValues = {
            "percent": 50,
            "remaining_bytes": 1073741824,  # 1 GB
            "eta": time.time() + 3600,  # 1 hour in the future
        }

        # Create a template for the embed description
        template = (
            "Moving data from SSD Cache to HDD Array.\n"
            "Progress: **{percent}** complete.\n"
            "Remaining data: {remaining_data}.\n"
            "Estimated completion time: {etc}."
        )

        # Format the message for the embed description
        formatted_message = format_discord_message(template, raw_values)

        # Create the embed with the formatted message
        embed = create_embed(
            title="Mover: Moving Data",
            description=formatted_message,
            color=16753920,  # Light Orange
            footer={"text": "Version: v0.1.0"},
        )

        # Check the structure of the embed
        assert embed["title"] == "Mover: Moving Data"
        assert "**50%**" in embed["description"]
        assert "1.0 GB" in embed["description"]
        assert "<t:" in embed["description"]  # Contains Discord timestamp format
        assert embed["color"] == 16753920
        assert embed["footer"]["text"] == "Version: v0.1.0"


class TestDiscordProvider:
    """Test cases for the Discord notification provider."""

    def test_init(self) -> None:
        """Test initialization of the Discord provider."""
        # Create a config dictionary
        config: DiscordConfig = {
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefg",
            "username": "Test Bot",
            "message_template": "Test message: {percent}%",
            "use_embeds": True,
            "embed_title": "Test Title",
            "embed_colors": {
                "low_progress": 16711680,  # Red
                "mid_progress": 16776960,  # Yellow
                "high_progress": 65280,    # Green
                "complete": 65535,         # Cyan
            },
        }

        # Initialize the provider
        provider = DiscordProvider(config)

        # Check that the provider was initialized correctly
        assert provider.name == "discord"
        assert provider.enabled is True
        assert provider.webhook_url == "https://discord.com/api/webhooks/123456789/abcdefg"
        assert provider.username == "Test Bot"
        assert provider.message_template == "Test message: {percent}%"
        assert provider.use_embeds is True
        assert provider.embed_title == "Test Title"
        assert provider.embed_colors["low_progress"] == 16711680
        assert provider.embed_colors["mid_progress"] == 16776960
        assert provider.embed_colors["high_progress"] == 65280
        assert provider.embed_colors["complete"] == 65535

    def test_validate_config_valid(self) -> None:
        """Test validation of a valid configuration."""
        # Create a valid config
        config: DiscordConfig = {
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefg",
            "username": "Test Bot",
        }

        # Initialize the provider
        provider = DiscordProvider(config)

        # Validate the config
        errors = provider.validate_config()

        # Check that there are no errors
        assert len(errors) == 0

    def test_validate_config_invalid_webhook_url(self) -> None:
        """Test validation of an invalid webhook URL."""
        # Create a config with an invalid webhook URL
        config: DiscordConfig = {
            "enabled": True,
            "webhook_url": "invalid-url",
            "username": "Test Bot",
        }

        # Initialize the provider
        provider = DiscordProvider(config)

        # Validate the config
        errors = provider.validate_config()

        # Check that there is an error for the webhook URL
        assert len(errors) == 1
        assert "webhook_url" in errors[0].lower()

    def test_validate_config_missing_webhook_url(self) -> None:
        """Test validation of a missing webhook URL."""
        # Create a config with a missing webhook URL
        config: DiscordConfig = {
            "enabled": True,
            "username": "Test Bot",
        }

        # Initialize the provider
        provider = DiscordProvider(config)

        # Validate the config
        errors = provider.validate_config()

        # Check that there is an error for the missing webhook URL
        assert len(errors) == 1
        assert "webhook_url" in errors[0].lower()

    @patch("requests.post")
    def test_send_notification_success(self, mock_post: MagicMock) -> None:
        """Test sending a notification successfully."""
        # Create a mock response
        mock_response = MagicMock()
        mock_response.status_code = 204  # Discord returns 204 No Content on success
        mock_post.return_value = mock_response

        # Create a config
        config: DiscordConfig = {
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefg",
            "username": "Test Bot",
            "message_template": "Test message: {percent}%",
            "use_embeds": True,
            "embed_title": "Test Title",
        }

        # Initialize the provider
        provider = DiscordProvider(config)

        # Send a notification
        result = provider.send_notification("Test message")

        # Check that the notification was sent successfully
        assert result is True
        mock_post.assert_called_once()

        # Check that the request was made with the correct URL
        args, kwargs = mock_post.call_args
        assert kwargs["url"] == "https://discord.com/api/webhooks/123456789/abcdefg"

    @patch("requests.post")
    def test_send_notification_with_raw_values(self, mock_post: MagicMock) -> None:
        """Test sending a notification with raw values."""
        # Create a mock response
        mock_response = MagicMock()
        mock_response.status_code = 204  # Discord returns 204 No Content on success
        mock_post.return_value = mock_response

        # Create a config
        config: DiscordConfig = {
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefg",
            "username": "Test Bot",
            "message_template": "Progress: {percent}%, Remaining: {remaining_data}",
            "use_embeds": True,
            "embed_title": "Test Title",
        }

        # Initialize the provider
        provider = DiscordProvider(config)

        # Define raw values
        raw_values: RawValues = {
            "percent": 50,
            "remaining_bytes": 1073741824,  # 1 GB
            "eta": None,
        }

        # Send a notification with raw values
        result = provider.send_notification("", raw_values=raw_values)

        # Check that the notification was sent successfully
        assert result is True
        mock_post.assert_called_once()

        # Check that the request was made with the correct data
        args, kwargs = mock_post.call_args
        assert "Progress: 50%" in str(kwargs["json"])
        assert "1.0 GB" in str(kwargs["json"])

    @patch("requests.post")
    def test_send_notification_api_error(self, mock_post: MagicMock) -> None:
        """Test handling of API errors when sending a notification."""
        # Create a mock response for an API error
        mock_response = MagicMock()
        mock_response.status_code = 400  # Bad Request
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400 Bad Request")
        mock_post.return_value = mock_response

        # Create a config
        config: DiscordConfig = {
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefg",
            "username": "Test Bot",
        }

        # Initialize the provider
        provider = DiscordProvider(config)

        # Send a notification
        result = provider.send_notification("Test message")

        # Check that the notification failed
        assert result is False
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_send_notification_network_error(self, mock_post: MagicMock) -> None:
        """Test handling of network errors when sending a notification."""
        # Create a mock for a network error
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        # Create a config
        config: DiscordConfig = {
            "enabled": True,
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefg",
            "username": "Test Bot",
        }

        # Initialize the provider
        provider = DiscordProvider(config)

        # Send a notification
        result = provider.send_notification("Test message")

        # Check that the notification failed
        assert result is False
        mock_post.assert_called_once()

    def test_send_notification_disabled(self) -> None:
        """Test that notifications are not sent when the provider is disabled."""
        # Create a config with the provider disabled
        config: DiscordConfig = {
            "enabled": False,
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefg",
            "username": "Test Bot",
        }

        # Initialize the provider
        provider = DiscordProvider(config)

        # Send a notification
        result = provider.send_notification("Test message")

        # Check that the notification was not sent
        assert result is False

    def test_send_notification_invalid_config(self) -> None:
        """Test that notifications are not sent with an invalid configuration."""
        # Create an invalid config
        config: DiscordConfig = {
            "enabled": True,
            "webhook_url": "invalid-url",
            "username": "Test Bot",
        }

        # Initialize the provider
        provider = DiscordProvider(config)

        # Send a notification
        result = provider.send_notification("Test message")

        # Check that the notification was not sent
        assert result is False
