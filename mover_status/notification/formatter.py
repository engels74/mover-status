"""
Common message formatting for notifications.

This module provides functions for formatting messages and raw values for
display in notifications. It includes functions for formatting ETA timestamps,
byte values, and progress percentages.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import TypedDict

from mover_status.core.calculation.size import format_bytes


class RawValues(TypedDict, total=False):
    """Raw values to be formatted for display in notifications."""
    percent: int | float
    remaining_bytes: int
    eta: float | None


class FormattedValues(TypedDict, total=False):
    """Formatted values for display in notifications."""
    percent: str
    remaining_data: str
    etc: str


def format_message(
    template: str,
    values: Mapping[str, object],
    defaults: Mapping[str, object] | None = None
) -> str:
    """
    Format a message template with the given values.

    Args:
        template: The message template with placeholders.
        values: The values to substitute for the placeholders.
        defaults: Optional default values to use for missing placeholders.

    Returns:
        The formatted message.

    Raises:
        KeyError: If a placeholder in the template is not found in values or defaults.

    Examples:
        >>> format_message("Progress: {percent}%", {"percent": 50})
        'Progress: 50%'
        >>> format_message("Progress: {percent}%", {}, {"percent": "Unknown"})
        'Progress: Unknown%'
    """
    # Create a copy of values to avoid modifying the original
    combined_values = dict(values)

    # Add default values for missing placeholders
    if defaults:
        for key, value in defaults.items():
            if key not in combined_values:
                combined_values[key] = value

    # Format the message
    return template.format(**combined_values)


def format_eta(eta: float | None) -> str:
    """
    Format an ETA timestamp for display.

    Args:
        eta: The ETA timestamp as a Unix timestamp, or None if still calculating.

    Returns:
        A formatted string representation of the ETA, or "Calculating..." if None.

    Examples:
        >>> format_eta(None)
        'Calculating...'
        >>> import time
        >>> current_time = time.time()
        >>> format_eta(current_time + 3600)  # 1 hour in the future
        '12:34 PM on May 19'  # Example output, actual time will vary
    """
    if eta is None:
        return "Calculating..."

    # Convert timestamp to datetime
    eta_datetime = datetime.fromtimestamp(eta)

    # Format the datetime
    return eta_datetime.strftime("%H:%M on %b %d (%Z)")


def format_bytes_for_display(bytes_value: int) -> str:
    """
    Format a byte value for display.

    This is a wrapper around the core.calculation.size.format_bytes function.

    Args:
        bytes_value: The number of bytes to format.

    Returns:
        A formatted string representation of the byte value.

    Examples:
        >>> format_bytes_for_display(1024)
        '1.0 KB'
        >>> format_bytes_for_display(1048576)
        '1.0 MB'
    """
    return format_bytes(bytes_value)


def format_progress_percentage(percent: int | float) -> str:
    """
    Format a progress percentage for display.

    Args:
        percent: The progress percentage (0-100).

    Returns:
        A formatted string representation of the progress percentage.

    Examples:
        >>> format_progress_percentage(50)
        '50%'
        >>> format_progress_percentage(33.33)
        '33%'
    """
    # Round to nearest integer and format as string with % symbol
    return f"{round(percent)}%"


def format_raw_values(raw_values: RawValues) -> FormattedValues:
    """
    Format raw calculation values for display in notifications.

    This function takes raw values from calculations and formats them for
    display in notifications. It handles converting None values to appropriate
    display strings and formatting byte values and percentages.

    Args:
        raw_values: A dictionary of raw values to format.

    Returns:
        A dictionary of formatted values.

    Examples:
        >>> format_raw_values({"percent": 50, "remaining_bytes": 1073741824, "eta": None})
        {'percent': '50%', 'remaining_data': '1.0 GB', 'etc': 'Calculating...'}
    """
    formatted_values: FormattedValues = {}

    # Format progress percentage
    if "percent" in raw_values:
        formatted_values["percent"] = format_progress_percentage(raw_values["percent"])

    # Format remaining bytes
    if "remaining_bytes" in raw_values:
        formatted_values["remaining_data"] = format_bytes_for_display(
            raw_values["remaining_bytes"]
        )

    # Format ETA
    if "eta" in raw_values:
        formatted_values["etc"] = format_eta(raw_values["eta"])

    return formatted_values
