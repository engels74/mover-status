"""
Progress calculation module.

This module provides functions for calculating progress percentages based on
initial and current data sizes.
"""


def calculate_progress(initial_size: int, current_size: int) -> int:
    """
    Calculate the progress percentage based on initial and current data sizes.

    Args:
        initial_size: The initial size of the data in bytes.
        current_size: The current size of the data in bytes.

    Returns:
        int: The progress percentage (0-100).

    Raises:
        ValueError: If initial_size is zero or negative, if current_size is negative,
                   or if current_size is greater than initial_size.

    Examples:
        >>> calculate_progress(1000, 600)
        40
        >>> calculate_progress(1000, 1000)
        0
        >>> calculate_progress(1000, 0)
        100
    """
    # Validate inputs
    if initial_size <= 0:
        raise ValueError("Initial size must be greater than zero")
    
    if current_size < 0:
        raise ValueError("Sizes cannot be negative")
    
    if current_size > initial_size:
        raise ValueError("Current size cannot be greater than initial size")
    
    # If current_size equals initial_size, no progress has been made
    if current_size == initial_size:
        return 0
    
    # If current_size is 0, all data has been moved (100% progress)
    if current_size == 0:
        return 100
    
    # Calculate total data moved
    total_data_moved = initial_size - current_size
    
    # Calculate progress percentage
    # Using the formula: (total_data_moved * 100) / (total_data_moved + current_size)
    # This simplifies to: (total_data_moved * 100) / initial_size
    progress_percent = round((total_data_moved * 100) / initial_size)
    
    return progress_percent
