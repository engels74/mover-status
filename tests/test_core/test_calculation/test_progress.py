"""
Tests for the progress calculation module.

This module contains tests for the calculate_progress function in the progress calculation module.
"""

import pytest


def test_calculate_progress_normal_case() -> None:
    """Test calculating progress with normal values."""
    from mover_status.core.calculation.progress import calculate_progress

    initial_size = 1000
    current_size = 600

    # Expected: (1000 - 600) * 100 / (1000 - 600 + 600) = 400 * 100 / 1000 = 40%
    result = calculate_progress(initial_size, current_size)
    assert result == 40


def test_calculate_progress_zero_initial_size() -> None:
    """Test calculating progress with zero initial size."""
    from mover_status.core.calculation.progress import calculate_progress

    initial_size = 0
    current_size = 0

    with pytest.raises(ValueError, match="Initial size must be greater than zero"):
        _ = calculate_progress(initial_size, current_size)


def test_calculate_progress_current_size_greater_than_initial() -> None:
    """Test calculating progress when current size is greater than initial size."""
    from mover_status.core.calculation.progress import calculate_progress

    initial_size = 1000
    current_size = 1200

    with pytest.raises(ValueError, match="Current size cannot be greater than initial size"):
        _ = calculate_progress(initial_size, current_size)


def test_calculate_progress_negative_sizes() -> None:
    """Test calculating progress with negative sizes."""
    from mover_status.core.calculation.progress import calculate_progress

    # Test with negative initial size
    with pytest.raises(ValueError, match="Initial size must be greater than zero"):
        _ = calculate_progress(-1000, 500)

    # Test with negative current size
    with pytest.raises(ValueError, match="Sizes cannot be negative"):
        _ = calculate_progress(1000, -500)


def test_calculate_progress_zero_percent() -> None:
    """Test calculating progress when no data has been moved (0%)."""
    from mover_status.core.calculation.progress import calculate_progress

    initial_size = 1000
    current_size = 1000  # No data moved yet

    result = calculate_progress(initial_size, current_size)
    assert result == 0


def test_calculate_progress_hundred_percent() -> None:
    """Test calculating progress when all data has been moved (100%)."""
    from mover_status.core.calculation.progress import calculate_progress

    initial_size = 1000
    current_size = 0  # All data moved

    result = calculate_progress(initial_size, current_size)
    assert result == 100


def test_calculate_progress_rounding() -> None:
    """Test that progress calculation rounds to the nearest integer."""
    from mover_status.core.calculation.progress import calculate_progress

    # This should give 33.33...%, which should be rounded to 33%
    initial_size = 1000
    current_size = 667

    result = calculate_progress(initial_size, current_size)
    assert result == 33

    # This should give 66.66...%, which should be rounded to 67%
    initial_size = 1000
    current_size = 333

    result = calculate_progress(initial_size, current_size)
    assert result == 67
