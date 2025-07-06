"""Tests for historical data management and moving averages."""

from __future__ import annotations

import pytest
import time
from decimal import Decimal

from mover_status.core.progress.history_manager import (
    HistoryManager,
    MovingAverageType,
    RetentionPolicy,
    DataPoint,
)


class TestDataPoint:
    """Test suite for DataPoint dataclass."""

    def test_data_point_creation(self) -> None:
        """Test basic DataPoint creation and properties."""
        timestamp = time.time()
        point = DataPoint(value=100.0, timestamp=timestamp)
        
        assert point.value == 100.0
        assert point.timestamp == timestamp
        assert isinstance(point.value, float)
        assert isinstance(point.timestamp, float)

    def test_data_point_with_metadata(self) -> None:
        """Test DataPoint creation with optional metadata."""
        timestamp = time.time()
        metadata: dict[str, str | int | float | bool] = {"source": "test", "quality": "high"}
        point = DataPoint(value=50.5, timestamp=timestamp, metadata=metadata)
        
        assert point.value == 50.5
        assert point.timestamp == timestamp
        assert point.metadata == metadata

    def test_data_point_ordering(self) -> None:
        """Test DataPoint comparison for sorting by timestamp."""
        t1 = time.time()
        t2 = t1 + 1.0
        
        point1 = DataPoint(value=10.0, timestamp=t1)
        point2 = DataPoint(value=20.0, timestamp=t2)
        
        assert point1 < point2
        assert point2 > point1
        assert point1 != point2


class TestHistoryManager:
    """Test suite for HistoryManager."""

    def test_initialization_defaults(self) -> None:
        """Test HistoryManager initialization with default parameters."""
        manager = HistoryManager()
        
        assert manager.max_size == 1000
        assert manager.retention_policy == RetentionPolicy.SIZE_BASED
        assert manager.retention_duration == 3600.0
        assert manager.moving_average_type == MovingAverageType.SIMPLE
        assert manager.window_size == 10
        assert len(manager.data) == 0

    def test_initialization_custom_parameters(self) -> None:
        """Test HistoryManager initialization with custom parameters."""
        manager = HistoryManager(
            max_size=500,
            retention_policy=RetentionPolicy.TIME_BASED,
            retention_duration=1800.0,
            moving_average_type=MovingAverageType.EXPONENTIAL,
            window_size=20,
            alpha=0.5
        )
        
        assert manager.max_size == 500
        assert manager.retention_policy == RetentionPolicy.TIME_BASED
        assert manager.retention_duration == 1800.0
        assert manager.moving_average_type == MovingAverageType.EXPONENTIAL
        assert manager.window_size == 20
        assert manager.alpha == 0.5

    def test_invalid_parameters(self) -> None:
        """Test HistoryManager initialization with invalid parameters."""
        # Invalid max_size
        with pytest.raises(ValueError, match="Max size must be at least 1"):
            _ = HistoryManager(max_size=0)

        # Invalid retention_duration
        with pytest.raises(ValueError, match="Retention duration must be positive"):
            _ = HistoryManager(retention_duration=-1.0)

        # Invalid window_size
        with pytest.raises(ValueError, match="Window size must be at least 1"):
            _ = HistoryManager(window_size=0)

        # Invalid alpha
        with pytest.raises(ValueError, match="Alpha must be between 0.0 and 1.0"):
            _ = HistoryManager(alpha=1.5)

    def test_add_data_point_basic(self) -> None:
        """Test adding basic data points."""
        manager = HistoryManager(max_size=5)
        
        # Add some data points
        manager.add_data_point(10.0)
        manager.add_data_point(20.0)
        manager.add_data_point(30.0)
        
        assert len(manager.data) == 3
        assert manager.data[0].value == 10.0
        assert manager.data[1].value == 20.0
        assert manager.data[2].value == 30.0

    def test_add_data_point_with_timestamp(self) -> None:
        """Test adding data points with custom timestamps."""
        manager = HistoryManager()
        
        t1 = time.time()
        t2 = t1 + 1.0
        
        manager.add_data_point(100.0, timestamp=t1)
        manager.add_data_point(200.0, timestamp=t2)
        
        assert len(manager.data) == 2
        assert manager.data[0].timestamp == t1
        assert manager.data[1].timestamp == t2

    def test_add_data_point_with_metadata(self) -> None:
        """Test adding data points with metadata."""
        manager = HistoryManager()
        
        metadata: dict[str, str | int | float | bool] = {"source": "sensor1", "quality": "high"}
        manager.add_data_point(50.0, metadata=metadata)
        
        assert len(manager.data) == 1
        assert manager.data[0].metadata == metadata

    def test_size_based_retention(self) -> None:
        """Test size-based retention policy."""
        manager = HistoryManager(max_size=3, retention_policy=RetentionPolicy.SIZE_BASED)
        
        # Add more data points than max_size
        for i in range(5):
            manager.add_data_point(float(i))
        
        # Should only keep the last 3 points
        assert len(manager.data) == 3
        assert manager.data[0].value == 2.0
        assert manager.data[1].value == 3.0
        assert manager.data[2].value == 4.0

    def test_time_based_retention(self) -> None:
        """Test time-based retention policy."""
        manager = HistoryManager(
            retention_policy=RetentionPolicy.TIME_BASED,
            retention_duration=2.0  # 2 seconds
        )
        
        current_time = time.time()
        
        # Add old data point (should be removed)
        manager.add_data_point(10.0, timestamp=current_time - 5.0)
        
        # Add recent data points (should be kept)
        manager.add_data_point(20.0, timestamp=current_time - 1.0)
        manager.add_data_point(30.0, timestamp=current_time)
        
        # Trigger cleanup by adding a new data point (which calls cleanup internally)
        manager.add_data_point(40.0, timestamp=current_time)
        
        # Should only keep recent data points (within 2 seconds)
        assert len(manager.data) == 3
        assert manager.data[0].value == 20.0
        assert manager.data[1].value == 30.0
        assert manager.data[2].value == 40.0

    def test_simple_moving_average(self) -> None:
        """Test simple moving average calculation."""
        manager = HistoryManager(
            moving_average_type=MovingAverageType.SIMPLE,
            window_size=3
        )
        
        # Add data points
        manager.add_data_point(10.0)
        manager.add_data_point(20.0)
        manager.add_data_point(30.0)
        manager.add_data_point(40.0)
        
        # Simple moving average of last 3 points: (20 + 30 + 40) / 3 = 30.0
        avg = manager.get_moving_average()
        assert avg == 30.0

    def test_weighted_moving_average(self) -> None:
        """Test weighted moving average calculation."""
        manager = HistoryManager(
            moving_average_type=MovingAverageType.WEIGHTED,
            window_size=3
        )
        
        # Add data points
        manager.add_data_point(10.0)
        manager.add_data_point(20.0)
        manager.add_data_point(30.0)
        
        # Weighted average: (10*1 + 20*2 + 30*3) / (1+2+3) = 140/6 ≈ 23.33
        avg = manager.get_moving_average()
        assert abs(avg - 23.333333333333332) < 1e-10

    def test_exponential_moving_average(self) -> None:
        """Test exponential moving average calculation."""
        manager = HistoryManager(
            moving_average_type=MovingAverageType.EXPONENTIAL,
            window_size=3,
            alpha=0.5
        )
        
        # Add data points
        manager.add_data_point(10.0)
        manager.add_data_point(20.0)
        manager.add_data_point(30.0)
        
        # EMA calculation with alpha=0.5
        # EMA1 = 10.0
        # EMA2 = 0.5 * 20.0 + 0.5 * 10.0 = 15.0
        # EMA3 = 0.5 * 30.0 + 0.5 * 15.0 = 22.5
        avg = manager.get_moving_average()
        assert avg == 22.5

    def test_insufficient_data_for_average(self) -> None:
        """Test moving average with insufficient data."""
        manager = HistoryManager(window_size=5)
        
        # Add fewer points than window size
        manager.add_data_point(10.0)
        manager.add_data_point(20.0)
        
        # Should return average of available data
        avg = manager.get_moving_average()
        assert avg == 15.0

    def test_empty_data_average(self) -> None:
        """Test moving average with no data."""
        manager = HistoryManager()
        
        avg = manager.get_moving_average()
        assert avg == 0.0

    def test_get_statistics(self) -> None:
        """Test getting comprehensive statistics."""
        manager = HistoryManager()
        
        # Add some data points
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for value in values:
            manager.add_data_point(value)
        
        stats = manager.get_statistics()
        
        assert stats.count == 5
        assert stats.mean == 30.0
        assert stats.min_value == 10.0
        assert stats.max_value == 50.0
        assert abs(stats.std_dev - 14.142135623730951) < 1e-10
        assert stats.moving_average == 30.0  # Simple average of all 5 points

    def test_get_recent_data(self) -> None:
        """Test getting recent data points."""
        manager = HistoryManager()
        
        current_time = time.time()
        
        # Add data points with different timestamps
        manager.add_data_point(10.0, timestamp=current_time - 10.0)
        manager.add_data_point(20.0, timestamp=current_time - 5.0)
        manager.add_data_point(30.0, timestamp=current_time - 1.0)
        manager.add_data_point(40.0, timestamp=current_time)
        
        # Get recent data (last 3 seconds)
        recent = manager.get_recent_data(duration=3.0)
        
        assert len(recent) == 2
        assert recent[0].value == 30.0
        assert recent[1].value == 40.0

    def test_clear_data(self) -> None:
        """Test clearing all data."""
        manager = HistoryManager()
        
        # Add some data
        manager.add_data_point(10.0)
        manager.add_data_point(20.0)
        
        assert len(manager.data) == 2
        
        # Clear data
        manager.clear()
        
        assert len(manager.data) == 0
        assert manager.get_moving_average() == 0.0

    def test_decimal_support(self) -> None:
        """Test support for Decimal values."""
        manager = HistoryManager()
        
        # Add Decimal values
        manager.add_data_point(Decimal('10.5'))
        manager.add_data_point(Decimal('20.7'))
        manager.add_data_point(Decimal('30.3'))
        
        assert len(manager.data) == 3
        assert manager.data[0].value == 10.5
        assert manager.data[1].value == 20.7
        assert manager.data[2].value == 30.3
        
        # Moving average should work with Decimal inputs
        avg = manager.get_moving_average()
        expected = (10.5 + 20.7 + 30.3) / 3
        assert abs(avg - expected) < 1e-10

    def test_large_dataset_performance(self) -> None:
        """Test performance with large datasets."""
        manager = HistoryManager(max_size=10000)
        
        # Add many data points
        for i in range(5000):
            manager.add_data_point(float(i))
        
        assert len(manager.data) == 5000
        
        # Operations should still be fast
        avg = manager.get_moving_average()
        stats = manager.get_statistics()
        
        assert avg > 0
        assert stats.count == 5000
