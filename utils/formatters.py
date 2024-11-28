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
from enum import Enum
from typing import Optional, Union

from config.constants import TimeConstants


class ProgressStyle(str, Enum):
    """Progress bar style options."""
    ASCII = "ascii"      # [====    ]
    UNICODE = "unicode"  # [████░░░░]
    BLOCKS = "blocks"    # [▓▓▓▓░░░░]
    DOTS = "dots"       # [●●●●○○○○]
    ARROW = "arrow"     # [→→→→----]


class SizeUnit(str, Enum):
    """Size unit systems."""
    BINARY = "binary"    # Uses 1024 (KiB, MiB, etc.)
    DECIMAL = "decimal"  # Uses 1000 (KB, MB, etc.)


class TimeFormat(str, Enum):
    """Time format options."""
    SHORT = "short"      # 2h 30m
    MEDIUM = "medium"    # 2 hours 30 minutes
    LONG = "long"        # 2 hours and 30 minutes
    PRECISE = "precise"  # 2 hours, 30 minutes, and 15 seconds


# Progress bar style definitions
PROGRESS_STYLES = {
    ProgressStyle.ASCII: ("=", "-", "[", "]"),
    ProgressStyle.UNICODE: ("█", "░", "│", "│"),
    ProgressStyle.BLOCKS: ("▓", "░", "│", "│"),
    ProgressStyle.DOTS: ("●", "○", "│", "│"),
    ProgressStyle.ARROW: ("→", "-", "│", "│"),
}

# Size unit multipliers
BINARY_UNITS = [
    (1, "B"),
    (1024, "KiB"),
    (1024**2, "MiB"),
    (1024**3, "GiB"),
    (1024**4, "TiB"),
    (1024**5, "PiB"),
]

DECIMAL_UNITS = [
    (1, "B"),
    (1000, "KB"),
    (1000**2, "MB"),
    (1000**3, "GB"),
    (1000**4, "TB"),
    (1000**5, "PB"),
]


def format_size(
    bytes_value: Union[int, float],
    precision: int = 2,
    unit_system: SizeUnit = SizeUnit.DECIMAL
) -> str:
    """Convert byte size to human-readable format.

    Args:
        bytes_value: Size in bytes
        precision: Number of decimal places to include (must be non-negative)
        unit_system: Unit system to use (binary or decimal)

    Returns:
        str: Formatted size string (e.g., "1.23 GB" or "1.23 GiB")

    Raises:
        ValueError: If bytes_value or precision is negative

    Examples:
        >>> format_size(1234567890)
        '1.15 GB'
        >>> format_size(1234567890, unit_system=SizeUnit.BINARY)
        '1.07 GiB'
    """
    if bytes_value < 0:
        raise ValueError("Byte size cannot be negative")
    if precision < 0:
        raise ValueError("Precision cannot be negative")

    bytes_value = float(bytes_value)
    units = BINARY_UNITS if unit_system == SizeUnit.BINARY else DECIMAL_UNITS

    # Find appropriate unit
    for factor, _unit in units:
        if bytes_value < factor * (1024 if unit_system == SizeUnit.BINARY else 1000):
            break

    # Handle special case for bytes
    if factor == 1:
        return f"{int(bytes_value)} B"

    value = bytes_value / factor
    return f"{value:.{precision}f} {_unit}"


def format_duration(  # noqa: C901
    seconds: Union[int, float],
    format_type: TimeFormat = TimeFormat.MEDIUM,
    max_units: int = 2
) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds
        format_type: Time format style
        max_units: Maximum number of units to include (default 2)

    Returns:
        str: Formatted duration string (e.g., "2 hours 30 minutes")

    Raises:
        ValueError: If seconds is negative or max_units is less than 1

    Examples:
        >>> format_duration(3665)
        '1 hour 1 minute'
        >>> format_duration(3665, format_type=TimeFormat.SHORT)
        '1h 1m'
    """
    if seconds < 0:
        raise ValueError("Duration cannot be negative")
    if max_units < 1:
        raise ValueError("max_units must be at least 1")

    seconds = float(seconds)
    intervals = [
        (TimeConstants.SECONDS_PER_DAY, "d", "day"),
        (TimeConstants.SECONDS_PER_HOUR, "h", "hour"),
        (TimeConstants.SECONDS_PER_MINUTE, "m", "minute"),
        (1, "s", "second")
    ]

    parts = []
    remaining = seconds

    for value, short_unit, long_unit in intervals:
        if remaining < 1:
            break
        count = int(remaining // value)
        if count > 0:
            if format_type == TimeFormat.SHORT:
                parts.append(f"{count}{short_unit}")
            else:
                unit_str = f"{long_unit}s" if count != 1 else long_unit
                parts.append(f"{count} {unit_str}")
            remaining %= value

        if len(parts) >= max_units:
            break

    if not parts:
        return "0s" if format_type == TimeFormat.SHORT else "0 seconds"

    if format_type == TimeFormat.LONG:
        if len(parts) > 1:
            return f"{', '.join(parts[:-1])} and {parts[-1]}"
        return parts[0]
    elif format_type == TimeFormat.MEDIUM:
        return " ".join(parts)
    else:
        return "".join(parts)


def format_progress(
    value: Union[int, float],
    style: Union[str, ProgressStyle] = ProgressStyle.ASCII,
    width: Optional[int] = None,
    show_percent: bool = True,
    color: bool = False
) -> str:
    """Format progress value as percentage or progress bar.

    Args:
        value: Progress value (0-100)
        style: Progress bar style
        width: Width of progress bar
        show_percent: Whether to show percentage
        color: Whether to use ANSI color codes

    Returns:
        str: Formatted progress string

    Raises:
        ValueError: If value is out of range or style is invalid

    Examples:
        >>> format_progress(75.5)
        '[===============     ] 75.5%'
        >>> format_progress(75.5, style=ProgressStyle.UNICODE)
        '│████████░░░░│ 75.5%'
    """
    if not isinstance(value, (int, float)):
        raise ValueError("Progress value must be a number")
    if not 0 <= value <= 100:
        raise ValueError("Progress value must be between 0 and 100")

    # Get style characters
    try:
        style_enum = ProgressStyle(style)
        fill_char, empty_char, left_border, right_border = PROGRESS_STYLES[style_enum]
    except ValueError as e:
        raise ValueError(f"Invalid style. Use one of: {', '.join(s.value for s in ProgressStyle)}") from e

    # Set bar width
    if width is None:
        width = 20

    if width < 2:
        raise ValueError("Width must be at least 2")

    # Calculate filled and empty portions
    inner_width = width - 2  # Account for borders
    filled = int(round(value / 100 * inner_width))
    empty = inner_width - filled

    # Build progress bar
    if color:
        # Color gradient based on progress
        if value < 33:
            color_code = "\033[91m"  # Red
        elif value < 66:
            color_code = "\033[93m"  # Yellow
        else:
            color_code = "\033[92m"  # Green
        reset_code = "\033[0m"
        bar = f"{left_border}{color_code}{fill_char * filled}{empty_char * empty}{reset_code}{right_border}"
    else:
        bar = f"{left_border}{fill_char * filled}{empty_char * empty}{right_border}"

    # Add percentage if requested
    if show_percent:
        return f"{bar} {value:.1f}%"
    return bar


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
            return format_duration(-delta.total_seconds(), format_type=TimeFormat.MEDIUM) + " from now"
        return format_duration(delta.total_seconds(), format_type=TimeFormat.MEDIUM) + " ago"

    if format_str is None:
        format_str = "%Y-%m-%d %H:%M:%S"

    try:
        return dt.strftime(format_str)
    except ValueError as e:
        raise ValueError(f"Invalid format string: {e}") from e


def format_eta(
    completion_time: datetime,
    format_type: TimeFormat = TimeFormat.MEDIUM
) -> str:
    """Format estimated completion time.

    Args:
        completion_time: Estimated completion datetime
        format_type: Time format style

    Returns:
        str: Formatted ETA string

    Raises:
        ValueError: If completion_time is invalid

    Examples:
        >>> future = datetime.now() + timedelta(hours=2)
        >>> format_eta(future)
        'in 2 hours'
        >>> format_eta(future, format_type=TimeFormat.SHORT)
        'in 2h'
    """
    if not isinstance(completion_time, datetime):
        raise ValueError("completion_time must be a datetime object")

    now = datetime.now()
    delta = completion_time - now

    if delta.total_seconds() < 0:
        raise ValueError("Completion time cannot be in the past")

    duration = format_duration(delta.total_seconds(), format_type=format_type)
    return f"in {duration}"


def format_template(
    template: str,
    validate: bool = True,
    **kwargs
) -> str:
    """Format template string with provided values.

    Args:
        template: Template string with placeholders
        validate: Whether to validate against predefined placeholders
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

    # Get placeholders from template
    placeholders = {
        p.strip("{}")
        for p in kwargs.keys()
        if p.strip("{}") in template
    }

    # Validate against predefined placeholders if requested
    if validate:
        invalid = {p for p in placeholders if p not in kwargs.keys()}
        if invalid:
            raise ValueError(f"Invalid template placeholders: {', '.join(invalid)}")

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
