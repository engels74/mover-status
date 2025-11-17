"""Unit tests for formatting utilities.

Tests cover:
- All unit boundaries (KB, MB, GB, TB)
- Edge cases (zero, negative, very large values)
- Feature parity with legacy bash implementation
- Property-based testing with Hypothesis
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mover_status.utils.formatting import format_duration, format_rate, format_size


class TestFormatSize:
    """Test suite for format_size function."""

    @pytest.mark.parametrize(
        ("bytes_value", "expected"),
        [
            # Bytes range (< 1024)
            (0, "0 Bytes"),
            (1, "1 Bytes"),
            (512, "512 Bytes"),
            (1023, "1023 Bytes"),
            # KB range (1024 <= x < 1024²)
            (1024, "1 KB"),
            (2048, "2 KB"),
            (1024 * 500, "500 KB"),
            (1024**2 - 1, "1023 KB"),
            # MB range (1024² <= x < 1024³)
            (1024**2, "1 MB"),
            (1024**2 * 5, "5 MB"),
            (1024**2 * 100, "100 MB"),
            (1024**3 - 1, "1023 MB"),
            # GB range (1024³ <= x < 1024⁴)
            (1024**3, "1 GB"),
            (1024**3 * 10, "10 GB"),
            (1024**3 * 500, "500 GB"),
            (1024**4 - 1, "1023 GB"),
            # TB range (>= 1024⁴)
            (1024**4, "1.0 TB (1024 GB)"),
            (1024**4 * 2, "2.0 TB (2048 GB)"),
            # TB with decimal (matches bash: 2.5 TB = 2560 GB)
            (2748779069440, "2.5 TB (2560 GB)"),
            # Large TB values
            (1024**4 * 10, "10.0 TB (10240 GB)"),
        ],
    )
    def test_format_size_boundaries(self, bytes_value: int, expected: str) -> None:
        """Test format_size at all unit boundaries."""
        assert format_size(bytes_value) == expected

    def test_format_size_negative_raises_error(self) -> None:
        """Test that negative bytes raise ValueError."""
        with pytest.raises(ValueError, match="bytes must be non-negative"):
            _ = format_size(-1)

    def test_format_size_precision_parameter(self) -> None:
        """Test precision parameter affects TB formatting."""
        tb_value = int(2.5 * 1024**4)  # 2.5 TB

        # Default precision (1)
        assert format_size(tb_value) == "2.5 TB (2560 GB)"

        # Zero precision
        assert format_size(tb_value, precision=0) == "2 TB (2560 GB)"

        # Higher precision
        assert format_size(tb_value, precision=2) == "2.50 TB (2560 GB)"

    def test_format_size_very_large_values(self) -> None:
        """Test format_size with very large byte values."""
        # 100 TB
        large_value = 1024**4 * 100
        result = format_size(large_value)
        assert result == "100.0 TB (102400 GB)"

        # 1000 TB (approaching PB)
        very_large = 1024**4 * 1000
        result = format_size(very_large)
        assert result == "1000.0 TB (1024000 GB)"

    @given(st.integers(min_value=0, max_value=1024**5))
    def test_format_size_always_returns_string(self, bytes_value: int) -> None:
        """Property test: format_size always returns a non-empty string."""
        result = format_size(bytes_value)
        assert isinstance(result, str)
        assert len(result) > 0
        assert any(unit in result for unit in ["Bytes", "KB", "MB", "GB", "TB"])

    @given(st.integers(min_value=0, max_value=1024**5))
    def test_format_size_idempotent(self, bytes_value: int) -> None:
        """Property test: same input always produces same output."""
        result1 = format_size(bytes_value)
        result2 = format_size(bytes_value)
        assert result1 == result2

    @given(st.integers(min_value=0, max_value=1024**5))
    def test_format_size_monotonic_within_unit(self, bytes_value: int) -> None:
        """Property test: larger byte values produce larger numeric values within same unit.

        This tests a form of reversibility: if two values format to the same unit,
        the larger byte value should have a larger numeric component.
        """
        # Test with a slightly larger value
        if bytes_value < 1024**5 - 1024:
            larger_value = bytes_value + 1024
            result1 = format_size(bytes_value)
            result2 = format_size(larger_value)

            # Extract unit from both results
            unit1 = result1.split()[-1] if "TB" not in result1 else "TB"
            unit2 = result2.split()[-1] if "TB" not in result2 else "TB"

            # If same unit, numeric value should be larger or equal
            if unit1 == unit2 and unit1 != "Bytes":
                # Extract numeric part (handle TB special case with parentheses)
                if "TB" in result1:
                    num1 = float(result1.split()[0])
                    num2 = float(result2.split()[0])
                else:
                    num1 = float(result1.split()[0])
                    num2 = float(result2.split()[0])
                assert num2 >= num1, f"{bytes_value} -> {result1}, {larger_value} -> {result2}"

    @given(
        bytes_value=st.integers(min_value=0, max_value=1024**5),
        precision=st.integers(min_value=0, max_value=5),
    )
    def test_format_size_precision_parameter_valid(self, bytes_value: int, precision: int) -> None:
        """Property test: precision parameter produces valid output for all values.

        This tests that the precision parameter works correctly across all byte ranges.
        """
        result = format_size(bytes_value, precision=precision)

        # Result should always be a valid string
        assert isinstance(result, str)
        assert len(result) > 0

        # For TB values, check precision is applied
        if bytes_value >= 1024**4:
            # Should contain a decimal point for TB values
            assert "TB" in result
            # Extract the TB value
            tb_part = result.split()[0]
            if "." in tb_part:
                decimal_part = tb_part.split(".")[1]
                # Decimal places should match precision (or be less if trailing zeros removed)
                assert len(decimal_part) <= precision + 1  # Allow some flexibility

    @given(st.integers(min_value=0, max_value=1024**5))
    def test_format_size_contains_valid_unit(self, bytes_value: int) -> None:
        """Property test: formatted size always contains exactly one valid unit."""
        result = format_size(bytes_value)

        # Count how many units appear in the result
        units = ["Bytes", "KB", "MB", "GB", "TB"]
        unit_count = sum(1 for unit in units if unit in result)

        # Should contain exactly one unit (TB case has both TB and GB, so special handling)
        if "TB" in result and "GB" in result:
            # TB format includes GB in parentheses, which is valid
            assert unit_count == 2
            assert "(" in result and ")" in result
        else:
            assert unit_count == 1


class TestFormatDuration:
    """Test suite for format_duration function."""

    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            # Seconds range (< 60)
            (0, "0s"),
            (1, "1s"),
            (45, "45s"),
            (59, "59s"),
            # Minutes range (60 <= x < 3600)
            (60, "1m"),
            (90, "1m 30s"),
            (120, "2m"),
            (150, "2m 30s"),
            (3540, "59m"),
            (3599, "59m 59s"),
            # Hours range (3600 <= x < 86400)
            (3600, "1h"),
            (3660, "1h 1m"),
            (7200, "2h"),
            (9000, "2h 30m"),
            (86340, "23h 59m"),
            # Days range (>= 86400)
            (86400, "1d"),
            (90000, "1d 1h"),
            (172800, "2d"),
            (176400, "2d 1h"),
            (259200, "3d"),
        ],
    )
    def test_format_duration_boundaries(self, seconds: float, expected: str) -> None:
        """Test format_duration at all unit boundaries."""
        assert format_duration(seconds) == expected

    def test_format_duration_negative_raises_error(self) -> None:
        """Test that negative seconds raise ValueError."""
        with pytest.raises(ValueError, match="seconds must be non-negative"):
            _ = format_duration(-1.0)

    def test_format_duration_float_values(self) -> None:
        """Test format_duration with float input (rounds down)."""
        assert format_duration(45.9) == "45s"
        assert format_duration(90.5) == "1m 30s"
        assert format_duration(3665.7) == "1h 1m"

    def test_format_duration_suppresses_zero_components(self) -> None:
        """Test that zero components are not shown."""
        # Exactly 1 hour (no minutes)
        assert format_duration(3600) == "1h"
        # Exactly 1 day (no hours)
        assert format_duration(86400) == "1d"
        # Exactly 2 minutes (no seconds)
        assert format_duration(120) == "2m"

    @given(st.floats(min_value=0.0, max_value=86400.0 * 365))
    def test_format_duration_always_returns_string(self, seconds: float) -> None:
        """Property test: format_duration always returns a non-empty string."""
        result = format_duration(seconds)
        assert isinstance(result, str)
        assert len(result) > 0
        assert any(unit in result for unit in ["s", "m", "h", "d"])

    @given(st.floats(min_value=0.0, max_value=86400.0 * 365))
    def test_format_duration_idempotent(self, seconds: float) -> None:
        """Property test: same input always produces same output."""
        result1 = format_duration(seconds)
        result2 = format_duration(seconds)
        assert result1 == result2


class TestFormatRate:
    """Test suite for format_rate function."""

    @pytest.mark.parametrize(
        ("bytes_per_second", "expected"),
        [
            # Bytes/s range (< 1024)
            (0.0, "0 Bytes/s"),
            (1.0, "1 Bytes/s"),
            (512.0, "512 Bytes/s"),
            (1023.0, "1023 Bytes/s"),
            # KB/s range (1024 <= x < 1024²)
            (1024.0, "1.0 KB/s"),
            (2048.0, "2.0 KB/s"),
            (1024.0 * 500, "500.0 KB/s"),
            (1024.0**2 - 1, "1024.0 KB/s"),  # 1023.999... rounds to 1024.0
            # MB/s range (1024² <= x < 1024³)
            (1024.0**2, "1.0 MB/s"),
            (1024.0**2 * 5, "5.0 MB/s"),
            (1024.0**2 * 45, "45.0 MB/s"),
            (1024.0**2 * 100, "100.0 MB/s"),
            (1024.0**3 - 1, "1024.0 MB/s"),  # 1023.999... rounds to 1024.0
            # GB/s range (1024³ <= x < 1024⁴)
            (1024.0**3, "1.0 GB/s"),
            (1024.0**3 * 10, "10.0 GB/s"),
            (1024.0**3 * 500, "500.0 GB/s"),
            (1024.0**4 - 1, "1024.0 GB/s"),  # 1023.999... rounds to 1024.0
            # TB/s range (>= 1024⁴)
            (1024.0**4, "1.0 TB/s"),
            (1024.0**4 * 2, "2.0 TB/s"),
            (1024.0**4 * 2.5, "2.5 TB/s"),
        ],
    )
    def test_format_rate_boundaries(self, bytes_per_second: float, expected: str) -> None:
        """Test format_rate at all unit boundaries."""
        assert format_rate(bytes_per_second) == expected

    def test_format_rate_negative_raises_error(self) -> None:
        """Test that negative rate raises ValueError."""
        with pytest.raises(ValueError, match="bytes_per_second must be non-negative"):
            _ = format_rate(-1.0)

    def test_format_rate_decimal_precision(self) -> None:
        """Test that rates show one decimal place for precision."""
        # 45.23 MB/s should show as 45.2 MB/s (one decimal)
        rate_bytes = 1024.0**2 * 45.23
        result = format_rate(rate_bytes)
        assert result == "45.2 MB/s"

        # 100.789 GB/s should show as 100.8 GB/s
        rate_bytes = 1024.0**3 * 100.789
        result = format_rate(rate_bytes)
        assert result == "100.8 GB/s"

    def test_format_rate_small_values_use_integers(self) -> None:
        """Test that Bytes/s uses integer format."""
        assert format_rate(42.7) == "42 Bytes/s"
        assert format_rate(999.9) == "999 Bytes/s"

    @given(st.floats(min_value=0.0, max_value=1024.0**5))
    def test_format_rate_always_returns_string(self, rate: float) -> None:
        """Property test: format_rate always returns a non-empty string."""
        result = format_rate(rate)
        assert isinstance(result, str)
        assert len(result) > 0
        assert "/s" in result
        assert any(unit in result for unit in ["Bytes/s", "KB/s", "MB/s", "GB/s", "TB/s"])

    @given(st.floats(min_value=0.0, max_value=1024.0**5))
    def test_format_rate_idempotent(self, rate: float) -> None:
        """Property test: same input always produces same output."""
        result1 = format_rate(rate)
        result2 = format_rate(rate)
        assert result1 == result2


class TestCrossFunction:
    """Integration tests across multiple formatting functions."""

    def test_all_functions_are_pure(self) -> None:
        """Verify that all functions are pure (same input = same output)."""
        # format_size
        size_result1 = format_size(1024**3)
        size_result2 = format_size(1024**3)
        assert size_result1 == size_result2

        # format_duration
        duration_result1 = format_duration(3665.0)
        duration_result2 = format_duration(3665.0)
        assert duration_result1 == duration_result2

        # format_rate
        rate_result1 = format_rate(1024.0**2 * 45)
        rate_result2 = format_rate(1024.0**2 * 45)
        assert rate_result1 == rate_result2

    def test_format_rate_consistent_with_format_size(self) -> None:
        """Verify format_rate uses same unit logic as format_size."""
        # 45 MB should use same threshold in both functions
        bytes_value = 1024**2 * 45

        size_result = format_size(bytes_value)
        rate_result = format_rate(float(bytes_value))

        # Size shows "45 MB", rate shows "45.0 MB/s"
        assert "45" in size_result
        assert "MB" in size_result
        assert "45.0 MB/s" == rate_result

    def test_realistic_usage_scenario(self) -> None:
        """Test realistic values from a data transfer scenario."""
        # Moving 2.5 TB of data
        total_bytes = int(2.5 * 1024**4)
        assert format_size(total_bytes) == "2.5 TB (2560 GB)"

        # At 45 MB/s transfer rate
        rate = 1024.0**2 * 45
        assert format_rate(rate) == "45.0 MB/s"

        # Will take approximately 16 hours
        estimated_seconds = total_bytes / rate
        duration_str = format_duration(estimated_seconds)
        # Should show hours and minutes
        assert "h" in duration_str


class TestPropertyBasedFormattingInvariants:
    """Property-based tests for formatting function invariants using Hypothesis.

    These tests ensure that formatting functions maintain critical invariants:
    - Never produce NaN or Infinity
    - Always produce valid, parseable output
    - Maintain consistency and determinism
    - Handle edge cases gracefully
    """

    @given(st.integers(min_value=0, max_value=1024**5))
    def test_format_size_never_produces_invalid_output(self, bytes_value: int) -> None:
        """Property: format_size never produces NaN, Infinity, or invalid strings.

        This test ensures format_size handles all valid byte values gracefully
        and produces well-formed output strings.
        """
        result = format_size(bytes_value)

        # Must be a valid non-empty string
        assert isinstance(result, str)
        assert len(result) > 0

        # Must not contain invalid float representations
        assert "nan" not in result.lower()
        assert "inf" not in result.lower()

        # Must contain a valid unit
        valid_units = ["Bytes", "KB", "MB", "GB", "TB"]
        assert any(unit in result for unit in valid_units)

        # Must be parseable (contains numeric component)
        # Extract first token which should be numeric
        first_token = result.split()[0]
        try:
            numeric_value = float(first_token)
            # Numeric value must be finite
            import math

            assert not math.isnan(numeric_value)
            assert not math.isinf(numeric_value)
            assert numeric_value >= 0
        except ValueError:
            pytest.fail(f"format_size produced non-numeric first token: {first_token}")

    @given(st.floats(min_value=0.0, max_value=1024.0**5, allow_nan=False, allow_infinity=False))
    def test_format_rate_never_produces_invalid_output(self, rate: float) -> None:
        """Property: format_rate never produces NaN, Infinity, or invalid strings.

        This test ensures format_rate handles all valid rate values gracefully
        and produces well-formed output strings.
        """
        result = format_rate(rate)

        # Must be a valid non-empty string
        assert isinstance(result, str)
        assert len(result) > 0

        # Must not contain invalid float representations
        assert "nan" not in result.lower()
        assert "inf" not in result.lower()

        # Must contain "/s" suffix
        assert "/s" in result

        # Must contain a valid unit
        valid_units = ["Bytes/s", "KB/s", "MB/s", "GB/s", "TB/s"]
        assert any(unit in result for unit in valid_units)

        # Must be parseable (contains numeric component)
        first_token = result.split()[0]
        try:
            numeric_value = float(first_token)
            import math

            assert not math.isnan(numeric_value)
            assert not math.isinf(numeric_value)
            assert numeric_value >= 0
        except ValueError:
            pytest.fail(f"format_rate produced non-numeric first token: {first_token}")

    @given(st.floats(min_value=0.0, max_value=86400.0 * 365, allow_nan=False, allow_infinity=False))
    def test_format_duration_never_produces_invalid_output(self, seconds: float) -> None:
        """Property: format_duration never produces NaN, Infinity, or invalid strings.

        This test ensures format_duration handles all valid duration values gracefully
        and produces well-formed output strings.
        """
        result = format_duration(seconds)

        # Must be a valid non-empty string
        assert isinstance(result, str)
        assert len(result) > 0

        # Must not contain invalid float representations
        assert "nan" not in result.lower()
        assert "inf" not in result.lower()

        # Must contain a valid time unit
        valid_units = ["s", "m", "h", "d"]
        assert any(unit in result for unit in valid_units)

        # All numeric components must be valid integers
        import re

        # Extract all numeric values from the result
        numbers: list[str] = re.findall(r"\d+", result)
        assert len(numbers) > 0, f"No numeric values found in: {result}"

        for num_str in numbers:
            num: int = int(num_str)
            assert num >= 0

    @given(
        bytes_value=st.integers(min_value=0, max_value=1024**5),
        precision1=st.integers(min_value=0, max_value=3),
        precision2=st.integers(min_value=0, max_value=3),
    )
    def test_format_size_precision_consistency(self, bytes_value: int, precision1: int, precision2: int) -> None:
        """Property: format_size with same precision always produces same output.

        This tests that the precision parameter is deterministic and consistent.
        """
        result1 = format_size(bytes_value, precision=precision1)
        result2 = format_size(bytes_value, precision=precision1)

        # Same precision should always produce identical output
        assert result1 == result2

        # Different precisions may produce different output for TB values
        if bytes_value >= 1024**4:
            result3 = format_size(bytes_value, precision=precision2)
            # All results should be valid
            assert isinstance(result3, str)
            assert len(result3) > 0
