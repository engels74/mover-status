# utils/formatters.py

"""
Formatting utilities for data sizes, time durations, and progress values.
Provides reusable functions for consistent data presentation across the application.

Functions:
    format_size: Convert byte size to human-readable format
    format_duration: Format duration in seconds to human-readable string
    format_progress: Format progress value as percentage or progress bar
    format_timestamp: Format datetime object to string
    format_eta: Format estimated completion time
    format_template: Format template string with provided values
"""

from datetime import datetime
from typing import Optional, Union

from config.constants import (
    BYTES_PER_GB,
    BYTES_PER_KB,
    BYTES_PER_MB,
    BYTES_PER_TB,
    SECONDS_PER_DAY,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
    TEMPLATE_PLACEHOLDERS,
    Percentage,
)


def format_size(bytes_value: Union[int, float], precision: int = 2) -> str:
    """Convert byte size to human-readable format.

    Args:
        bytes_value: Size in bytes
        precision: Number of decimal places to include (must be non-negative)

    Returns:
        str: Formatted size string (e.g., "1.23 GB")

    Raises:
        ValueError: If bytes_value or precision is negative

    Examples:
        >>> format_size(1234567890)
        '1.15 GB'
        >>> format_size(1234567890, precision=1)
        '1.1 GB'
    """
    if bytes_value < 0:
        raise ValueError("Byte size cannot be negative")
    if precision < 0:
        raise ValueError("Precision cannot be negative")

    bytes_value = float(bytes_value)  # Convert to float for division
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_boundaries = [1, BYTES_PER_KB, BYTES_PER_MB, BYTES_PER_GB, BYTES_PER_TB]

    # Find appropriate unit
    unit_index = 0
    for i, boundary in enumerate(unit_boundaries):
        if bytes_value < boundary:
            break
        unit_index = i

    # Handle special case for bytes
    if unit_index == 0:
        return f"{int(bytes_value)} {units[0]}"

    # Calculate value in appropriate unit
    value = bytes_value / unit_boundaries[unit_index]
    return f"{value:.{precision}f} {units[unit_index]}"


def format_duration(
    seconds: Union[int, float],
    include_seconds: bool = True,
    max_units: int = 2
) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds
        include_seconds: Whether to include seconds in output
        max_units: Maximum number of units to include (default 2)

    Returns:
        str: Formatted duration string (e.g., "2 hours 30 minutes")

    Raises:
        ValueError: If seconds is negative or max_units is less than 1

    Examples:
        >>> format_duration(3665)
        '1 hour 1 minute'
        >>> format_duration(3665, max_units=3)
        '1 hour 1 minute 5 seconds'
    """
    if seconds < 0:
        raise ValueError("Duration cannot be negative")
    if max_units < 1:
        raise ValueError("max_units must be at least 1")

    seconds = float(seconds)  # Convert to float for division
    intervals = [
        (SECONDS_PER_DAY, "day"),
        (SECONDS_PER_HOUR, "hour"),
        (SECONDS_PER_MINUTE, "minute"),
        (1, "second")
    ]

    parts = []
    remaining = seconds
    for value, unit in intervals:
        if remaining < 1:
            break
        count = int(remaining // value)
        if count > 0:
            unit_str = f"{unit}s" if count != 1 else unit
            parts.append(f"{count} {unit_str}")
            remaining %= value

        if len(parts) >= max_units:
            break

    if not include_seconds and parts and "second" in parts[-1]:
        parts.pop()

    if not parts:
        return "0 seconds" if include_seconds else "0 minutes"

    return " ".join(parts[:max_units])


def format_progress(
    value: Percentage,
    style: str = "percent",
    width: Optional[int] = None,
    chars: Optional[tuple[str, str]] = None
) -> str:
    """Format progress value as percentage or progress bar.

    Args:
        value: Progress value (0-100)
        style: Format style ("percent" or "bar")
        width: Width of progress bar (if style="bar")
        chars: Tuple of (fill_char, empty_char) for progress bar

    Returns:
        str: Formatted progress string

    Raises:
        ValueError: If value is out of range or style is invalid

    Examples:
        >>> format_progress(75.5)
        '75.5%'
        >>> format_progress(75.5, style="bar", width=20)
        '[===============     ]'
    """
    if not isinstance(value, (int, float)):
        raise ValueError("Progress value must be a number")
    if not 0 <= value <= 100:
        raise ValueError("Progress value must be between 0 and 100")

    if style == "percent":
        return f"{value:.1f}%"
    elif style == "bar":
        if width is None:
            width = 20
        if width < 2:
            raise ValueError("Width must be at least 2")
        fill_char, empty_char = chars or ('=', ' ')
        inner_width = width - 2  # Account for brackets
        filled = int(round(value / 100 * inner_width))
        return f"[{fill_char * filled}{empty_char * (inner_width - filled)}]"
    else:
        raise ValueError("Invalid style. Use 'percent' or 'bar'")


def format_timestamp(
    dt: datetime,
    format_str: Optional[str] = None,
    relative: bool = False
) -> str:
    """Format datetime object to string.

    Args:
        dt: Datetime object to format
        format_str: Optional strftime format string
        relative: Whether to return relative time

    Returns:
        str: Formatted datetime string

    Raises:
        ValueError: If format string is invalid

    Examples:
        >>> dt = datetime(2024, 1, 1, 12, 0, 0)
        >>> format_timestamp(dt)
        '2024-01-01 12:00:00'
        >>> format_timestamp(dt, relative=True)
        '2 months ago'
    """
    if not isinstance(dt, datetime):
        raise ValueError("dt must be a datetime object")

    if relative:
        delta = datetime.now() - dt
        if delta.total_seconds() < 0:
            return format_duration(-delta.total_seconds(), include_seconds=False) + " from now"
        return format_duration(delta.total_seconds(), include_seconds=False) + " ago"

    if format_str is None:
        format_str = "%Y-%m-%d %H:%M:%S"

    try:
        return dt.strftime(format_str)
    except ValueError as e:
        raise ValueError(f"Invalid format string: {e}") from e


def format_eta(
    completion_time: datetime,
    short_format: bool = False
) -> str:
    """Format estimated completion time.

    Args:
        completion_time: Estimated completion datetime
        short_format: Whether to use short format

    Returns:
        str: Formatted ETA string

    Raises:
        ValueError: If completion_time is invalid

    Examples:
        >>> future = datetime.now() + timedelta(hours=2)
        >>> format_eta(future)
        'in 2 hours'
        >>> format_eta(future, short_format=True)
        '14:00'
    """
    if not isinstance(completion_time, datetime):
        raise ValueError("completion_time must be a datetime object")

    now = datetime.now()
    delta = completion_time - now

    if delta.total_seconds() < 0:
        raise ValueError("Completion time cannot be in the past")

    if short_format:
        # If same day, show only time
        if completion_time.date() == now.date():
            return completion_time.strftime("%H:%M")
        # If within a week, show day and time
        if delta.days < 7:
            return completion_time.strftime("%a %H:%M")
        # Otherwise show date and time
        return completion_time.strftime("%Y-%m-%d %H:%M")

    return f"in {format_duration(delta.total_seconds(), include_seconds=False)}"


def format_template(template: str, **kwargs) -> str:
    """Format template string with provided values.

    Args:
        template: Template string with placeholders
        **kwargs: Values to substitute in template

    Returns:
        str: Formatted template string

    Raises:
        ValueError: If template is invalid or missing required values

    Examples:
        >>> template = "Progress: {percent}% ({remaining_data} remaining)"
        >>> format_template(template, percent="75.5", remaining_data="1.2 GB")
        'Progress: 75.5% (1.2 GB remaining)'
    """
    if not template:
        raise ValueError("Template string cannot be empty")

    # Get required placeholders from template
    placeholders = {
        p.strip("{}")
        for p in TEMPLATE_PLACEHOLDERS.values()
        if p.strip("{}") in template
    }

    # Check for required values
    missing = placeholders - set(kwargs.keys())
    if missing:
        raise ValueError(f"Missing required template values: {', '.join(missing)}")

    try:
        return template.format(**kwargs)
    except KeyError as err:
        raise ValueError(f"Invalid template placeholder: {err}") from err
    except ValueError as err:
        raise ValueError(f"Invalid placeholder value: {err}") from err
    except Exception as err:
        raise ValueError(f"Template formatting error: {err}") from err
