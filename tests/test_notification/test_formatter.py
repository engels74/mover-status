"""
Tests for the notification formatter module.

This module contains tests for the notification formatter module, which is
responsible for formatting messages and raw values for display in notifications.
"""

import time

import pytest

from mover_status.notification.formatter import RawValues


class TestMessageFormatting:
    """Tests for message formatting functions."""

    def test_format_message_with_placeholders(self) -> None:
        """Test formatting a message with placeholders."""
        from mover_status.notification.formatter import format_message

        template = "Progress: {percent}% complete. Remaining: {remaining_data}."
        values = {"percent": 50, "remaining_data": "500 GB"}

        result = format_message(template, values)

        assert result == "Progress: 50% complete. Remaining: 500 GB."

    def test_handle_missing_placeholders(self) -> None:
        """Test handling missing placeholders in a message template."""
        from mover_status.notification.formatter import format_message

        template = "Progress: {percent}% complete. Remaining: {remaining_data}."
        values = {"percent": 50}  # Missing remaining_data

        # Should raise a KeyError for missing placeholders
        with pytest.raises(KeyError):
            _ = format_message(template, values)

    def test_handle_missing_placeholders_with_default(self) -> None:
        """Test handling missing placeholders with default values."""
        from mover_status.notification.formatter import format_message

        template = "Progress: {percent}% complete. Remaining: {remaining_data}."
        values = {"percent": 50}  # Missing remaining_data
        defaults = {"remaining_data": "Unknown"}

        result = format_message(template, values, defaults)

        assert result == "Progress: 50% complete. Remaining: Unknown."

    def test_integrate_with_calculation_values(self) -> None:
        """Test integrating with platform-agnostic calculation values."""
        from mover_status.notification.formatter import format_message
        from mover_status.core.calculation.size import format_bytes

        template = "Progress: {percent}% complete. Remaining: {remaining_data}."

        # Simulate calculation values
        remaining_bytes = 536870912  # 512 MB
        formatted_bytes = format_bytes(remaining_bytes)

        values = {
            "percent": 75,
            "remaining_data": formatted_bytes
        }

        result = format_message(template, values)

        assert result == "Progress: 75% complete. Remaining: 512.0 MB."


class TestRawValueFormatting:
    """Tests for raw value formatting functions."""

    def test_format_eta_none(self) -> None:
        """Test formatting None ETA to 'Calculating...'."""
        from mover_status.notification.formatter import format_eta

        result = format_eta(None)

        assert result == "Calculating..."

    def test_format_eta_timestamp(self) -> None:
        """Test formatting ETA timestamp."""
        from mover_status.notification.formatter import format_eta

        # Create a timestamp 1 hour in the future
        current_time = time.time()
        eta_timestamp = current_time + 3600  # 1 hour later

        result = format_eta(eta_timestamp)

        # The result should be a formatted time string
        assert isinstance(result, str)
        assert result != "Calculating..."
        # Basic format check - should contain time information
        assert ":" in result

    def test_format_bytes(self) -> None:
        """Test formatting byte values for display."""
        from mover_status.notification.formatter import format_bytes_for_display

        # Test with various byte values
        assert format_bytes_for_display(1024) == "1.0 KB"
        assert format_bytes_for_display(1048576) == "1.0 MB"
        assert format_bytes_for_display(1073741824) == "1.0 GB"

    def test_format_progress_percentage(self) -> None:
        """Test formatting progress percentage for display."""
        from mover_status.notification.formatter import format_progress_percentage

        # Test with various percentage values
        assert format_progress_percentage(0) == "0%"
        assert format_progress_percentage(50) == "50%"
        assert format_progress_percentage(100) == "100%"

        # Test with decimal values
        assert format_progress_percentage(33.33) == "33%"
        assert format_progress_percentage(66.67) == "67%"


class TestModularFormattingArchitecture:
    """Tests for the modular formatting architecture."""

    def test_common_formatter_basic_conversions(self) -> None:
        """Test that common formatter handles basic conversions."""
        from mover_status.notification.formatter import format_raw_values

        # Create raw values
        raw_values: RawValues = {
            "percent": 50,
            "remaining_bytes": 1073741824,  # 1 GB
            "eta": None
        }

        # Format raw values
        formatted_values = format_raw_values(raw_values)

        # Check that the values were formatted correctly
        assert "percent" in formatted_values and formatted_values["percent"] == "50%"
        assert "remaining_data" in formatted_values and formatted_values["remaining_data"] == "1.0 GB"
        assert "etc" in formatted_values and formatted_values["etc"] == "Calculating..."

    def test_provider_specific_formatting(self) -> None:
        """Test that provider formatters can use common formatter functions."""
        from mover_status.notification.formatter import (
            format_raw_values,
            format_message
        )

        # Create raw values
        raw_values: RawValues = {
            "percent": 75,
            "remaining_bytes": 536870912,  # 512 MB
            "eta": time.time() + 1800  # 30 minutes in the future
        }

        # Format raw values using common formatter
        formatted_values = format_raw_values(raw_values)

        # Use provider-specific template
        discord_template = (
            "Moving data from SSD Cache to HDD Array.\n"
            "Progress: **{percent}** complete.\n"
            "Remaining data: {remaining_data}.\n"
            "Estimated completion time: {etc}.\n\n"
            "Note: Services like Plex may run slow or be unavailable during the move."
        )

        # Format message using provider-specific template
        result = format_message(discord_template, formatted_values)

        # Check that the message contains the formatted values
        assert "Progress: **75%** complete" in result
        assert "Remaining data: 512.0 MB" in result
        assert "Estimated completion time:" in result
        assert "Calculating..." not in result  # ETA should be formatted, not "Calculating..."
