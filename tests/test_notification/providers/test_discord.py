"""
Tests for the Discord notification provider.

This module contains tests for the Discord notification provider, including
the formatter module and the provider implementation.
"""

# pyright: reportTypedDictNotRequiredAccess=false

import time

from mover_status.notification.formatter import RawValues
from mover_status.notification.providers.discord.formatter import (
    format_discord_message,
    format_discord_eta,
    format_markdown_text,
    format_timestamp_for_discord,
    create_embed,
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
