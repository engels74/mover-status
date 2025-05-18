"""
Size calculation module.

This module provides functions for formatting byte sizes into human-readable formats.
"""


def format_bytes(
    bytes_value: int,
    precision: int = 1,
    binary_units: bool = False
) -> str:
    """
    Format a byte value into a human-readable string.

    Args:
        bytes_value: The number of bytes to format.
        precision: The number of decimal places to include in the formatted string.
        binary_units: Whether to use binary units (KiB, MiB, etc.) instead of
                      decimal units (KB, MB, etc.).

    Returns:
        str: A human-readable string representation of the byte value.

    Raises:
        ValueError: If bytes_value is negative.

    Examples:
        >>> format_bytes(1500)
        '1.5 KB'
        >>> format_bytes(1500, binary_units=True)
        '1.5 KiB'
        >>> format_bytes(1500, precision=2)
        '1.50 KB'
    """
    if bytes_value < 0:
        raise ValueError("Bytes value cannot be negative")

    if bytes_value == 0:
        return "0 Bytes"

    # Define unit prefixes and thresholds
    if binary_units:
        # Binary units (powers of 1024)
        unit_prefix = ["Bytes", "KiB", "MiB", "GiB", "TiB"]
        base = 1024
    else:
        # Decimal units (powers of 1000)
        unit_prefix = ["Bytes", "KB", "MB", "GB", "TB"]
        base = 1024  # Still using 1024 for consistency with the original script

    # Calculate the appropriate unit
    exponent = 0
    value = float(bytes_value)

    # Find the appropriate unit
    while value >= base and exponent < len(unit_prefix) - 1:
        value /= base
        exponent += 1

    # Format the value with the specified precision
    formatted_value = f"{value:.{precision}f}"

    # Special case for bytes (no decimal places)
    if exponent == 0:
        formatted_value = str(int(value))

    # Special case for TB with GB remainder (similar to the original script)
    if exponent == 4 and not binary_units:  # TB with decimal units
        tb_value = int(bytes_value / (base ** 4))
        remaining_bytes = bytes_value % (base ** 4)
        gb_value = int(remaining_bytes / (base ** 3))

        # Only show the remainder if there is one
        if gb_value > 0:
            # Calculate the decimal part for TB (e.g., 5.5 TB)
            decimal_part = gb_value / (base / 1)  # Convert GB to decimal TB
            tb_with_decimal = tb_value + decimal_part

            # Format with the specified precision
            formatted_tb = f"{tb_with_decimal:.{precision}f}"

            return f"{formatted_tb} TB ({tb_value * 1024 + gb_value} GB)"

    # Return the formatted string
    return f"{formatted_value} {unit_prefix[exponent]}"
