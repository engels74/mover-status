"""Tests for transfer rate calculation."""

from __future__ import annotations

import pytest
from decimal import Decimal
from unittest.mock import patch

from mover_status.core.progress.transfer_rate_calculator import (
    TransferRateCalculator,
    RateUnit,
    SmoothingMethod,
)


class TestTransferRateCalculator:
    """Test suite for TransferRateCalculator."""

    def test_basic_rate_calculation(self) -> None:
        """Test basic transfer rate calculation."""
        calculator = TransferRateCalculator()
        
        # Simulate transfer progress over time
        with patch('time.time') as mock_time:
            # Start at time 0
            mock_time.return_value = 0.0
            calculator.add_sample(0, 0)
            
            # After 1 second, 1000 bytes transferred
            mock_time.return_value = 1.0
            calculator.add_sample(1000, 1.0)
            
            rate = calculator.get_current_rate()
            assert rate == pytest.approx(1000.0, rel=1e-5)  # pyright: ignore[reportUnknownMemberType] # 1000 bytes/second

    def test_rate_with_multiple_samples(self) -> None:
        """Test rate calculation with multiple data points."""
        calculator = TransferRateCalculator()
        
        with patch('time.time') as mock_time:
            # Add multiple samples
            mock_time.return_value = 0.0
            calculator.add_sample(0, 0.0)
            
            mock_time.return_value = 1.0
            calculator.add_sample(1000, 1.0)
            
            mock_time.return_value = 2.0
            calculator.add_sample(3000, 2.0)  # 2000 bytes in second 2
            
            mock_time.return_value = 3.0
            calculator.add_sample(4500, 3.0)  # 1500 bytes in second 3
            
            rate = calculator.get_current_rate()
            # Average rate over 3 seconds: 4500 bytes / 3 seconds = 1500 bytes/second
            assert rate == pytest.approx(1500.0, rel=1e-5)  # pyright: ignore[reportUnknownMemberType]

    def test_instantaneous_rate(self) -> None:
        """Test instantaneous rate calculation between last two samples."""
        calculator = TransferRateCalculator()
        
        with patch('time.time') as mock_time:
            mock_time.return_value = 0.0
            calculator.add_sample(0, 0.0)
            
            mock_time.return_value = 1.0
            calculator.add_sample(500, 1.0)  # 500 bytes/second
            
            mock_time.return_value = 2.0
            calculator.add_sample(2500, 2.0)  # 2000 bytes in last second
            
            instant_rate = calculator.get_instantaneous_rate()
            assert instant_rate == pytest.approx(2000.0, rel=1e-5)  # pyright: ignore[reportUnknownMemberType]

    def test_different_rate_units(self) -> None:
        """Test rate calculation with different units."""
        # Bytes per second (default)
        calc_bytes = TransferRateCalculator(unit=RateUnit.BYTES_PER_SECOND)
        
        # Kilobytes per second
        calc_kb = TransferRateCalculator(unit=RateUnit.KILOBYTES_PER_SECOND)
        
        # Megabytes per second
        calc_mb = TransferRateCalculator(unit=RateUnit.MEGABYTES_PER_SECOND)
        
        with patch('time.time') as mock_time:
            # Transfer 1MB in 1 second
            mock_time.return_value = 0.0
            for calc in [calc_bytes, calc_kb, calc_mb]:
                calc.add_sample(0, 0.0)
            
            mock_time.return_value = 1.0
            mb_bytes = 1024 * 1024  # 1MB in bytes
            for calc in [calc_bytes, calc_kb, calc_mb]:
                calc.add_sample(mb_bytes, 1.0)
            
            # Check rates in different units
            assert calc_bytes.get_current_rate() == pytest.approx(mb_bytes, rel=1e-5)  # pyright: ignore[reportUnknownMemberType]
            assert calc_kb.get_current_rate() == pytest.approx(1024.0, rel=1e-5)  # pyright: ignore[reportUnknownMemberType]
            assert calc_mb.get_current_rate() == pytest.approx(1.0, rel=1e-5)  # pyright: ignore[reportUnknownMemberType]

    def test_smoothing_methods(self) -> None:
        """Test different smoothing algorithms."""
        # Simple moving average
        calc_simple = TransferRateCalculator(smoothing=SmoothingMethod.SIMPLE_MOVING_AVERAGE)
        
        # Exponential smoothing
        calc_exp = TransferRateCalculator(smoothing=SmoothingMethod.EXPONENTIAL_SMOOTHING)
        
        with patch('time.time') as mock_time:
            # Add samples with varying rates
            samples = [(0, 0), (1000, 1), (1500, 2), (3000, 3), (3800, 4)]
            
            for bytes_transferred, timestamp in samples:
                mock_time.return_value = float(timestamp)
                calc_simple.add_sample(bytes_transferred, float(timestamp))
                calc_exp.add_sample(bytes_transferred, float(timestamp))
            
            simple_rate = calc_simple.get_current_rate()
            exp_rate = calc_exp.get_current_rate()
            
            # Both should be positive and reasonable
            assert simple_rate > 0
            assert exp_rate > 0
            # Exponential smoothing typically gives different results than simple average
            assert abs(simple_rate - exp_rate) > 1e-6

    def test_window_size_configuration(self) -> None:
        """Test configurable window size for rate calculation."""
        # Small window (last 3 samples)
        calc_small = TransferRateCalculator(window_size=3)
        
        # Large window (last 10 samples)
        calc_large = TransferRateCalculator(window_size=10)
        
        with patch('time.time') as mock_time:
            # Add many samples
            for i in range(15):
                mock_time.return_value = float(i)
                bytes_val = i * 1000  # Linear growth
                calc_small.add_sample(bytes_val, float(i))
                calc_large.add_sample(bytes_val, float(i))
            
            small_rate = calc_small.get_current_rate()
            large_rate = calc_large.get_current_rate()
            
            # Both should calculate reasonable rates
            assert small_rate > 0
            assert large_rate > 0

    def test_edge_cases(self) -> None:
        """Test various edge cases."""
        calculator = TransferRateCalculator()
        
        # No samples - should return 0
        assert calculator.get_current_rate() == 0.0
        assert calculator.get_instantaneous_rate() == 0.0
        
        # Single sample - should return 0
        calculator.add_sample(1000, 1.0)
        assert calculator.get_current_rate() == 0.0
        assert calculator.get_instantaneous_rate() == 0.0
        
        # Zero time difference
        with patch('time.time') as mock_time:
            calc = TransferRateCalculator()
            mock_time.return_value = 1.0
            calc.add_sample(0, 1.0)
            calc.add_sample(1000, 1.0)  # Same timestamp
            
            # Should handle zero time difference gracefully
            rate = calc.get_current_rate()
            assert rate == 0.0

    def test_negative_progress_handling(self) -> None:
        """Test handling of negative progress (should raise error)."""
        calculator = TransferRateCalculator()
        
        with pytest.raises(ValueError, match="Progress cannot be negative"):
            calculator.add_sample(-100, 1.0)

    def test_non_monotonic_time_handling(self) -> None:
        """Test handling of non-monotonic timestamps."""
        calculator = TransferRateCalculator()
        
        # Add samples with decreasing timestamps (should raise error)
        calculator.add_sample(0, 2.0)
        
        with pytest.raises(ValueError, match="Timestamp must be monotonic"):
            calculator.add_sample(1000, 1.0)  # Earlier timestamp

    def test_large_numbers(self) -> None:
        """Test rate calculation with large file sizes."""
        calculator = TransferRateCalculator()
        
        with patch('time.time') as mock_time:
            # Transfer 1TB over 1000 seconds
            tb_size = 1_000_000_000_000  # 1TB in bytes
            
            mock_time.return_value = 0.0
            calculator.add_sample(0, 0.0)
            
            mock_time.return_value = 1000.0
            calculator.add_sample(tb_size, 1000.0)
            
            rate = calculator.get_current_rate()
            expected_rate = tb_size / 1000.0  # 1GB/second
            assert rate == pytest.approx(expected_rate, rel=1e-5)  # pyright: ignore[reportUnknownMemberType]

    def test_decimal_precision(self) -> None:
        """Test rate calculation with high precision Decimal inputs."""
        calculator = TransferRateCalculator()

        with patch('time.time') as mock_time:
            mock_time.return_value = 0.0
            calculator.add_sample(Decimal('0'), 0.0)

            mock_time.return_value = 1.0
            calculator.add_sample(Decimal('1000.123456'), 1.0)

            rate = calculator.get_current_rate()
            assert rate == pytest.approx(1000.123456, rel=1e-6)  # pyright: ignore[reportUnknownMemberType]

    def test_rate_history_access(self) -> None:
        """Test access to rate calculation history."""
        calculator = TransferRateCalculator()
        
        with patch('time.time') as mock_time:
            # Add several samples
            for i in range(5):
                mock_time.return_value = float(i)
                calculator.add_sample(i * 1000, float(i))
            
            history = calculator.get_rate_history()
            assert len(history) > 0
            
            # History should contain rate calculations
            for rate_entry in history:
                assert 'rate' in rate_entry
                assert 'timestamp' in rate_entry
                assert rate_entry['rate'] >= 0

    def test_reset_functionality(self) -> None:
        """Test resetting the calculator state."""
        calculator = TransferRateCalculator()
        
        # Add some samples
        calculator.add_sample(1000, 1.0)
        calculator.add_sample(2000, 2.0)
        
        assert calculator.get_current_rate() > 0
        
        # Reset and verify clean state
        calculator.reset()
        assert calculator.get_current_rate() == 0.0
        assert len(calculator.get_rate_history()) == 0
