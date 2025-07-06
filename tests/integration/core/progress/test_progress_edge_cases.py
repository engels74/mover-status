"""Edge case testing for network interruptions and boundary conditions."""

from __future__ import annotations

import pytest
from decimal import Decimal
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


class TestProgressEdgeCases:
    """Edge case testing for progress tracking components."""

    def test_network_interruption_simulation(self) -> None:
        """Test behavior during network interruptions and connectivity issues."""
        rate_calc = TransferRateCalculator(window_size=10)
        etc_estimator = ETCEstimator(method=EstimationMethod.ADAPTIVE)
        history_manager = HistoryManager(moving_average_type=MovingAverageType.EXPONENTIAL)
        
        total_size = 100000  # 100KB
        
        with patch('time.time') as mock_time:
            # Normal transfer start
            mock_time.return_value = 0.0
            rate_calc.add_sample(0, 0.0)
            etc_estimator.add_sample(0, total_size)
            history_manager.add_data_point(0.0, timestamp=0.0)
            
            # Good transfer rate initially
            for i in range(1, 6):
                timestamp = float(i)
                bytes_transferred = i * 10000  # 10KB/s
                
                mock_time.return_value = timestamp
                rate_calc.add_sample(bytes_transferred, timestamp)
                etc_estimator.add_sample(bytes_transferred, total_size)
                history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
            
            # Verify good initial rates
            initial_rate = rate_calc.get_current_rate()
            initial_etc = etc_estimator.get_etc()
            assert initial_rate > 0
            assert initial_etc.seconds > 0
            
            # Network interruption: no progress for 30 seconds
            for i in range(6, 36):  # 30 seconds of no progress
                timestamp = float(i)
                bytes_transferred = 50000  # Stuck at 50KB
                
                mock_time.return_value = timestamp
                
                # Some components might handle stalled progress gracefully
                try:
                    rate_calc.add_sample(bytes_transferred, timestamp)
                    etc_estimator.add_sample(bytes_transferred, total_size)
                    history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
                except ValueError:
                    # Some components might reject non-monotonic progress
                    pass
            
            # Check behavior during interruption
            stalled_rate = rate_calc.get_current_rate()
            stalled_etc = etc_estimator.get_etc()
            
            # Rate should be very low or zero during stall
            assert stalled_rate < initial_rate / 2  # Significantly reduced rate
            
            # ETC should increase or show uncertainty
            if stalled_etc.confidence > 0:
                assert stalled_etc.confidence < initial_etc.confidence
            
            # Recovery: normal transfer resumes
            for i in range(36, 46):
                timestamp = float(i)
                bytes_transferred = 50000 + (i - 35) * 5000  # 5KB/s recovery
                
                mock_time.return_value = timestamp
                rate_calc.add_sample(bytes_transferred, timestamp)
                etc_estimator.add_sample(bytes_transferred, total_size)
                history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
            
            # Verify recovery
            recovery_rate = rate_calc.get_current_rate()
            recovery_etc = etc_estimator.get_etc()
            
            assert recovery_rate > 0
            assert recovery_etc.seconds >= 0

    def test_burst_transfer_patterns(self) -> None:
        """Test handling of bursty transfer patterns with high variability."""
        rate_calc = TransferRateCalculator(
            smoothing=SmoothingMethod.EXPONENTIAL_SMOOTHING,
            window_size=20
        )
        etc_estimator = ETCEstimator(method=EstimationMethod.ADAPTIVE)
        
        total_size = 1000000  # 1MB
        
        with patch('time.time') as mock_time:
            # Simulate bursty pattern: fast bursts followed by slow periods
            burst_pattern = [
                # Fast burst
                (0, 0),
                (100000, 1),    # 100KB in 1s
                (200000, 2),    # 200KB in 2s  
                (300000, 3),    # 300KB in 3s
                
                # Slow period
                (310000, 8),    # Only 10KB in 5s
                (320000, 13),   # Only 10KB in 5s
                (330000, 18),   # Only 10KB in 5s
                
                # Another fast burst
                (530000, 19),   # 200KB in 1s
                (730000, 20),   # 200KB in 1s
                (930000, 21),   # 200KB in 1s
                
                # Final slow finish
                (950000, 26),   # 20KB in 5s
                (970000, 31),   # 20KB in 5s
                (1000000, 36),  # 30KB in 5s (complete)
            ]
            
            rates: list[float] = []
            etc_estimates: list[float] = []
            
            for bytes_transferred, timestamp in burst_pattern:
                mock_time.return_value = float(timestamp)
                
                rate_calc.add_sample(bytes_transferred, float(timestamp))
                etc_estimator.add_sample(bytes_transferred, total_size)
                
                current_rate = rate_calc.get_current_rate()
                etc_result = etc_estimator.get_etc()
                
                rates.append(current_rate)
                etc_estimates.append(etc_result.seconds)
            
            # Verify rate calculation handled bursts
            assert len(rates) == len(burst_pattern)
            assert all(rate >= 0 for rate in rates)
            
            # Verify ETC adapted to pattern changes
            assert len(etc_estimates) == len(burst_pattern)
            assert all(etc >= 0 for etc in etc_estimates)
            assert etc_estimates[-1] == 0.0  # Should be 0 at completion

    def test_extremely_slow_transfer(self) -> None:
        """Test handling of extremely slow transfers with minimal progress."""
        percentage_calc = ProgressPercentageCalculator(precision=6)  # High precision
        rate_calc = TransferRateCalculator(unit=RateUnit.BYTES_PER_SECOND)
        etc_estimator = ETCEstimator(method=EstimationMethod.LINEAR_PROJECTION)
        
        # Very large file with extremely slow progress
        total_size = 1_000_000_000  # 1GB
        
        with patch('time.time') as mock_time:
            # Progress only 1 byte per second
            slow_progress = [
                (0, 0),
                (1, 1),      # 1 byte/s
                (2, 2),      # 1 byte/s
                (3, 3),      # 1 byte/s
                (4, 4),      # 1 byte/s
                (5, 5),      # 1 byte/s
                (10, 10),    # 1 byte/s (skip ahead)
                (100, 100),  # 1 byte/s (skip ahead)
                (1000, 1000), # 1 byte/s (skip ahead)
            ]
            
            for bytes_transferred, timestamp in slow_progress:
                mock_time.return_value = float(timestamp)
                
                # Test percentage with high precision
                percentage = percentage_calc.calculate_percentage(bytes_transferred, total_size)
                assert 0.0 <= percentage <= 100.0
                
                # For very small percentages, should be close to zero
                if bytes_transferred < 1000:
                    assert percentage < 0.001  # Less than 0.001%
                
                # Test rate calculation
                rate_calc.add_sample(bytes_transferred, float(timestamp))
                current_rate = rate_calc.get_current_rate()
                
                if timestamp > 0:
                    # Should detect very slow rate (around 1 byte/s)
                    assert 0.5 <= current_rate <= 2.0  # Allow some variance
                
                # Test ETC estimation
                etc_estimator.add_sample(bytes_transferred, total_size)
                etc_result = etc_estimator.get_etc()
                
                if timestamp > 1:
                    # ETC should be very large for such slow transfers
                    expected_etc = (total_size - bytes_transferred) / current_rate
                    # Allow significant variance for ETC estimates
                    assert etc_result.seconds > expected_etc * 0.1

    def test_massive_file_boundary_conditions(self) -> None:
        """Test boundary conditions with extremely large files."""
        # Test with multi-terabyte file sizes
        massive_sizes = [
            2**40,  # 1TB
            2**50,  # 1PB  
            2**60,  # 1EB (exabyte)
        ]
        
        percentage_calc = ProgressPercentageCalculator(precision=2)
        
        for total_size in massive_sizes:
            # Test various progress points
            test_points = [
                (0, 0.0),
                (total_size // 1000000, 0.0001),  # 0.0001%
                (total_size // 10000, 0.01),      # 0.01%
                (total_size // 1000, 0.1),        # 0.1%
                (total_size // 100, 1.0),         # 1%
                (total_size // 10, 10.0),         # 10%
                (total_size // 2, 50.0),          # 50%
                (total_size - 1, 99.999999),      # Nearly complete
                (total_size, 100.0),              # Complete
            ]
            
            for bytes_transferred, expected_percentage in test_points:
                percentage = percentage_calc.calculate_percentage(bytes_transferred, total_size)
                
                # Verify percentage is reasonable
                assert 0.0 <= percentage <= 100.0
                
                # For very large files, small progress might round to 0
                if expected_percentage < 0.01:
                    assert percentage <= 0.01
                elif expected_percentage > 99.99:
                    assert percentage >= 99.99
                else:
                    # Allow some precision variance
                    assert abs(percentage - expected_percentage) < 1.0

    def test_rapid_completion_scenarios(self) -> None:
        """Test scenarios where transfers complete very rapidly."""
        rate_calc = TransferRateCalculator(window_size=5)
        etc_estimator = ETCEstimator(method=EstimationMethod.LINEAR_PROJECTION)
        history_manager = HistoryManager(window_size=5)
        
        total_size = 10000  # 10KB
        
        with patch('time.time') as mock_time:
            # Complete transfer in just 2 seconds
            rapid_completion = [
                (0, 0.0),
                (5000, 0.5),    # 50% in 0.5s (10KB/s)
                (10000, 1.0),   # 100% in 1.0s (10KB/s)
            ]
            
            for bytes_transferred, timestamp in rapid_completion:
                mock_time.return_value = timestamp
                
                rate_calc.add_sample(bytes_transferred, timestamp)
                etc_estimator.add_sample(bytes_transferred, total_size)
                history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
                
                # Verify components handle rapid completion
                current_rate = rate_calc.get_current_rate()
                etc_result = etc_estimator.get_etc()
                avg_data = history_manager.get_moving_average()
                
                assert current_rate >= 0
                assert etc_result.seconds >= 0
                assert avg_data >= 0
                
                # At completion, ETC should be zero
                if bytes_transferred == total_size:
                    assert etc_result.seconds == 0.0
                    assert etc_result.confidence == 1.0

    def test_floating_point_precision_edge_cases(self) -> None:
        """Test edge cases related to floating-point precision."""
        percentage_calc = ProgressPercentageCalculator(precision=6)
        
        # Test very small differences that might cause precision issues
        precision_tests = [
            # Tiny differences
            (0.000001, 1.0, 0.0001),
            (0.999999, 1.0, 99.9999),
            (1.0, 1.000001, 99.9999),
            
            # Large numbers with small differences
            (999999999.0, 1000000000.0, 99.9999999),
            (999999999.999999, 1000000000.0, 99.999999999999),
            
            # Edge cases near zero
            (1e-15, 1e-10, 0.00001),
            (1e-10, 1e-5, 0.001),
        ]
        
        for progress, total, expected_approx in precision_tests:
            percentage = percentage_calc.calculate_percentage(progress, total)
            
            # Verify calculation is reasonable
            assert 0.0 <= percentage <= 100.0
            
            # For very small values, allow more variance
            if expected_approx < 1.0:
                assert abs(percentage - expected_approx) < 1.0
            else:
                # For larger values, expect better precision
                assert abs(percentage - expected_approx) < 0.1

    def test_timestamp_inconsistencies(self) -> None:
        """Test handling of timestamp inconsistencies and clock adjustments."""
        rate_calc = TransferRateCalculator()
        etc_estimator = ETCEstimator()
        history_manager = HistoryManager()
        
        total_size = 50000  # 50KB
        
        # Test scenarios with timestamp issues
        timestamp_scenarios = [
            # Normal progression
            [(0, 0.0), (10000, 1.0), (20000, 2.0)],
            
            # Small backward jump (clock adjustment)
            [(0, 0.0), (10000, 1.0), (20000, 0.9)],  # Should raise error
            
            # Large forward jump (system suspend/resume)
            [(0, 0.0), (10000, 1.0), (20000, 100.0)],
            
            # Duplicate timestamps
            [(0, 0.0), (10000, 1.0), (20000, 1.0)],  # Should handle gracefully
        ]
        
        for scenario_idx, scenario in enumerate(timestamp_scenarios):
            # Reset components for each scenario
            rate_calc = TransferRateCalculator()
            etc_estimator = ETCEstimator()
            history_manager = HistoryManager()
            
            for i, (bytes_transferred, timestamp) in enumerate(scenario):
                try:
                    rate_calc.add_sample(bytes_transferred, timestamp)
                    etc_estimator.add_sample(bytes_transferred, total_size)
                    history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
                    
                    # Verify components still work
                    rate = rate_calc.get_current_rate()
                    etc = etc_estimator.get_etc()
                    avg = history_manager.get_moving_average()
                    
                    assert rate >= 0
                    assert etc.seconds >= 0
                    assert avg >= 0
                    
                except ValueError:
                    # Some scenarios are expected to fail (backward timestamps)
                    if scenario_idx == 1 and i == 2:  # Backward jump scenario
                        # This is expected to fail
                        pass
                    else:
                        # Unexpected failure
                        raise

    def test_extreme_rate_variations(self) -> None:
        """Test handling of extreme rate variations and spikes."""
        rate_calc = TransferRateCalculator(
            smoothing=SmoothingMethod.EXPONENTIAL_SMOOTHING,
            window_size=10
        )
        etc_estimator = ETCEstimator(method=EstimationMethod.ADAPTIVE)
        
        total_size = 1000000  # 1MB
        
        with patch('time.time') as mock_time:
            # Extreme rate variation pattern
            extreme_pattern = [
                (0, 0.0),           # Start
                (1, 1.0),           # 1 byte/s (extremely slow)
                (1000001, 2.0),     # 1MB/s (extremely fast spike)
                (1000002, 3.0),     # 1 byte/s (back to slow)
                (1000003, 4.0),     # 1 byte/s
                (1000004, 5.0),     # 1 byte/s
                (1000000, 6.0),     # Completed
            ]
            
            rates: list[float] = []
            etc_values: list[float] = []
            
            for bytes_transferred, timestamp in extreme_pattern:
                mock_time.return_value = timestamp
                
                # Ensure we don't exceed total size
                actual_bytes = min(bytes_transferred, total_size)
                
                rate_calc.add_sample(actual_bytes, timestamp)
                etc_estimator.add_sample(actual_bytes, total_size)
                
                current_rate = rate_calc.get_current_rate()
                etc_result = etc_estimator.get_etc()
                
                rates.append(current_rate)
                etc_values.append(etc_result.seconds)
                
                # Verify components handle extreme variations
                assert current_rate >= 0
                assert etc_result.seconds >= 0
                assert 0.0 <= etc_result.confidence <= 1.0
            
            # Check that smoothing handled the spike appropriately
            assert len(rates) == len(extreme_pattern)
            assert all(rate >= 0 for rate in rates)
            
            # The spike shouldn't completely dominate the smoothed rate
            max_rate = max(rates[1:])  # Skip first rate (might be 0)
            min_rate = min(rate for rate in rates[1:] if rate > 0)
            
            # Rate variation should be smoothed, not show the full extreme
            if max_rate > 0 and min_rate > 0:
                variation_ratio = max_rate / min_rate
                # Smoothing should reduce extreme variations
                assert variation_ratio < 1000000  # Much less than the raw 1,000,000x variation

    def test_memory_pressure_edge_cases(self) -> None:
        """Test behavior under memory pressure and resource constraints."""
        # Create components with very limited memory
        rate_calc = TransferRateCalculator(window_size=3)
        etc_estimator = ETCEstimator(window_size=3)
        history_manager = HistoryManager(max_size=5)
        
        with patch('time.time') as mock_time:
            # Add many samples to test memory management
            for i in range(100):
                timestamp = float(i)
                bytes_transferred = i * 1000
                
                mock_time.return_value = timestamp
                
                rate_calc.add_sample(bytes_transferred, timestamp)
                etc_estimator.add_sample(bytes_transferred, 100000)
                history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
                
                # Verify memory constraints are maintained
                assert len(history_manager.data) <= 5
                
                # Components should still function correctly
                rate = rate_calc.get_current_rate()
                etc = etc_estimator.get_etc()
                avg = history_manager.get_moving_average()
                
                assert rate >= 0
                assert etc.seconds >= 0
                assert avg >= 0
                
                # Performance shouldn't degrade significantly
                if i > 10:  # After initial ramp-up
                    assert rate > 0  # Should detect ongoing transfer

    def test_concurrent_edge_cases(self) -> None:
        """Test edge cases under concurrent access and threading scenarios."""
        import threading
        import queue
        import random
        
        rate_calc = TransferRateCalculator()
        etc_estimator = ETCEstimator()
        history_manager = HistoryManager()
        
        error_queue: queue.Queue[str] = queue.Queue()
        
        def worker_with_edge_cases(_thread_id: int) -> None:
            """Worker that simulates various edge case scenarios."""
            try:
                with patch('time.time') as mock_time:
                    for i in range(50):
                        # Create edge case scenarios
                        timestamp = float(_thread_id * 100 + i + random.uniform(0, 0.1))
                        bytes_transferred = _thread_id * 10000 + i * 100
                        
                        # Occasionally create edge cases
                        if random.random() < 0.1:  # 10% chance
                            # Create timestamp slightly in the past (small variation)
                            timestamp -= random.uniform(0, 0.01)
                        
                        mock_time.return_value = timestamp
                        
                        try:
                            rate_calc.add_sample(bytes_transferred, timestamp)
                            etc_estimator.add_sample(bytes_transferred, 1000000)
                            history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)
                            
                            # Verify outputs are reasonable
                            rate = rate_calc.get_current_rate()
                            etc = etc_estimator.get_etc()
                            avg = history_manager.get_moving_average()
                            
                            if rate < 0 or etc.seconds < 0 or avg < 0:
                                error_queue.put(f"Thread {_thread_id}: Invalid values detected")
                                
                        except ValueError as e:
                            # Some edge cases might trigger validation errors
                            # This is acceptable behavior
                            if "monotonic" not in str(e).lower():
                                error_queue.put(f"Thread {_thread_id}: Unexpected error: {e}")
                        
            except Exception as e:
                error_queue.put(f"Thread {_thread_id}: Exception: {e}")
        
        # Start multiple threads with edge cases
        threads: list[threading.Thread] = []
        for i in range(3):
            thread = threading.Thread(target=worker_with_edge_cases, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check for any unexpected errors
        errors: list[str] = []
        while not error_queue.empty():
            errors.append(error_queue.get())
        
        # Should handle edge cases gracefully
        if errors:
            pytest.fail(f"Unexpected errors in concurrent edge cases: {errors}")

    def test_data_type_edge_cases(self) -> None:
        """Test edge cases with different data types and numerical limits."""
        percentage_calc = ProgressPercentageCalculator(precision=6)
        
        # Test with different numerical types and edge values
        edge_cases = [
            # Regular integers
            (50, 100, 50.0),
            
            # Large integers
            (2**62, 2**63, 50.0),
            
            # Floats with high precision
            (1.23456789, 2.0, 61.728394),
            
            # Very small floats
            (1e-10, 2e-10, 50.0),
            
            # Decimal types
            (Decimal('33.333333'), Decimal('100.0'), 33.333333),
            
            # Mixed types
            (50.5, 100, 50.5),
            (50, 100.0, 50.0),
            
            # Edge values near limits
            (float('inf'), float('inf')),  # Should handle gracefully
            (1.0, float('inf')),           # Should handle gracefully
        ]
        
        for case in edge_cases:
            if len(case) == 3:
                progress, total, expected = case
                try:
                    result = percentage_calc.calculate_percentage(progress, total)
                    assert 0.0 <= result <= 100.0
                    # Allow some precision variance
                    assert abs(result - expected) < 1.0
                except (ValueError, OverflowError):
                    # Some edge cases might legitimately fail
                    pass
            else:
                progress, total = case
                try:
                    result = percentage_calc.calculate_percentage(progress, total)
                    # Should handle infinity cases gracefully
                    assert isinstance(result, float)
                except (ValueError, OverflowError):
                    # Infinity cases might legitimately fail
                    pass