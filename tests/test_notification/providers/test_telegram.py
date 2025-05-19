"""
Tests for the Telegram notification provider formatter module.

This module contains tests for the Telegram-specific formatter module, which is
responsible for formatting messages for the Telegram notification provider.
"""

import time
from datetime import datetime

from mover_status.notification.formatter import RawValues
from mover_status.notification.providers.telegram.formatter import (
    format_telegram_message,
    format_telegram_eta,
    format_html_text,
    format_timestamp_for_telegram,
)


class TestTelegramFormatter:
    """Test cases for the Telegram formatter module."""

    def test_format_html_text(self) -> None:
        """Test formatting text with HTML tags for Telegram."""
        # Test basic text formatting
        assert format_html_text("Test") == "Test"

        # Test bold formatting
        assert format_html_text("Test", bold=True) == "<b>Test</b>"

        # Test italic formatting
        assert format_html_text("Test", italic=True) == "<i>Test</i>"

        # Test combined formatting
        assert format_html_text("Test", bold=True, italic=True) == "<b><i>Test</i></b>"

    def test_format_telegram_eta(self) -> None:
        """Test formatting ETA for Telegram."""
        # Test None ETA (still calculating)
        assert format_telegram_eta(None) == "Calculating..."

        # Test with a specific timestamp
        # Create a timestamp for testing (e.g., 1 hour from now)
        current_time = time.time()
        future_time = current_time + 3600  # 1 hour in the future

        # Format the expected result manually for comparison
        expected_format = datetime.fromtimestamp(future_time).strftime("%H:%M on %b %d (%Z)")

        # Test the formatter
        assert format_telegram_eta(future_time) == expected_format

    def test_format_telegram_message_with_raw_values(self) -> None:
        """Test formatting a message with raw values for Telegram."""
        # Define a template with HTML formatting
        template = (
            "Moving data from SSD Cache to HDD Array. &#10;"
            "Progress: <b>{percent}</b> complete. &#10;"
            "Remaining data: {remaining_data}.&#10;"
            "Estimated completion time: {etc}.&#10;&#10;"
            "Note: Services like Plex may run slow or be unavailable during the move."
        )

        # Define raw values
        raw_values: RawValues = {
            "percent": 50,
            "remaining_bytes": 1073741824,  # 1 GB
            "eta": None,
        }

        # Format the message
        formatted_message = format_telegram_message(template, raw_values)

        # Check that the message contains expected formatted values
        assert "<b>50%</b>" in formatted_message
        assert "1.0 GB" in formatted_message
        assert "Calculating..." in formatted_message
        assert "&#10;" in formatted_message  # HTML newline entity

    def test_format_timestamp_for_telegram(self) -> None:
        """Test formatting a timestamp for Telegram."""
        # Create a specific timestamp for testing
        test_timestamp = 1609459200  # 2021-01-01 00:00:00 UTC

        # Format the timestamp
        formatted_timestamp = format_timestamp_for_telegram(test_timestamp)

        # Expected format: "%H:%M on %b %d (%Z)"
        # The exact output will depend on the local timezone, so we'll check the format
        assert ":" in formatted_timestamp  # Contains time with colon
        assert " on " in formatted_timestamp  # Contains " on " separator
        assert "(" in formatted_timestamp and ")" in formatted_timestamp  # Contains timezone in parentheses
