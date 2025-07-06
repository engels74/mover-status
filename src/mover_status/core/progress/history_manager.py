"""Historical data management and moving averages implementation."""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from collections.abc import Mapping


# Type alias for numeric types using modern Python 3.13 syntax
Number = int | float | Decimal


class MovingAverageType(Enum):
    """Types of moving averages available."""
    SIMPLE = "simple"
    WEIGHTED = "weighted"
    EXPONENTIAL = "exponential"


class RetentionPolicy(Enum):
    """Data retention policies."""
    SIZE_BASED = "size_based"
    TIME_BASED = "time_based"
    HYBRID = "hybrid"


@dataclass
class DataPoint:
    """Represents a single data point with timestamp and optional metadata."""
    value: float
    timestamp: float
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Convert value to float for consistent calculations."""
        self.value = float(self.value)
        self.timestamp = float(self.timestamp)
    
    def __lt__(self, other: DataPoint) -> bool:
        """Compare data points by timestamp for sorting."""
        return self.timestamp < other.timestamp
    
    def __le__(self, other: DataPoint) -> bool:
        """Compare data points by timestamp for sorting."""
        return self.timestamp <= other.timestamp
    
    def __gt__(self, other: DataPoint) -> bool:
        """Compare data points by timestamp for sorting."""
        return self.timestamp > other.timestamp
    
    def __ge__(self, other: DataPoint) -> bool:
        """Compare data points by timestamp for sorting."""
        return self.timestamp >= other.timestamp


@dataclass
class HistoryStats:
    """Statistics calculated from historical data."""
    count: int
    mean: float
    min_value: float
    max_value: float
    std_dev: float
    moving_average: float


class HistoryManager:
    """Manages historical data with configurable retention and moving averages."""
    
    max_size: int
    retention_policy: RetentionPolicy
    retention_duration: float
    moving_average_type: MovingAverageType
    window_size: int
    alpha: float
    data: deque[DataPoint]
    
    def __init__(
        self,
        max_size: int = 1000,
        retention_policy: RetentionPolicy = RetentionPolicy.SIZE_BASED,
        retention_duration: float = 3600.0,  # 1 hour in seconds
        moving_average_type: MovingAverageType = MovingAverageType.SIMPLE,
        window_size: int = 10,
        alpha: float = 0.3,
    ) -> None:
        """Initialize the history manager.
        
        Args:
            max_size: Maximum number of data points to retain
            retention_policy: Policy for data retention (size, time, or hybrid)
            retention_duration: Duration in seconds for time-based retention
            moving_average_type: Type of moving average to calculate
            window_size: Window size for moving average calculations
            alpha: Smoothing factor for exponential moving average (0.0 to 1.0)
        
        Raises:
            ValueError: If parameters are invalid
        """
        if max_size < 1:
            raise ValueError("Max size must be at least 1")
        
        if retention_duration <= 0:
            raise ValueError("Retention duration must be positive")
        
        if window_size < 1:
            raise ValueError("Window size must be at least 1")
        
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("Alpha must be between 0.0 and 1.0")
        
        self.max_size = max_size
        self.retention_policy = retention_policy
        self.retention_duration = retention_duration
        self.moving_average_type = moving_average_type
        self.window_size = window_size
        self.alpha = alpha
        self.data = deque(maxlen=max_size if retention_policy == RetentionPolicy.SIZE_BASED else None)
    
    def add_data_point(
        self,
        value: Number,
        timestamp: float | None = None,
        metadata: Mapping[str, str | int | float | bool] | None = None
    ) -> None:
        """Add a new data point to the history.
        
        Args:
            value: The data value to add
            timestamp: Timestamp of the data point (uses current time if None)
            metadata: Optional metadata associated with the data point
            
        Raises:
            ValueError: If timestamp is negative
        """
        if timestamp is None:
            timestamp = time.time()
        
        if timestamp < 0:
            raise ValueError("Timestamp cannot be negative")
        
        if metadata is None:
            metadata_dict: dict[str, str | int | float | bool] = {}
        else:
            metadata_dict = dict(metadata)

        point = DataPoint(value=float(value), timestamp=timestamp, metadata=metadata_dict)
        self.data.append(point)
        
        # Apply retention policies
        if self.retention_policy == RetentionPolicy.TIME_BASED:
            self._cleanup_old_data()
        elif self.retention_policy == RetentionPolicy.HYBRID:
            self._cleanup_old_data()
            # Size-based cleanup is handled by deque maxlen
    
    def get_moving_average(self, window_size: int | None = None) -> float:
        """Calculate the moving average of recent data points.
        
        Args:
            window_size: Override the default window size for this calculation
            
        Returns:
            The calculated moving average
        """
        if not self.data:
            return 0.0
        
        effective_window = window_size or self.window_size
        recent_data = list(self.data)[-effective_window:]
        
        if self.moving_average_type == MovingAverageType.SIMPLE:
            return self._calculate_simple_average(recent_data)
        elif self.moving_average_type == MovingAverageType.WEIGHTED:
            return self._calculate_weighted_average(recent_data)
        else:  # EXPONENTIAL
            return self._calculate_exponential_average(recent_data)
    
    def get_statistics(self) -> HistoryStats:
        """Get comprehensive statistics for the historical data.
        
        Returns:
            HistoryStats object with calculated statistics
        """
        if not self.data:
            return HistoryStats(
                count=0,
                mean=0.0,
                min_value=0.0,
                max_value=0.0,
                std_dev=0.0,
                moving_average=0.0
            )
        
        values = [point.value for point in self.data]
        count = len(values)
        mean = sum(values) / count
        min_value = min(values)
        max_value = max(values)
        
        # Calculate standard deviation
        if count > 1:
            variance = sum((x - mean) ** 2 for x in values) / count
            std_dev = math.sqrt(variance)
        else:
            std_dev = 0.0
        
        moving_average = self.get_moving_average()
        
        return HistoryStats(
            count=count,
            mean=mean,
            min_value=min_value,
            max_value=max_value,
            std_dev=std_dev,
            moving_average=moving_average
        )
    
    def get_recent_data(self, duration: float) -> list[DataPoint]:
        """Get data points from the last specified duration.
        
        Args:
            duration: Duration in seconds to look back
            
        Returns:
            List of data points within the specified duration
        """
        if not self.data:
            return []
        
        cutoff_time = time.time() - duration
        return [point for point in self.data if point.timestamp >= cutoff_time]
    
    def clear(self) -> None:
        """Clear all historical data."""
        self.data.clear()
    
    def _cleanup_old_data(self) -> None:
        """Remove data points that exceed the retention duration."""
        if not self.data:
            return
        
        cutoff_time = time.time() - self.retention_duration
        
        # Remove old data points from the left
        while self.data and self.data[0].timestamp < cutoff_time:
            _ = self.data.popleft()
    
    def _calculate_simple_average(self, data_points: list[DataPoint]) -> float:
        """Calculate simple moving average."""
        if not data_points:
            return 0.0
        
        return sum(point.value for point in data_points) / len(data_points)
    
    def _calculate_weighted_average(self, data_points: list[DataPoint]) -> float:
        """Calculate weighted moving average with more recent points having higher weight."""
        if not data_points:
            return 0.0
        
        total_weighted_value = 0.0
        total_weight = 0.0
        
        for i, point in enumerate(data_points):
            weight = float(i + 1)  # More recent points get higher weight
            total_weighted_value += point.value * weight
            total_weight += weight
        
        return total_weighted_value / total_weight if total_weight > 0 else 0.0
    
    def _calculate_exponential_average(self, data_points: list[DataPoint]) -> float:
        """Calculate exponential moving average."""
        if not data_points:
            return 0.0
        
        if len(data_points) == 1:
            return data_points[0].value
        
        # Start with the first value
        ema = data_points[0].value
        
        # Apply exponential smoothing to subsequent values
        for point in data_points[1:]:
            ema = self.alpha * point.value + (1 - self.alpha) * ema
        
        return ema
