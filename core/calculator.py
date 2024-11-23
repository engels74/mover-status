# core/calculator.py

"""
Data transfer calculation utilities for monitoring mover progress.
Handles cache directory size monitoring, transfer rate calculations,
and estimated time remaining predictions.

Example:
    >>> calculator = TransferCalculator(settings)
    >>> calculator.initialize_transfer(initial_size=1024**3)  # 1GB
    >>> stats = calculator.update_progress(current_size=512*1024**2)  # 512MB
    >>> print(f"Progress: {stats.percent_complete}%")
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Deque, List, Optional, Tuple

from structlog import get_logger

from config.constants import ByteSize
from config.settings import Settings
from utils.formatters import format_size

logger = get_logger(__name__)

@dataclass
class TransferStats:
    """Statistics for ongoing data transfer."""
    initial_size: ByteSize           # Initial cache size
    current_size: ByteSize          # Current cache size
    bytes_moved: ByteSize           # Total bytes moved
    transfer_rate: float            # Current transfer rate (bytes/sec)
    percent_complete: float         # Progress percentage
    start_time: datetime           # Transfer start time
    estimated_completion: Optional[datetime] = None  # Estimated completion time
    moving_average_window: int = field(default=5, repr=False)  # Window size for rate calculation
    _rate_history: Deque[float] = field(default_factory=lambda: deque(maxlen=5), repr=False)

    def update_rate(self, new_rate: float) -> None:
        """Update transfer rate using moving average.

        Args:
            new_rate: New transfer rate to add to history
        """
        self._rate_history.append(new_rate)
        self.transfer_rate = sum(self._rate_history) / len(self._rate_history)

class TransferCalculator:
    """
    Calculates and tracks data transfer progress.
    Maintains historical data for accurate rate and ETA calculations.
    """

    def __init__(self, settings: Settings):
        """Initialize calculator with settings.

        Args:
            settings: Application settings instance
        """
        self._settings = settings
        self._window_size = 5  # Number of samples for moving average
        self._transfer_history: List[Tuple[datetime, ByteSize]] = []
        self._current_stats: Optional[TransferStats] = None
        self._initial_size: Optional[ByteSize] = None
        self._start_time: Optional[datetime] = None
        self._min_sample_interval = 0.5  # Minimum seconds between samples
        self._last_sample_time: Optional[datetime] = None

    def initialize_transfer(self, initial_size: ByteSize) -> None:
        """Initialize new transfer monitoring.

        Args:
            initial_size: Initial size of cache directory in bytes

        Raises:
            ValueError: If initial size is invalid
        """
        if initial_size <= 0:
            raise ValueError("Initial size must be positive")

        self._initial_size = initial_size
        self._start_time = datetime.now()
        self._transfer_history.clear()
        self._last_sample_time = None
        self._current_stats = TransferStats(
            initial_size=initial_size,
            current_size=initial_size,
            bytes_moved=0,
            transfer_rate=0.0,
            percent_complete=0.0,
            start_time=self._start_time
        )
        logger.info(
            "Transfer monitoring initialized",
            initial_size=format_size(initial_size)
        )

    def update_progress(self, current_size: ByteSize) -> TransferStats:
        """Update transfer progress with current cache size.

        Args:
            current_size: Current size of cache directory in bytes

        Returns:
            TransferStats: Updated transfer statistics

        Raises:
            ValueError: If transfer not initialized or current size invalid
        """
        if not self._initial_size or not self._start_time:
            raise ValueError("Transfer not initialized")

        if current_size < 0:
            raise ValueError("Current size cannot be negative")

        now = datetime.now()

        # Enforce minimum sample interval
        if (self._last_sample_time and
            (now - self._last_sample_time).total_seconds() < self._min_sample_interval):
            return self._current_stats

        # Update transfer history
        self._transfer_history.append((now, current_size))
        if len(self._transfer_history) > self._window_size:
            self._transfer_history.pop(0)

        # Calculate bytes moved and progress
        bytes_moved = max(0, self._initial_size - current_size)
        total_bytes = bytes_moved + current_size

        # Handle edge case where total_bytes is 0
        percent_complete = (bytes_moved / total_bytes * 100) if total_bytes > 0 else 0.0

        # Calculate transfer rate using weighted moving average
        transfer_rate = self._calculate_transfer_rate()

        # Estimate completion time
        estimated_completion = self._estimate_completion_time(
            current_size, transfer_rate
        ) if transfer_rate > 0 else None

        # Update current stats
        self._current_stats = TransferStats(
            initial_size=self._initial_size,
            current_size=current_size,
            bytes_moved=bytes_moved,
            transfer_rate=transfer_rate,
            percent_complete=min(100.0, percent_complete),  # Ensure doesn't exceed 100%
            start_time=self._start_time,
            estimated_completion=estimated_completion
        )

        self._last_sample_time = now
        return self._current_stats

    def _calculate_transfer_rate(self) -> float:
        """Calculate current transfer rate using weighted moving average.

        Returns:
            float: Transfer rate in bytes per second
        """
        if len(self._transfer_history) < 2:
            return 0.0

        rates = []
        weights = []
        total_weight = 0

        # Calculate weighted rates between consecutive samples
        for i in range(1, len(self._transfer_history)):
            time_prev, size_prev = self._transfer_history[i - 1]
            time_curr, size_curr = self._transfer_history[i]

            time_diff = (time_curr - time_prev).total_seconds()
            if time_diff > 0:
                size_diff = max(0, size_prev - size_curr)  # Ensure non-negative
                rate = size_diff / time_diff
                # More recent samples get higher weights
                weight = i / len(self._transfer_history)
                rates.append(rate)
                weights.append(weight)
                total_weight += weight

        # Calculate weighted average
        if not rates or total_weight == 0:
            return 0.0

        weighted_sum = sum(rate * weight for rate, weight in zip(rates, weights, strict=False))
        return weighted_sum / total_weight

    def _estimate_completion_time(
        self,
        current_size: ByteSize,
        transfer_rate: float,
        confidence_factor: float = 1.1  # 10% buffer
    ) -> Optional[datetime]:
        """Estimate transfer completion time.

        Args:
            current_size: Current cache directory size
            transfer_rate: Current transfer rate (bytes/sec)
            confidence_factor: Buffer factor for estimation

        Returns:
            Optional[datetime]: Estimated completion time or None if cannot estimate
        """
        if transfer_rate <= 0 or current_size <= 0:
            return None

        try:
            # Calculate remaining time with buffer
            seconds_remaining = (current_size / transfer_rate) * confidence_factor

            # Apply reasonable bounds
            max_remaining = timedelta(days=7)  # Cap at 1 week
            seconds_remaining = min(seconds_remaining, max_remaining.total_seconds())

            return datetime.now() + timedelta(seconds=seconds_remaining)

        except (ZeroDivisionError, OverflowError):
            return None

    def get_current_stats(self) -> Optional[TransferStats]:
        """Get current transfer statistics.

        Returns:
            Optional[TransferStats]: Current statistics or None if not initialized
        """
        return self._current_stats

    def reset(self) -> None:
        """Reset calculator state."""
        self._transfer_history.clear()
        self._initial_size = None
        self._start_time = None
        self._current_stats = None
        self._last_sample_time = None
        logger.info("Transfer calculator reset")

    async def monitor_transfer(
        self,
        get_current_size: callable,
        update_interval: float = 1.0
    ) -> None:
        """Monitor transfer progress continuously.

        Args:
            get_current_size: Async callable that returns current cache size
            update_interval: Update interval in seconds

        Raises:
            ValueError: If transfer not initialized or interval invalid
            TypeError: If get_current_size is not callable
        """
        if not self._initial_size:
            raise ValueError("Transfer not initialized")

        if update_interval <= 0:
            raise ValueError("Update interval must be positive")

        if not callable(get_current_size):
            raise TypeError("get_current_size must be callable")

        logger.info("Starting transfer monitoring")
        try:
            while True:
                try:
                    current_size = await get_current_size()
                    stats = self.update_progress(current_size)

                    logger.debug(
                        "Transfer progress updated",
                        current_size=format_size(stats.current_size),
                        bytes_moved=format_size(stats.bytes_moved),
                        percent_complete=f"{stats.percent_complete:.1f}%",
                        transfer_rate=f"{format_size(int(stats.transfer_rate))}/s"
                    )

                except (ValueError, TypeError) as err:
                    logger.error(f"Error updating progress: {err}")
                    # Continue monitoring despite errors

                await asyncio.sleep(update_interval)

        except asyncio.CancelledError:
            logger.info("Transfer monitoring stopped")
            raise
        except Exception as err:
            logger.error("Transfer monitoring error", error=str(err))
            raise
