"""Unit tests for disk usage tracking module.

Tests cover:
- Exclusion path filtering logic
- Disk usage calculation with mock filesystem
- Baseline capture functionality
- Current usage sampling functionality
- Error handling for inaccessible paths
- Edge cases (empty paths, permission errors, missing files)
- Async integration with asyncio.to_thread
- Caching mechanism for disk usage samples
- Context variable preservation across thread boundaries
"""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mover_status.core.disk_tracker import (
    calculate_disk_usage_sync,
    capture_baseline,
    capture_baseline_async,
    clear_sample_cache,
    is_excluded,
    sample_current_usage,
    sample_current_usage_async,
)
from mover_status.types.models import DiskSample


class TestIsExcluded:
    """Test exclusion path filtering logic."""

    def test_exact_match_is_excluded(self) -> None:
        """Path that exactly matches exclusion should be excluded."""
        path = Path("/mnt/cache/appdata")
        exclusions = [Path("/mnt/cache/appdata")]

        assert is_excluded(path, exclusions) is True

    def test_subdirectory_is_excluded(self) -> None:
        """Path that is subdirectory of exclusion should be excluded."""
        path = Path("/mnt/cache/appdata/qbittorrent/downloads")
        exclusions = [Path("/mnt/cache/appdata")]

        assert is_excluded(path, exclusions) is True

    def test_parent_directory_not_excluded(self) -> None:
        """Path that is parent of exclusion should not be excluded."""
        path = Path("/mnt/cache")
        exclusions = [Path("/mnt/cache/appdata")]

        assert is_excluded(path, exclusions) is False

    def test_sibling_directory_not_excluded(self) -> None:
        """Path that is sibling of exclusion should not be excluded."""
        path = Path("/mnt/cache/downloads")
        exclusions = [Path("/mnt/cache/appdata")]

        assert is_excluded(path, exclusions) is False

    def test_multiple_exclusions(self) -> None:
        """Path matching any exclusion should be excluded."""
        path = Path("/mnt/cache/torrents/complete")
        exclusions = [
            Path("/mnt/cache/appdata"),
            Path("/mnt/cache/torrents"),
            Path("/mnt/cache/system"),
        ]

        assert is_excluded(path, exclusions) is True

    def test_no_exclusions(self) -> None:
        """Path with empty exclusion list should not be excluded."""
        path = Path("/mnt/cache/downloads")
        exclusions: list[Path] = []

        assert is_excluded(path, exclusions) is False

    def test_different_root_not_excluded(self) -> None:
        """Path with completely different root should not be excluded."""
        path = Path("/mnt/array/media")
        exclusions = [Path("/mnt/cache/appdata")]

        assert is_excluded(path, exclusions) is False


class TestCalculateDiskUsageSync:
    """Test disk usage calculation with various filesystem scenarios."""

    def test_empty_paths_returns_zero(self) -> None:
        """Calculating usage for empty path list should return zero."""
        result = calculate_disk_usage_sync(paths=[])

        assert result == 0

    def test_single_file(self, tmp_path: Path) -> None:
        """Calculating usage for single file should return file size."""
        test_file = tmp_path / "test.txt"
        _ = test_file.write_text("Hello, World!")  # 13 bytes

        result = calculate_disk_usage_sync(paths=[test_file])

        assert result == 13

    def test_directory_with_multiple_files(self, tmp_path: Path) -> None:
        """Calculating usage for directory should sum all file sizes."""
        _ = (tmp_path / "file1.txt").write_text("A" * 100)  # 100 bytes
        _ = (tmp_path / "file2.txt").write_text("B" * 200)  # 200 bytes
        _ = (tmp_path / "file3.txt").write_text("C" * 50)  # 50 bytes

        result = calculate_disk_usage_sync(paths=[tmp_path])

        assert result == 350

    def test_nested_directories(self, tmp_path: Path) -> None:
        """Calculating usage should traverse nested directories."""
        subdir1 = tmp_path / "level1"
        subdir2 = subdir1 / "level2"
        subdir2.mkdir(parents=True)

        _ = (tmp_path / "root.txt").write_text("A" * 100)
        _ = (subdir1 / "level1.txt").write_text("B" * 50)
        _ = (subdir2 / "level2.txt").write_text("C" * 25)

        result = calculate_disk_usage_sync(paths=[tmp_path])

        assert result == 175

    def test_exclusion_path_filtering(self, tmp_path: Path) -> None:
        """Files in excluded paths should not be counted."""
        excluded_dir = tmp_path / "excluded"
        excluded_dir.mkdir()
        included_dir = tmp_path / "included"
        included_dir.mkdir()

        _ = (excluded_dir / "file1.txt").write_text("A" * 100)  # Should be excluded
        _ = (included_dir / "file2.txt").write_text("B" * 50)  # Should be included

        result = calculate_disk_usage_sync(
            paths=[tmp_path],
            exclusion_paths=[excluded_dir],
        )

        assert result == 50

    def test_multiple_exclusion_paths(self, tmp_path: Path) -> None:
        """Multiple exclusion paths should all be filtered."""
        excluded1 = tmp_path / "excluded1"
        excluded2 = tmp_path / "excluded2"
        included = tmp_path / "included"

        excluded1.mkdir()
        excluded2.mkdir()
        included.mkdir()

        _ = (excluded1 / "file1.txt").write_text("A" * 100)
        _ = (excluded2 / "file2.txt").write_text("B" * 200)
        _ = (included / "file3.txt").write_text("C" * 50)

        result = calculate_disk_usage_sync(
            paths=[tmp_path],
            exclusion_paths=[excluded1, excluded2],
        )

        assert result == 50

    def test_nonexistent_path_skipped(self, tmp_path: Path) -> None:
        """Nonexistent paths should be skipped without error."""
        nonexistent = tmp_path / "does_not_exist"
        existing = tmp_path / "exists.txt"
        _ = existing.write_text("Hello")

        result = calculate_disk_usage_sync(paths=[nonexistent, existing])

        assert result == 5

    def test_symlinks_not_counted(self, tmp_path: Path) -> None:
        """Symbolic links should not be counted to avoid double-counting."""
        real_file = tmp_path / "real.txt"
        _ = real_file.write_text("A" * 100)

        symlink = tmp_path / "link.txt"
        symlink.symlink_to(real_file)

        result = calculate_disk_usage_sync(paths=[tmp_path])

        assert result == 100

    def test_permission_error_handling(self, tmp_path: Path) -> None:
        """Permission errors should be logged and skipped."""
        accessible = tmp_path / "accessible.txt"
        _ = accessible.write_text("A" * 50)

        with patch.object(Path, "rglob") as mock_rglob:

            def mock_iterator() -> list[Path]:
                return [accessible]

            mock_rglob.return_value = mock_iterator()

            original_stat = Path.stat

            def mock_stat(self: Path) -> object:
                if self == accessible:
                    return original_stat(self)
                raise PermissionError("Access denied")

            with patch.object(Path, "stat", mock_stat):
                result = calculate_disk_usage_sync(paths=[tmp_path])

            assert result == 50

    def test_multiple_paths(self, tmp_path: Path) -> None:
        """Multiple root paths should all be traversed."""
        path1 = tmp_path / "path1"
        path2 = tmp_path / "path2"
        path1.mkdir()
        path2.mkdir()

        _ = (path1 / "file1.txt").write_text("A" * 100)
        _ = (path2 / "file2.txt").write_text("B" * 200)

        result = calculate_disk_usage_sync(paths=[path1, path2])

        assert result == 300

    def test_empty_directory_returns_zero(self, tmp_path: Path) -> None:
        """Empty directory should return zero usage."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = calculate_disk_usage_sync(paths=[empty_dir])

        assert result == 0

    def test_excluded_base_path_returns_zero(self, tmp_path: Path) -> None:
        """If base path itself is excluded, should return zero."""
        base = tmp_path / "base"
        base.mkdir()
        _ = (base / "file.txt").write_text("A" * 100)

        result = calculate_disk_usage_sync(
            paths=[base],
            exclusion_paths=[base],
        )

        assert result == 0


class TestCaptureBaseline:
    """Test baseline disk usage capture."""

    def test_baseline_returns_disk_sample(self, tmp_path: Path) -> None:
        """Baseline capture should return DiskSample with current timestamp."""
        _ = (tmp_path / "file.txt").write_text("A" * 100)

        baseline = capture_baseline(paths=[tmp_path])

        assert isinstance(baseline, DiskSample)
        assert baseline.bytes_used == 100
        assert isinstance(baseline.timestamp, datetime)

    def test_baseline_includes_path_info(self, tmp_path: Path) -> None:
        """Baseline should include consolidated path information."""
        _ = (tmp_path / "file.txt").write_text("A" * 50)

        baseline = capture_baseline(paths=[tmp_path])

        assert str(tmp_path) in baseline.path

    def test_baseline_with_exclusions(self, tmp_path: Path) -> None:
        """Baseline capture should respect exclusion paths."""
        excluded = tmp_path / "excluded"
        excluded.mkdir()
        included = tmp_path / "included"
        included.mkdir()

        _ = (excluded / "file1.txt").write_text("A" * 100)
        _ = (included / "file2.txt").write_text("B" * 50)

        baseline = capture_baseline(
            paths=[tmp_path],
            exclusion_paths=[excluded],
        )

        assert baseline.bytes_used == 50

    def test_baseline_multiple_paths(self, tmp_path: Path) -> None:
        """Baseline should handle multiple paths."""
        path1 = tmp_path / "path1"
        path2 = tmp_path / "path2"
        path1.mkdir()
        path2.mkdir()

        _ = (path1 / "file1.txt").write_text("A" * 100)
        _ = (path2 / "file2.txt").write_text("B" * 200)

        baseline = capture_baseline(paths=[path1, path2])

        assert baseline.bytes_used == 300
        assert str(path1) in baseline.path
        assert str(path2) in baseline.path


class TestSampleCurrentUsage:
    """Test current usage sampling during mover execution."""

    def test_sample_returns_disk_sample(self, tmp_path: Path) -> None:
        """Current usage sample should return DiskSample."""
        _ = (tmp_path / "file.txt").write_text("A" * 100)

        sample = sample_current_usage(paths=[tmp_path])

        assert isinstance(sample, DiskSample)
        assert sample.bytes_used == 100
        assert isinstance(sample.timestamp, datetime)

    def test_sample_with_exclusions(self, tmp_path: Path) -> None:
        """Current usage sampling should respect exclusion paths."""
        excluded = tmp_path / "excluded"
        excluded.mkdir()
        _ = (excluded / "file.txt").write_text("A" * 100)

        sample = sample_current_usage(
            paths=[tmp_path],
            exclusion_paths=[excluded],
        )

        assert sample.bytes_used == 0

    def test_sample_tracks_changes(self, tmp_path: Path) -> None:
        """Successive samples should reflect disk usage changes."""
        test_file = tmp_path / "file.txt"

        _ = test_file.write_text("A" * 100)
        sample1 = sample_current_usage(paths=[tmp_path])

        _ = test_file.write_text("B" * 50)
        sample2 = sample_current_usage(paths=[tmp_path])

        assert sample1.bytes_used == 100
        assert sample2.bytes_used == 50
        assert sample2.timestamp > sample1.timestamp

    def test_sample_multiple_paths(self, tmp_path: Path) -> None:
        """Current usage sample should handle multiple paths."""
        path1 = tmp_path / "path1"
        path2 = tmp_path / "path2"
        path1.mkdir()
        path2.mkdir()

        _ = (path1 / "file1.txt").write_text("A" * 75)
        _ = (path2 / "file2.txt").write_text("B" * 125)

        sample = sample_current_usage(paths=[path1, path2])

        assert sample.bytes_used == 200


class TestIntegrationScenarios:
    """Integration tests simulating real-world usage scenarios."""

    def test_baseline_and_progress_tracking(self, tmp_path: Path) -> None:
        """Simulate capturing baseline and tracking progress over time."""
        _ = (tmp_path / "file1.txt").write_text("A" * 1000)
        _ = (tmp_path / "file2.txt").write_text("B" * 500)

        baseline = capture_baseline(paths=[tmp_path])
        assert baseline.bytes_used == 1500

        _ = (tmp_path / "file1.txt").write_text("A" * 600)
        sample1 = sample_current_usage(paths=[tmp_path])
        assert sample1.bytes_used == 1100

        _ = (tmp_path / "file1.txt").write_text("A" * 200)
        _ = (tmp_path / "file2.txt").write_text("B" * 100)
        sample2 = sample_current_usage(paths=[tmp_path])
        assert sample2.bytes_used == 300

        assert baseline.bytes_used > sample1.bytes_used > sample2.bytes_used

    def test_exclusion_consistency(self, tmp_path: Path) -> None:
        """Exclusions should be consistent across baseline and samples."""
        excluded = tmp_path / "excluded"
        included = tmp_path / "included"
        excluded.mkdir()
        included.mkdir()

        _ = (excluded / "excluded.txt").write_text("E" * 1000)
        _ = (included / "included.txt").write_text("I" * 500)

        exclusions = [excluded]

        baseline = capture_baseline(paths=[tmp_path], exclusion_paths=exclusions)
        assert baseline.bytes_used == 500

        _ = (excluded / "excluded.txt").write_text("E" * 2000)

        sample = sample_current_usage(paths=[tmp_path], exclusion_paths=exclusions)
        assert sample.bytes_used == 500


class TestAsyncIntegration:
    """Test async integration using asyncio.to_thread."""

    @pytest.mark.asyncio
    async def test_capture_baseline_async_returns_disk_sample(self, tmp_path: Path) -> None:
        """Async baseline capture should return DiskSample."""
        _ = (tmp_path / "file.txt").write_text("A" * 100)

        baseline = await capture_baseline_async(paths=[tmp_path])

        assert isinstance(baseline, DiskSample)
        assert baseline.bytes_used == 100
        assert isinstance(baseline.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_capture_baseline_async_with_exclusions(self, tmp_path: Path) -> None:
        """Async baseline capture should respect exclusion paths."""
        excluded = tmp_path / "excluded"
        excluded.mkdir()
        included = tmp_path / "included"
        included.mkdir()

        _ = (excluded / "file1.txt").write_text("A" * 100)
        _ = (included / "file2.txt").write_text("B" * 50)

        baseline = await capture_baseline_async(
            paths=[tmp_path],
            exclusion_paths=[excluded],
        )

        assert baseline.bytes_used == 50

    @pytest.mark.asyncio
    async def test_sample_current_usage_async_returns_disk_sample(self, tmp_path: Path) -> None:
        """Async current usage sample should return DiskSample."""
        _ = (tmp_path / "file.txt").write_text("A" * 100)

        sample = await sample_current_usage_async(paths=[tmp_path])

        assert isinstance(sample, DiskSample)
        assert sample.bytes_used == 100
        assert isinstance(sample.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_sample_current_usage_async_with_exclusions(self, tmp_path: Path) -> None:
        """Async current usage sampling should respect exclusion paths."""
        excluded = tmp_path / "excluded"
        excluded.mkdir()
        _ = (excluded / "file.txt").write_text("A" * 100)

        sample = await sample_current_usage_async(
            paths=[tmp_path],
            exclusion_paths=[excluded],
        )

        assert sample.bytes_used == 0

    @pytest.mark.asyncio
    async def test_async_functions_run_concurrently(self, tmp_path: Path) -> None:
        """Multiple async calls should run concurrently without blocking."""
        path1 = tmp_path / "path1"
        path2 = tmp_path / "path2"
        path1.mkdir()
        path2.mkdir()

        _ = (path1 / "file1.txt").write_text("A" * 100)
        _ = (path2 / "file2.txt").write_text("B" * 200)

        # Run both samples concurrently
        results = await asyncio.gather(
            sample_current_usage_async(paths=[path1]),
            sample_current_usage_async(paths=[path2]),
        )

        assert len(results) == 2
        assert results[0].bytes_used == 100
        assert results[1].bytes_used == 200


class TestCachingMechanism:
    """Test caching mechanism for disk usage samples."""

    @pytest.mark.asyncio
    async def test_cache_returns_same_sample_within_duration(self, tmp_path: Path) -> None:
        """Cached sample should be returned within cache duration."""
        clear_sample_cache()  # Start with clean cache

        _ = (tmp_path / "file.txt").write_text("A" * 100)

        # First call should perform calculation
        sample1 = await sample_current_usage_async(
            paths=[tmp_path],
            cache_duration_seconds=60,
        )

        # Modify file
        _ = (tmp_path / "file.txt").write_text("B" * 200)

        # Second call within cache duration should return cached result
        sample2 = await sample_current_usage_async(
            paths=[tmp_path],
            cache_duration_seconds=60,
        )

        # Should return cached value (100), not new value (200)
        assert sample1.bytes_used == 100
        assert sample2.bytes_used == 100
        assert sample1.timestamp == sample2.timestamp

    @pytest.mark.asyncio
    async def test_cache_expires_after_duration(self, tmp_path: Path) -> None:
        """Cache should expire and recalculate after duration."""
        clear_sample_cache()  # Start with clean cache

        _ = (tmp_path / "file.txt").write_text("A" * 100)

        # First call with very short cache duration
        sample1 = await sample_current_usage_async(
            paths=[tmp_path],
            cache_duration_seconds=0,  # Immediate expiry
        )

        # Modify file
        _ = (tmp_path / "file.txt").write_text("B" * 200)

        # Wait a tiny bit to ensure cache expires
        await asyncio.sleep(0.01)

        # Second call should recalculate
        sample2 = await sample_current_usage_async(
            paths=[tmp_path],
            cache_duration_seconds=0,
        )

        # Should return new value (200), not cached value (100)
        assert sample1.bytes_used == 100
        assert sample2.bytes_used == 200
        assert sample2.timestamp > sample1.timestamp

    @pytest.mark.asyncio
    async def test_cache_key_includes_paths(self, tmp_path: Path) -> None:
        """Cache should be keyed by paths - different paths get different cache entries."""
        clear_sample_cache()  # Start with clean cache

        path1 = tmp_path / "path1"
        path2 = tmp_path / "path2"
        path1.mkdir()
        path2.mkdir()

        _ = (path1 / "file1.txt").write_text("A" * 100)
        _ = (path2 / "file2.txt").write_text("B" * 200)

        # Sample different paths
        sample1 = await sample_current_usage_async(
            paths=[path1],
            cache_duration_seconds=60,
        )
        sample2 = await sample_current_usage_async(
            paths=[path2],
            cache_duration_seconds=60,
        )

        # Should return different values (different cache keys)
        assert sample1.bytes_used == 100
        assert sample2.bytes_used == 200

    @pytest.mark.asyncio
    async def test_cache_key_includes_exclusions(self, tmp_path: Path) -> None:
        """Cache should be keyed by exclusion paths - different exclusions get different cache entries."""
        clear_sample_cache()  # Start with clean cache

        excluded = tmp_path / "excluded"
        excluded.mkdir()
        _ = (excluded / "file.txt").write_text("A" * 100)
        _ = (tmp_path / "included.txt").write_text("B" * 50)

        # Sample without exclusions
        sample1 = await sample_current_usage_async(
            paths=[tmp_path],
            cache_duration_seconds=60,
        )

        # Sample with exclusions (different cache key)
        sample2 = await sample_current_usage_async(
            paths=[tmp_path],
            exclusion_paths=[excluded],
            cache_duration_seconds=60,
        )

        # Should return different values (different cache keys)
        assert sample1.bytes_used == 150  # All files
        assert sample2.bytes_used == 50  # Excluded directory not counted

    @pytest.mark.asyncio
    async def test_clear_cache_forces_recalculation(self, tmp_path: Path) -> None:
        """Clearing cache should force fresh calculation."""
        clear_sample_cache()  # Start with clean cache

        _ = (tmp_path / "file.txt").write_text("A" * 100)

        # First call
        sample1 = await sample_current_usage_async(
            paths=[tmp_path],
            cache_duration_seconds=60,
        )

        # Modify file
        _ = (tmp_path / "file.txt").write_text("B" * 200)

        # Clear cache
        clear_sample_cache()

        # Second call should recalculate
        sample2 = await sample_current_usage_async(
            paths=[tmp_path],
            cache_duration_seconds=60,
        )

        # Should return new value (200), not cached value (100)
        assert sample1.bytes_used == 100
        assert sample2.bytes_used == 200

    @pytest.mark.asyncio
    async def test_baseline_async_does_not_use_cache(self, tmp_path: Path) -> None:
        """Baseline capture should not use caching."""
        clear_sample_cache()  # Start with clean cache

        _ = (tmp_path / "file.txt").write_text("A" * 100)

        # First baseline call
        baseline1 = await capture_baseline_async(paths=[tmp_path])

        # Modify file
        _ = (tmp_path / "file.txt").write_text("B" * 200)

        # Second baseline call should always recalculate
        baseline2 = await capture_baseline_async(paths=[tmp_path])

        # Should return different values (no caching for baseline)
        assert baseline1.bytes_used == 100
        assert baseline2.bytes_used == 200
        assert baseline2.timestamp > baseline1.timestamp


class TestPropertyBasedInvariants:
    """Property-based tests for disk usage calculation invariants using Hypothesis."""

    @given(
        st.lists(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs", "Cc"),
                    blacklist_characters="/\\",
                ),
                min_size=1,
            ),
            min_size=0,
            max_size=10,
        )
    )
    def test_is_excluded_with_empty_exclusions_always_false(self, path_parts: list[str]) -> None:
        """Property: is_excluded with empty exclusion list always returns False."""
        if not path_parts:
            path_parts = ["tmp"]

        path = Path(*path_parts)
        exclusions: list[Path] = []

        result = is_excluded(path, exclusions)

        assert result is False

    @given(
        st.lists(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs", "Cc"),
                    blacklist_characters="/\\",
                ),
                min_size=1,
            ),
            min_size=1,
            max_size=10,
        )
    )
    def test_is_excluded_path_equals_self(self, path_parts: list[str]) -> None:
        """Property: A path is always excluded if it's in the exclusion list."""
        path = Path(*path_parts)
        exclusions = [path]

        result = is_excluded(path, exclusions)

        assert result is True

    @given(
        st.lists(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs", "Cc"),
                    blacklist_characters="/\\",
                ),
                min_size=1,
            ),
            min_size=1,
            max_size=5,
        ),
        st.lists(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=("Cs", "Cc"),
                    blacklist_characters="/\\",
                ),
                min_size=1,
            ),
            min_size=1,
            max_size=3,
        ),
    )
    def test_is_excluded_child_of_excluded_parent(self, parent_parts: list[str], child_parts: list[str]) -> None:
        """Property: A child path is excluded if its parent is in exclusion list."""
        parent = Path(*parent_parts)
        # Create child by appending additional parts to parent
        child = parent / Path(*child_parts)
        exclusions = [parent]

        result = is_excluded(child, exclusions)

        assert result is True

    def test_calculate_disk_usage_never_negative(self, tmp_path: Path) -> None:
        """Property: Disk usage is always non-negative."""
        # Create some files
        _ = (tmp_path / "file1.txt").write_text("A" * 100)
        _ = (tmp_path / "file2.txt").write_text("B" * 200)

        result = calculate_disk_usage_sync(paths=[tmp_path])

        assert result >= 0

    def test_calculate_disk_usage_monotonic_with_additions(self, tmp_path: Path) -> None:
        """Property: Disk usage increases or stays same when files are added."""
        # Initial state
        _ = (tmp_path / "file1.txt").write_text("A" * 100)
        usage1 = calculate_disk_usage_sync(paths=[tmp_path])

        # Add more data
        _ = (tmp_path / "file2.txt").write_text("B" * 200)
        usage2 = calculate_disk_usage_sync(paths=[tmp_path])

        # Usage should increase
        assert usage2 >= usage1

    def test_exclusions_reduce_or_maintain_usage(self, tmp_path: Path) -> None:
        """Property: Adding exclusions never increases total disk usage."""
        excluded_dir = tmp_path / "excluded"
        excluded_dir.mkdir()

        _ = (excluded_dir / "file1.txt").write_text("A" * 100)
        _ = (tmp_path / "file2.txt").write_text("B" * 200)

        # Calculate without exclusions
        usage_without = calculate_disk_usage_sync(paths=[tmp_path])

        # Calculate with exclusions
        usage_with = calculate_disk_usage_sync(
            paths=[tmp_path],
            exclusion_paths=[excluded_dir],
        )

        # Exclusions should reduce or maintain usage, never increase
        assert usage_with <= usage_without

    def test_baseline_and_sample_have_consistent_structure(self, tmp_path: Path) -> None:
        """Property: Baseline and sample always return valid DiskSample objects."""
        _ = (tmp_path / "file.txt").write_text("A" * 100)

        baseline = capture_baseline(paths=[tmp_path])
        sample = sample_current_usage(paths=[tmp_path])

        # Both should be DiskSample instances
        assert isinstance(baseline, DiskSample)
        assert isinstance(sample, DiskSample)

        # Both should have valid fields
        assert baseline.bytes_used >= 0
        assert sample.bytes_used >= 0
        assert isinstance(baseline.timestamp, datetime)
        assert isinstance(sample.timestamp, datetime)
        assert isinstance(baseline.path, str)
        assert isinstance(sample.path, str)

    @pytest.mark.asyncio
    async def test_async_and_sync_return_equivalent_results(self, tmp_path: Path) -> None:
        """Property: Async and sync versions return equivalent disk usage values."""
        _ = (tmp_path / "file1.txt").write_text("A" * 100)
        _ = (tmp_path / "file2.txt").write_text("B" * 200)

        # Capture using sync version
        sync_baseline = capture_baseline(paths=[tmp_path])

        # Capture using async version
        async_baseline = await capture_baseline_async(paths=[tmp_path])

        # Both should report same bytes_used (within small margin for timing)
        assert sync_baseline.bytes_used == async_baseline.bytes_used

    @pytest.mark.asyncio
    async def test_cache_preserves_sample_value(self, tmp_path: Path) -> None:
        """Property: Cached samples preserve the original bytes_used value."""
        clear_sample_cache()  # Start fresh

        _ = (tmp_path / "file.txt").write_text("A" * 100)

        # First call (uncached)
        sample1 = await sample_current_usage_async(
            paths=[tmp_path],
            cache_duration_seconds=60,
        )

        # Second call (cached) - should return same value
        sample2 = await sample_current_usage_async(
            paths=[tmp_path],
            cache_duration_seconds=60,
        )

        # Cache should preserve the exact value
        assert sample1.bytes_used == sample2.bytes_used
        assert sample1.timestamp == sample2.timestamp
