"""Pure calculation functions for progress tracking and ETC estimation.

This module provides stateless, side-effect-free functions for calculating:
- Progress percentage from baseline and current disk usage
- Data movement rate from historical samples
- Estimated time of completion (ETC) based on current rate
- Remaining data to be transferred
- Threshold evaluation for notification triggering

All functions use immutable dataclasses for inputs and outputs to ensure
predictable behavior and comprehensive testability.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

from mover_status.types.models import DiskSample, ProgressData


def calculate_progress(*, baseline: int, current: int) -> float:
    """Calculate progress percentage from baseline and current disk usage.

    Progress is calculated as the proportion of data that has been moved
    from the baseline (starting) usage to the current usage.

    Args:
        baseline: Starting disk usage in bytes (must be non-negative)
        current: Current disk usage in bytes (must be non-negative)

    Returns:
        Progress percentage between 0.0 and 100.0

    Edge cases:
        - If baseline is 0, returns 100.0 (nothing to move)
        - If current > baseline (negative delta), returns 0.0 (no progress)
        - If current is 0, returns 100.0 (all data moved)
        - If current == baseline, returns 0.0 (no movement yet)

    Examples:
        >>> calculate_progress(baseline=1000, current=500)
        50.0
        >>> calculate_progress(baseline=1000, current=0)
        100.0
        >>> calculate_progress(baseline=0, current=0)
        100.0
        >>> calculate_progress(baseline=100, current=150)  # Negative delta
        0.0
    """
    if baseline < 0:
        msg = "baseline must be non-negative"
        raise ValueError(msg)
    if current < 0:
        msg = "current must be non-negative"
        raise ValueError(msg)

    # Edge case: Zero baseline means nothing to move
    if baseline == 0:
        return 100.0

    # Edge case: Current > baseline indicates negative delta (data added)
    if current > baseline:
        return 0.0

    # Standard calculation: (baseline - current) / baseline * 100
    moved = baseline - current
    return (moved / baseline) * 100.0


def calculate_remaining(*, baseline: int, current: int) -> int:
    """Calculate remaining data to be transferred in bytes.

    Args:
        baseline: Starting disk usage in bytes (must be non-negative)
        current: Current disk usage in bytes (must be non-negative)

    Returns:
        Remaining bytes to transfer (always non-negative)

    Edge cases:
        - If current > baseline, returns 0 (no remaining data)
        - If baseline is 0, returns 0 (nothing to transfer)

    Examples:
        >>> calculate_remaining(baseline=1000, current=400)
        400
        >>> calculate_remaining(baseline=1000, current=1200)  # Negative delta
        0
        >>> calculate_remaining(baseline=0, current=0)
        0
    """
    if baseline < 0:
        msg = "baseline must be non-negative"
        raise ValueError(msg)
    if current < 0:
        msg = "current must be non-negative"
        raise ValueError(msg)

    # Edge case: Current > baseline or zero baseline
    if current >= baseline or baseline == 0:
        return 0

    return current


def calculate_rate(samples: Sequence[DiskSample], *, window_size: int = 3) -> float:
    """Calculate moving average data movement rate from disk samples.

    Uses a moving average over recent samples to smooth out transient
    variations in transfer rate. Rate is calculated from time and byte
    deltas between consecutive samples.

    Args:
        samples: Sequence of disk usage samples ordered by timestamp
                (must contain at least 2 samples for rate calculation)
        window_size: Number of recent samples to include in moving average
                    (default: 3, must be >= 2)

    Returns:
        Average data movement rate in bytes per second

    Edge cases:
        - If fewer than 2 samples, returns 0.0 (insufficient data)
        - If time delta is zero between samples, skips that pair
        - If all time deltas are zero, returns 0.0
        - If disk usage increases (negative delta), skips that pair
        - Uses min(len(samples), window_size) for averaging window

    Examples:
        >>> samples = [
        ...     DiskSample(datetime(2024,1,1,10,0,0), 1000, "/cache"),
        ...     DiskSample(datetime(2024,1,1,10,0,10), 900, "/cache"),  # 100 bytes in 10s = 10 B/s
        ...     DiskSample(datetime(2024,1,1,10,0,20), 800, "/cache"),  # 100 bytes in 10s = 10 B/s
        ... ]
        >>> calculate_rate(samples)
        10.0
    """
    if window_size < 2:
        msg = "window_size must be at least 2"
        raise ValueError(msg)

    # Edge case: Need at least 2 samples to calculate rate
    if len(samples) < 2:
        return 0.0

    # Use the most recent `window_size` samples
    recent_samples = list(samples[-window_size:])

    # Calculate rates between consecutive sample pairs
    rates: list[float] = []

    for i in range(len(recent_samples) - 1):
        prev_sample = recent_samples[i]
        curr_sample = recent_samples[i + 1]

        # Calculate time delta in seconds
        time_delta = (curr_sample.timestamp - prev_sample.timestamp).total_seconds()

        # Skip if no time elapsed (avoid division by zero)
        if time_delta <= 0:
            continue

        # Calculate bytes moved (should be positive for transfer)
        bytes_delta = prev_sample.bytes_used - curr_sample.bytes_used

        # Skip if disk usage increased (negative delta indicates data added)
        if bytes_delta <= 0:
            continue

        # Calculate rate for this interval
        rate = bytes_delta / time_delta
        rates.append(rate)

    # Edge case: No valid rates calculated
    if not rates:
        return 0.0

    # Return moving average
    return sum(rates) / len(rates)


def calculate_etc(*, remaining: int, rate: float) -> datetime | None:
    """Calculate estimated time of completion based on remaining data and transfer rate.

    Projects the completion time by dividing remaining bytes by the current
    transfer rate and adding the result to the current time.

    Args:
        remaining: Remaining bytes to transfer (must be non-negative)
        rate: Current transfer rate in bytes per second (must be non-negative)

    Returns:
        Estimated completion datetime, or None if rate is zero/negative
        or if the calculation would overflow

    Edge cases:
        - If rate <= 0, returns None (cannot estimate)
        - If remaining is 0, returns current time (already complete)
        - If seconds_remaining would overflow timedelta, returns None
        - Handles very large remaining values gracefully

    Examples:
        >>> import datetime
        >>> # Transfer 1000 bytes at 10 bytes/second = 100 seconds
        >>> etc = calculate_etc(remaining=1000, rate=10.0)
        >>> # ETC should be ~100 seconds from now
        >>> etc is not None
        True
    """
    if remaining < 0:
        msg = "remaining must be non-negative"
        raise ValueError(msg)
    if rate < 0:
        msg = "rate must be non-negative"
        raise ValueError(msg)

    # Edge case: Zero or negative rate means we can't estimate completion
    if rate <= 0:
        return None

    # Edge case: No remaining data means already complete
    if remaining == 0:
        return datetime.now()

    # Calculate seconds remaining
    seconds_remaining = remaining / rate

    # Edge case: Check for overflow or infinity
    # timedelta.max is ~999999999 days * 86400 seconds/day
    max_seconds = 999_999_999 * 86400
    if not (0 < seconds_remaining < max_seconds):
        return None  # Cannot represent this far in the future

    try:
        # Return ETC as current time + remaining duration
        return datetime.now() + timedelta(seconds=seconds_remaining)
    except (OverflowError, ValueError):
        # Overflow in datetime calculation
        return None


def calculate_progress_data(
    *,
    baseline: int,
    current: int,
    samples: Sequence[DiskSample],
    window_size: int = 3,
) -> ProgressData:
    """Calculate comprehensive progress data from baseline, current usage, and sample history.

    This is a convenience function that combines all individual calculation functions
    to produce a complete ProgressData result with all metrics.

    Args:
        baseline: Starting disk usage in bytes (must be non-negative)
        current: Current disk usage in bytes (must be non-negative)
        samples: Sequence of disk usage samples for rate calculation
        window_size: Number of samples for moving average (default: 3)

    Returns:
        ProgressData dataclass with all calculated metrics

    Examples:
        >>> from datetime import datetime
        >>> samples = [
        ...     DiskSample(datetime(2024,1,1,10,0,0), 1000, "/cache"),
        ...     DiskSample(datetime(2024,1,1,10,0,10), 900, "/cache"),
        ... ]
        >>> progress = calculate_progress_data(baseline=1000, current=900, samples=samples)
        >>> progress.percent
        10.0
        >>> progress.remaining_bytes
        900
        >>> progress.moved_bytes
        100
    """
    # Calculate individual metrics
    percent = calculate_progress(baseline=baseline, current=current)
    remaining_bytes = calculate_remaining(baseline=baseline, current=current)
    moved_bytes = max(0, baseline - current)  # Ensure non-negative
    rate_bytes_per_second = calculate_rate(samples, window_size=window_size)
    etc = calculate_etc(remaining=remaining_bytes, rate=rate_bytes_per_second)

    return ProgressData(
        percent=percent,
        remaining_bytes=remaining_bytes,
        moved_bytes=moved_bytes,
        total_bytes=baseline,
        rate_bytes_per_second=rate_bytes_per_second,
        etc=etc,
    )


def evaluate_threshold_crossed(
    *,
    current_percent: float,
    thresholds: Sequence[float],
    notified_thresholds: Sequence[float],
) -> float | None:
    """Evaluate if a notification threshold has been crossed.

    Determines if the current progress percentage has crossed any configured
    threshold that has not already been notified. Returns the highest crossed
    threshold that hasn't been notified yet, or None if no new threshold crossed.

    This function enables notification dispatch only when progress crosses a new
    threshold, preventing duplicate notifications for the same threshold.

    Args:
        current_percent: Current progress percentage (0.0 to 100.0)
        thresholds: Sequence of threshold percentages to evaluate (0.0 to 100.0)
        notified_thresholds: Sequence of thresholds already notified (0.0 to 100.0)

    Returns:
        The highest crossed threshold not yet notified, or None if no new threshold

    Edge cases:
        - If current_percent < 0 or > 100, raises ValueError
        - If any threshold < 0 or > 100, raises ValueError
        - If thresholds is empty, returns None (no thresholds to evaluate)
        - If all crossed thresholds already notified, returns None
        - If multiple thresholds crossed, returns the highest one
        - Thresholds are evaluated with >= comparison (inclusive)

    Examples:
        >>> # First notification at 25%
        >>> evaluate_threshold_crossed(
        ...     current_percent=25.0,
        ...     thresholds=[0.0, 25.0, 50.0, 75.0, 100.0],
        ...     notified_thresholds=[0.0]
        ... )
        25.0

        >>> # No new threshold crossed (already notified 25%)
        >>> evaluate_threshold_crossed(
        ...     current_percent=30.0,
        ...     thresholds=[0.0, 25.0, 50.0, 75.0, 100.0],
        ...     notified_thresholds=[0.0, 25.0]
        ... )

        >>> # Multiple thresholds crossed, returns highest
        >>> evaluate_threshold_crossed(
        ...     current_percent=60.0,
        ...     thresholds=[0.0, 25.0, 50.0, 75.0, 100.0],
        ...     notified_thresholds=[0.0]
        ... )
        50.0
    """
    # Validate current_percent is in valid range
    if not 0.0 <= current_percent <= 100.0:
        msg = f"current_percent must be between 0.0 and 100.0, got: {current_percent}"
        raise ValueError(msg)

    # Validate all thresholds are in valid range
    for threshold in thresholds:
        if not 0.0 <= threshold <= 100.0:
            msg = f"threshold must be between 0.0 and 100.0, got: {threshold}"
            raise ValueError(msg)

    # Validate all notified_thresholds are in valid range
    for threshold in notified_thresholds:
        if not 0.0 <= threshold <= 100.0:
            msg = f"notified threshold must be between 0.0 and 100.0, got: {threshold}"
            raise ValueError(msg)

    # Edge case: No thresholds to evaluate
    if not thresholds:
        return None

    # Convert to sets for efficient lookup
    notified_set = set(notified_thresholds)

    # Find all crossed thresholds that haven't been notified
    # A threshold is "crossed" when current_percent >= threshold
    crossed_unnotified: list[float] = [
        threshold
        for threshold in thresholds
        if current_percent >= threshold and threshold not in notified_set
    ]

    # Edge case: No new thresholds crossed
    if not crossed_unnotified:
        return None

    # Return the highest crossed threshold
    # This ensures we notify for the most significant progress milestone
    return max(crossed_unnotified)
