"""Pure formatting utilities for human-readable output.

This module provides stateless formatting functions for converting raw data
into human-readable strings. All functions are pure with no side effects.

Requirements:
- 16.1: Shared utility modules for data size and time formatting
- 16.4: Pure and stateless utility functions for reuse without side effects
- 16.5: No provider-specific logic in shared utility modules
"""

# Binary unit constants (1024-based)
_KB_INT = 1024
_MB_INT = _KB_INT * 1024  # 1,048,576
_GB_INT = _MB_INT * 1024  # 1,073,741,824
_TB_INT = _GB_INT * 1024  # 1,099,511,627,776

_KB_FLOAT = 1024.0
_MB_FLOAT = _KB_FLOAT * 1024.0  # 1,048,576
_GB_FLOAT = _MB_FLOAT * 1024.0  # 1,073,741,824
_TB_FLOAT = _GB_FLOAT * 1024.0  # 1,099,511,627,776

# Time unit constants
_MINUTE = 60
_HOUR = _MINUTE * 60  # 3,600
_DAY = _HOUR * 24  # 86,400


def format_size(bytes: int, *, precision: int = 1) -> str:
    """Convert bytes to human-readable size format.

    Uses binary units (1024-based) for consistency with system tools.
    For terabyte values, displays both TB and GB components for clarity.

    Args:
        bytes: Number of bytes to format (must be non-negative)
        precision: Number of decimal places for TB display (default: 1)

    Returns:
        Human-readable string representation of the size.
        - TB: "X.Y TB (NNNN GB)" showing both units
        - GB/MB/KB: Integer values without decimals
        - < 1024: "X Bytes"

    Examples:
        >>> format_size(512)
        '512 Bytes'
        >>> format_size(2048)
        '2 KB'
        >>> format_size(5242880)
        '5 MB'
        >>> format_size(10737418240)
        '10 GB'
        >>> format_size(2748779069440)
        '2.5 TB (2560 GB)'

    Note:
        Maintains feature parity with legacy bash implementation.
        Uses binary units (1024) not decimal units (1000).
    """
    if bytes < 0:
        msg = "bytes must be non-negative"
        raise ValueError(msg)

    if bytes >= _TB_INT:
        # TB: Show both TB and GB for clarity
        tb = bytes // _TB_INT
        remaining = bytes % _TB_INT
        gb = remaining // _GB_INT

        # Format with precision decimal places
        tb_decimal = tb + (gb / 1024.0)
        total_gb = tb * 1024 + gb

        return f"{tb_decimal:.{precision}f} TB ({total_gb} GB)"

    if bytes >= _GB_INT:
        gb = bytes // _GB_INT
        return f"{gb} GB"

    if bytes >= _MB_INT:
        mb = bytes // _MB_INT
        return f"{mb} MB"

    if bytes >= _KB_INT:
        kb = bytes // _KB_INT
        return f"{kb} KB"

    return f"{bytes} Bytes"


def format_duration(seconds: float) -> str:
    """Convert seconds to human-readable duration format.

    Automatically selects appropriate time units based on magnitude.
    Shows the two most significant units for values over 1 hour.

    Args:
        seconds: Duration in seconds (must be non-negative)

    Returns:
        Human-readable duration string with adaptive granularity.
        - Days: "Xd Yh" (shows days and remaining hours)
        - Hours: "Xh Ym" (shows hours and remaining minutes)
        - Minutes: "Xm Ys" (shows minutes and remaining seconds)
        - Seconds: "Xs" (shows seconds only)

    Examples:
        >>> format_duration(45)
        '45s'
        >>> format_duration(90)
        '1m 30s'
        >>> format_duration(3665)
        '1h 1m'
        >>> format_duration(90000)
        '1d 1h'

    Note:
        Rounds down to whole units for cleaner display.
        Does not show zero values (e.g., "1h 0m" becomes "1h").
    """
    if seconds < 0:
        msg = "seconds must be non-negative"
        raise ValueError(msg)

    # Convert to integer for cleaner display
    total_seconds = int(seconds)

    if total_seconds >= _DAY:
        days = total_seconds // _DAY
        remaining = total_seconds % _DAY
        hours = remaining // _HOUR

        if hours > 0:
            return f"{days}d {hours}h"
        return f"{days}d"

    if total_seconds >= _HOUR:
        hours = total_seconds // _HOUR
        remaining = total_seconds % _HOUR
        minutes = remaining // _MINUTE

        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"

    if total_seconds >= _MINUTE:
        minutes = total_seconds // _MINUTE
        remaining = total_seconds % _MINUTE

        if remaining > 0:
            return f"{minutes}m {remaining}s"
        return f"{minutes}m"

    return f"{total_seconds}s"


def format_rate(bytes_per_second: float) -> str:
    """Convert bytes per second to human-readable data rate.

    Uses the same unit logic as format_size but adds '/s' suffix.
    Shows one decimal place for precision in rate display.

    Args:
        bytes_per_second: Transfer rate in bytes/second (must be non-negative)

    Returns:
        Human-readable rate string with appropriate unit and '/s' suffix.
        - TB/s, GB/s, MB/s, KB/s: One decimal place
        - Bytes/s: Integer value

    Examples:
        >>> format_rate(512.0)
        '512 Bytes/s'
        >>> format_rate(2048.5)
        '2.0 KB/s'
        >>> format_rate(5242880.0)
        '5.0 MB/s'
        >>> format_rate(47185920.0)
        '45.0 MB/s'
        >>> format_rate(10737418240.0)
        '10.0 GB/s'

    Note:
        Uses binary units (1024-based) for consistency with format_size.
        Always shows one decimal place for better precision in rate monitoring.
    """
    if bytes_per_second < 0:
        msg = "bytes_per_second must be non-negative"
        raise ValueError(msg)

    if bytes_per_second >= _TB_FLOAT:
        tb = bytes_per_second / _TB_FLOAT
        return f"{tb:.1f} TB/s"

    if bytes_per_second >= _GB_FLOAT:
        gb = bytes_per_second / _GB_FLOAT
        return f"{gb:.1f} GB/s"

    if bytes_per_second >= _MB_FLOAT:
        mb = bytes_per_second / _MB_FLOAT
        return f"{mb:.1f} MB/s"

    if bytes_per_second >= _KB_FLOAT:
        kb = bytes_per_second / _KB_FLOAT
        return f"{kb:.1f} KB/s"

    # For small values, show integer
    return f"{int(bytes_per_second)} Bytes/s"
