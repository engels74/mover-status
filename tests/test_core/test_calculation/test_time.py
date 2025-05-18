"""
Tests for the time calculation module.

This module contains tests for the calculate_eta function in the time calculation module.
"""

import time
import pytest


def test_calculate_eta_zero_progress() -> None:
    """Test calculating ETA with 0% progress."""
    from mover_status.core.calculation.time import calculate_eta

    # Mock parameters
    start_time = time.time()
    current_time = start_time + 10  # 10 seconds later
    progress_percent = 0

    result = calculate_eta(start_time, current_time, progress_percent)
    assert result is None  # Should return None for 0% progress


def test_calculate_eta_mid_progress() -> None:
    """Test calculating ETA with mid-progress."""
    from mover_status.core.calculation.time import calculate_eta

    # Mock parameters
    start_time = time.time()
    current_time = start_time + 300  # 5 minutes later
    progress_percent = 50  # 50% complete

    # Expected completion time would be another 5 minutes from current_time
    expected_completion_time = current_time + 300

    result = calculate_eta(start_time, current_time, progress_percent)

    # Allow a small margin of error (1 second) due to test execution time
    assert result is not None
    assert abs(result - expected_completion_time) <= 1


def test_calculate_eta_almost_complete() -> None:
    """Test calculating ETA when progress is almost complete."""
    from mover_status.core.calculation.time import calculate_eta

    # Mock parameters
    start_time = time.time()
    current_time = start_time + 950  # 950 seconds later
    progress_percent = 95  # 95% complete

    # Expected completion time would be another 50 seconds from current_time
    expected_completion_time = current_time + 50

    result = calculate_eta(start_time, current_time, progress_percent)

    # Allow a small margin of error (1 second) due to test execution time
    assert result is not None
    assert abs(result - expected_completion_time) <= 1


def test_calculate_eta_negative_progress() -> None:
    """Test that calculating ETA with negative progress raises a ValueError."""
    from mover_status.core.calculation.time import calculate_eta

    # Mock parameters
    start_time = time.time()
    current_time = start_time + 300
    progress_percent = -10  # Negative progress

    with pytest.raises(ValueError, match="Progress percentage must be between 0 and 100"):
        _ = calculate_eta(start_time, current_time, progress_percent)


def test_calculate_eta_progress_over_100() -> None:
    """Test that calculating ETA with progress over 100% raises a ValueError."""
    from mover_status.core.calculation.time import calculate_eta

    # Mock parameters
    start_time = time.time()
    current_time = start_time + 300
    progress_percent = 110  # Progress over 100%

    with pytest.raises(ValueError, match="Progress percentage must be between 0 and 100"):
        _ = calculate_eta(start_time, current_time, progress_percent)


def test_calculate_eta_start_time_after_current_time() -> None:
    """Test that calculating ETA with start time after current time raises a ValueError."""
    from mover_status.core.calculation.time import calculate_eta

    # Mock parameters
    start_time = time.time() + 100  # Start time in the future
    current_time = time.time()
    progress_percent = 50

    with pytest.raises(ValueError, match="Start time must be before current time"):
        _ = calculate_eta(start_time, current_time, progress_percent)
