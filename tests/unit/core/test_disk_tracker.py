"""Unit tests for disk usage tracking module.

Tests cover:
- Exclusion path filtering logic
- Disk usage calculation with mock filesystem
- Baseline capture functionality
- Current usage sampling functionality
- Error handling for inaccessible paths
- Edge cases (empty paths, permission errors, missing files)
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from mover_status.core import disk_tracker
from mover_status.core.disk_tracker import (
    calculate_disk_usage_sync,
    capture_baseline,
    sample_current_usage,
)
from mover_status.types.models import DiskSample


class TestIsExcluded:
    """Test exclusion path filtering logic."""

    def test_exact_match_is_excluded(self) -> None:
        """Path that exactly matches exclusion should be excluded."""
        path = Path("/mnt/cache/appdata")
        exclusions = [Path("/mnt/cache/appdata")]

        assert disk_tracker._is_excluded(path, exclusions) is True

    def test_subdirectory_is_excluded(self) -> None:
        """Path that is subdirectory of exclusion should be excluded."""
        path = Path("/mnt/cache/appdata/qbittorrent/downloads")
        exclusions = [Path("/mnt/cache/appdata")]

        assert disk_tracker._is_excluded(path, exclusions) is True

    def test_parent_directory_not_excluded(self) -> None:
        """Path that is parent of exclusion should not be excluded."""
        path = Path("/mnt/cache")
        exclusions = [Path("/mnt/cache/appdata")]

        assert disk_tracker._is_excluded(path, exclusions) is False

    def test_sibling_directory_not_excluded(self) -> None:
        """Path that is sibling of exclusion should not be excluded."""
        path = Path("/mnt/cache/downloads")
        exclusions = [Path("/mnt/cache/appdata")]

        assert disk_tracker._is_excluded(path, exclusions) is False

    def test_multiple_exclusions(self) -> None:
        """Path matching any exclusion should be excluded."""
        path = Path("/mnt/cache/torrents/complete")
        exclusions = [
            Path("/mnt/cache/appdata"),
            Path("/mnt/cache/torrents"),
            Path("/mnt/cache/system"),
        ]

        assert disk_tracker._is_excluded(path, exclusions) is True

    def test_no_exclusions(self) -> None:
        """Path with empty exclusion list should not be excluded."""
        path = Path("/mnt/cache/downloads")
        exclusions: list[Path] = []

        assert disk_tracker._is_excluded(path, exclusions) is False

    def test_different_root_not_excluded(self) -> None:
        """Path with completely different root should not be excluded."""
        path = Path("/mnt/array/media")
        exclusions = [Path("/mnt/cache/appdata")]

        assert disk_tracker._is_excluded(path, exclusions) is False


class TestCalculateDiskUsageSync:
    """Test disk usage calculation with various filesystem scenarios."""

    def test_empty_paths_returns_zero(self) -> None:
        """Calculating usage for empty path list should return zero."""
        result = calculate_disk_usage_sync(paths=[])

        assert result == 0

    def test_single_file(self, tmp_path: Path) -> None:
        """Calculating usage for single file should return file size."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")  # 13 bytes

        result = calculate_disk_usage_sync(paths=[test_file])

        assert result == 13

    def test_directory_with_multiple_files(self, tmp_path: Path) -> None:
        """Calculating usage for directory should sum all file sizes."""
        (tmp_path / "file1.txt").write_text("A" * 100)  # 100 bytes
        (tmp_path / "file2.txt").write_text("B" * 200)  # 200 bytes
        (tmp_path / "file3.txt").write_text("C" * 50)   # 50 bytes

        result = calculate_disk_usage_sync(paths=[tmp_path])

        assert result == 350

    def test_nested_directories(self, tmp_path: Path) -> None:
        """Calculating usage should traverse nested directories."""
        subdir1 = tmp_path / "level1"
        subdir2 = subdir1 / "level2"
        subdir2.mkdir(parents=True)

        (tmp_path / "root.txt").write_text("A" * 100)
        (subdir1 / "level1.txt").write_text("B" * 50)
        (subdir2 / "level2.txt").write_text("C" * 25)

        result = calculate_disk_usage_sync(paths=[tmp_path])

        assert result == 175

    def test_exclusion_path_filtering(self, tmp_path: Path) -> None:
        """Files in excluded paths should not be counted."""
        excluded_dir = tmp_path / "excluded"
        excluded_dir.mkdir()
        included_dir = tmp_path / "included"
        included_dir.mkdir()

        (excluded_dir / "file1.txt").write_text("A" * 100)  # Should be excluded
        (included_dir / "file2.txt").write_text("B" * 50)   # Should be included

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

        (excluded1 / "file1.txt").write_text("A" * 100)
        (excluded2 / "file2.txt").write_text("B" * 200)
        (included / "file3.txt").write_text("C" * 50)

        result = calculate_disk_usage_sync(
            paths=[tmp_path],
            exclusion_paths=[excluded1, excluded2],
        )

        assert result == 50

    def test_nonexistent_path_skipped(self, tmp_path: Path) -> None:
        """Nonexistent paths should be skipped without error."""
        nonexistent = tmp_path / "does_not_exist"
        existing = tmp_path / "exists.txt"
        existing.write_text("Hello")

        result = calculate_disk_usage_sync(paths=[nonexistent, existing])

        assert result == 5

    def test_symlinks_not_counted(self, tmp_path: Path) -> None:
        """Symbolic links should not be counted to avoid double-counting."""
        real_file = tmp_path / "real.txt"
        real_file.write_text("A" * 100)

        symlink = tmp_path / "link.txt"
        symlink.symlink_to(real_file)

        result = calculate_disk_usage_sync(paths=[tmp_path])

        assert result == 100

    def test_permission_error_handling(self, tmp_path: Path) -> None:
        """Permission errors should be logged and skipped."""
        accessible = tmp_path / "accessible.txt"
        accessible.write_text("A" * 50)

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

        (path1 / "file1.txt").write_text("A" * 100)
        (path2 / "file2.txt").write_text("B" * 200)

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
        (base / "file.txt").write_text("A" * 100)

        result = calculate_disk_usage_sync(
            paths=[base],
            exclusion_paths=[base],
        )

        assert result == 0


class TestCaptureBaseline:
    """Test baseline disk usage capture."""

    def test_baseline_returns_disk_sample(self, tmp_path: Path) -> None:
        """Baseline capture should return DiskSample with current timestamp."""
        (tmp_path / "file.txt").write_text("A" * 100)

        baseline = capture_baseline(paths=[tmp_path])

        assert isinstance(baseline, DiskSample)
        assert baseline.bytes_used == 100
        assert isinstance(baseline.timestamp, datetime)

    def test_baseline_includes_path_info(self, tmp_path: Path) -> None:
        """Baseline should include consolidated path information."""
        (tmp_path / "file.txt").write_text("A" * 50)

        baseline = capture_baseline(paths=[tmp_path])

        assert str(tmp_path) in baseline.path

    def test_baseline_with_exclusions(self, tmp_path: Path) -> None:
        """Baseline capture should respect exclusion paths."""
        excluded = tmp_path / "excluded"
        excluded.mkdir()
        included = tmp_path / "included"
        included.mkdir()

        (excluded / "file1.txt").write_text("A" * 100)
        (included / "file2.txt").write_text("B" * 50)

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

        (path1 / "file1.txt").write_text("A" * 100)
        (path2 / "file2.txt").write_text("B" * 200)

        baseline = capture_baseline(paths=[path1, path2])

        assert baseline.bytes_used == 300
        assert str(path1) in baseline.path
        assert str(path2) in baseline.path


class TestSampleCurrentUsage:
    """Test current usage sampling during mover execution."""

    def test_sample_returns_disk_sample(self, tmp_path: Path) -> None:
        """Current usage sample should return DiskSample."""
        (tmp_path / "file.txt").write_text("A" * 100)

        sample = sample_current_usage(paths=[tmp_path])

        assert isinstance(sample, DiskSample)
        assert sample.bytes_used == 100
        assert isinstance(sample.timestamp, datetime)

    def test_sample_with_exclusions(self, tmp_path: Path) -> None:
        """Current usage sampling should respect exclusion paths."""
        excluded = tmp_path / "excluded"
        excluded.mkdir()
        (excluded / "file.txt").write_text("A" * 100)

        sample = sample_current_usage(
            paths=[tmp_path],
            exclusion_paths=[excluded],
        )

        assert sample.bytes_used == 0

    def test_sample_tracks_changes(self, tmp_path: Path) -> None:
        """Successive samples should reflect disk usage changes."""
        test_file = tmp_path / "file.txt"

        test_file.write_text("A" * 100)
        sample1 = sample_current_usage(paths=[tmp_path])

        test_file.write_text("B" * 50)
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

        (path1 / "file1.txt").write_text("A" * 75)
        (path2 / "file2.txt").write_text("B" * 125)

        sample = sample_current_usage(paths=[path1, path2])

        assert sample.bytes_used == 200


class TestIntegrationScenarios:
    """Integration tests simulating real-world usage scenarios."""

    def test_baseline_and_progress_tracking(self, tmp_path: Path) -> None:
        """Simulate capturing baseline and tracking progress over time."""
        (tmp_path / "file1.txt").write_text("A" * 1000)
        (tmp_path / "file2.txt").write_text("B" * 500)

        baseline = capture_baseline(paths=[tmp_path])
        assert baseline.bytes_used == 1500

        (tmp_path / "file1.txt").write_text("A" * 600)
        sample1 = sample_current_usage(paths=[tmp_path])
        assert sample1.bytes_used == 1100

        (tmp_path / "file1.txt").write_text("A" * 200)
        (tmp_path / "file2.txt").write_text("B" * 100)
        sample2 = sample_current_usage(paths=[tmp_path])
        assert sample2.bytes_used == 300

        assert baseline.bytes_used > sample1.bytes_used > sample2.bytes_used

    def test_exclusion_consistency(self, tmp_path: Path) -> None:
        """Exclusions should be consistent across baseline and samples."""
        excluded = tmp_path / "excluded"
        included = tmp_path / "included"
        excluded.mkdir()
        included.mkdir()

        (excluded / "excluded.txt").write_text("E" * 1000)
        (included / "included.txt").write_text("I" * 500)

        exclusions = [excluded]

        baseline = capture_baseline(paths=[tmp_path], exclusion_paths=exclusions)
        assert baseline.bytes_used == 500

        (excluded / "excluded.txt").write_text("E" * 2000)

        sample = sample_current_usage(paths=[tmp_path], exclusion_paths=exclusions)
        assert sample.bytes_used == 500
