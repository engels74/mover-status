# core/calculator.py

"""
Data transfer calculation utilities for monitoring mover progress.
This module implements the core calculation logic for tracking file transfer
progress, including size monitoring, rate calculations, and time estimations.

Components:
- TransferStats: Data structure for transfer statistics and progress metrics
- TransferCalculator: Main calculator for transfer progress and estimations

Features:
- Real-time transfer rate calculation with moving average
- Progress tracking with percentage completion
- Time estimation (elapsed and remaining)
- Size-based progress monitoring
- Continuous monitoring with configurable intervals
- Error handling and boundary checks

Example:
    >>> from core.calculator import TransferCalculator
    >>> from config.settings import Settings
    >>>
    >>> # Initialize calculator
    >>> settings = Settings.from_file("config.yaml")
    >>> calculator = TransferCalculator(settings)
    >>>
    >>> # Start tracking a 1GB transfer
    >>> calculator.initialize_transfer(initial_size=1024**3)
    >>>
    >>> # Update progress (500MB remaining)
    >>> stats = calculator.update_progress(current_size=512*1024**2)
    >>> print(f"Progress: {stats.percent_complete}%")
    >>> print(f"Transfer Rate: {stats.transfer_rate/1024**2:.1f} MB/s")
    >>> print(f"Time Remaining: {stats.remaining_time:.0f} seconds")
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
    """Statistics and metrics for a data transfer operation.

    Tracks comprehensive statistics about an ongoing transfer operation,
    including size metrics, progress calculations, timing information,
    and rate measurements.

    All size measurements are in bytes, and time measurements in seconds
    unless otherwise specified.

    Attributes:
        initial_size (int): Total size of data to be transferred
        current_size (int): Current size remaining to transfer
        bytes_transferred (int): Number of bytes already transferred
        bytes_remaining (int): Number of bytes still to transfer
        percent_complete (float): Transfer completion percentage (0-100)
        transfer_rate (float): Current transfer speed in bytes/second
        elapsed_time (float): Time elapsed since transfer start in seconds
        remaining_time (float): Estimated time to completion in seconds
        start_time (Optional[datetime]): Transfer start timestamp
        end_time (Optional[datetime]): Transfer completion timestamp or None

    Example:
        >>> stats = calculator.get_current_stats()
        >>> if stats:
        ...     print(f"Progress: {stats.percent_complete:.1f}%")
        ...     print(f"Speed: {stats.transfer_rate/1024**2:.1f} MB/s")
        ...     print(f"ETA: {stats.remaining_time/60:.1f} minutes")
    """
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
    """Advanced calculator for transfer progress and performance metrics.

    This class provides comprehensive transfer progress tracking and statistical
    analysis for file transfer operations. It uses a moving average approach
    for transfer rate calculations to provide stable estimates.

    Features:
    - Initialization with size validation
    - Real-time progress tracking
    - Moving average transfer rate calculation
    - Time remaining estimation
    - Continuous monitoring capability
    - Boundary checking and error handling

    The calculator maintains internal state to track:
    - Initial and current transfer sizes
    - Timing information (start, last update)
    - Rate history for moving average calculation
    - Transfer lifecycle (start to completion)

    Attributes:
        _settings (Settings): Application configuration
        _initial_size (Optional[int]): Total transfer size in bytes
        _start_time (Optional[datetime]): Transfer start timestamp
        _last_update (Optional[datetime]): Last progress update timestamp
        _last_size (Optional[int]): Previous recorded size
        _rate_history (Deque[float]): Recent transfer rates for averaging

    Example:
        >>> calculator = TransferCalculator(settings)
        >>>
        >>> # Initialize a new transfer
        >>> calculator.initialize_transfer(initial_size=1024**3)  # 1GB
        >>>
        >>> # Monitor progress with custom size checker
        >>> async def get_size():
        ...     return current_cache_size()
        >>>
        >>> await calculator.monitor_transfer(
        ...     get_current_size=get_size,
        ...     update_interval=2.0
        ... )
    """

    def __init__(self, settings: Settings):
        """Initialize the transfer calculator with configuration settings.

        Sets up internal state tracking and configures the rate history buffer
        for transfer speed calculations using a moving average approach.

        Args:
            settings (Settings): Application configuration containing transfer
                monitoring settings and thresholds
        """
        self._settings = settings
        self._initial_size: Optional[int] = None
        self._start_time: Optional[datetime] = None
        self._last_update: Optional[datetime] = None
        self._last_size: Optional[int] = None
        self._rate_history: Deque[float] = deque(maxlen=10)

    def initialize_transfer(self, initial_size: int) -> None:
        """Initialize a new transfer operation with size validation.

        Prepares the calculator for monitoring a new transfer by setting up
        initial state and validating the transfer size. This method must be
        called before any progress updates can be processed.

        Args:
            initial_size (int): Total size of data to be transferred in bytes

        Raises:
            ValueError: If initial size is not positive or exceeds maximum limit
                (1 PB) to prevent integer overflow issues

        Example:
            >>> # Initialize a 2GB transfer
            >>> calculator.initialize_transfer(2 * 1024**3)
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
        """Update transfer progress and calculate comprehensive statistics.

        Processes a new size measurement to update transfer progress metrics,
        including completion percentage, transfer rate, and time estimates.
        Uses a moving average for transfer rate to provide stable estimates.

        Args:
            current_size (int): Current size remaining to transfer in bytes

        Returns:
            TransferStats: Updated transfer statistics including progress,
                speed, and timing information

        Raises:
            ValueError: If transfer not initialized or current_size is invalid
                (negative or exceeds initial size)

        Example:
            >>> stats = calculator.update_progress(750_000_000)
            >>> print(f"Progress: {stats.percent_complete:.1f}%")
            >>> print(f"Speed: {stats.transfer_rate/1024**2:.1f} MB/s")
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
        """Reset calculator state for a new transfer operation.

        Clears all internal state including:
        - Initial and current sizes
        - Timing information
        - Rate history buffer
        - Progress tracking variables

        This method should be called when abandoning a transfer or
        preparing for a new one without initializing it immediately.

        Example:
            >>> calculator.reset()  # Clear state for new transfer
        """
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
        """Monitor transfer progress continuously with async updates.

        Starts an asynchronous monitoring loop that periodically checks
        transfer progress using the provided size callback function.
        Continues until the transfer completes or monitoring is cancelled.

        Args:
            get_current_size (callable): Async function that returns current
                cache size in bytes when called
            update_interval (float, optional): Time between updates in seconds.
                Defaults to 1.0 second.

        Raises:
            ValueError: If transfer not initialized or interval <= 0
            TypeError: If get_current_size is not a callable function
            asyncio.CancelledError: If monitoring is cancelled
            Exception: If monitoring encounters an unrecoverable error

        Example:
            >>> async def get_size():
            ...     return await measure_cache_size()
            >>>
            >>> try:
            ...     await calculator.monitor_transfer(get_size, 2.0)
            ... except asyncio.CancelledError:
            ...     print("Monitoring stopped")
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
        """Get current transfer statistics snapshot.

        Creates a new TransferStats object with the current state of the
        transfer. Returns None if the transfer has not been initialized
        or is in an invalid state.

        Returns:
            Optional[TransferStats]: Current transfer statistics or None
                if transfer not initialized

        Example:
            >>> stats = calculator.get_current_stats()
            >>> if stats:
            ...     print(f"Progress: {stats.percent_complete}%")
            ...     print(f"Transferred: {stats.bytes_transferred}")
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
