"""Tests for ETC (Estimated Time to Completion) estimation."""

from __future__ import annotations

import pytest
from decimal import Decimal
from unittest.mock import patch

from mover_status.core.progress.etc_estimator import (
    ETCEstimator,
    EstimationMethod,
)


class TestETCEstimator:
    """Test suite for ETCEstimator."""

    def test_linear_projection_basic(self) -> None:
        """Test basic linear projection ETC calculation."""
        estimator = ETCEstimator(method=EstimationMethod.LINEAR_PROJECTION)
        
        # Simulate steady transfer: 1000 bytes/second
        with patch('time.time') as mock_time:
            mock_time.return_value = 0.0
            estimator.add_sample(0, 10000)  # 0 bytes transferred, 10KB total
            
            mock_time.return_value = 1.0
            estimator.add_sample(1000, 10000)  # 1KB transferred after 1 second
            
            etc_result = estimator.get_etc()
            
            # Should estimate 9 more seconds (9KB remaining at 1KB/s)
            assert etc_result.seconds == pytest.approx(9.0, rel=1e-5)  # pyright: ignore[reportUnknownMemberType]
            assert etc_result.method == EstimationMethod.LINEAR_PROJECTION
            assert etc_result.confidence > 0.0

    def test_exponential_smoothing_basic(self) -> None:
        """Test basic exponential smoothing ETC calculation."""
        estimator = ETCEstimator(
            method=EstimationMethod.EXPONENTIAL_SMOOTHING,
            alpha=0.3
        )
        
        with patch('time.time') as mock_time:
            # Add samples with varying rates
            mock_time.return_value = 0.0
            estimator.add_sample(0, 10000)
            
            mock_time.return_value = 1.0
            estimator.add_sample(500, 10000)  # 500 bytes/s
            
            mock_time.return_value = 2.0
            estimator.add_sample(1500, 10000)  # 1000 bytes/s in second 2
            
            etc_result = estimator.get_etc()
            
            # Should provide reasonable ETC estimate
            assert etc_result.seconds > 0
            assert etc_result.method == EstimationMethod.EXPONENTIAL_SMOOTHING
            assert etc_result.confidence > 0.0

    def test_adaptive_estimation(self) -> None:
        """Test adaptive ETC estimation that switches methods based on data."""
        estimator = ETCEstimator(method=EstimationMethod.ADAPTIVE)
        
        with patch('time.time') as mock_time:
            # Start with consistent rate
            samples = [
                (0, 0, 10000),
                (1000, 1, 10000),
                (2000, 2, 10000),
                (3000, 3, 10000),
            ]
            
            for bytes_transferred, timestamp, total in samples:
                mock_time.return_value = float(timestamp)
                estimator.add_sample(bytes_transferred, total)
            
            etc_result = estimator.get_etc()
            
            # Should provide reasonable estimate
            assert etc_result.seconds > 0
            assert etc_result.method == EstimationMethod.ADAPTIVE
            assert etc_result.confidence > 0.0

    def test_confidence_intervals(self) -> None:
        """Test confidence interval calculation."""
        estimator = ETCEstimator()
        
        with patch('time.time') as mock_time:
            # Add samples with consistent rate
            for i in range(5):
                mock_time.return_value = float(i)
                estimator.add_sample(i * 1000, 10000)
            
            etc_result = estimator.get_etc()
            
            # Should have confidence intervals
            assert etc_result.confidence_min is not None
            assert etc_result.confidence_max is not None
            assert etc_result.confidence_min <= etc_result.seconds <= etc_result.confidence_max

    def test_variable_transfer_rates(self) -> None:
        """Test ETC estimation with highly variable transfer rates."""
        estimator = ETCEstimator()
        
        with patch('time.time') as mock_time:
            # Simulate variable network conditions
            samples = [
                (0, 0, 10000),
                (100, 1, 10000),    # Slow start
                (2000, 2, 10000),   # Speed up
                (2500, 3, 10000),   # Slow down
                (5000, 4, 10000),   # Speed up again
            ]
            
            for bytes_transferred, timestamp, total in samples:
                mock_time.return_value = float(timestamp)
                estimator.add_sample(bytes_transferred, total)
            
            etc_result = estimator.get_etc()
            
            # Should handle variability gracefully
            assert etc_result.seconds > 0
            assert 0.0 <= etc_result.confidence <= 1.0

    def test_paused_operations(self) -> None:
        """Test ETC estimation when operations are paused."""
        estimator = ETCEstimator()
        
        with patch('time.time') as mock_time:
            # Normal progress
            mock_time.return_value = 0.0
            estimator.add_sample(0, 10000)
            
            mock_time.return_value = 1.0
            estimator.add_sample(1000, 10000)
            
            # Pause (no progress for 5 seconds)
            mock_time.return_value = 6.0
            estimator.add_sample(1000, 10000)  # Same bytes transferred
            
            # Resume
            mock_time.return_value = 7.0
            estimator.add_sample(2000, 10000)
            
            etc_result = estimator.get_etc()
            
            # Should detect pause and adjust estimation
            assert etc_result.seconds > 0
            # Confidence should be lower due to pause
            assert etc_result.confidence < 1.0

    def test_near_completion(self) -> None:
        """Test ETC estimation when transfer is nearly complete."""
        estimator = ETCEstimator()
        
        with patch('time.time') as mock_time:
            mock_time.return_value = 0.0
            estimator.add_sample(9900, 10000)  # 99% complete
            
            mock_time.return_value = 1.0
            estimator.add_sample(9950, 10000)  # 99.5% complete
            
            etc_result = estimator.get_etc()
            
            # Should provide short ETC estimate
            assert etc_result.seconds < 10.0  # Should be very short
            assert etc_result.seconds > 0

    def test_completion_detection(self) -> None:
        """Test detection of completed transfers."""
        estimator = ETCEstimator()
        
        with patch('time.time') as mock_time:
            mock_time.return_value = 0.0
            estimator.add_sample(10000, 10000)  # 100% complete
            
            etc_result = estimator.get_etc()
            
            # Should return 0 seconds for completed transfer
            assert etc_result.seconds == 0.0
            assert etc_result.confidence == 1.0

    def test_edge_cases(self) -> None:
        """Test various edge cases."""
        estimator = ETCEstimator()
        
        # No samples - should return None or handle gracefully
        etc_result = estimator.get_etc()
        assert etc_result.seconds == 0.0 or etc_result.seconds is None
        
        # Single sample - insufficient data
        estimator.add_sample(1000, 10000)
        etc_result = estimator.get_etc()
        assert etc_result.seconds >= 0.0  # Should handle gracefully
        
        # Zero total size
        estimator_zero = ETCEstimator()
        estimator_zero.add_sample(0, 0)
        etc_result = estimator_zero.get_etc()
        assert etc_result.seconds == 0.0

    def test_large_file_handling(self) -> None:
        """Test ETC estimation with very large files."""
        estimator = ETCEstimator()
        
        # 1TB file transfer
        total_size = 1_000_000_000_000
        
        with patch('time.time') as mock_time:
            mock_time.return_value = 0.0
            estimator.add_sample(0, total_size)
            
            # Transfer 1GB in 10 seconds (100MB/s)
            mock_time.return_value = 10.0
            estimator.add_sample(1_000_000_000, total_size)
            
            etc_result = estimator.get_etc()
            
            # Should estimate reasonable time for remaining 999GB
            expected_seconds = (total_size - 1_000_000_000) / (1_000_000_000 / 10.0)
            assert etc_result.seconds == pytest.approx(expected_seconds, rel=0.1)  # pyright: ignore[reportUnknownMemberType]

    def test_decimal_precision(self) -> None:
        """Test ETC estimation with high precision Decimal inputs."""
        estimator = ETCEstimator()
        
        with patch('time.time') as mock_time:
            mock_time.return_value = 0.0
            estimator.add_sample(Decimal('0'), Decimal('10000.123456'))
            
            mock_time.return_value = 1.0
            estimator.add_sample(Decimal('1000.123456'), Decimal('10000.123456'))
            
            etc_result = estimator.get_etc()
            
            # Should handle Decimal precision appropriately
            assert etc_result.seconds > 0
            assert isinstance(etc_result.seconds, float)

    def test_multiple_estimation_methods(self) -> None:
        """Test getting estimates from multiple methods simultaneously."""
        estimator = ETCEstimator()
        
        with patch('time.time') as mock_time:
            # Add consistent samples
            for i in range(5):
                mock_time.return_value = float(i)
                estimator.add_sample(i * 1000, 10000)
            
            # Get estimates from all methods
            linear_result = estimator.get_etc_with_method(EstimationMethod.LINEAR_PROJECTION)
            exp_result = estimator.get_etc_with_method(EstimationMethod.EXPONENTIAL_SMOOTHING)
            adaptive_result = estimator.get_etc_with_method(EstimationMethod.ADAPTIVE)
            
            # All should provide reasonable estimates
            assert linear_result.seconds > 0
            assert exp_result.seconds > 0
            assert adaptive_result.seconds > 0
            
            # Methods should be correctly identified
            assert linear_result.method == EstimationMethod.LINEAR_PROJECTION
            assert exp_result.method == EstimationMethod.EXPONENTIAL_SMOOTHING
            assert adaptive_result.method == EstimationMethod.ADAPTIVE

    def test_reset_functionality(self) -> None:
        """Test resetting the estimator state."""
        estimator = ETCEstimator()
        
        # Add some samples
        estimator.add_sample(1000, 10000)
        estimator.add_sample(2000, 10000)
        
        # Reset
        estimator.reset()
        
        # Should behave like a new estimator
        etc_result = estimator.get_etc()
        assert etc_result.seconds == 0.0 or etc_result.seconds is None
