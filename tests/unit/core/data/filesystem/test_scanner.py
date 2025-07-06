"""Test suite for filesystem scanner."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from mover_status.core.data.filesystem.scanner import DirectoryScanner, ScanStrategy

if TYPE_CHECKING:
    pass


class TestDirectoryScanner:
    """Test the DirectoryScanner class."""

    def test_directory_scanner_creation(self) -> None:
        """Test creating a DirectoryScanner instance."""
        scanner = DirectoryScanner()
        
        assert scanner.exclusions == {".snapshots", ".Recycle.Bin", "@eaDir"}
        assert scanner.max_depth is None
        assert scanner.strategy == ScanStrategy.DEPTH_FIRST

    def test_directory_scanner_with_custom_exclusions(self) -> None:
        """Test creating DirectoryScanner with custom exclusions."""
        exclusions = {"*.tmp", "cache", ".git"}
        scanner = DirectoryScanner(exclusions=exclusions)
        
        assert scanner.exclusions == exclusions

    def test_directory_scanner_with_max_depth(self) -> None:
        """Test creating DirectoryScanner with max depth."""
        scanner = DirectoryScanner(max_depth=3)
        
        assert scanner.max_depth == 3

    def test_directory_scanner_with_strategy(self) -> None:
        """Test creating DirectoryScanner with different strategy."""
        scanner = DirectoryScanner(strategy=ScanStrategy.BREADTH_FIRST)
        
        assert scanner.strategy == ScanStrategy.BREADTH_FIRST

    def test_scan_directory_basic(self) -> None:
        """Test basic directory scanning."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            _ = (temp_path / "file1.txt").write_text("test")
            _ = (temp_path / "file2.py").write_text("test")
            
            scanner = DirectoryScanner()
            files = list(scanner.scan_directory(temp_path))
            
            assert len(files) == 2
            assert all(f.is_file() for f in files)
            assert {f.name for f in files} == {"file1.txt", "file2.py"}

    def test_scan_directory_recursive(self) -> None:
        """Test recursive directory scanning."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create nested structure
            _ = (temp_path / "file1.txt").write_text("test")
            (temp_path / "subdir").mkdir()
            _ = (temp_path / "subdir" / "file2.txt").write_text("test")
            (temp_path / "subdir" / "nested").mkdir()
            _ = (temp_path / "subdir" / "nested" / "file3.txt").write_text("test")
            
            scanner = DirectoryScanner()
            files = list(scanner.scan_directory(temp_path))
            
            assert len(files) == 3
            assert all(f.is_file() for f in files)
            assert {f.name for f in files} == {"file1.txt", "file2.txt", "file3.txt"}

    def test_scan_directory_with_exclusions(self) -> None:
        """Test directory scanning with exclusions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files and directories
            _ = (temp_path / "file1.txt").write_text("test")
            _ = (temp_path / "file2.py").write_text("test")
            (temp_path / ".snapshots").mkdir()
            _ = (temp_path / ".snapshots" / "backup.txt").write_text("test")
            (temp_path / "cache").mkdir()
            _ = (temp_path / "cache" / "temp.txt").write_text("test")
            
            scanner = DirectoryScanner(exclusions={"*.txt", ".snapshots"})
            files = list(scanner.scan_directory(temp_path))
            
            # Only .py file should be found
            assert len(files) == 1
            assert files[0].name == "file2.py"

    def test_scan_directory_with_max_depth(self) -> None:
        """Test directory scanning with depth limit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create nested structure
            _ = (temp_path / "file1.txt").write_text("test")
            (temp_path / "level1").mkdir()
            _ = (temp_path / "level1" / "file2.txt").write_text("test")
            (temp_path / "level1" / "level2").mkdir()
            _ = (temp_path / "level1" / "level2" / "file3.txt").write_text("test")
            
            scanner = DirectoryScanner(max_depth=1)
            files = list(scanner.scan_directory(temp_path))
            
            # Should find files at depth 0 and 1, but not 2
            assert len(files) == 2
            assert {f.name for f in files} == {"file1.txt", "file2.txt"}

    def test_scan_directory_permission_error(self) -> None:
        """Test directory scanning with permission errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test file
            _ = (temp_path / "file1.txt").write_text("test")
            
            scanner = DirectoryScanner()
            
            # Mock iterdir to raise PermissionError
            with patch.object(Path, 'iterdir', side_effect=PermissionError("Access denied")):
                files = list(scanner.scan_directory(temp_path))
                
                # Should handle permission error gracefully
                assert files == []

    def test_scan_directory_empty_directory(self) -> None:
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            scanner = DirectoryScanner()
            files = list(scanner.scan_directory(temp_path))
            
            assert files == []

    def test_scan_directory_nonexistent_path(self) -> None:
        """Test scanning a non-existent directory."""
        scanner = DirectoryScanner()
        non_existent_path = Path("/non/existent/path")
        
        files = list(scanner.scan_directory(non_existent_path))
        
        assert files == []

    def test_exclusion_pattern_matching_integration(self) -> None:
        """Test exclusion pattern matching through integration testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files with different patterns
            _ = (temp_path / "file.tmp").write_text("temp")
            (temp_path / "cache123").mkdir()
            _ = (temp_path / "cache123" / "data.txt").write_text("data")
            _ = (temp_path / "file.txt").write_text("text")
            (temp_path / ".git").mkdir()
            _ = (temp_path / ".git" / "config").write_text("config")
            
            scanner = DirectoryScanner(exclusions={"*.tmp", "cache*", ".git"})
            files = list(scanner.scan_directory(temp_path))
            
            # Should only find file.txt (others are excluded)
            assert len(files) == 1
            assert files[0].name == "file.txt"

    def test_exclusion_directory_vs_file_integration(self) -> None:
        """Test that exclusions work for both files and directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files and directories
            _ = (temp_path / "error.log").write_text("error")
            (temp_path / "temp").mkdir()
            _ = (temp_path / "temp" / "data.txt").write_text("data")
            _ = (temp_path / "important.txt").write_text("important")
            
            scanner = DirectoryScanner(exclusions={"*.log", "temp"})
            files = list(scanner.scan_directory(temp_path))
            
            # Should only find important.txt (others are excluded)
            assert len(files) == 1
            assert files[0].name == "important.txt"

    def test_breadth_first_strategy(self) -> None:
        """Test breadth-first scanning strategy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create nested structure
            _ = (temp_path / "file1.txt").write_text("test")
            (temp_path / "level1").mkdir()
            _ = (temp_path / "level1" / "file2.txt").write_text("test")
            (temp_path / "level1" / "level2").mkdir()
            _ = (temp_path / "level1" / "level2" / "file3.txt").write_text("test")
            
            scanner = DirectoryScanner(strategy=ScanStrategy.BREADTH_FIRST)
            files = list(scanner.scan_directory(temp_path))
            
            # Should find all files, order depends on strategy
            assert len(files) == 3
            assert {f.name for f in files} == {"file1.txt", "file2.txt", "file3.txt"}

    def test_depth_first_strategy(self) -> None:
        """Test depth-first scanning strategy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create nested structure
            _ = (temp_path / "file1.txt").write_text("test")
            (temp_path / "level1").mkdir()
            _ = (temp_path / "level1" / "file2.txt").write_text("test")
            (temp_path / "level1" / "level2").mkdir()
            _ = (temp_path / "level1" / "level2" / "file3.txt").write_text("test")
            
            scanner = DirectoryScanner(strategy=ScanStrategy.DEPTH_FIRST)
            files = list(scanner.scan_directory(temp_path))
            
            # Should find all files, order depends on strategy
            assert len(files) == 3
            assert {f.name for f in files} == {"file1.txt", "file2.txt", "file3.txt"}

    def test_scan_directory_with_symlinks(self) -> None:
        """Test directory scanning with symbolic links."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            _ = (temp_path / "file1.txt").write_text("test")
            (temp_path / "subdir").mkdir()
            _ = (temp_path / "subdir" / "file2.txt").write_text("test")
            
            # Create symlink if the system supports it
            try:
                os.symlink(temp_path / "subdir", temp_path / "symlink_dir")
                symlink_created = True
            except OSError:
                # Symlinks not supported on this system
                symlink_created = False
            
            scanner = DirectoryScanner()
            files = list(scanner.scan_directory(temp_path))
            
            if symlink_created:
                # Current implementation follows symlinks, so we get all files
                assert len(files) == 3
                assert {f.name for f in files} == {"file1.txt", "file2.txt", "file2.txt"}
            else:
                # No symlinks, just regular files
                assert len(files) == 2
                assert {f.name for f in files} == {"file1.txt", "file2.txt"}

    def test_scan_directory_with_broken_symlinks(self) -> None:
        """Test directory scanning with broken symbolic links."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            _ = (temp_path / "file1.txt").write_text("test")
            
            # Create broken symlink if the system supports it
            try:
                os.symlink(temp_path / "nonexistent", temp_path / "broken_symlink")
            except OSError:
                # Symlinks not supported on this system
                pass
            
            scanner = DirectoryScanner()
            files = list(scanner.scan_directory(temp_path))
            
            # Should only find the regular file, broken symlink should be ignored
            assert len(files) == 1
            assert files[0].name == "file1.txt"

    def test_scan_directory_symlink_loop_prevention(self) -> None:
        """Test prevention of infinite symlink loops."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            _ = (temp_path / "file1.txt").write_text("test")
            (temp_path / "dir1").mkdir()
            _ = (temp_path / "dir1" / "file2.txt").write_text("test")
            
            # Create symlink loop if the system supports it
            try:
                os.symlink(temp_path / "dir1", temp_path / "dir1" / "loop_back")
            except OSError:
                # Symlinks not supported on this system
                pass
            
            scanner = DirectoryScanner()
            files = list(scanner.scan_directory(temp_path))
            
            # Should find files but not get stuck in loop
            assert len(files) >= 2
            assert {f.name for f in files} >= {"file1.txt", "file2.txt"}

    def test_scan_directory_no_follow_symlinks(self) -> None:
        """Test directory scanning with symlinks disabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            _ = (temp_path / "file1.txt").write_text("test")
            (temp_path / "subdir").mkdir()
            _ = (temp_path / "subdir" / "file2.txt").write_text("test")
            
            # Create symlink if the system supports it
            try:
                os.symlink(temp_path / "subdir", temp_path / "symlink_dir")
            except OSError:
                # Symlinks not supported on this system
                pass
            
            scanner = DirectoryScanner(follow_symlinks=False)
            files = list(scanner.scan_directory(temp_path))
            
            # Should not follow symlinks
            assert len(files) == 2
            assert {f.name for f in files} == {"file1.txt", "file2.txt"}

    def test_scan_directory_file_symlinks(self) -> None:
        """Test directory scanning with file symbolic links."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            _ = (temp_path / "file1.txt").write_text("test")
            
            # Create file symlink if the system supports it
            symlink_created = False
            try:
                os.symlink(temp_path / "file1.txt", temp_path / "file_symlink.txt")
                symlink_created = True
            except OSError:
                # Symlinks not supported on this system
                pass
            
            scanner = DirectoryScanner()
            files = list(scanner.scan_directory(temp_path))
            
            if symlink_created:
                # Should find both the original file and the symlink
                assert len(files) == 2
                assert {f.name for f in files} == {"file1.txt", "file_symlink.txt"}
            else:
                # No symlinks, just regular files
                assert len(files) == 1
                assert files[0].name == "file1.txt"

    def test_scan_directory_max_symlink_depth(self) -> None:
        """Test maximum symlink depth prevention."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            _ = (temp_path / "file1.txt").write_text("test")
            (temp_path / "subdir").mkdir()
            _ = (temp_path / "subdir" / "file2.txt").write_text("test")
            
            # Create symlink if the system supports it
            try:
                os.symlink(temp_path / "subdir", temp_path / "symlink_dir")
            except OSError:
                # Symlinks not supported on this system
                pass
            
            # Set a very low max symlink depth
            scanner = DirectoryScanner(max_symlink_depth=1)
            files = list(scanner.scan_directory(temp_path))
            
            # Should still work but respect the depth limit
            assert len(files) >= 2
            assert {f.name for f in files} >= {"file1.txt", "file2.txt"}

    def test_scan_directory_large_directory_performance(self) -> None:
        """Test performance with a moderately sized directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create multiple files
            num_files = 100
            for i in range(num_files):
                _ = (temp_path / f"file_{i:03d}.txt").write_text(f"content {i}")
            
            scanner = DirectoryScanner()
            files = list(scanner.scan_directory(temp_path))
            
            assert len(files) == num_files
            assert all(f.is_file() for f in files)

    def test_scan_directory_mixed_file_types(self) -> None:
        """Test scanning directory with various file types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create various file types
            _ = (temp_path / "document.txt").write_text("text")
            _ = (temp_path / "script.py").write_text("python")
            _ = (temp_path / "data.json").write_text("{}")
            _ = (temp_path / "image.jpg").write_bytes(b"fake image")
            _ = (temp_path / "archive.zip").write_bytes(b"fake zip")
            
            scanner = DirectoryScanner()
            files = list(scanner.scan_directory(temp_path))
            
            assert len(files) == 5
            expected_names = {"document.txt", "script.py", "data.json", "image.jpg", "archive.zip"}
            assert {f.name for f in files} == expected_names

    def test_scan_directory_with_zero_depth(self) -> None:
        """Test scanning with max_depth=0 (only root level)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create files at different levels
            _ = (temp_path / "root_file.txt").write_text("test")
            (temp_path / "subdir").mkdir()
            _ = (temp_path / "subdir" / "sub_file.txt").write_text("test")
            
            scanner = DirectoryScanner(max_depth=0)
            files = list(scanner.scan_directory(temp_path))
            
            # Should only find root level files
            assert len(files) == 1
            assert files[0].name == "root_file.txt"

    def test_breadth_first_with_depth_limit(self) -> None:
        """Test breadth-first scanning with depth limit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create nested structure
            _ = (temp_path / "file1.txt").write_text("test")
            (temp_path / "level1").mkdir()
            _ = (temp_path / "level1" / "file2.txt").write_text("test")
            (temp_path / "level1" / "level2").mkdir()
            _ = (temp_path / "level1" / "level2" / "file3.txt").write_text("test")
            
            scanner = DirectoryScanner(strategy=ScanStrategy.BREADTH_FIRST, max_depth=1)
            files = list(scanner.scan_directory(temp_path))
            
            # Should find files at depth 0 and 1, but not 2
            assert len(files) == 2
            assert {f.name for f in files} == {"file1.txt", "file2.txt"}

    def test_breadth_first_permission_error(self) -> None:
        """Test breadth-first scanning with permission errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test file
            _ = (temp_path / "file1.txt").write_text("test")
            
            scanner = DirectoryScanner(strategy=ScanStrategy.BREADTH_FIRST)
            
            # Mock iterdir to raise PermissionError for breadth-first path
            with patch.object(Path, 'iterdir', side_effect=PermissionError("Access denied")):
                files = list(scanner.scan_directory(temp_path))
                
                # Should handle permission error gracefully
                assert files == []

    def test_breadth_first_with_exclusions(self) -> None:
        """Test breadth-first scanning with exclusions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files and directories
            _ = (temp_path / "file.txt").write_text("test")
            _ = (temp_path / "file.tmp").write_text("temp")
            (temp_path / "subdir").mkdir()
            _ = (temp_path / "subdir" / "file2.txt").write_text("test")
            
            scanner = DirectoryScanner(strategy=ScanStrategy.BREADTH_FIRST, exclusions={"*.tmp"})
            files = list(scanner.scan_directory(temp_path))
            
            # Should find .txt files but not .tmp files
            assert len(files) == 2
            assert {f.name for f in files} == {"file.txt", "file2.txt"}