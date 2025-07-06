"""Unit tests for the unified progress calculator."""

from __future__ import annotations

import pytest
import time
from decimal import Decimal

from mover_status.core.progress.calculator import ProgressCalculator


class TestProgressCalculator:
    """Test suite for the unified ProgressCalculator class."""

    def test_progress_percentage_calculation(self) -> None:
        """Test basic progress percentage calculation."""
        calc = ProgressCalculator()
        result = calc.calculate_progress(transferred=50, total=100)
        
        assert result.percentage == 50.0
        assert result.bytes_remaining == 50
        assert result.transfer_rate == 0.0  # No history yet
        assert result.etc_seconds is None  # No rate yet

    def test_zero_size_handling(self) -> None:
        """Test edge case of zero total size."""
        calc = ProgressCalculator()
        result = calc.calculate_progress(transferred=0, total=0)
        
        assert result.percentage == 100.0
        assert result.bytes_remaining == 0
        assert result.transfer_rate == 0.0
        assert result.etc_seconds == 0.0  # Completed transfers have ETC = 0

    def test_transfer_rate_calculation(self) -> None:
        """Test transfer rate calculation with history."""
        calc = ProgressCalculator()
        
        # First sample - no rate yet
        result1 = calc.calculate_progress(transferred=10, total=100)
        assert result1.transfer_rate == 0.0
        
        # Small delay to create measurable time difference
        time.sleep(0.01)
        
        # Second sample - should have a rate
        result2 = calc.calculate_progress(transferred=20, total=100)
        assert result2.transfer_rate > 0.0
        assert result2.percentage == 20.0
        assert result2.bytes_remaining == 80

    def test_etc_estimation(self) -> None:
        """Test ETC estimation with sufficient data."""
        calc = ProgressCalculator()
        
        # Add multiple samples to build history
        for i in range(1, 6):
            _ = calc.calculate_progress(transferred=i * 10, total=100)
            time.sleep(0.001)  # Small delay
        
        result = calc.calculate_progress(transferred=50, total=100)
        
        # Should have ETC estimate with sufficient data
        assert result.etc_seconds is not None
        assert result.etc_seconds >= 0
        assert result.percentage == 50.0

    def test_completion_handling(self) -> None:
        """Test handling of completed transfers."""
        calc = ProgressCalculator()
        result = calc.calculate_progress(transferred=100, total=100)
        
        assert result.percentage == 100.0
        assert result.bytes_remaining == 0
        assert result.etc_seconds == 0

    def test_over_completion_handling(self) -> None:
        """Test handling when transferred exceeds total."""
        calc = ProgressCalculator()
        result = calc.calculate_progress(transferred=150, total=100)
        
        assert result.percentage == 100.0  # Capped at 100%
        assert result.bytes_remaining == 0  # Can't be negative
        assert result.etc_seconds == 0

    def test_negative_values_handling(self) -> None:
        """Test handling of negative values."""
        calc = ProgressCalculator()
        
        with pytest.raises(ValueError, match="Progress cannot be negative"):
            _ = calc.calculate_progress(transferred=-10, total=100)
        
        with pytest.raises(ValueError, match="Total cannot be negative"):
            _ = calc.calculate_progress(transferred=10, total=-100)

    def test_decimal_precision(self) -> None:
        """Test handling of high-precision decimal values."""
        calc = ProgressCalculator(precision=4)
        
        # Use Decimal for high precision
        result = calc.calculate_progress(
            transferred=Decimal("33.3333"), 
            total=Decimal("100.0000")
        )
        
        assert result.percentage == 33.3333
        assert result.bytes_remaining == 66  # bytes_remaining is converted to int

    def test_large_numbers(self) -> None:
        """Test handling of very large numbers."""
        calc = ProgressCalculator()
        
        # Test with TB-scale numbers
        tb_size = 1024 * 1024 * 1024 * 1024  # 1 TB
        result = calc.calculate_progress(transferred=tb_size // 2, total=tb_size)
        
        assert result.percentage == 50.0
        assert result.bytes_remaining == tb_size // 2

    def test_reset_functionality(self) -> None:
        """Test resetting the calculator state."""
        calc = ProgressCalculator()
        
        # Add some samples
        for i in range(3):
            _ = calc.calculate_progress(transferred=i * 10, total=100)
            time.sleep(0.001)
        
        # Reset should clear history
        calc.reset()
        
        # Should behave like a fresh calculator
        result = calc.calculate_progress(transferred=50, total=100)
        assert result.transfer_rate == 0.0  # No history
        assert result.etc_seconds is None

    def test_stalled_transfer_detection(self) -> None:
        """Test detection of stalled transfers."""
        calc = ProgressCalculator()
        
        # Add same progress multiple times (stalled)
        for _ in range(5):
            _ = calc.calculate_progress(transferred=50, total=100)
            time.sleep(0.001)
        
        result = calc.calculate_progress(transferred=50, total=100)
        
        # Rate should be zero for stalled transfer
        assert result.transfer_rate == 0.0
        assert result.percentage == 50.0

    def test_configurable_precision(self) -> None:
        """Test configurable precision settings."""
        calc_2 = ProgressCalculator(precision=2)
        calc_4 = ProgressCalculator(precision=4)
        
        result_2 = calc_2.calculate_progress(transferred=33.333333, total=100)
        result_4 = calc_4.calculate_progress(transferred=33.333333, total=100)
        
        assert result_2.percentage == 33.33
        assert result_4.percentage == 33.3333

    def test_window_size_configuration(self) -> None:
        """Test configurable window size for rate calculation."""
        calc_small = ProgressCalculator(window_size=3)
        calc_large = ProgressCalculator(window_size=10)
        
        # Both should work but may have different smoothing behavior
        result_small = None
        result_large = None
        for i in range(5):
            result_small = calc_small.calculate_progress(transferred=i * 10, total=100)
            result_large = calc_large.calculate_progress(transferred=i * 10, total=100)
            time.sleep(0.001)
        
        # Both should produce valid results
        assert result_small is not None
        assert result_large is not None
        assert result_small.percentage >= 0
        assert result_large.percentage >= 0