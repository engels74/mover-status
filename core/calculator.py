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
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Optional

from structlog import get_logger

from config.constants import Units
from config.settings import Settings
from utils.formatters import format_size

logger = get_logger(__name__)

@dataclass
class TransferStats:
    """Statistics for a data transfer operation."""
    initial_size: int = 0
    current_size: int = 0
    bytes_transferred: int = 0
    bytes_remaining: int = 0
    percent_complete: float = 0.0
    transfer_rate: float = 0.0  # bytes/second
    elapsed_time: float = 0.0  # seconds
    remaining_time: float = 0.0  # seconds
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class TransferCalculator:
    """Calculates transfer progress and statistics."""

    def __init__(self, settings: Settings):
        """Initialize calculator with settings.

        Args:
            settings: Application settings
        """
        self._settings = settings
        self._initial_size: Optional[int] = None
        self._start_time: Optional[datetime] = None
        self._last_update: Optional[datetime] = None
        self._last_size: Optional[int] = None
        self._rate_history: Deque[float] = deque(maxlen=10)

    def initialize_transfer(self, initial_size: int) -> None:
        """Initialize a new transfer operation.

        Args:
            initial_size: Initial size in bytes
        """
        if initial_size <= 0:
            raise ValueError("Initial size must be positive")

        if initial_size > Units.ByteSize.PETABYTE:
            raise ValueError(f"Initial size exceeds maximum ({format_size(Units.ByteSize.PETABYTE)})")

        self._initial_size = initial_size
        self._start_time = datetime.now()
        self._last_update = None
        self._last_size = None
        self._rate_history.clear()

        logger.debug(
            "Transfer initialized",
            initial_size=format_size(initial_size)
        )

    def update_progress(self, current_size: int) -> TransferStats:
        """Update transfer progress and calculate statistics.

        Args:
            current_size: Current size in bytes

        Returns:
            TransferStats: Updated transfer statistics

        Raises:
            ValueError: If transfer not initialized or invalid size
        """
        if self._initial_size is None or self._start_time is None:
            raise ValueError("Transfer not initialized")

        if current_size < 0:
            raise ValueError("Current size cannot be negative")

        if current_size > self._initial_size:
            logger.warning(
                "Current size exceeds initial size",
                current=format_size(current_size),
                initial=format_size(self._initial_size)
            )
            current_size = self._initial_size

        # Calculate basic metrics
        now = datetime.now()
        elapsed = (now - self._start_time).total_seconds()
        bytes_transferred = self._initial_size - current_size
        bytes_remaining = current_size
        percent_complete = (bytes_transferred / self._initial_size) * 100

        # Calculate transfer rate
        if self._last_update and self._last_size is not None:
            time_delta = (now - self._last_update).total_seconds()
            if time_delta > 0:
                size_delta = abs(current_size - self._last_size)
                current_rate = size_delta / time_delta
                self._rate_history.append(current_rate)

        # Update tracking variables
        self._last_update = now
        self._last_size = current_size

        # Calculate average transfer rate
        transfer_rate = (
            sum(self._rate_history) / len(self._rate_history)
            if self._rate_history
            else 0.0
        )

        # Estimate remaining time
        remaining_time = (
            bytes_remaining / transfer_rate if transfer_rate > 0 else 0.0
        )

        # Create statistics object
        stats = TransferStats(
            initial_size=self._initial_size,
            current_size=current_size,
            bytes_transferred=bytes_transferred,
            bytes_remaining=bytes_remaining,
            percent_complete=round(percent_complete, 2),
            transfer_rate=transfer_rate,
            elapsed_time=elapsed,
            remaining_time=remaining_time,
            start_time=self._start_time,
            end_time=now if percent_complete >= 100 else None
        )

        logger.debug(
            "Progress updated",
            percent=f"{stats.percent_complete:.1f}%",
            remaining=format_size(stats.bytes_remaining),
            rate=f"{format_size(stats.transfer_rate)}/s"
        )

        return stats

    def reset(self) -> None:
        """Reset calculator state."""
        self._initial_size = None
        self._start_time = None
        self._last_update = None
        self._last_size = None
        self._rate_history.clear()
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
                        bytes_transferred=format_size(stats.bytes_transferred),
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

    def get_current_stats(self) -> Optional[TransferStats]:
        """Get current transfer statistics.

        Returns:
            Optional[TransferStats]: Current statistics or None if not initialized
        """
        return TransferStats(
            initial_size=self._initial_size,
            current_size=self._last_size,
            bytes_transferred=self._initial_size - self._last_size,
            bytes_remaining=self._last_size,
            percent_complete=0.0,
            transfer_rate=0.0,
            elapsed_time=0.0,
            remaining_time=0.0,
            start_time=self._start_time,
            end_time=None
        ) if self._initial_size and self._last_size else None
