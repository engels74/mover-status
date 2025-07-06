"""Performance validation tests for progress tracking components."""

from __future__ import annotations

import math
import time
from unittest.mock import patch

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
)


class TestProgressPerformance:
    """Performance validation tests for progress tracking components."""

    def test_percentage_calculator_performance(self) -> None:
        """Test percentage calculator performance with large datasets."""
        calculator = ProgressPercentageCalculator(precision=2)
        
        # Test with various data sizes
        test_sizes = [1000, 10000, 100000]
        
        for size in test_sizes:
            start_time = time.time()
            
            # Perform many calculations
            for i in range(size):
                result = calculator.calculate_percentage(i, size)
                assert 0.0 <= result <= 100.0
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Performance requirements: should complete within reasonable time
            # Allow more time for larger datasets
            max_duration = size / 10000.0  # 1 second per 10k calculations
            assert duration < max_duration, f"Performance too slow for {size} calculations: {duration:.3f}s"
            
            # Calculate operations per second
            ops_per_second = size / duration
            assert ops_per_second > 1000, f"Performance too slow: {ops_per_second:.0f} ops/sec"

    def test_transfer_rate_calculator_performance(self) -> None:
        """Test transfer rate calculator performance with high-frequency updates."""
        calculator = TransferRateCalculator(window_size=100)
        
        # Test with high-frequency updates
        start_time = time.time()
        
        # Simulate 10,000 samples over 1000 seconds (10 samples per second)
        sample_count = 10000
        for i in range(sample_count):
            timestamp = i * 0.1  # Every 100ms
            bytes_transferred = i * 1000  # 1KB per sample
            
            calculator.add_sample(bytes_transferred, timestamp)
            
            # Get rate calculation periodically
            if i % 100 == 0:
                _ = calculator.get_current_rate()
                _ = calculator.get_instantaneous_rate()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should handle high-frequency updates efficiently
        assert duration < 5.0, f"Performance too slow for {sample_count} samples: {duration:.3f}s"
        
        # Final rate calculation should be fast
        rate_start = time.time()
        final_rate = calculator.get_current_rate()
        rate_end = time.time()
        
        assert final_rate > 0
        assert (rate_end - rate_start) < 0.1, "Rate calculation too slow"

    def test_etc_estimator_performance(self) -> None:
        """Test ETC estimator performance with various algorithms."""
        estimators = [
            ETCEstimator(method=EstimationMethod.LINEAR_PROJECTION),
            ETCEstimator(method=EstimationMethod.EXPONENTIAL_SMOOTHING),
            ETCEstimator(method=EstimationMethod.ADAPTIVE),
        ]
        
        total_size = 1000000  # 1MB
        
        for estimator in estimators:
            start_time = time.time()
            
            # Add many samples
            sample_count = 5000
            for i in range(sample_count):
                _timestamp = float(i)
                bytes_transferred = int((i / sample_count) * total_size)
                
                estimator.add_sample(bytes_transferred, total_size)
                
                # Get ETC estimate periodically
                if i % 100 == 0:
                    _ = estimator.get_etc()
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Should handle many samples efficiently
            assert duration < 5.0, f"ETC estimator {estimator.method} too slow: {duration:.3f}s"
            
            # Final ETC calculation should be fast
            etc_start = time.time()
            final_etc = estimator.get_etc()
            etc_end = time.time()
            
            assert final_etc.seconds >= 0
            assert (etc_end - etc_start) < 0.1, "ETC calculation too slow"

    def test_history_manager_performance(self) -> None:
        """Test history manager performance with large datasets."""
        # Test different configurations
        managers = [
            HistoryManager(max_size=1000, moving_average_type=MovingAverageType.SIMPLE),
            HistoryManager(max_size=1000, moving_average_type=MovingAverageType.WEIGHTED),
            HistoryManager(max_size=1000, moving_average_type=MovingAverageType.EXPONENTIAL),
        ]
        
        for manager in managers:
            start_time = time.time()
            
            # Add many data points
            data_count = 10000
            for i in range(data_count):
                timestamp = float(i)
                value = float(i * 100)
                
                manager.add_data_point(value, timestamp=timestamp)
                
                # Get statistics periodically
                if i % 1000 == 0:
                    _ = manager.get_moving_average()
                    _ = manager.get_statistics()
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Should handle large datasets efficiently
            assert duration < 5.0, f"History manager too slow: {duration:.3f}s"
            
            # Should maintain size constraints
            assert len(manager.data) <= 1000
            
            # Statistics calculation should be fast
            stats_start = time.time()
            _ = manager.get_statistics()
            _ = manager.get_moving_average()
            stats_end = time.time()
            
            assert (stats_end - stats_start) < 0.1, "Statistics calculation too slow"

    def test_memory_usage_under_load(self) -> None:
        """Test memory usage patterns under heavy load."""
        import gc
        
        # Initialize components with memory constraints
        percentage_calc = ProgressPercentageCalculator()
        rate_calc = TransferRateCalculator(window_size=100)
        etc_estimator = ETCEstimator(window_size=100)
        history_manager = HistoryManager(max_size=500)
        
        # Force garbage collection and measure initial memory
        _ = gc.collect()
        initial_objects = len(gc.get_objects())
        
        total_size = 10000000  # 10MB
        
        with patch('time.time') as mock_time:
            # Simulate intensive usage
            for i in range(10000):
                timestamp = float(i)
                bytes_transferred = int((i / 10000) * total_size)
                
                mock_time.return_value = timestamp
                
                # Update all components
                _ = percentage_calc.calculate_percentage(bytes_transferred, total_size)
                rate_calc.add_sample(bytes_transferred, timestamp)
                etc_estimator.add_sample(bytes_transferred, total_size)
                history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
                
                # Periodically check memory usage
                if i % 1000 == 0:
                    _ = gc.collect()
                    _ = len(gc.get_objects())
        
        # Final memory check
        _ = gc.collect()
        final_objects = len(gc.get_objects())
        memory_growth = (final_objects - initial_objects) / initial_objects
        
        # Memory growth should be reasonable (less than 50% increase)
        assert memory_growth < 0.5, f"Excessive memory growth: {memory_growth:.2%}"

    def test_concurrent_performance(self) -> None:
        """Test performance under concurrent access."""
        import threading
        import queue
        
        results_queue: queue.Queue[float] = queue.Queue()
        
        def worker_thread(_thread_id: int) -> None:
            """Worker thread that performs calculations."""
            # Each thread gets its own components to avoid contention
            rate_calc = TransferRateCalculator()
            etc_estimator = ETCEstimator()
            history_manager = HistoryManager()
            
            start_time = time.time()
            
            for i in range(1000):
                timestamp = float(i * 0.1)  # Monotonic timestamps for each thread
                bytes_transferred = i * 100
                
                # Update components
                rate_calc.add_sample(bytes_transferred, timestamp)
                etc_estimator.add_sample(bytes_transferred, 1000000)
                history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
                
                # Get calculations
                _ = rate_calc.get_current_rate()
                _ = etc_estimator.get_etc()
                _ = history_manager.get_moving_average()
            
            end_time = time.time()
            results_queue.put(end_time - start_time)
        
        # Start multiple worker threads
        threads: list[threading.Thread] = []
        thread_count = 4
        
        overall_start = time.time()
        
        for i in range(thread_count):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        overall_end = time.time()
        overall_duration = overall_end - overall_start
        
        # Collect individual thread durations
        thread_durations: list[float] = []
        while not results_queue.empty():
            thread_durations.append(results_queue.get())
        
        # Verify performance
        assert len(thread_durations) == thread_count
        assert all(duration < 5.0 for duration in thread_durations), "Some threads too slow"
        assert overall_duration < 10.0, f"Overall concurrent performance too slow: {overall_duration:.3f}s"
        
        # Average thread duration should be reasonable
        avg_duration = sum(thread_durations) / len(thread_durations)
        assert avg_duration < 3.0, f"Average thread duration too slow: {avg_duration:.3f}s"

    def test_large_file_simulation_performance(self) -> None:
        """Test performance with very large file transfer simulation."""
        # Simulate a 10GB file transfer
        total_size = 10 * 1024 * 1024 * 1024  # 10GB
        
        # Initialize components
        percentage_calc = ProgressPercentageCalculator(precision=1)
        rate_calc = TransferRateCalculator(unit=RateUnit.MEGABYTES_PER_SECOND)
        etc_estimator = ETCEstimator(method=EstimationMethod.ADAPTIVE)
        history_manager = HistoryManager(max_size=1000)
        
        start_time = time.time()
        
        # Simulate transfer progress over 1000 time points
        time_points = 1000
        for i in range(time_points):
            timestamp = float(i)
            # Non-linear progress (faster at start, slower in middle, faster at end)
            ratio: float = i / time_points
            progress_ratio = math.pow(ratio, 0.8)
            bytes_transferred = int(progress_ratio * total_size)
            
            # Update all components
            percentage = percentage_calc.calculate_percentage(bytes_transferred, total_size)
            rate_calc.add_sample(bytes_transferred, timestamp)
            etc_estimator.add_sample(bytes_transferred, total_size)
            history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
            
            # Verify calculations are reasonable
            assert 0.0 <= percentage <= 100.0
            assert rate_calc.get_current_rate() >= 0
            assert etc_estimator.get_etc().seconds >= 0
            assert history_manager.get_moving_average() >= 0
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should handle large file simulation efficiently
        assert duration < 10.0, f"Large file simulation too slow: {duration:.3f}s"
        
        # Final calculations should be accurate
        final_percentage = percentage_calc.calculate_percentage(total_size, total_size)
        assert final_percentage == 100.0
        
        final_etc = etc_estimator.get_etc()
        assert final_etc.seconds < 1.0  # Should be nearly complete

    def test_precision_vs_performance_tradeoff(self) -> None:
        """Test performance tradeoffs with different precision levels."""
        precisions = [0, 2, 4, 6]
        total_calculations = 10000
        
        for precision in precisions:
            calculator = ProgressPercentageCalculator(precision=precision)
            
            start_time = time.time()
            
            # Perform calculations with varying precision
            for i in range(total_calculations):
                # Use values that would show precision differences
                progress = i * 0.123456789
                total = total_calculations * 0.123456789
                _ = calculator.calculate_percentage(progress, total)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Higher precision might be slightly slower, but should still be fast
            max_expected_duration = 0.1 * (precision + 1)  # Linear scaling with precision
            assert duration < max_expected_duration, (
                f"Precision {precision} too slow: {duration:.3f}s"
            )

    def test_algorithm_performance_comparison(self) -> None:
        """Compare performance of different algorithms within components."""
        total_size = 100000
        sample_count = 5000
        
        # Test different smoothing methods
        smoothing_methods = [
            SmoothingMethod.SIMPLE_MOVING_AVERAGE,
            SmoothingMethod.EXPONENTIAL_SMOOTHING,
            SmoothingMethod.WEIGHTED_MOVING_AVERAGE,
        ]
        
        performance_results: dict[str, float] = {}
        
        for method in smoothing_methods:
            calculator = TransferRateCalculator(smoothing=method, window_size=50)
            
            start_time = time.time()
            
            for i in range(sample_count):
                timestamp = float(i)
                bytes_transferred = i * 100
                
                calculator.add_sample(bytes_transferred, timestamp)
                
                # Get rate every 100 samples
                if i % 100 == 0:
                    _ = calculator.get_current_rate()
            
            end_time = time.time()
            duration = end_time - start_time
            performance_results[method.value] = duration
        
        # All methods should complete in reasonable time
        for method, duration in performance_results.items():
            assert duration < 2.0, f"Method {method} too slow: {duration:.3f}s"
        
        # Test different ETC estimation methods
        etc_methods = [
            EstimationMethod.LINEAR_PROJECTION,
            EstimationMethod.EXPONENTIAL_SMOOTHING,
            EstimationMethod.ADAPTIVE,
        ]
        
        etc_performance: dict[str, float] = {}
        
        for method in etc_methods:
            estimator = ETCEstimator(method=method)
            
            start_time = time.time()
            
            for i in range(sample_count):
                _timestamp = float(i)
                bytes_transferred = int((i / sample_count) * total_size)
                
                estimator.add_sample(bytes_transferred, total_size)
                
                # Get ETC every 100 samples
                if i % 100 == 0:
                    _ = estimator.get_etc()
            
            end_time = time.time()
            duration = end_time - start_time
            etc_performance[method.value] = duration
        
        # All ETC methods should complete in reasonable time
        for method, duration in etc_performance.items():
            assert duration < 2.0, f"ETC method {method} too slow: {duration:.3f}s"

    def test_scalability_with_data_volume(self) -> None:
        """Test how components scale with increasing data volumes."""
        data_volumes = [1000, 5000, 10000, 25000]
        
        for volume in data_volumes:
            # Test percentage calculator
            start_time = time.time()
            percentage_calc = ProgressPercentageCalculator()
            for i in range(volume):
                _ = percentage_calc.calculate_percentage(i, volume)
            end_time = time.time()
            duration = end_time - start_time
            max_expected = (volume / 1000.0) * 2.0  # 2 seconds per 1000 items
            assert duration < max_expected, (
                f"percentage component doesn't scale well: {duration:.3f}s for {volume} items"
            )
            
            # Test rate calculator
            start_time = time.time()
            rate_calc = TransferRateCalculator(window_size=min(volume//10, 1000))
            with patch('time.time') as mock_time:
                for i in range(volume):
                    mock_time.return_value = float(i)
                    rate_calc.add_sample(i * 100, float(i))
                    if i % 100 == 0:
                        _ = rate_calc.get_current_rate()
            end_time = time.time()
            duration = end_time - start_time
            max_expected = (volume / 1000.0) * 2.0  # 2 seconds per 1000 items
            assert duration < max_expected, (
                f"rate component doesn't scale well: {duration:.3f}s for {volume} items"
            )
            
            # Test ETC estimator
            start_time = time.time()
            etc_calc = ETCEstimator(window_size=min(volume//10, 1000))
            with patch('time.time') as mock_time:
                for i in range(volume):
                    mock_time.return_value = float(i)
                    etc_calc.add_sample(i * 100, volume * 100)
                    if i % 100 == 0:
                        _ = etc_calc.get_etc()
            end_time = time.time()
            duration = end_time - start_time
            max_expected = (volume / 1000.0) * 2.0  # 2 seconds per 1000 items
            assert duration < max_expected, (
                f"etc component doesn't scale well: {duration:.3f}s for {volume} items"
            )
            
            # Test history manager
            start_time = time.time()
            history_calc = HistoryManager(max_size=min(volume//10, 1000))
            for i in range(volume):
                history_calc.add_data_point(float(i), timestamp=float(i))
                if i % 100 == 0:
                    _ = history_calc.get_moving_average()
                    _ = history_calc.get_statistics()
            end_time = time.time()
            duration = end_time - start_time
            max_expected = (volume / 1000.0) * 2.0  # 2 seconds per 1000 items
            assert duration < max_expected, (
                f"history component doesn't scale well: {duration:.3f}s for {volume} items"
            )