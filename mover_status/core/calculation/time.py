"""
Time calculation module.

This module provides functions for calculating estimated time of completion
based on progress rate.
"""

from typing import Optional


def calculate_eta(
    start_time: float,
    current_time: float,
    progress_percent: int
) -> Optional[float]:
    """
    Calculate the estimated time of completion based on progress rate.

    Args:
        start_time: The timestamp when monitoring started.
        current_time: The current timestamp.
        progress_percent: The current progress percentage (0-100).

    Returns:
        Optional[float]: The estimated completion time as a Unix timestamp,
                         or None if progress is 0% (still calculating).

    Raises:
        ValueError: If progress_percent is not between 0 and 100,
                   or if start_time is after current_time.

    Examples:
        >>> # If current progress is 50% after 5 minutes, ETA would be 5 minutes later
        >>> start = time.time() - 300  # 5 minutes ago
        >>> current = time.time()
        >>> eta = calculate_eta(start, current, 50)
        >>> # eta would be approximately current + 300 seconds
    """
    # Validate inputs
    if progress_percent < 0 or progress_percent > 100:
        raise ValueError("Progress percentage must be between 0 and 100")

    if start_time > current_time:
        raise ValueError("Start time must be before current time")

    # If progress is 0%, return None to indicate "still calculating"
    if progress_percent == 0:
        return None

    # Calculate elapsed time
    elapsed_time = current_time - start_time

    # Calculate estimated total time based on current progress rate
    # If we've completed progress_percent in elapsed_time,
    # then 100% would take (elapsed_time * 100 / progress_percent)
    estimated_total_time = elapsed_time * 100 / progress_percent

    # Calculate remaining time
    remaining_time = estimated_total_time - elapsed_time

    # Calculate estimated completion time
    completion_time = current_time + remaining_time

    return completion_time
