"""Transfer rate calculation implementation."""

from __future__ import annotations

import time
from collections import deque
from decimal import Decimal
from enum import Enum

# Type alias for numeric types using modern Python 3.13 syntax
Number = int | float | Decimal


class RateUnit(Enum):
    """Units for transfer rate calculation."""
    BYTES_PER_SECOND = "bytes/s"
    KILOBYTES_PER_SECOND = "KB/s"
    MEGABYTES_PER_SECOND = "MB/s"
    GIGABYTES_PER_SECOND = "GB/s"


class SmoothingMethod(Enum):
    """Methods for smoothing transfer rate calculations."""
    SIMPLE_MOVING_AVERAGE = "simple"
    EXPONENTIAL_SMOOTHING = "exponential"
    WEIGHTED_MOVING_AVERAGE = "weighted"


class TransferRateCalculator:
    """Calculator for transfer rates with configurable smoothing and units."""

    window_size: int
    unit: RateUnit
    smoothing: SmoothingMethod
    alpha: float
    samples: deque[tuple[Number, float]]
    rate_history: deque[dict[str, float]]
    smoothed_rate: float

    def __init__(
        self,
        window_size: int = 10,
        unit: RateUnit = RateUnit.BYTES_PER_SECOND,
        smoothing: SmoothingMethod = SmoothingMethod.SIMPLE_MOVING_AVERAGE,
        alpha: float = 0.3,
    ) -> None:
        """Initialize the transfer rate calculator.

        Args:
            window_size: Number of samples to keep for rate calculation
            unit: Unit for rate calculation (bytes/s, KB/s, etc.)
            smoothing: Smoothing method to use
            alpha: Smoothing factor for exponential smoothing (0.0 to 1.0)
        """
        if window_size < 1:
            raise ValueError("Window size must be at least 1")

        if not 0.0 <= alpha <= 1.0:
            raise ValueError("Alpha must be between 0.0 and 1.0")

        self.window_size = window_size
        self.unit = unit
        self.smoothing = smoothing
        self.alpha = alpha

        # Storage for samples: (bytes_transferred, timestamp)
        self.samples = deque(maxlen=window_size)

        # Storage for calculated rates with timestamps
        self.rate_history = deque(maxlen=window_size)

        # For exponential smoothing
        self.smoothed_rate = 0.0
    
    def add_sample(self, bytes_transferred: Number, timestamp: float | None = None) -> None:
        """Add a new sample for rate calculation.

        Args:
            bytes_transferred: Total bytes transferred so far
            timestamp: Timestamp of the sample (uses current time if None)

        Raises:
            ValueError: If bytes_transferred is negative or timestamp is not monotonic
        """
        if float(bytes_transferred) < 0:
            raise ValueError("Progress cannot be negative")

        if timestamp is None:
            timestamp = time.time()
        else:
            # Ensure timestamp is always a float for consistent calculations
            timestamp = float(timestamp)

        # Check for monotonic timestamps
        if self.samples and timestamp < self.samples[-1][1]:
            raise ValueError("Timestamp must be monotonic (non-decreasing)")

        self.samples.append((bytes_transferred, timestamp))
        self._update_rate_calculation()
    
    def get_current_rate(self) -> float:
        """Get the current transfer rate.
        
        Returns:
            Current transfer rate in the configured unit
        """
        if len(self.samples) < 2:
            return 0.0
        
        if self.smoothing == SmoothingMethod.EXPONENTIAL_SMOOTHING:
            return self.smoothed_rate
        
        return self._calculate_average_rate()
    
    def get_instantaneous_rate(self) -> float:
        """Get the instantaneous rate between the last two samples.
        
        Returns:
            Instantaneous transfer rate in the configured unit
        """
        if len(self.samples) < 2:
            return 0.0
        
        last_sample = self.samples[-1]
        prev_sample = self.samples[-2]
        
        bytes_diff = float(last_sample[0]) - float(prev_sample[0])
        time_diff = last_sample[1] - prev_sample[1]
        
        if time_diff <= 0:
            return 0.0
        
        rate = bytes_diff / time_diff
        return self._convert_to_unit(rate)
    
    def get_rate_history(self) -> list[dict[str, float]]:
        """Get the history of rate calculations.

        Returns:
            List of rate history entries with rate and timestamp
        """
        return list(self.rate_history)
    
    def reset(self) -> None:
        """Reset the calculator state."""
        self.samples.clear()
        self.rate_history.clear()
        self.smoothed_rate = 0.0
    
    def _update_rate_calculation(self) -> None:
        """Update the rate calculation with the latest sample."""
        if len(self.samples) < 2:
            return
        
        current_rate = self._calculate_average_rate()
        
        if self.smoothing == SmoothingMethod.EXPONENTIAL_SMOOTHING:
            if self.smoothed_rate == 0.0:
                self.smoothed_rate = current_rate
            else:
                self.smoothed_rate = (self.alpha * current_rate + 
                                    (1 - self.alpha) * self.smoothed_rate)
        
        # Store rate history
        self.rate_history.append({
            'rate': current_rate,
            'timestamp': self.samples[-1][1],
            'smoothed_rate': self.smoothed_rate if self.smoothing == SmoothingMethod.EXPONENTIAL_SMOOTHING else current_rate
        })
    
    def _calculate_average_rate(self) -> float:
        """Calculate the average rate over the current window."""
        if len(self.samples) < 2:
            return 0.0
        
        if self.smoothing == SmoothingMethod.WEIGHTED_MOVING_AVERAGE:
            return self._calculate_weighted_average()
        
        # Simple moving average (default)
        first_sample = self.samples[0]
        last_sample = self.samples[-1]
        
        bytes_diff = float(last_sample[0]) - float(first_sample[0])
        time_diff = last_sample[1] - first_sample[1]
        
        if time_diff <= 0:
            return 0.0
        
        rate = bytes_diff / time_diff
        return self._convert_to_unit(rate)
    
    def _calculate_weighted_average(self) -> float:
        """Calculate weighted moving average with more recent samples having higher weight."""
        if len(self.samples) < 2:
            return 0.0
        
        total_weighted_rate = 0.0
        total_weight = 0.0
        
        # Calculate rates between consecutive samples
        for i in range(1, len(self.samples)):
            prev_sample = self.samples[i-1]
            curr_sample = self.samples[i]
            
            bytes_diff = float(curr_sample[0]) - float(prev_sample[0])
            time_diff = curr_sample[1] - prev_sample[1]
            
            if time_diff > 0:
                rate = bytes_diff / time_diff
                weight = float(i)  # More recent samples get higher weight
                total_weighted_rate += rate * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        average_rate = total_weighted_rate / total_weight
        return self._convert_to_unit(average_rate)
    
    def _convert_to_unit(self, rate_bytes_per_second: float) -> float:
        """Convert rate from bytes/second to the configured unit.
        
        Args:
            rate_bytes_per_second: Rate in bytes per second
            
        Returns:
            Rate in the configured unit
        """
        if self.unit == RateUnit.BYTES_PER_SECOND:
            return rate_bytes_per_second
        elif self.unit == RateUnit.KILOBYTES_PER_SECOND:
            return rate_bytes_per_second / 1024.0
        elif self.unit == RateUnit.MEGABYTES_PER_SECOND:
            return rate_bytes_per_second / (1024.0 * 1024.0)
        elif self.unit == RateUnit.GIGABYTES_PER_SECOND:
            return rate_bytes_per_second / (1024.0 * 1024.0 * 1024.0)
        else:
            return rate_bytes_per_second
