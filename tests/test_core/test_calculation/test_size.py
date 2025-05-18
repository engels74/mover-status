"""
Tests for the size calculation module.

This module contains tests for the format_bytes function in the size calculation module.
"""

import pytest

def test_format_bytes_zero() -> None:
    """Test formatting zero bytes."""
    from mover_status.core.calculation.size import format_bytes

    result = format_bytes(0)
    assert result == "0 Bytes"


def test_format_bytes_bytes() -> None:
    """Test formatting a small number of bytes."""
    from mover_status.core.calculation.size import format_bytes

    result = format_bytes(500)
    assert result == "500 Bytes"


def test_format_bytes_kilobytes() -> None:
    """Test formatting kilobytes."""
    from mover_status.core.calculation.size import format_bytes

    result = format_bytes(2048)
    assert result == "2.0 KB"


def test_format_bytes_megabytes() -> None:
    """Test formatting megabytes."""
    from mover_status.core.calculation.size import format_bytes

    result = format_bytes(3145728)  # 3 MB
    assert result == "3.0 MB"


def test_format_bytes_gigabytes() -> None:
    """Test formatting gigabytes."""
    from mover_status.core.calculation.size import format_bytes

    result = format_bytes(4294967296)  # 4 GB
    assert result == "4.0 GB"


def test_format_bytes_terabytes() -> None:
    """Test formatting terabytes."""
    from mover_status.core.calculation.size import format_bytes

    result = format_bytes(5497558138880)  # 5 TB
    assert result == "5.0 TB"


def test_format_bytes_large_tb_with_remainder() -> None:
    """Test formatting a large TB value with GB remainder."""
    from mover_status.core.calculation.size import format_bytes

    # 5.5 TB (5 TB + 512 GB)
    result = format_bytes(6047313952768)
    assert result == "5.5 TB (5632 GB)"


def test_format_bytes_negative() -> None:
    """Test that formatting negative bytes raises a ValueError."""
    from mover_status.core.calculation.size import format_bytes

    with pytest.raises(ValueError, match="Bytes value cannot be negative"):
        _ = format_bytes(-1)


def test_format_bytes_with_custom_precision() -> None:
    """Test formatting bytes with custom decimal precision."""
    from mover_status.core.calculation.size import format_bytes

    result = format_bytes(2097152, precision=3)  # 2 MB
    assert result == "2.000 MB"


def test_format_bytes_with_binary_units() -> None:
    """Test formatting bytes with binary units (KiB, MiB, etc.)."""
    from mover_status.core.calculation.size import format_bytes

    result = format_bytes(2048, binary_units=True)
    assert result == "2.0 KiB"

    result = format_bytes(3145728, binary_units=True)  # 3 MiB
    assert result == "3.0 MiB"
