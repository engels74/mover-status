"""Unit tests for progress calculation engine.

Tests cover:
- All calculation functions with edge cases
- Progress percentage calculation
- Data movement rate calculation with moving average
- Estimated time of completion (ETC) calculation
- Remaining data calculation
- Property-based testing with Hypothesis for invariants
"""

from datetime import datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mover_status.core.calculation import (
    calculate_etc,
    calculate_progress,
    calculate_progress_data,
    calculate_rate,
    calculate_remaining,
)
from mover_status.types.models import DiskSample


class TestCalculateProgress:
    """Test suite for calculate_progress function."""

    @pytest.mark.parametrize(
        ("baseline", "current", "expected"),
        [
            # Standard cases
            (1000, 500, 50.0),  # 50% complete
            (1000, 0, 100.0),  # 100% complete
            (1000, 1000, 0.0),  # 0% complete (no movement)
            (1000, 250, 75.0),  # 75% complete
            # Edge case: Zero baseline
            (0, 0, 100.0),  # Nothing to move
            # Edge case: Negative delta (current > baseline)
            (100, 150, 0.0),  # Data added, no progress
            (500, 600, 0.0),  # Data added, no progress
            # Exact values
            (1024, 512, 50.0),  # Exactly 50%
            (1024, 256, 75.0),  # Exactly 75%
            (1024, 768, 25.0),  # Exactly 25%
        ],
    )
    def test_calculate_progress_standard_cases(
        self, baseline: int, current: int, expected: float
    ) -> None:
        """Test calculate_progress with standard and edge cases."""
        result = calculate_progress(baseline=baseline, current=current)
        assert result == pytest.approx(expected, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations

    def test_calculate_progress_negative_baseline_raises_error(self) -> None:
        """Test that negative baseline raises ValueError."""
        with pytest.raises(ValueError, match="baseline must be non-negative"):
            _ = calculate_progress(baseline=-1, current=0)

    def test_calculate_progress_negative_current_raises_error(self) -> None:
        """Test that negative current raises ValueError."""
        with pytest.raises(ValueError, match="current must be non-negative"):
            _ = calculate_progress(baseline=100, current=-1)

    @pytest.mark.parametrize(
        ("baseline", "current"),
        [
            (1024**3, int(1024**3 * 0.5)),  # 1 GB baseline, 50% remaining
            (1024**4, int(1024**4 * 0.25)),  # 1 TB baseline, 75% complete
            (1024**4 * 5, int(1024**4 * 5 * 0.1)),  # 5 TB baseline, 90% complete
        ],
    )
    def test_calculate_progress_large_values(
        self, baseline: int, current: int
    ) -> None:
        """Test calculate_progress with large realistic values (GB, TB)."""
        result = calculate_progress(baseline=baseline, current=current)
        assert 0.0 <= result <= 100.0
        # Verify calculation is correct
        expected = ((baseline - current) / baseline) * 100.0
        assert result == pytest.approx(expected, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations

    @given(
        baseline=st.integers(min_value=0, max_value=1024**5),
        current=st.integers(min_value=0, max_value=1024**5),
    )
    def test_calculate_progress_always_in_range(
        self, baseline: int, current: int
    ) -> None:
        """Property test: progress percentage always between 0 and 100."""
        result = calculate_progress(baseline=baseline, current=current)
        assert 0.0 <= result <= 100.0

    @given(
        baseline=st.integers(min_value=1, max_value=1024**5),
        current=st.integers(min_value=0, max_value=1024**5),
    )
    def test_calculate_progress_idempotent(self, baseline: int, current: int) -> None:
        """Property test: same input always produces same output."""
        result1 = calculate_progress(baseline=baseline, current=current)
        result2 = calculate_progress(baseline=baseline, current=current)
        assert result1 == result2

    @given(baseline=st.integers(min_value=1, max_value=1024**4))
    def test_calculate_progress_complete_transfer(self, baseline: int) -> None:
        """Property test: current=0 always means 100% complete."""
        result = calculate_progress(baseline=baseline, current=0)
        assert result == 100.0

    @given(baseline=st.integers(min_value=1, max_value=1024**4))
    def test_calculate_progress_no_movement(self, baseline: int) -> None:
        """Property test: current=baseline always means 0% complete."""
        result = calculate_progress(baseline=baseline, current=baseline)
        assert result == 0.0


class TestCalculateRemaining:
    """Test suite for calculate_remaining function."""

    @pytest.mark.parametrize(
        ("baseline", "current", "expected"),
        [
            # Standard cases
            (1000, 400, 400),  # 400 bytes remaining
            (1000, 0, 0),  # All transferred
            (1000, 1000, 0),  # Nothing transferred
            # Edge case: Negative delta
            (100, 150, 0),  # Data added, no remaining
            # Edge case: Zero baseline
            (0, 0, 0),  # Nothing to transfer
        ],
    )
    def test_calculate_remaining_standard_cases(
        self, baseline: int, current: int, expected: int
    ) -> None:
        """Test calculate_remaining with standard and edge cases."""
        result = calculate_remaining(baseline=baseline, current=current)
        assert result == expected

    def test_calculate_remaining_negative_baseline_raises_error(self) -> None:
        """Test that negative baseline raises ValueError."""
        with pytest.raises(ValueError, match="baseline must be non-negative"):
            _ = calculate_remaining(baseline=-1, current=0)

    def test_calculate_remaining_negative_current_raises_error(self) -> None:
        """Test that negative current raises ValueError."""
        with pytest.raises(ValueError, match="current must be non-negative"):
            _ = calculate_remaining(baseline=100, current=-1)

    @given(
        baseline=st.integers(min_value=0, max_value=1024**5),
        current=st.integers(min_value=0, max_value=1024**5),
    )
    def test_calculate_remaining_always_non_negative(
        self, baseline: int, current: int
    ) -> None:
        """Property test: remaining bytes always non-negative."""
        result = calculate_remaining(baseline=baseline, current=current)
        assert result >= 0

    @given(
        baseline=st.integers(min_value=0, max_value=1024**5),
        current=st.integers(min_value=0, max_value=1024**5),
    )
    def test_calculate_remaining_never_exceeds_baseline(
        self, baseline: int, current: int
    ) -> None:
        """Property test: remaining never exceeds baseline."""
        result = calculate_remaining(baseline=baseline, current=current)
        assert result <= baseline


class TestCalculateRate:
    """Test suite for calculate_rate function."""

    def test_calculate_rate_single_interval(self) -> None:
        """Test rate calculation with two samples (one interval)."""
        samples = [
            DiskSample(datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache"),
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 10), 900, "/cache"
            ),  # 100 bytes in 10s = 10 B/s
        ]
        result = calculate_rate(samples)
        assert result == pytest.approx(10.0, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations

    def test_calculate_rate_moving_average(self) -> None:
        """Test rate calculation with moving average over multiple intervals."""
        samples = [
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache"
            ),  # 100 bytes in 10s = 10 B/s
            DiskSample(datetime(2024, 1, 1, 10, 0, 10), 900, "/cache"),
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 20), 800, "/cache"
            ),  # 100 bytes in 10s = 10 B/s
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 30), 700, "/cache"
            ),  # 100 bytes in 10s = 10 B/s
        ]
        # Average of three intervals: (10 + 10 + 10) / 3 = 10 B/s
        result = calculate_rate(samples, window_size=3)
        assert result == pytest.approx(10.0, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations

    def test_calculate_rate_varying_rates(self) -> None:
        """Test rate calculation with varying transfer rates."""
        samples = [
            DiskSample(datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache"),
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 10), 800, "/cache"
            ),  # 200 bytes in 10s = 20 B/s
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 20), 700, "/cache"
            ),  # 100 bytes in 10s = 10 B/s
        ]
        # Average: (20 + 10) / 2 = 15 B/s
        result = calculate_rate(samples, window_size=3)
        assert result == pytest.approx(15.0, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations

    def test_calculate_rate_insufficient_samples(self) -> None:
        """Test that fewer than 2 samples returns 0.0."""
        # Single sample
        samples = [DiskSample(datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache")]
        result = calculate_rate(samples)
        assert result == 0.0

        # Empty samples
        result = calculate_rate([])
        assert result == 0.0

    def test_calculate_rate_zero_time_delta(self) -> None:
        """Test that samples with same timestamp are skipped."""
        samples = [
            DiskSample(datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache"),
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 0), 900, "/cache"
            ),  # Same timestamp, skip
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 10), 800, "/cache"
            ),  # Valid intervals: (1000->900 skipped), (900->800 over 10s = 10 B/s)
        ]
        # Window size is 3, so uses all 3 samples but skips invalid interval
        # Valid rate: 900 -> 800 over 10s = 10 B/s
        result = calculate_rate(samples)
        assert result == pytest.approx(10.0, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations

    def test_calculate_rate_negative_delta(self) -> None:
        """Test that negative deltas (disk usage increase) are skipped."""
        samples = [
            DiskSample(datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache"),
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 10), 1100, "/cache"
            ),  # Increased, skip (1000->1100)
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 20), 900, "/cache"
            ),  # Valid: 1100->900 over 10s = 200 bytes in 10s = 20 B/s
        ]
        # Window contains all 3 samples
        # Interval 1: 1000->1100 is negative delta, skip
        # Interval 2: 1100->900 is 200 bytes in 10s = 20 B/s
        result = calculate_rate(samples)
        assert result == pytest.approx(20.0, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations

    def test_calculate_rate_all_invalid_intervals(self) -> None:
        """Test that all invalid intervals returns 0.0."""
        samples = [
            DiskSample(datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache"),
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 10), 1100, "/cache"
            ),  # Negative delta
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 10), 1200, "/cache"
            ),  # Zero time delta
        ]
        result = calculate_rate(samples)
        assert result == 0.0

    def test_calculate_rate_window_size_smaller_than_samples(self) -> None:
        """Test that window_size limits the samples used."""
        samples = [
            DiskSample(datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache"),
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 10), 900, "/cache"
            ),  # 100 bytes in 10s = 10 B/s
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 20), 800, "/cache"
            ),  # 100 bytes in 10s = 10 B/s
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 30), 600, "/cache"
            ),  # 200 bytes in 10s = 20 B/s (most recent)
        ]
        # With window_size=2, should only use last 2 samples
        # Rate from 800->600 in 10s = 20 B/s
        result = calculate_rate(samples, window_size=2)
        assert result == pytest.approx(20.0, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations

    def test_calculate_rate_invalid_window_size(self) -> None:
        """Test that window_size < 2 raises ValueError."""
        samples = [
            DiskSample(datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache"),
            DiskSample(datetime(2024, 1, 1, 10, 0, 10), 900, "/cache"),
        ]
        with pytest.raises(ValueError, match="window_size must be at least 2"):
            _ = calculate_rate(samples, window_size=1)

    def test_calculate_rate_realistic_scenario(self) -> None:
        """Test rate calculation with realistic data transfer scenario."""
        # Simulating transfer at ~45 MB/s
        bytes_per_second = 1024.0**2 * 45  # 45 MB/s
        samples = [
            DiskSample(datetime(2024, 1, 1, 10, 0, 0), int(1024**3), "/cache"),
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 1),
                int(1024**3 - bytes_per_second),
                "/cache",
            ),
            DiskSample(
                datetime(2024, 1, 1, 10, 0, 2),
                int(1024**3 - bytes_per_second * 2),
                "/cache",
            ),
        ]
        result = calculate_rate(samples)
        expected = bytes_per_second
        assert result == pytest.approx(expected, rel=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations


class TestCalculateETC:
    """Test suite for calculate_etc function."""

    def test_calculate_etc_standard_case(self) -> None:
        """Test ETC calculation with standard inputs."""
        # 1000 bytes at 10 bytes/second = 100 seconds
        before = datetime.now()
        result = calculate_etc(remaining=1000, rate=10.0)

        assert result is not None
        # ETC should be approximately 100 seconds from now
        expected_etc = before + timedelta(seconds=100)
        # Allow small tolerance for execution time
        assert abs((result - expected_etc).total_seconds()) < 2

    def test_calculate_etc_zero_rate(self) -> None:
        """Test that zero rate returns None."""
        result = calculate_etc(remaining=1000, rate=0.0)
        assert result is None

    def test_calculate_etc_negative_rate(self) -> None:
        """Test that negative rate raises ValueError."""
        with pytest.raises(ValueError, match="rate must be non-negative"):
            _ = calculate_etc(remaining=1000, rate=-1.0)

    def test_calculate_etc_zero_remaining(self) -> None:
        """Test that zero remaining returns current time."""
        before = datetime.now()
        result = calculate_etc(remaining=0, rate=10.0)
        after = datetime.now()

        assert result is not None
        # Should be very close to current time
        assert before <= result <= after + timedelta(seconds=1)

    def test_calculate_etc_negative_remaining_raises_error(self) -> None:
        """Test that negative remaining raises ValueError."""
        with pytest.raises(ValueError, match="remaining must be non-negative"):
            _ = calculate_etc(remaining=-1, rate=10.0)

    def test_calculate_etc_large_values(self) -> None:
        """Test ETC calculation with large realistic values."""
        # 1 TB remaining at 45 MB/s
        remaining = 1024**4
        rate = 1024.0**2 * 45  # 45 MB/s

        before = datetime.now()
        result = calculate_etc(remaining=remaining, rate=rate)

        assert result is not None
        # ETC should be in the future
        assert result > before

        # Verify calculation
        expected_seconds = remaining / rate
        expected_etc = before + timedelta(seconds=expected_seconds)
        # Allow tolerance for execution time
        assert abs((result - expected_etc).total_seconds()) < 2

    @given(
        remaining=st.integers(min_value=0, max_value=1024**5),
        rate=st.floats(min_value=0.1, max_value=1024.0**4),
    )
    def test_calculate_etc_always_in_future(self, remaining: int, rate: float) -> None:
        """Property test: ETC is always in the future (or None)."""
        before = datetime.now()
        result = calculate_etc(remaining=remaining, rate=rate)

        if result is not None:
            # Allow small tolerance for very fast transfers
            assert result >= before - timedelta(seconds=1)


class TestCalculateProgressData:
    """Test suite for calculate_progress_data convenience function."""

    def test_calculate_progress_data_complete_scenario(self) -> None:
        """Test complete progress data calculation with all metrics."""
        baseline = 1000
        current = 500
        samples = [
            DiskSample(datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache"),
            DiskSample(datetime(2024, 1, 1, 10, 0, 10), 900, "/cache"),
            DiskSample(datetime(2024, 1, 1, 10, 0, 20), 800, "/cache"),
            DiskSample(datetime(2024, 1, 1, 10, 0, 30), 700, "/cache"),
        ]

        result = calculate_progress_data(baseline=baseline, current=current, samples=samples)

        # Verify all fields
        assert result.percent == pytest.approx(50.0, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations
        assert result.remaining_bytes == 500
        assert result.moved_bytes == 500
        assert result.total_bytes == 1000
        assert result.rate_bytes_per_second == pytest.approx(10.0, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations
        assert result.etc is not None

    def test_calculate_progress_data_no_samples(self) -> None:
        """Test that insufficient samples results in zero rate and no ETC."""
        baseline = 1000
        current = 500
        samples = [DiskSample(datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache")]

        result = calculate_progress_data(baseline=baseline, current=current, samples=samples)

        assert result.percent == pytest.approx(50.0, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations
        assert result.remaining_bytes == 500
        assert result.moved_bytes == 500
        assert result.total_bytes == 1000
        assert result.rate_bytes_per_second == 0.0
        assert result.etc is None  # No rate means no ETC

    def test_calculate_progress_data_negative_delta(self) -> None:
        """Test progress data when current > baseline (negative delta)."""
        baseline = 1000
        current = 1200  # Data added
        samples = [
            DiskSample(datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache"),
            DiskSample(datetime(2024, 1, 1, 10, 0, 10), 1200, "/cache"),
        ]

        result = calculate_progress_data(baseline=baseline, current=current, samples=samples)

        assert result.percent == 0.0  # No progress
        assert result.remaining_bytes == 0  # No remaining (current >= baseline)
        assert result.moved_bytes == 0  # No data moved (ensured non-negative)
        assert result.total_bytes == 1000

    def test_calculate_progress_data_window_size_parameter(self) -> None:
        """Test that window_size parameter is passed through correctly."""
        baseline = 1000
        current = 500
        samples = [
            DiskSample(datetime(2024, 1, 1, 10, 0, 0), 1000, "/cache"),
            DiskSample(datetime(2024, 1, 1, 10, 0, 10), 900, "/cache"),  # 10 B/s
            DiskSample(datetime(2024, 1, 1, 10, 0, 20), 800, "/cache"),  # 10 B/s
            DiskSample(datetime(2024, 1, 1, 10, 0, 30), 600, "/cache"),  # 20 B/s (most recent)
        ]

        # With window_size=2, should only use last 2 samples
        result = calculate_progress_data(baseline=baseline, current=current, samples=samples, window_size=2)

        # Rate should be 20 B/s from the most recent interval
        assert result.rate_bytes_per_second == pytest.approx(20.0, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations


class TestPropertyBasedInvariants:
    """Property-based tests for calculation invariants using Hypothesis."""

    @given(
        baseline=st.integers(min_value=1, max_value=1024**4),
        current=st.integers(min_value=0, max_value=1024**4),
    )
    def test_progress_plus_remaining_equals_baseline(
        self, baseline: int, current: int
    ) -> None:
        """Property: progress + remaining should relate correctly to baseline."""
        progress_percent = calculate_progress(baseline=baseline, current=current)
        remaining = calculate_remaining(baseline=baseline, current=current)

        # If current < baseline, remaining should match current
        if current < baseline:
            assert remaining == current
            # Progress calculation: (baseline - current) / baseline * 100
            # So: moved = baseline - current = baseline - remaining
            moved = baseline - remaining
            expected_progress = (moved / baseline) * 100
            assert progress_percent == pytest.approx(expected_progress, abs=0.01)  # pyright: ignore[reportUnknownMemberType]  # pytest.approx has incomplete type annotations
        elif current == baseline:
            # No movement yet, so remaining should be 0
            assert remaining == 0
            assert progress_percent == 0.0
        else:
            # current > baseline (negative delta)
            assert remaining == 0
            assert progress_percent == 0.0

    @given(
        samples=st.lists(
            st.builds(
                DiskSample,
                timestamp=st.datetimes(
                    min_value=datetime(2024, 1, 1), max_value=datetime(2024, 12, 31)
                ),
                bytes_used=st.integers(min_value=0, max_value=1024**4),
                path=st.just("/cache"),
            ),
            min_size=0,
            max_size=10,
        )
    )
    def test_rate_always_non_negative(self, samples: list[DiskSample]) -> None:
        """Property: rate is always non-negative."""
        rate = calculate_rate(samples)
        assert rate >= 0.0

    @given(
        remaining=st.integers(min_value=0, max_value=1024**4),
        rate=st.floats(min_value=0.0, max_value=1024.0**3),
    )
    def test_etc_is_none_or_future(self, remaining: int, rate: float) -> None:
        """Property: ETC is either None or in the future."""
        before = datetime.now()
        etc = calculate_etc(remaining=remaining, rate=rate)

        if etc is not None:
            # Allow small tolerance
            assert etc >= before - timedelta(seconds=1)
