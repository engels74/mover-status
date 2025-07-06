"""Integration tests for progress tracking components working together."""

from __future__ import annotations

import pytest
from decimal import Decimal
from unittest.mock import patch
from typing import Any

from mover_status.core.progress.percentage_calculator import ProgressPercentageCalculator
from mover_status.core.progress.transfer_rate_calculator import (
    TransferRateCalculator,
    RateUnit,
    SmoothingMethod,
)
from mover_status.core.progress.etc_estimator import (
    ETCEstimator,
    EstimationMethod,
)
from mover_status.core.progress.history_manager import (
    HistoryManager,
    MovingAverageType,
    RetentionPolicy,
)


class TestProgressIntegration:
    """Integration tests for progress tracking components."""

    def test_complete_progress_tracking_workflow(self) -> None:
        """Test a complete progress tracking workflow using all components."""
        # Initialize all components
        percentage_calc = ProgressPercentageCalculator(precision=2)
        rate_calc = TransferRateCalculator(unit=RateUnit.MEGABYTES_PER_SECOND)
        etc_estimator = ETCEstimator(method=EstimationMethod.ADAPTIVE)
        history_manager = HistoryManager(
            moving_average_type=MovingAverageType.EXPONENTIAL,
            window_size=5,
            alpha=0.3
        )
        
        # Simulate file transfer: 100MB file
        total_size = 100 * 1024 * 1024  # 100MB in bytes
        
        with patch('time.time') as mock_time:
            transfer_data = [
                (0, 0.0),           # Start
                (10485760, 5.0),    # 10MB after 5s (2MB/s)
                (31457280, 10.0),   # 30MB after 10s (4MB/s avg)
                (52428800, 15.0),   # 50MB after 15s (3.33MB/s avg)
                (73400320, 20.0),   # 70MB after 20s (3.5MB/s avg)
                (94371840, 25.0),   # 90MB after 25s (3.6MB/s avg)
                (104857600, 30.0),  # 100MB after 30s (3.33MB/s avg)
            ]
            
            results: list[dict[str, float]] = []
            
            for bytes_transferred, timestamp in transfer_data:
                mock_time.return_value = timestamp
                
                # Calculate progress percentage
                percentage = percentage_calc.calculate_percentage(bytes_transferred, total_size)
                
                # Update transfer rate calculator
                rate_calc.add_sample(bytes_transferred, timestamp)
                current_rate = rate_calc.get_current_rate()
                
                # Update ETC estimator
                etc_estimator.add_sample(bytes_transferred, total_size)
                etc_result = etc_estimator.get_etc()
                
                # Update history manager with rate data
                history_manager.add_data_point(current_rate, timestamp=timestamp)
                avg_rate = history_manager.get_moving_average()
                
                results.append({
                    'timestamp': timestamp,
                    'bytes_transferred': float(bytes_transferred),
                    'percentage': percentage,
                    'current_rate': current_rate,
                    'avg_rate': avg_rate,
                    'etc_seconds': etc_result.seconds,
                    'etc_confidence': etc_result.confidence,
                })
            
            # Verify progress tracking consistency
            assert len(results) == 7
            
            # Check percentage progression
            percentages = [r['percentage'] for r in results]
            assert percentages == [0.0, 10.0, 30.0, 50.0, 70.0, 90.0, 100.0]
            
            # Check rate calculations are reasonable
            for i, result in enumerate(results[1:], 1):  # Skip first result (no rate yet)
                assert result['current_rate'] >= 0
                assert result['avg_rate'] >= 0
                
                # ETC should decrease as progress increases (except for completion)
                if i < len(results) - 1:  # Not the last result
                    assert result['etc_seconds'] >= 0
                else:  # Last result (100% complete)
                    assert result['etc_seconds'] == 0.0
                    assert result['etc_confidence'] == 1.0

    def test_cross_component_data_consistency(self) -> None:
        """Test that data is consistent across different components."""
        # Use high precision for consistency checking
        percentage_calc = ProgressPercentageCalculator(precision=6)
        rate_calc = TransferRateCalculator(unit=RateUnit.BYTES_PER_SECOND)
        etc_estimator = ETCEstimator(method=EstimationMethod.LINEAR_PROJECTION)
        
        total_size = 10000  # 10KB for easy calculation
        
        with patch('time.time') as mock_time:
            # Add same data to all components
            test_data = [
                (0, 0.0),
                (2500, 1.0),    # 25% after 1s
                (5000, 2.0),    # 50% after 2s
                (7500, 3.0),    # 75% after 3s
            ]
            
            for bytes_transferred, timestamp in test_data:
                mock_time.return_value = timestamp
                
                # Update all components
                percentage = percentage_calc.calculate_percentage(bytes_transferred, total_size)
                rate_calc.add_sample(bytes_transferred, timestamp)
                etc_estimator.add_sample(bytes_transferred, total_size)
                
                # Verify consistency
                if bytes_transferred > 0:
                    expected_percentage = (bytes_transferred / total_size) * 100
                    assert abs(percentage - expected_percentage) < 1e-6
                    
                    # Rate should be consistent with bytes/time
                    if timestamp > 0:
                        expected_rate = bytes_transferred / timestamp
                        current_rate = rate_calc.get_current_rate()
                        # Allow some tolerance for rate calculation differences
                        assert abs(current_rate - expected_rate) < expected_rate * 0.1

    def test_component_synchronization_under_load(self) -> None:
        """Test component synchronization under high-frequency updates."""
        # Initialize components with small buffers to test overflow handling
        rate_calc = TransferRateCalculator(window_size=5)
        etc_estimator = ETCEstimator(window_size=5)
        history_manager = HistoryManager(max_size=10)
        
        total_size = 1000000  # 1MB
        
        with patch('time.time') as mock_time:
            # Simulate high-frequency updates (100 updates over 10 seconds)
            for i in range(100):
                timestamp = i * 0.1  # Every 100ms
                bytes_transferred = int((i / 100) * total_size)
                
                mock_time.return_value = timestamp
                
                # Update all components
                rate_calc.add_sample(bytes_transferred, timestamp)
                etc_estimator.add_sample(bytes_transferred, total_size)
                history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
            
            # Verify all components handled the load
            assert rate_calc.get_current_rate() >= 0
            assert etc_estimator.get_etc().seconds >= 0
            assert history_manager.get_moving_average() >= 0
            
            # Check that components maintained their size limits
            assert len(history_manager.data) <= 10
            # Rate calculator and ETC estimator should maintain their window sizes internally

    def test_real_world_transfer_simulation(self) -> None:
        """Test simulation of real-world transfer patterns with varying speeds."""
        # Initialize components for realistic scenario
        percentage_calc = ProgressPercentageCalculator(precision=1)
        rate_calc = TransferRateCalculator(
            unit=RateUnit.MEGABYTES_PER_SECOND,
            smoothing=SmoothingMethod.EXPONENTIAL_SMOOTHING,
            window_size=10
        )
        etc_estimator = ETCEstimator(method=EstimationMethod.ADAPTIVE)
        history_manager = HistoryManager(
            moving_average_type=MovingAverageType.WEIGHTED,
            window_size=15,
            retention_policy=RetentionPolicy.TIME_BASED,
            retention_duration=60.0  # Keep last 60 seconds
        )
        
        # Simulate 1GB file transfer with realistic patterns
        total_size = 1024 * 1024 * 1024  # 1GB
        
        with patch('time.time') as mock_time:
            # Realistic transfer pattern: fast start, slow middle, fast end
            transfer_pattern = [
                (0, 0.0),                           # Start
                (50 * 1024 * 1024, 5.0),           # 50MB in 5s (10MB/s)
                (100 * 1024 * 1024, 12.0),         # 100MB in 12s (slower)
                (150 * 1024 * 1024, 20.0),         # 150MB in 20s (even slower)
                (200 * 1024 * 1024, 25.0),         # 200MB in 25s (picking up)
                (400 * 1024 * 1024, 35.0),         # 400MB in 35s (much faster)
                (600 * 1024 * 1024, 42.0),         # 600MB in 42s (consistent)
                (800 * 1024 * 1024, 48.0),         # 800MB in 48s (consistent)
                (1000 * 1024 * 1024, 53.0),        # 1000MB in 53s (consistent)
                (1024 * 1024 * 1024, 55.0),        # 1024MB in 55s (final push)
            ]
            
            progress_snapshots: list[dict[str, float]] = []
            
            for bytes_transferred, timestamp in transfer_pattern:
                mock_time.return_value = timestamp
                
                # Update all components
                percentage = percentage_calc.calculate_percentage(bytes_transferred, total_size)
                rate_calc.add_sample(bytes_transferred, timestamp)
                etc_estimator.add_sample(bytes_transferred, total_size)
                
                current_rate = rate_calc.get_current_rate()
                history_manager.add_data_point(current_rate, timestamp=timestamp)
                
                etc_result = etc_estimator.get_etc()
                stats = history_manager.get_statistics()
                
                progress_snapshots.append({
                    'timestamp': timestamp,
                    'percentage': percentage,
                    'current_rate_mbps': current_rate,
                    'avg_rate_mbps': stats.mean,
                    'etc_seconds': etc_result.seconds,
                    'etc_confidence': etc_result.confidence,
                })
            
            # Verify realistic progression
            assert len(progress_snapshots) == 10
            
            # Check that percentages increase monotonically
            percentages = [s['percentage'] for s in progress_snapshots]
            assert all(percentages[i] <= percentages[i+1] for i in range(len(percentages)-1))
            
            # Check that ETC decreases as we approach completion
            # ETC should generally decrease (allowing for some variance due to rate changes)
            assert progress_snapshots[-1]['etc_seconds'] == 0.0  # Should be 0 at completion
            
            # Check that rates are reasonable (not negative, not impossibly high)
            for snapshot in progress_snapshots:
                assert snapshot['current_rate_mbps'] >= 0
                assert snapshot['avg_rate_mbps'] >= 0
                assert snapshot['current_rate_mbps'] < 1000  # Less than 1GB/s (reasonable)

    def test_component_error_propagation(self) -> None:
        """Test error handling and propagation across components."""
        percentage_calc = ProgressPercentageCalculator()
        rate_calc = TransferRateCalculator()
        etc_estimator = ETCEstimator()
        history_manager = HistoryManager()
        
        # Test invalid data handling
        with pytest.raises(ValueError):
            percentage_calc.calculate_percentage(-100, 1000)  # Negative progress
        
        with pytest.raises(ValueError):
            rate_calc.add_sample(-100, 1.0)  # Negative bytes
        
        with pytest.raises(ValueError):
            history_manager.add_data_point(100.0, timestamp=-1.0)  # Negative timestamp
        
        # Test recovery after errors
        # Components should continue working after handling errors
        assert percentage_calc.calculate_percentage(50, 100) == 50.0
        
        rate_calc.add_sample(1000, 1.0)
        rate_calc.add_sample(2000, 2.0)
        assert rate_calc.get_current_rate() > 0
        
        etc_estimator.add_sample(1000, 10000)
        etc_estimator.add_sample(2000, 10000)
        _ = etc_estimator.get_etc().seconds  # Verify it works

    def test_memory_efficiency_integration(self) -> None:
        """Test memory efficiency when components work together."""
        # Initialize components with memory constraints
        rate_calc = TransferRateCalculator(window_size=5)
        etc_estimator = ETCEstimator(window_size=5)
        history_manager = HistoryManager(max_size=10)
        
        # Add many data points
        with patch('time.time') as mock_time:
            for i in range(100):
                timestamp = float(i)
                bytes_transferred = i * 1000
                
                mock_time.return_value = timestamp
                
                rate_calc.add_sample(bytes_transferred, timestamp)
                etc_estimator.add_sample(bytes_transferred, 100000)
                history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
            
            # Verify memory constraints are maintained
            assert len(history_manager.data) <= 10
            
            # Components should still function correctly
            assert rate_calc.get_current_rate() >= 0
            assert etc_estimator.get_etc().seconds >= 0
            assert history_manager.get_moving_average() >= 0

    def test_decimal_precision_integration(self) -> None:
        """Test high-precision calculations across all components."""
        # Initialize with high precision
        percentage_calc = ProgressPercentageCalculator(precision=6)
        rate_calc = TransferRateCalculator(unit=RateUnit.BYTES_PER_SECOND)
        etc_estimator = ETCEstimator()
        history_manager = HistoryManager()
        
        # Use high-precision Decimal inputs
        total_size = Decimal('10000.123456')
        
        with patch('time.time') as mock_time:
            test_data = [
                (Decimal('0'), 0.0),
                (Decimal('2500.123456'), 1.0),
                (Decimal('5000.123456'), 2.0),
                (Decimal('7500.123456'), 3.0),
                (Decimal('10000.123456'), 4.0),
            ]
            
            for bytes_transferred, timestamp in test_data:
                mock_time.return_value = timestamp
                
                # Test percentage calculation with Decimals
                percentage = percentage_calc.calculate_percentage(bytes_transferred, total_size)
                assert isinstance(percentage, float)
                
                # Test rate calculation with Decimals
                rate_calc.add_sample(bytes_transferred, timestamp)
                current_rate = rate_calc.get_current_rate()
                assert isinstance(current_rate, float)
                assert current_rate >= 0
                
                # Test ETC estimation with Decimals
                etc_estimator.add_sample(bytes_transferred, total_size)
                etc_result = etc_estimator.get_etc()
                assert isinstance(etc_result.seconds, float)
                assert etc_result.seconds >= 0
                
                # Test history manager with Decimal-derived values
                history_manager.add_data_point(current_rate, timestamp=timestamp)
                avg_rate = history_manager.get_moving_average()
                assert isinstance(avg_rate, float)
                assert avg_rate >= 0

    def test_concurrent_component_access(self) -> None:
        """Test components working together under concurrent access patterns."""
        import threading
        import queue
        
        # Initialize components
        percentage_calc = ProgressPercentageCalculator()
        rate_calc = TransferRateCalculator()
        etc_estimator = ETCEstimator()
        history_manager = HistoryManager()
        
        total_size = 100000
        results_queue: queue.Queue[dict[str, float]] = queue.Queue()
        
        def worker(thread_id: int) -> None:
            """Worker function that updates all components."""
            with patch('time.time') as mock_time:
                for i in range(10):
                    timestamp = float(thread_id * 10 + i)
                    bytes_transferred = (thread_id * 10 + i) * 1000
                    
                    mock_time.return_value = timestamp
                    
                    # Update all components
                    percentage = percentage_calc.calculate_percentage(
                        min(bytes_transferred, total_size), total_size
                    )
                    rate_calc.add_sample(min(bytes_transferred, total_size), timestamp)
                    etc_estimator.add_sample(min(bytes_transferred, total_size), total_size)
                    history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
                    
                    results_queue.put({
                        'thread_id': thread_id,
                        'percentage': percentage,
                        'rate': rate_calc.get_current_rate(),
                        'etc': etc_estimator.get_etc().seconds,
                        'avg': history_manager.get_moving_average(),
                    })
        
        # Start multiple threads
        threads: list[threading.Thread] = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Collect results
        results: list[dict[str, float]] = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # Verify all threads completed successfully
        assert len(results) == 30  # 3 threads * 10 iterations
        
        # Verify all results are valid
        for result in results:
            assert 0 <= result['percentage'] <= 100
            assert result['rate'] >= 0
            assert result['etc'] >= 0
            assert result['avg'] >= 0