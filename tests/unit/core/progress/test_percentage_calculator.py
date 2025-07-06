"""Tests for progress percentage calculation."""

from __future__ import annotations

import pytest
from decimal import Decimal

from mover_status.core.progress.percentage_calculator import ProgressPercentageCalculator


class TestProgressPercentageCalculator:
    """Test suite for ProgressPercentageCalculator."""

    def test_basic_percentage_calculation(self) -> None:
        """Test basic percentage calculation with integers."""
        calculator = ProgressPercentageCalculator()
        
        # Test 50% progress
        result = calculator.calculate_percentage(50, 100)
        assert result == 50.0
        
        # Test 25% progress
        result = calculator.calculate_percentage(25, 100)
        assert result == 25.0
        
        # Test 100% progress
        result = calculator.calculate_percentage(100, 100)
        assert result == 100.0
        
        # Test 0% progress
        result = calculator.calculate_percentage(0, 100)
        assert result == 0.0

    def test_zero_total_handling(self) -> None:
        """Test handling of zero total - should return 100% for zero/zero."""
        calculator = ProgressPercentageCalculator()
        
        # Zero total with zero progress should be 100%
        result = calculator.calculate_percentage(0, 0)
        assert result == 100.0
        
        # Non-zero progress with zero total should raise error
        with pytest.raises(ValueError, match="Cannot calculate percentage with zero total"):
            _ = calculator.calculate_percentage(50, 0)

    def test_negative_values(self) -> None:
        """Test handling of negative values."""
        calculator = ProgressPercentageCalculator()
        
        # Negative progress should raise error
        with pytest.raises(ValueError, match="Progress cannot be negative"):
            _ = calculator.calculate_percentage(-10, 100)
        
        # Negative total should raise error
        with pytest.raises(ValueError, match="Total cannot be negative"):
            _ = calculator.calculate_percentage(50, -100)

    def test_progress_greater_than_total(self) -> None:
        """Test handling when progress exceeds total."""
        calculator = ProgressPercentageCalculator()
        
        # Progress greater than total should cap at 100%
        result = calculator.calculate_percentage(150, 100)
        assert result == 100.0
        
        # Significantly greater progress should still cap at 100%
        result = calculator.calculate_percentage(1000, 100)
        assert result == 100.0

    def test_float_inputs(self) -> None:
        """Test percentage calculation with float inputs."""
        calculator = ProgressPercentageCalculator()
        
        # Float inputs
        result = calculator.calculate_percentage(33.33, 100.0)
        assert result == pytest.approx(33.33, rel=1e-5)  # pyright: ignore[reportUnknownMemberType]
        
        # Mixed int/float inputs
        result = calculator.calculate_percentage(50, 100.0)
        assert result == 50.0
        
        result = calculator.calculate_percentage(50.0, 100)
        assert result == 50.0

    def test_decimal_inputs(self) -> None:
        """Test percentage calculation with Decimal inputs."""
        calculator = ProgressPercentageCalculator()
        
        # Decimal inputs for high precision
        result = calculator.calculate_percentage(Decimal("33.333333"), Decimal("100.0"))
        assert result == pytest.approx(33.333333, rel=1e-6)  # pyright: ignore[reportUnknownMemberType]
        
        # Mixed Decimal and numeric inputs
        result = calculator.calculate_percentage(Decimal("50.5"), 100)
        assert result == 50.5

    def test_precision_levels(self) -> None:
        """Test configurable precision levels."""
        # Default precision (2 decimal places)
        calculator = ProgressPercentageCalculator()
        result = calculator.calculate_percentage(33.333333, 100)
        assert result == pytest.approx(33.33, rel=1e-5)  # pyright: ignore[reportUnknownMemberType]

        # High precision (6 decimal places)
        calculator = ProgressPercentageCalculator(precision=6)
        result = calculator.calculate_percentage(33.333333, 100)
        assert result == pytest.approx(33.333333, rel=1e-6)  # pyright: ignore[reportUnknownMemberType]
        
        # Low precision (0 decimal places)
        calculator = ProgressPercentageCalculator(precision=0)
        result = calculator.calculate_percentage(33.7, 100)
        assert result == 34.0

    def test_large_numbers(self) -> None:
        """Test percentage calculation with large numbers."""
        calculator = ProgressPercentageCalculator()
        
        # Large file sizes (terabytes)
        tb_size = 1_000_000_000_000  # 1TB in bytes
        result = calculator.calculate_percentage(tb_size // 2, tb_size)
        assert result == 50.0
        
        # Very large numbers
        huge_number = 10**18
        result = calculator.calculate_percentage(huge_number // 4, huge_number)
        assert result == 25.0

    def test_small_numbers(self) -> None:
        """Test percentage calculation with very small numbers."""
        calculator = ProgressPercentageCalculator()
        
        # Small fractions
        result = calculator.calculate_percentage(0.001, 0.01)
        assert result == 10.0
        
        # Very small numbers
        result = calculator.calculate_percentage(1e-10, 1e-9)
        assert result == 10.0

    def test_edge_cases(self) -> None:
        """Test various edge cases."""
        calculator = ProgressPercentageCalculator()
        
        # Same number for progress and total
        result = calculator.calculate_percentage(42, 42)
        assert result == 100.0
        
        # Very small difference - with default precision of 2, 99.999% rounds to 100.0%
        result = calculator.calculate_percentage(99.999, 100)
        assert result == 100.0
        
        # Test with higher precision to preserve the exact value
        high_precision_calculator = ProgressPercentageCalculator(precision=3)
        result = high_precision_calculator.calculate_percentage(99.999, 100)
        assert result == pytest.approx(99.999, rel=1e-5)  # pyright: ignore[reportUnknownMemberType]



    def test_different_data_types(self) -> None:
        """Test percentage calculation with different data types."""
        calculator = ProgressPercentageCalculator()
        
        # Bytes transferred
        result = calculator.calculate_percentage(512_000, 1_024_000)  # 512KB of 1MB
        assert result == 50.0
        
        # Items processed
        result = calculator.calculate_percentage(75, 150)  # 75 items of 150
        assert result == 50.0
        
        # Time elapsed (seconds)
        result = calculator.calculate_percentage(1800, 3600)  # 30 minutes of 60 minutes
        assert result == 50.0

    def test_batch_calculation(self) -> None:
        """Test batch calculation of multiple percentages."""
        calculator = ProgressPercentageCalculator()
        
        # List of (progress, total) tuples
        test_cases = [
            (25, 100),
            (50, 100),
            (75, 100),
            (100, 100),
        ]
        
        results = [calculator.calculate_percentage(prog, tot) for prog, tot in test_cases]
        expected = [25.0, 50.0, 75.0, 100.0]
        
        assert results == expected

    def test_performance_with_large_dataset(self) -> None:
        """Test performance with large number of calculations."""
        calculator = ProgressPercentageCalculator()
        
        # Perform many calculations
        import time
        start_time = time.time()
        
        for i in range(10000):
            _ = calculator.calculate_percentage(i, 10000)
        
        end_time = time.time()
        
        # Should complete within reasonable time (less than 1 second)
        assert end_time - start_time < 1.0 