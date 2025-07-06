"""ETC (Estimated Time to Completion) estimation implementation."""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


# Type alias for numeric types using modern Python 3.13 syntax
Number = int | float | Decimal


class EstimationMethod(Enum):
    """Available ETC estimation methods."""
    LINEAR_PROJECTION = "linear_projection"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    ADAPTIVE = "adaptive"


@dataclass
class ETCResult:
    """Result of ETC estimation."""
    seconds: float
    method: EstimationMethod
    confidence: float
    confidence_min: float | None = None
    confidence_max: float | None = None


class ETCEstimator:
    """Sophisticated ETC estimator with multiple prediction methods."""

    method: EstimationMethod
    window_size: int
    alpha: float
    min_samples: int

    def __init__(
        self,
        method: EstimationMethod = EstimationMethod.LINEAR_PROJECTION,
        window_size: int = 10,
        alpha: float = 0.3,
        min_samples: int = 2,
    ) -> None:
        """Initialize the ETC estimator.
        
        Args:
            method: Primary estimation method to use
            window_size: Number of samples to keep for calculations
            alpha: Smoothing factor for exponential smoothing (0.0 to 1.0)
            min_samples: Minimum samples required for estimation
        """
        if window_size < 1:
            raise ValueError("Window size must be at least 1")
        
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("Alpha must be between 0.0 and 1.0")
        
        if min_samples < 1:
            raise ValueError("Minimum samples must be at least 1")
        
        self.method = method
        self.window_size = window_size
        self.alpha = alpha
        self.min_samples = min_samples
        
        # Store samples as (bytes_transferred, total_size, timestamp)
        self.samples: deque[tuple[float, float, float]] = deque(maxlen=window_size)
        
        # For exponential smoothing
        self.smoothed_rate: float = 0.0
        
        # For adaptive method
        self.rate_variance_history: deque[float] = deque(maxlen=window_size)
    
    def add_sample(self, bytes_transferred: Number, total_size: Number, timestamp: float | None = None) -> None:
        """Add a progress sample for ETC calculation.
        
        Args:
            bytes_transferred: Current bytes transferred
            total_size: Total size of the transfer
            timestamp: Optional timestamp (uses current time if None)
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Convert to float for calculations
        bytes_val = float(bytes_transferred)
        total_val = float(total_size)
        
        # Validate inputs
        if bytes_val < 0:
            raise ValueError("Bytes transferred cannot be negative")
        
        if total_val < 0:
            raise ValueError("Total size cannot be negative")
        
        if bytes_val > total_val:
            # Cap at total size
            bytes_val = total_val
        
        # Validate timestamp ordering
        if self.samples and timestamp < self.samples[-1][2]:
            raise ValueError("Timestamps must be monotonically increasing")
        
        self.samples.append((bytes_val, total_val, timestamp))
        
        # Update rate calculations for adaptive method
        if len(self.samples) >= 2:
            self._update_rate_statistics()
    
    def get_etc(self) -> ETCResult:
        """Get ETC estimate using the configured method.
        
        Returns:
            ETCResult with estimation details
        """
        return self.get_etc_with_method(self.method)
    
    def get_etc_with_method(self, method: EstimationMethod) -> ETCResult:
        """Get ETC estimate using a specific method.
        
        Args:
            method: Estimation method to use
            
        Returns:
            ETCResult with estimation details
        """
        if len(self.samples) == 0:
            return ETCResult(0.0, method, 0.0)
        
        # Check if transfer is complete
        last_sample = self.samples[-1]
        if last_sample[0] >= last_sample[1]:  # bytes_transferred >= total_size
            return ETCResult(0.0, method, 1.0)
        
        if len(self.samples) < self.min_samples:
            # Insufficient data for reliable estimation
            return ETCResult(0.0, method, 0.0)
        
        if method == EstimationMethod.LINEAR_PROJECTION:
            return self._linear_projection()
        elif method == EstimationMethod.EXPONENTIAL_SMOOTHING:
            return self._exponential_smoothing()
        else:  # method == EstimationMethod.ADAPTIVE
            return self._adaptive_estimation()
    
    def reset(self) -> None:
        """Reset the estimator state."""
        self.samples.clear()
        self.rate_variance_history.clear()
        self.smoothed_rate = 0.0
    
    def _linear_projection(self) -> ETCResult:
        """Calculate ETC using linear projection."""
        if len(self.samples) < 2:
            return ETCResult(0.0, EstimationMethod.LINEAR_PROJECTION, 0.0)
        
        first_sample = self.samples[0]
        last_sample = self.samples[-1]
        
        bytes_diff = last_sample[0] - first_sample[0]
        time_diff = last_sample[2] - first_sample[2]
        
        if time_diff <= 0 or bytes_diff <= 0:
            return ETCResult(0.0, EstimationMethod.LINEAR_PROJECTION, 0.0)
        
        # Calculate average rate
        rate = bytes_diff / time_diff
        
        # Calculate remaining bytes and time
        remaining_bytes = last_sample[1] - last_sample[0]
        etc_seconds = remaining_bytes / rate
        
        # Calculate confidence based on rate consistency
        confidence = self._calculate_confidence()
        
        # Calculate confidence intervals
        confidence_range = etc_seconds * (1.0 - confidence) * 0.5
        confidence_min = max(0.0, etc_seconds - confidence_range)
        confidence_max = etc_seconds + confidence_range
        
        return ETCResult(
            seconds=etc_seconds,
            method=EstimationMethod.LINEAR_PROJECTION,
            confidence=confidence,
            confidence_min=confidence_min,
            confidence_max=confidence_max
        )
    
    def _exponential_smoothing(self) -> ETCResult:
        """Calculate ETC using exponential smoothing."""
        if len(self.samples) < 2:
            return ETCResult(0.0, EstimationMethod.EXPONENTIAL_SMOOTHING, 0.0)
        
        # Calculate current rate
        last_sample = self.samples[-1]
        prev_sample = self.samples[-2]
        
        bytes_diff = last_sample[0] - prev_sample[0]
        time_diff = last_sample[2] - prev_sample[2]
        
        if time_diff <= 0:
            return ETCResult(0.0, EstimationMethod.EXPONENTIAL_SMOOTHING, 0.0)
        
        current_rate = bytes_diff / time_diff
        
        # Update smoothed rate
        if self.smoothed_rate == 0.0:
            self.smoothed_rate = current_rate
        else:
            self.smoothed_rate = (self.alpha * current_rate + 
                                (1 - self.alpha) * self.smoothed_rate)
        
        if self.smoothed_rate <= 0:
            return ETCResult(0.0, EstimationMethod.EXPONENTIAL_SMOOTHING, 0.0)
        
        # Calculate ETC
        remaining_bytes = last_sample[1] - last_sample[0]
        etc_seconds = remaining_bytes / self.smoothed_rate
        
        # Calculate confidence
        confidence = self._calculate_confidence()
        
        # Calculate confidence intervals
        confidence_range = etc_seconds * (1.0 - confidence) * 0.5
        confidence_min = max(0.0, etc_seconds - confidence_range)
        confidence_max = etc_seconds + confidence_range
        
        return ETCResult(
            seconds=etc_seconds,
            method=EstimationMethod.EXPONENTIAL_SMOOTHING,
            confidence=confidence,
            confidence_min=confidence_min,
            confidence_max=confidence_max
        )
    
    def _adaptive_estimation(self) -> ETCResult:
        """Calculate ETC using adaptive method that chooses best approach."""
        if len(self.samples) < 2:
            return ETCResult(0.0, EstimationMethod.ADAPTIVE, 0.0)
        
        # Get estimates from both methods
        linear_result = self._linear_projection()
        exp_result = self._exponential_smoothing()
        
        # Choose method based on rate variance
        if len(self.rate_variance_history) > 0:
            avg_variance = sum(self.rate_variance_history) / len(self.rate_variance_history)
            
            # If variance is low, prefer linear projection (more stable)
            # If variance is high, prefer exponential smoothing (more adaptive)
            if avg_variance < 0.1:  # Low variance threshold
                chosen_result = linear_result
            else:
                chosen_result = exp_result
        else:
            # Default to linear projection
            chosen_result = linear_result
        
        # Update method in result
        return ETCResult(
            seconds=chosen_result.seconds,
            method=EstimationMethod.ADAPTIVE,
            confidence=chosen_result.confidence,
            confidence_min=chosen_result.confidence_min,
            confidence_max=chosen_result.confidence_max
        )
    
    def _calculate_confidence(self) -> float:
        """Calculate confidence level based on rate consistency."""
        if len(self.samples) < 3:
            return 0.5  # Medium confidence with limited data

        # Calculate rate variations
        rates: list[float] = []
        for i in range(1, len(self.samples)):
            prev_sample = self.samples[i-1]
            curr_sample = self.samples[i]

            bytes_diff = curr_sample[0] - prev_sample[0]
            time_diff = curr_sample[2] - prev_sample[2]

            if time_diff > 0 and bytes_diff >= 0:
                rate = bytes_diff / time_diff
                rates.append(rate)

        if len(rates) < 2:
            return 0.5

        # Calculate coefficient of variation (std dev / mean)
        mean_rate = sum(rates) / len(rates)
        if mean_rate == 0:
            return 0.0

        variance: float = sum((rate - mean_rate) ** 2 for rate in rates) / len(rates)
        std_dev: float = math.sqrt(variance)
        cv: float = std_dev / mean_rate

        # Convert CV to confidence (lower CV = higher confidence)
        confidence: float = max(0.0, min(1.0, 1.0 - cv))

        return confidence
    
    def _update_rate_statistics(self) -> None:
        """Update rate statistics for adaptive method."""
        if len(self.samples) < 2:
            return

        # Calculate recent rate variance
        recent_rates: list[float] = []
        for i in range(max(1, len(self.samples) - 5), len(self.samples)):
            prev_sample = self.samples[i-1]
            curr_sample = self.samples[i]

            bytes_diff = curr_sample[0] - prev_sample[0]
            time_diff = curr_sample[2] - prev_sample[2]

            if time_diff > 0 and bytes_diff >= 0:
                rate = bytes_diff / time_diff
                recent_rates.append(rate)

        if len(recent_rates) >= 2:
            mean_rate = sum(recent_rates) / len(recent_rates)
            if mean_rate > 0:
                variance: float = sum((rate - mean_rate) ** 2 for rate in recent_rates) / len(recent_rates)
                cv: float = math.sqrt(variance) / mean_rate
                self.rate_variance_history.append(cv)
