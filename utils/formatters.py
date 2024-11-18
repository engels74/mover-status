# utils/formatters.py

"""
Formatting utilities for data sizes, time durations, and progress values.
Provides reusable functions for consistent data presentation across the application.
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
    ByteSize,
    Percentage,
)


def format_size(bytes_value: ByteSize, precision: int = 2) -> str:
    """Convert byte size to human-readable format.

    Args:
        bytes_value: Size in bytes
        precision: Number of decimal places to include

    Returns:
        str: Formatted size string (e.g., "1.23 GB")

    Examples:
        >>> format_size(1234567890)
        '1.15 GB'
        >>> format_size(1234567890, precision=1)
        '1.1 GB'
    """
    if bytes_value < 0:
        raise ValueError("Byte size cannot be negative")

    if bytes_value < BYTES_PER_KB:
        return f"{bytes_value} Bytes"
    elif bytes_value < BYTES_PER_MB:
        return f"{bytes_value / BYTES_PER_KB:.{precision}f} KB"
    elif bytes_value < BYTES_PER_GB:
        return f"{bytes_value / BYTES_PER_MB:.{precision}f} MB"
    elif bytes_value < BYTES_PER_TB:
        return f"{bytes_value / BYTES_PER_GB:.{precision}f} GB"
    else:
        return f"{bytes_value / BYTES_PER_TB:.{precision}f} TB"

def format_duration(seconds: Union[int, float], include_seconds: bool = True) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds
        include_seconds: Whether to include seconds in output

    Returns:
        str: Formatted duration string (e.g., "2 hours 30 minutes")

    Examples:
        >>> format_duration(3665)
        '1 hour 1 minute 5 seconds'
        >>> format_duration(3665, include_seconds=False)
        '1 hour 1 minute'
    """
    if seconds < 0:
        raise ValueError("Duration cannot be negative")

    days = int(seconds // SECONDS_PER_DAY)
    remaining = seconds % SECONDS_PER_DAY
    hours = int(remaining // SECONDS_PER_HOUR)
    remaining = remaining % SECONDS_PER_HOUR
    minutes = int(remaining // SECONDS_PER_MINUTE)
    remaining = remaining % SECONDS_PER_MINUTE
    parts = []
    if days > 0:
        parts.append(f"{days} {'day' if days == 1 else 'days'}")
    if hours > 0:
        parts.append(f"{hours} {'hour' if hours == 1 else 'hours'}")
    if minutes > 0:
        parts.append(f"{minutes} {'minute' if minutes == 1 else 'minutes'}")
    if include_seconds and remaining > 0:
        parts.append(f"{int(remaining)} {'second' if int(remaining) == 1 else 'seconds'}")

    if not parts:
        return "0 seconds" if include_seconds else "0 minutes"
    return " ".join(parts)

def format_progress(
    value: Percentage,
    style: str = "percent",
    width: Optional[int] = None
) -> str:
    """Format progress value as percentage or progress bar.

    Args:
        value: Progress value (0-100)
        style: Format style ("percent" or "bar")
        width: Width of progress bar (if style="bar")

    Returns:
        str: Formatted progress string

    Examples:
        >>> format_progress(75.5)
        '75.5%'
        >>> format_progress(75.5, style="bar", width=20)
        '[===============     ]'
    """
    if not 0 <= value <= 100:
        raise ValueError("Progress value must be between 0 and 100")

    if style == "percent":
        return f"{value:.1f}%"
    elif style == "bar":
        if not width:
            width = 20
        filled = int(value / 100 * width)
        return f"[{'=' * filled}{' ' * (width - filled)}]"
    else:
        raise ValueError("Invalid style. Use 'percent' or 'bar'")

def format_timestamp(
    dt: datetime,
    format_str: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """Format datetime object to string.

    Args:
        dt: Datetime object to format
        format_str: strftime format string

    Returns:
        str: Formatted datetime string

    Examples:
        >>> from datetime import datetime
        >>> dt = datetime(2024, 1, 1, 12, 0, 0)
        >>> format_timestamp(dt)
        '2024-01-01 12:00:00'
    """
    return dt.strftime(format_str)

def format_eta(
    completion_time: datetime,
    relative: bool = True
) -> str:
    """Format estimated completion time.

    Args:
        completion_time: Estimated completion datetime
        relative: Whether to return relative time

    Returns:
        str: Formatted ETA string

    Examples:
        >>> from datetime import datetime, timedelta
        >>> future = datetime.now() + timedelta(hours=2)
        >>> format_eta(future)
        'in 2 hours'
        >>> format_eta(future, relative=False)
        '14:00'
    """
    if completion_time < datetime.now():
        raise ValueError("Completion time cannot be in the past")

    if relative:
        delta = completion_time - datetime.now()
        return f"in {format_duration(delta.total_seconds(), include_seconds=False)}"
    else:
        return completion_time.strftime("%H:%M")

def format_template(
    template: str,
    **kwargs
) -> str:
    """Format template string with provided values.

    Args:
        template: Template string with placeholders
        **kwargs: Values to substitute in template

    Returns:
        str: Formatted template string

    Examples:
        >>> template = "Progress: {percent}% ({remaining_data} remaining)"
        >>> format_template(template, percent="75.5", remaining_data="1.2 GB")
        'Progress: 75.5% (1.2 GB remaining)'
    """
    required_placeholders = {
        p.strip("{}") for p in TEMPLATE_PLACEHOLDERS.values()
        if p.strip("{}") in template
    }
    missing = required_placeholders - set(kwargs.keys())
    if missing:
        raise ValueError(f"Missing required template values: {', '.join(missing)}")

    try:
        return template.format(**kwargs)
    except KeyError as err:
        raise ValueError(f"Invalid template placeholder: {err}") from err
    except Exception as err:
        raise ValueError(f"Template formatting error: {err}") from err
