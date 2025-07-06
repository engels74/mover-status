"""Unified progress calculation engine that combines all progress tracking components."""

from __future__ import annotations

import time
from dataclasses import dataclass

from .percentage_calculator import ProgressPercentageCalculator, Number
from .transfer_rate_calculator import TransferRateCalculator, RateUnit, SmoothingMethod
from .etc_estimator import ETCEstimator, EstimationMethod, ETCResult


@dataclass
class ProgressMetrics:
    """Comprehensive progress metrics combining all calculation components."""
    
    percentage: float
    bytes_remaining: int
    transfer_rate: float
    etc_seconds: float | None


class ProgressCalculator:
    """Unified progress calculation engine that orchestrates all progress tracking components.
    
    This class integrates percentage calculation, transfer rate computation, and ETC estimation
    to provide comprehensive progress tracking with a single, easy-to-use interface.
    """

    percentage_calc: ProgressPercentageCalculator
    rate_calc: TransferRateCalculator
    etc_calc: ETCEstimator
    _last_transferred: int
    _last_timestamp: float

    def __init__(
        self,
        precision: int = 2,
        window_size: int = 10,
        rate_unit: RateUnit = RateUnit.BYTES_PER_SECOND,
        smoothing: SmoothingMethod = SmoothingMethod.SIMPLE_MOVING_AVERAGE,
        etc_method: EstimationMethod = EstimationMethod.LINEAR_PROJECTION,
        alpha: float = 0.3,
    ) -> None:
        """Initialize the unified progress calculator.
        
        Args:
            precision: Number of decimal places for percentage calculations
            window_size: Size of the sliding window for rate calculations
            rate_unit: Unit for transfer rate calculations
            smoothing: Smoothing method for rate calculations
            etc_method: Method for ETC estimation
            alpha: Smoothing factor for exponential smoothing algorithms
        """
        self.percentage_calc = ProgressPercentageCalculator(precision=precision)
        self.rate_calc = TransferRateCalculator(
            window_size=window_size,
            unit=rate_unit,
            smoothing=smoothing,
            alpha=alpha,
        )
        self.etc_calc = ETCEstimator(
            method=etc_method,
            window_size=window_size,
            alpha=alpha,
        )
        self._last_transferred = 0
        self._last_timestamp = 0.0

    def calculate_progress(self, transferred: Number, total: Number) -> ProgressMetrics:
        """Calculate comprehensive progress metrics.
        
        Args:
            transferred: Amount of data transferred so far
            total: Total amount of data to transfer
            
        Returns:
            ProgressMetrics containing percentage, remaining bytes, transfer rate, and ETC
            
        Raises:
            ValueError: If transferred or total are negative
        """
        # Input validation
        if transferred < 0:
            raise ValueError("Progress cannot be negative")
        if total < 0:
            raise ValueError("Total cannot be negative")
        
        # Calculate percentage
        percentage = self.percentage_calc.calculate_percentage(transferred, total)
        
        # Calculate bytes remaining (ensure non-negative)
        # Convert to float first to handle decimals properly
        remaining_float = max(0.0, float(total) - float(transferred))
        bytes_remaining = int(remaining_float)
        
        # Handle completion case
        if percentage >= 100.0:
            return ProgressMetrics(
                percentage=100.0,
                bytes_remaining=0,
                transfer_rate=0.0,
                etc_seconds=0.0,
            )
        
        # Update rate calculator with new sample
        current_time = time.time()
        self.rate_calc.add_sample(transferred, current_time)
        
        # Get current transfer rate
        transfer_rate = self.rate_calc.get_current_rate()
        
        # Update ETC estimator
        self.etc_calc.add_sample(transferred, total, current_time)
        
        # Get ETC estimate
        etc_result = self.etc_calc.get_etc()
        # Return None if there's no meaningful ETC estimate (no confidence)
        etc_seconds = etc_result.seconds if etc_result.confidence > 0.0 else None
        
        return ProgressMetrics(
            percentage=percentage,
            bytes_remaining=bytes_remaining,
            transfer_rate=transfer_rate,
            etc_seconds=etc_seconds,
        )

    def reset(self) -> None:
        """Reset all internal state and history."""
        self.rate_calc.reset()
        self.etc_calc.reset()
        self._last_transferred = 0
        self._last_timestamp = 0.0

    def get_detailed_etc(self) -> ETCResult | None:
        """Get detailed ETC estimation with confidence intervals.
        
        Returns:
            ETCResult with detailed estimation information, or None if insufficient data
        """
        return self.etc_calc.get_etc()

    def get_rate_history(self) -> list[dict[str, float]]:
        """Get the history of transfer rates.
        
        Returns:
            List of rate history entries with timestamps and rates
        """
        return self.rate_calc.get_rate_history()

    def get_instantaneous_rate(self) -> float:
        """Get the instantaneous transfer rate.
        
        Returns:
            Current instantaneous transfer rate
        """
        return self.rate_calc.get_instantaneous_rate()

    @property
    def is_stalled(self) -> bool:
        """Check if the transfer appears to be stalled.
        
        Returns:
            True if the transfer rate is effectively zero
        """
        return self.rate_calc.get_current_rate() == 0.0

    @property
    def sample_count(self) -> int:
        """Get the number of samples collected.
        
        Returns:
            Number of samples in the rate calculator history
        """
        return len(self.rate_calc.samples)