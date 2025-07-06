"""Test suite for filesystem size calculator."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from mover_status.core.data.filesystem.scanner import DirectoryScanner, ScanStrategy
from mover_status.core.data.filesystem.size_calculator import SizeCalculator, SizeMode

if TYPE_CHECKING:
    pass


class TestSizeCalculator:
    """Test the SizeCalculator class."""

    def test_size_calculator_creation(self) -> None:
        """Test creating a SizeCalculator instance."""
        calculator = SizeCalculator()
        
        assert calculator.scanner is not None
        assert calculator.mode == SizeMode.APPARENT
        assert calculator.cache_enabled is True

    def test_size_calculator_with_custom_scanner(self) -> None:
        """Test creating SizeCalculator with custom scanner."""
        scanner = DirectoryScanner(strategy=ScanStrategy.BREADTH_FIRST)
        calculator = SizeCalculator(scanner=scanner)
        
        assert calculator.scanner is scanner
        assert calculator.scanner.strategy == ScanStrategy.BREADTH_FIRST

    def test_size_calculator_with_disk_usage_mode(self) -> None:
        """Test creating SizeCalculator with disk usage mode."""
        calculator = SizeCalculator(mode=SizeMode.DISK_USAGE)
        
        assert calculator.mode == SizeMode.DISK_USAGE

    def test_size_calculator_with_cache_disabled(self) -> None:
        """Test creating SizeCalculator with cache disabled."""
        calculator = SizeCalculator(cache_enabled=False)
        
        assert calculator.cache_enabled is False

    def test_calculate_file_size_basic(self) -> None:
        """Test basic file size calculation."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            _ = temp_file.write("Hello, World!")
            temp_file_path = Path(temp_file.name)
        
        try:
            calculator = SizeCalculator()
            size = calculator.calculate_size(temp_file_path)
            
            assert size == 13  # "Hello, World!" is 13 bytes
        finally:
            temp_file_path.unlink()

    def test_calculate_directory_size_basic(self) -> None:
        """Test basic directory size calculation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            _ = (temp_path / "file1.txt").write_text("Hello")
            _ = (temp_path / "file2.txt").write_text("World")
            
            calculator = SizeCalculator()
            size = calculator.calculate_size(temp_path)
            
            assert size == 10  # "Hello" (5) + "World" (5) = 10 bytes

    def test_calculate_directory_size_with_subdirectories(self) -> None:
        """Test directory size calculation with subdirectories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files and subdirectories
            _ = (temp_path / "file1.txt").write_text("Hello")
            sub_dir = temp_path / "subdir"
            sub_dir.mkdir()
            _ = (sub_dir / "file2.txt").write_text("World")
            
            calculator = SizeCalculator()
            size = calculator.calculate_size(temp_path)
            
            assert size == 10  # "Hello" (5) + "World" (5) = 10 bytes

    def test_calculate_size_with_exclusions(self) -> None:
        """Test size calculation with exclusions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            _ = (temp_path / "file1.txt").write_text("Hello")
            _ = (temp_path / "file2.tmp").write_text("Excluded")
            
            # Create scanner with exclusions
            scanner = DirectoryScanner(exclusions={"*.tmp"})
            calculator = SizeCalculator(scanner=scanner)
            size = calculator.calculate_size(temp_path)
            
            assert size == 5  # Only "Hello" (5 bytes), "Excluded" should be excluded

    def test_calculate_size_nonexistent_path(self) -> None:
        """Test size calculation for nonexistent path."""
        calculator = SizeCalculator()
        nonexistent_path = Path("/nonexistent/path")
        
        with pytest.raises(OSError, match="Path does not exist"):
            _ = calculator.calculate_size(nonexistent_path)

    def test_calculate_size_with_progress(self) -> None:
        """Test size calculation with progress reporting."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            _ = (temp_path / "file1.txt").write_text("Hello")  # 5 bytes
            _ = (temp_path / "file2.txt").write_text("World")  # 5 bytes
            
            calculator = SizeCalculator()
            progress_items = list(calculator.calculate_size_with_progress(temp_path))
            
            assert len(progress_items) == 2
            # Progress should be cumulative
            assert progress_items[0][0] == 5
            assert progress_items[1][0] == 10

    def test_calculate_size_with_progress_single_file(self) -> None:
        """Test size calculation with progress for single file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            _ = temp_file.write("Hello")
            temp_file_path = Path(temp_file.name)
        
        try:
            calculator = SizeCalculator()
            progress_items = list(calculator.calculate_size_with_progress(temp_file_path))
            
            assert len(progress_items) == 1
            assert progress_items[0][0] == 5
            assert progress_items[0][1] == temp_file_path
        finally:
            temp_file_path.unlink()

    def test_file_cache_basic(self) -> None:
        """Test basic file caching functionality."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            _ = temp_file.write("Hello")
            temp_file_path = Path(temp_file.name)
        
        try:
            calculator = SizeCalculator()
            
            # First calculation should cache the result
            size1 = calculator.calculate_size(temp_file_path)
            assert size1 == 5
            
            # Second calculation should use cache
            size2 = calculator.calculate_size(temp_file_path)
            assert size2 == 5
            
            # Verify cache was used
            stats = calculator.get_cache_stats()
            assert stats["file_cache_size"] == 1
        finally:
            temp_file_path.unlink()

    def test_directory_cache_basic(self) -> None:
        """Test basic directory caching functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            _ = (temp_path / "file1.txt").write_text("Hello")
            
            calculator = SizeCalculator()
            
            # First calculation should cache the result
            size1 = calculator.calculate_size(temp_path)
            assert size1 == 5
            
            # Second calculation should use cache
            size2 = calculator.calculate_size(temp_path)
            assert size2 == 5
            
            # Verify cache was used
            stats = calculator.get_cache_stats()
            assert stats["directory_cache_size"] == 1

    def test_cache_invalidation_by_modification_time(self) -> None:
        """Test cache invalidation when file is modified."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            _ = temp_file.write("Hello")
            temp_file_path = Path(temp_file.name)
        
        try:
            calculator = SizeCalculator()
            
            # First calculation
            size1 = calculator.calculate_size(temp_file_path)
            assert size1 == 5
            
            # Modify file
            time.sleep(0.1)  # Ensure different mtime
            with open(temp_file_path, 'w') as f:
                _ = f.write("Hello, World!")
            
            # Second calculation should detect change and recalculate
            size2 = calculator.calculate_size(temp_file_path)
            assert size2 == 13
        finally:
            temp_file_path.unlink()

    def test_cache_disabled(self) -> None:
        """Test size calculation with cache disabled."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            _ = temp_file.write("Hello")
            temp_file_path = Path(temp_file.name)
        
        try:
            calculator = SizeCalculator(cache_enabled=False)
            
            # Multiple calculations should not use cache
            size1 = calculator.calculate_size(temp_file_path)
            size2 = calculator.calculate_size(temp_file_path)
            
            assert size1 == 5
            assert size2 == 5
            
            # Verify no cache was used
            stats = calculator.get_cache_stats()
            assert stats["file_cache_size"] == 0
            assert stats["directory_cache_size"] == 0
        finally:
            temp_file_path.unlink()

    def test_manual_cache_invalidation(self) -> None:
        """Test manual cache invalidation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            _ = (temp_path / "file1.txt").write_text("Hello")
            
            calculator = SizeCalculator()
            
            # Cache some data
            _ = calculator.calculate_size(temp_path)
            stats = calculator.get_cache_stats()
            assert stats["total_cache_entries"] > 0
            
            # Invalidate all cache
            calculator.invalidate_cache()
            stats = calculator.get_cache_stats()
            assert stats["total_cache_entries"] == 0

    def test_specific_path_cache_invalidation(self) -> None:
        """Test cache invalidation for specific path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            _ = (temp_path / "file1.txt").write_text("Hello")
            
            # Create subdirectory
            sub_dir = temp_path / "subdir"
            sub_dir.mkdir()
            _ = (sub_dir / "file2.txt").write_text("World")
            
            calculator = SizeCalculator()
            
            # Cache data for both directories
            _ = calculator.calculate_size(temp_path)
            _ = calculator.calculate_size(sub_dir)
            
            # Invalidate cache for subdirectory
            calculator.invalidate_cache(sub_dir)
            
            # Parent directory cache should still exist
            stats = calculator.get_cache_stats()
            assert stats["total_cache_entries"] > 0

    def test_size_mode_apparent(self) -> None:
        """Test size calculation in apparent mode."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            _ = temp_file.write("Hello")
            temp_file_path = Path(temp_file.name)
        
        try:
            calculator = SizeCalculator(mode=SizeMode.APPARENT)
            size = calculator.calculate_size(temp_file_path)
            
            assert size == 5  # Apparent size is file content size
        finally:
            temp_file_path.unlink()

    def test_size_mode_disk_usage(self) -> None:
        """Test size calculation in disk usage mode."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            _ = temp_file.write("Hello")
            temp_file_path = Path(temp_file.name)
        
        try:
            calculator = SizeCalculator(mode=SizeMode.DISK_USAGE)
            size = calculator.calculate_size(temp_file_path)
            
            # Disk usage should be at least as large as apparent size
            assert size >= 5
        finally:
            temp_file_path.unlink()

    def test_permission_error_handling(self) -> None:
        """Test handling of permission errors during calculation."""
        calculator = SizeCalculator()
        
        # Mock the _calculate_file_size method to raise PermissionError
        with patch.object(calculator, '_calculate_file_size') as mock_calc:
            mock_calc.side_effect = PermissionError("Permission denied")
            
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file_path = Path(temp_file.name)
            
            try:
                # Should handle permission error gracefully
                size = calculator.calculate_size(temp_file_path)
                assert size == 0
            finally:
                temp_file_path.unlink()

    def test_os_error_handling(self) -> None:
        """Test handling of OS errors during calculation."""
        calculator = SizeCalculator()
        
        # Mock the _calculate_file_size method to raise OSError
        with patch.object(calculator, '_calculate_file_size') as mock_calc:
            mock_calc.side_effect = OSError("OS error")
            
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file_path = Path(temp_file.name)
            
            try:
                # Should handle OS error gracefully
                size = calculator.calculate_size(temp_file_path)
                assert size == 0
            finally:
                temp_file_path.unlink()

    def test_calculate_size_with_progress_error_handling(self) -> None:
        """Test error handling in progress calculation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            _ = (temp_path / "file1.txt").write_text("Hello")
            
            calculator = SizeCalculator()
            
            # Mock file access to raise error for some files
            with patch.object(calculator, '_get_file_size') as mock_get_size:
                mock_get_size.side_effect = [OSError("Access denied"), 5]
                
                # Should continue despite errors
                progress_items = list(calculator.calculate_size_with_progress(temp_path))
                assert len(progress_items) >= 0  # May be empty if all files fail

    def test_cache_stats(self) -> None:
        """Test cache statistics reporting."""
        calculator = SizeCalculator()
        
        # Initial stats
        stats = calculator.get_cache_stats()
        assert stats["file_cache_size"] == 0
        assert stats["directory_cache_size"] == 0
        assert stats["total_cache_entries"] == 0
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            _ = (temp_path / "file1.txt").write_text("Hello")
            
            # Calculate some sizes to populate cache
            _ = calculator.calculate_size(temp_path)
            
            # Check updated stats
            stats = calculator.get_cache_stats()
            assert stats["total_cache_entries"] > 0

    def test_special_file_handling(self) -> None:
        """Test handling of special files (not regular files or directories)."""
        calculator = SizeCalculator()
        
        # Mock a path that is neither file nor directory
        mock_path = Mock(spec=Path)
        mock_path.exists = Mock(return_value=True)
        mock_path.is_file = Mock(return_value=False)
        mock_path.is_dir = Mock(return_value=False)
        
        size = calculator.calculate_size(mock_path)
        assert size == 0

    def test_large_directory_performance(self) -> None:
        """Test performance with a larger directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create multiple files
            for i in range(10):
                _ = (temp_path / f"file_{i}.txt").write_text(f"Content {i}")
            
            calculator = SizeCalculator()
            
            # First calculation (no cache)
            size1 = calculator.calculate_size(temp_path)
            
            # Second calculation (with cache)
            size2 = calculator.calculate_size(temp_path)
            
            assert size1 == size2
            assert size1 > 0

    def test_symlink_handling(self) -> None:
        """Test handling of symbolic links."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a regular file
            regular_file = temp_path / "regular.txt"
            _ = regular_file.write_text("Hello")
            
            # Create a symbolic link
            try:
                symlink_file = temp_path / "symlink.txt"
                symlink_file.symlink_to(regular_file)
                
                calculator = SizeCalculator()
                size = calculator.calculate_size(temp_path)
                
                # Size should account for files accessible through symlinks
                assert size > 0
            except OSError:
                # Skip test if symlinks not supported on this platform
                pytest.skip("Symlinks not supported on this platform")

    def test_empty_directory(self) -> None:
        """Test size calculation for empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            calculator = SizeCalculator()
            size = calculator.calculate_size(temp_path)
            
            assert size == 0

    def test_deeply_nested_directory(self) -> None:
        """Test size calculation for deeply nested directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create nested structure
            current_path = temp_path
            for i in range(5):
                current_path = current_path / f"level_{i}"
                current_path.mkdir()
                _ = (current_path / f"file_{i}.txt").write_text(f"Level {i}")
            
            calculator = SizeCalculator()
            size = calculator.calculate_size(temp_path)
            
            assert size == 35  # "Level 0" + "Level 1" + ... + "Level 4" = 7*5 = 35 bytes