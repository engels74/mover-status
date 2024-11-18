# core/calculator.py

"""
Data transfer calculation utilities for monitoring mover progress.
Handles cache directory size monitoring, transfer rate calculations,
and estimated time remaining predictions.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

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
        self._transfer_history: List[Tuple[datetime, ByteSize]] = []
        self._window_size = 5  # Number of samples for moving average
        self._current_stats: Optional[TransferStats] = None
        self._initial_size: Optional[ByteSize] = None
        self._start_time: Optional[datetime] = None

    def initialize_transfer(self, initial_size: ByteSize) -> None:
        """Initialize new transfer monitoring.

        Args:
            initial_size: Initial size of cache directory in bytes
        """
        self._initial_size = initial_size
        self._start_time = datetime.now()
        self._transfer_history.clear()
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
            ValueError: If transfer not initialized
        """
        if not self._initial_size or not self._start_time:
            raise ValueError("Transfer not initialized")

        now = datetime.now()

        # Update transfer history
        self._transfer_history.append((now, current_size))
        if len(self._transfer_history) > self._window_size:
            self._transfer_history.pop(0)

        # Calculate bytes moved and progress
        bytes_moved = self._initial_size - current_size
        if bytes_moved < 0:
            logger.warning("Negative bytes moved detected, resetting to 0")
            bytes_moved = 0

        total_bytes = bytes_moved + current_size
        percent_complete = (bytes_moved / total_bytes * 100) if total_bytes > 0 else 0.0

        # Calculate transfer rate using moving average
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
            percent_complete=percent_complete,
            start_time=self._start_time,
            estimated_completion=estimated_completion
        )

        return self._current_stats

    def _calculate_transfer_rate(self) -> float:
        """Calculate current transfer rate using moving average.

        Returns:
            float: Transfer rate in bytes per second
        """
        if len(self._transfer_history) < 2:
            return 0.0

        # Calculate rates between consecutive samples
        rates = []
        for i in range(1, len(self._transfer_history)):
            time_prev, size_prev = self._transfer_history[i - 1]
            time_curr, size_curr = self._transfer_history[i]

            time_diff = (time_curr - time_prev).total_seconds()
            if time_diff > 0:
                size_diff = size_prev - size_curr  # Size decreases as files move
                if size_diff > 0:  # Only count positive transfers
                    rates.append(size_diff / time_diff)

        # Return average rate
        return sum(rates) / len(rates) if rates else 0.0

    def _estimate_completion_time(
        self,
        current_size: ByteSize,
        transfer_rate: float
    ) -> Optional[datetime]:
        """Estimate transfer completion time.

        Args:
            current_size: Current cache directory size
            transfer_rate: Current transfer rate (bytes/sec)

        Returns:
            Optional[datetime]: Estimated completion time or None if cannot estimate
        """
        if transfer_rate <= 0 or current_size <= 0:
            return None

        # Calculate remaining time
        seconds_remaining = current_size / transfer_rate

        # Add some buffer for filesystem operations
        buffer_factor = 1.1  # 10% buffer
        seconds_remaining *= buffer_factor

        # Return estimated completion time
        return datetime.now() + timedelta(seconds=seconds_remaining)

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
        logger.info("Transfer calculator reset")

    async def monitor_transfer(
        self,
        get_current_size: callable,
        update_interval: float = 1.0
    ) -> None:
        """Monitor transfer progress continuously.

        Args:
            get_current_size: Callable that returns current cache size
            update_interval: Update interval in seconds

        Raises:
            ValueError: If transfer not initialized
        """
        if not self._initial_size:
            raise ValueError("Transfer not initialized")

        logger.info("Starting transfer monitoring")
        try:
            while True:
                current_size = await get_current_size()
                stats = self.update_progress(current_size)

                logger.debug(
                    "Transfer progress updated",
                    current_size=format_size(stats.current_size),
                    bytes_moved=format_size(stats.bytes_moved),
                    percent_complete=f"{stats.percent_complete:.1f}%",
                    transfer_rate=f"{format_size(int(stats.transfer_rate))}/s"
                )

                await asyncio.sleep(update_interval)

        except asyncio.CancelledError:
            logger.info("Transfer monitoring stopped")
            raise
        except Exception as err:
            logger.error("Transfer monitoring error", error=str(err))
            raise
