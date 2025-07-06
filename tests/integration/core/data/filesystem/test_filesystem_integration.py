"""Integration tests for filesystem operations module."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mover_status.core.data.filesystem.exclusions import ExclusionFilter
from mover_status.core.data.filesystem.scanner import DirectoryScanner, ScanStrategy
from mover_status.core.data.filesystem.size_calculator import SizeCalculator

if TYPE_CHECKING:
    pass


class TestFilesystemIntegration:
    """Integration tests for complete filesystem workflows."""

    def test_complete_directory_analysis_workflow(self) -> None:
        """Test complete workflow: scan directory, calculate sizes, apply exclusions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create complex directory structure
            self._create_complex_directory_structure(temp_path)
            
            # Create scanner with exclusions
            exclusion_filter = ExclusionFilter()
            exclusion_filter.add_patterns(["*.tmp", "cache*"])
            exclusion_filter.add_extensions([".log"])
            
            scanner = DirectoryScanner(exclusion_filter=exclusion_filter)
            calculator = SizeCalculator(scanner=scanner)
            
            # Scan and calculate
            files = list(scanner.scan_directory(temp_path))
            total_size = calculator.calculate_size(temp_path)
            
            # Verify results
            assert len(files) > 0
            assert total_size > 0
            
            # Check that excluded files are not in results
            file_names = {f.name for f in files}
            assert "temp.tmp" not in file_names
            assert "debug.log" not in file_names
            assert not any(name.startswith("cache") for name in file_names)

    def test_size_calculation_with_progress_tracking(self) -> None:
        """Test size calculation with progress reporting for large directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create directory with many files
            for i in range(50):
                file_path = temp_path / f"file_{i:03d}.txt"
                _ = file_path.write_text(f"Content for file {i} " * 10)
            
            # Create subdirectories
            for i in range(5):
                subdir = temp_path / f"subdir_{i}"
                subdir.mkdir()
                for j in range(10):
                    file_path = subdir / f"subfile_{j}.txt"
                    _ = file_path.write_text(f"Subcontent {i}-{j} " * 5)
            
            calculator = SizeCalculator()
            
            # Track progress
            progress_updates: list[tuple[int, Path]] = []
            total_files = 0
            
            for cumulative_size, current_file in calculator.calculate_size_with_progress(temp_path):
                progress_updates.append((cumulative_size, current_file))
                total_files += 1
            
            # Verify progress tracking
            assert len(progress_updates) > 0
            assert total_files == 100  # 50 + (5 * 10)
            
            # Verify cumulative size increases
            sizes = [update[0] for update in progress_updates]
            assert all(sizes[i] <= sizes[i + 1] for i in range(len(sizes) - 1))
            
            # Compare with direct calculation
            direct_size = calculator.calculate_size(temp_path)
            assert sizes[-1] == direct_size

    def test_cache_performance_across_operations(self) -> None:
        """Test caching behavior across multiple operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test structure
            self._create_complex_directory_structure(temp_path)
            
            calculator = SizeCalculator(cache_enabled=True)
            
            # First calculation - populate cache
            start_time = time.time()
            size1 = calculator.calculate_size(temp_path)
            first_duration = time.time() - start_time
            
            # Check cache stats
            stats = calculator.get_cache_stats()
            assert stats["file_cache_hits"] == 0  # First run, no hits
            assert stats["directory_cache_hits"] == 0
            assert stats["file_cache_misses"] > 0  # Should have cache misses
            assert stats["directory_cache_misses"] > 0
            
            # Second calculation - should use cache
            start_time = time.time()
            size2 = calculator.calculate_size(temp_path)
            second_duration = time.time() - start_time
            
            # Verify results
            assert size1 == size2
            assert second_duration <= first_duration  # Should be faster with cache
            
            # Check cache utilization - directory caching should provide the speedup
            stats = calculator.get_cache_stats()
            assert stats["directory_cache_hits"] > 0  # Directory cache should have hits
            assert stats["total_cache_entries"] > 0
            
            # Test file cache hits by calculating individual files
            # Get some files from the structure
            docs_dir = temp_path / "documents"
            if docs_dir.exists():
                report_file = docs_dir / "report.pdf"
                if report_file.exists():
                    # Calculate individual file size - should use file cache
                    file_size1 = calculator.calculate_size(report_file)
                    file_size2 = calculator.calculate_size(report_file)  # Second time should be cache hit
                    assert file_size1 == file_size2
                    
                    final_stats = calculator.get_cache_stats()
                    assert final_stats["file_cache_hits"] > stats["file_cache_hits"]

    def test_symlink_handling_integration(self) -> None:
        """Test complete symlink handling workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create original files
            original_dir = temp_path / "original"
            original_dir.mkdir()
            
            file1 = original_dir / "file1.txt"
            _ = file1.write_text("Original content")
            
            file2 = original_dir / "file2.txt"
            _ = file2.write_text("More content")
            
            # Create symlinks if supported
            symlink_dir = temp_path / "symlinks"
            symlink_dir.mkdir()
            
            symlinks_created = 0
            try:
                # File symlink
                os.symlink(file1, symlink_dir / "link_to_file1.txt")
                symlinks_created += 1
                
                # Directory symlink  
                os.symlink(original_dir, symlink_dir / "link_to_original")
                symlinks_created += 1
                
                # Broken symlink
                os.symlink(temp_path / "nonexistent", symlink_dir / "broken_link")
                symlinks_created += 1
                
            except OSError:
                # Symlinks not supported on this system
                pass
            
            if symlinks_created > 0:
                # Test with symlink following enabled
                scanner_follow = DirectoryScanner(follow_symlinks=True)
                calculator_follow = SizeCalculator(scanner=scanner_follow)
                
                files_follow = list(scanner_follow.scan_directory(temp_path))
                size_follow = calculator_follow.calculate_size(temp_path)
                
                # Test with symlink following disabled
                scanner_no_follow = DirectoryScanner(follow_symlinks=False)
                calculator_no_follow = SizeCalculator(scanner=scanner_no_follow)
                
                files_no_follow = list(scanner_no_follow.scan_directory(temp_path))
                size_no_follow = calculator_no_follow.calculate_size(temp_path)
                
                # With symlinks, we should get more files and larger size
                assert len(files_follow) > len(files_no_follow)
                assert size_follow >= size_no_follow
                
                # Verify specific behavior
                follow_names = {f.name for f in files_follow}
                no_follow_names = {f.name for f in files_no_follow}
                
                # Original files should be in both
                assert "file1.txt" in follow_names
                assert "file1.txt" in no_follow_names
                assert "file2.txt" in follow_names
                assert "file2.txt" in no_follow_names

    def test_error_resilience_workflow(self) -> None:
        """Test system resilience to various error conditions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create some valid files
            valid_file = temp_path / "valid.txt"
            _ = valid_file.write_text("Valid content")
            
            # Create subdirectory
            subdir = temp_path / "subdir"
            subdir.mkdir()
            sub_file = subdir / "sub.txt"
            _ = sub_file.write_text("Sub content")
            
            scanner = DirectoryScanner()
            calculator = SizeCalculator(scanner=scanner)
            
            # Should handle missing files gracefully
            missing_path = temp_path / "missing"
            with pytest.raises(OSError):
                _ = calculator.calculate_size(missing_path)
            
            # Should handle directory scanning gracefully
            files = list(scanner.scan_directory(temp_path))
            assert len(files) >= 2  # At least the files we created
            
            # Size calculation should work
            total_size = calculator.calculate_size(temp_path)
            assert total_size > 0

    def test_mixed_scan_strategies_comparison(self) -> None:
        """Test and compare different scanning strategies."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create nested structure for strategy comparison
            self._create_nested_structure(temp_path, depth=4, files_per_level=3)
            
            # Test depth-first strategy
            scanner_df = DirectoryScanner(strategy=ScanStrategy.DEPTH_FIRST)
            files_df = list(scanner_df.scan_directory(temp_path))
            
            # Test breadth-first strategy
            scanner_bf = DirectoryScanner(strategy=ScanStrategy.BREADTH_FIRST)
            files_bf = list(scanner_bf.scan_directory(temp_path))
            
            # Both should find the same files (order may differ)
            assert len(files_df) == len(files_bf)
            assert {f.name for f in files_df} == {f.name for f in files_bf}
            
            # Test with depth limits
            scanner_df_limited = DirectoryScanner(
                strategy=ScanStrategy.DEPTH_FIRST, 
                max_depth=2
            )
            files_df_limited = list(scanner_df_limited.scan_directory(temp_path))
            
            scanner_bf_limited = DirectoryScanner(
                strategy=ScanStrategy.BREADTH_FIRST, 
                max_depth=2
            )
            files_bf_limited = list(scanner_bf_limited.scan_directory(temp_path))
            
            # Limited depth should find fewer files
            assert len(files_df_limited) < len(files_df)
            assert len(files_bf_limited) < len(files_bf)
            assert len(files_df_limited) == len(files_bf_limited)

    def test_exclusion_filter_integration(self) -> None:
        """Test integration of different exclusion filter types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create files matching different exclusion patterns
            files_to_create = [
                "document.txt",      # Should be included
                "temp.tmp",          # Excluded by glob
                "cache_file",        # Excluded by glob
                "script.py",         # Should be included
                "debug.log",         # Excluded by extension
                "config.ini",        # Excluded by exact match
                "README.md",         # Should be included
            ]
            
            for filename in files_to_create:
                _ = (temp_path / filename).write_text(f"Content of {filename}")
            
            # Set up exclusion filter
            exclusion_filter = ExclusionFilter()
            exclusion_filter.add_patterns(["*.tmp", "cache*"])
            exclusion_filter.add_extensions([".log"])
            exclusion_filter.add_exact_names(["config.ini"])
            
            scanner = DirectoryScanner(exclusion_filter=exclusion_filter)
            calculator = SizeCalculator(scanner=scanner)
            
            # Scan directory
            files = list(scanner.scan_directory(temp_path))
            file_names = {f.name for f in files}
            
            # Verify inclusions
            assert "document.txt" in file_names
            assert "script.py" in file_names
            assert "README.md" in file_names
            
            # Verify exclusions
            assert "temp.tmp" not in file_names
            assert "cache_file" not in file_names
            assert "debug.log" not in file_names
            assert "config.ini" not in file_names
            
            # Calculate size (should only include non-excluded files)
            total_size = calculator.calculate_size(temp_path)
            assert total_size > 0
            
            # Compare with no exclusions
            scanner_no_exclusions = DirectoryScanner(exclusion_filter=ExclusionFilter())
            all_files = list(scanner_no_exclusions.scan_directory(temp_path))
            
            assert len(all_files) > len(files)
            assert len(all_files) == len(files_to_create)

    def test_default_exclusion_filter_behavior(self) -> None:
        """Test behavior of default exclusion filter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create files that should be excluded by default
            system_files = [
                ".snapshots/backup.txt",
                ".Recycle.Bin/deleted.txt", 
                "@eaDir/metadata.txt",
                ".git/config",
                "node_modules/package.json",
                "__pycache__/module.pyc",
                ".venv/lib/python.py",
                "thumbs.db",
                "desktop.ini",
                "temp.tmp",
            ]
            
            # Create directory structure
            for file_path in system_files:
                full_path = temp_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                _ = full_path.write_text("system file content")
            
            # Create some files that should be included
            normal_files = ["document.txt", "script.py", "data.json"]
            for filename in normal_files:
                _ = (temp_path / filename).write_text("normal content")
            
            # Use default exclusion filter
            scanner = DirectoryScanner()  # Uses DefaultExclusionFilter
            files = list(scanner.scan_directory(temp_path))
            file_names = {f.name for f in files}
            
            # Normal files should be included
            for normal_file in normal_files:
                assert normal_file in file_names
            
            # System files should be excluded
            excluded_names = {
                "backup.txt", "deleted.txt", "metadata.txt", "config", 
                "package.json", "module.pyc", "python.py", "thumbs.db", 
                "desktop.ini", "temp.tmp"
            }
            
            for excluded_name in excluded_names:
                assert excluded_name not in file_names

    def _create_complex_directory_structure(self, base_path: Path) -> None:
        """Create a complex directory structure for testing."""
        # Main files
        _ = (base_path / "readme.txt").write_text("This is a readme file")
        _ = (base_path / "temp.tmp").write_text("Temporary file")  # Should be excluded
        _ = (base_path / "debug.log").write_text("Debug log")      # Should be excluded
        
        # Documents directory
        docs_dir = base_path / "documents"
        docs_dir.mkdir()
        _ = (docs_dir / "report.pdf").write_bytes(b"PDF content" * 100)
        _ = (docs_dir / "notes.txt").write_text("Important notes")
        
        # Cache directory (should be excluded)
        cache_dir = base_path / "cache_data"
        cache_dir.mkdir()
        _ = (cache_dir / "cached_file.dat").write_bytes(b"cached data" * 50)
        
        # Source code directory
        src_dir = base_path / "src"
        src_dir.mkdir()
        _ = (src_dir / "main.py").write_text("print('Hello, world!')")
        _ = (src_dir / "utils.py").write_text("def helper(): pass")
        
        # Nested subdirectory
        nested_dir = src_dir / "modules"
        nested_dir.mkdir()
        _ = (nested_dir / "module1.py").write_text("class Module1: pass")
        _ = (nested_dir / "module2.py").write_text("class Module2: pass")

    def _create_nested_structure(self, base_path: Path, depth: int, files_per_level: int) -> None:
        """Create a nested directory structure for depth testing."""
        current_path = base_path
        
        for level in range(depth):
            # Create files at current level
            for file_num in range(files_per_level):
                filename = f"level_{level}_file_{file_num}.txt"
                _ = (current_path / filename).write_text(f"Content at level {level}, file {file_num}")
            
            # Create subdirectory for next level
            if level < depth - 1:
                next_dir = current_path / f"level_{level + 1}"
                next_dir.mkdir()
                current_path = next_dir


class TestFilesystemPerformance:
    """Performance tests for filesystem operations."""

    def test_large_directory_scanning_performance(self) -> None:
        """Test performance with large directory structures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create large directory structure
            num_files = 500
            num_dirs = 20
            
            # Create files
            for i in range(num_files):
                file_path = temp_path / f"file_{i:04d}.txt"
                _ = file_path.write_text(f"Content for file {i}")
            
            # Create subdirectories with files
            for dir_num in range(num_dirs):
                subdir = temp_path / f"subdir_{dir_num:02d}"
                subdir.mkdir()
                
                for file_num in range(25):  # 25 files per subdir
                    file_path = subdir / f"subfile_{file_num:03d}.txt"
                    _ = file_path.write_text(f"Subcontent {dir_num}-{file_num}")
            
            # Test scanning performance
            scanner = DirectoryScanner()
            
            start_time = time.time()
            files = list(scanner.scan_directory(temp_path))
            scan_duration = time.time() - start_time
            
            # Verify results
            expected_files = num_files + (num_dirs * 25)
            assert len(files) == expected_files
            
            # Performance check (should complete in reasonable time)
            assert scan_duration < 5.0  # Should complete within 5 seconds
            
            print(f"Scanned {len(files)} files in {scan_duration:.3f} seconds")

    def test_size_calculation_performance(self) -> None:
        """Test size calculation performance with caching."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create files of various sizes
            file_sizes = [1024, 4096, 16384, 65536, 262144]  # 1KB to 256KB
            
            for i, size in enumerate(file_sizes * 20):  # 100 files total
                file_path = temp_path / f"file_{i:03d}.dat"
                _ = file_path.write_bytes(b"x" * size)
            
            # Test without cache
            calculator_no_cache = SizeCalculator(cache_enabled=False)
            
            start_time = time.time()
            size1 = calculator_no_cache.calculate_size(temp_path)
            no_cache_duration = time.time() - start_time
            
            # Test with cache (first run)
            calculator_with_cache = SizeCalculator(cache_enabled=True)
            
            start_time = time.time()
            size2 = calculator_with_cache.calculate_size(temp_path)
            first_cache_duration = time.time() - start_time
            
            # Test with cache (second run - should use cache)
            start_time = time.time()
            size3 = calculator_with_cache.calculate_size(temp_path)
            second_cache_duration = time.time() - start_time
            
            # Verify results
            assert size1 == size2 == size3
            
            # Performance expectations
            assert second_cache_duration <= first_cache_duration
            assert second_cache_duration <= no_cache_duration
            
            print(f"No cache: {no_cache_duration:.3f}s, " +
                  f"First cache: {first_cache_duration:.3f}s, " +
                  f"Second cache: {second_cache_duration:.3f}s")

    def test_deep_nesting_performance(self) -> None:
        """Test performance with deeply nested directory structures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create deeply nested structure
            current_path = temp_path
            depth = 50
            
            for level in range(depth):
                # Create a file at each level
                file_path = current_path / f"level_{level}.txt"
                _ = file_path.write_text(f"Content at level {level}")
                
                # Create next level directory
                if level < depth - 1:
                    next_dir = current_path / f"level_{level + 1}"
                    next_dir.mkdir()
                    current_path = next_dir
            
            # Test scanning with different strategies
            strategies = [ScanStrategy.DEPTH_FIRST, ScanStrategy.BREADTH_FIRST]
            
            for strategy in strategies:
                scanner = DirectoryScanner(strategy=strategy)
                
                start_time = time.time()
                files = list(scanner.scan_directory(temp_path))
                duration = time.time() - start_time
                
                # Verify all files found
                assert len(files) == depth
                
                # Should complete in reasonable time
                assert duration < 2.0
                
                print(f"{strategy.value} strategy: {len(files)} files in {duration:.3f}s")


class TestFilesystemEdgeCases:
    """Edge case tests for filesystem operations."""

    def test_empty_directory_handling(self) -> None:
        """Test handling of completely empty directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create empty subdirectories
            for i in range(5):
                empty_dir = temp_path / f"empty_{i}"
                empty_dir.mkdir()
            
            scanner = DirectoryScanner()
            calculator = SizeCalculator(scanner=scanner)
            
            # Scan empty directory structure
            files = list(scanner.scan_directory(temp_path))
            assert len(files) == 0  # No files in empty directories
            
            # Calculate size of empty structure
            total_size = calculator.calculate_size(temp_path)
            assert total_size == 0  # Empty directories have no content size

    def test_very_long_filenames(self) -> None:
        """Test handling of very long filenames (within OS limits)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create file with long name (but within typical OS limits)
            long_name = "a" * 200 + ".txt"
            long_file = temp_path / long_name
            
            try:
                _ = long_file.write_text("Content with very long filename")
                
                scanner = DirectoryScanner()
                calculator = SizeCalculator(scanner=scanner)
                
                files = list(scanner.scan_directory(temp_path))
                assert len(files) == 1
                assert files[0].name == long_name
                
                total_size = calculator.calculate_size(temp_path)
                assert total_size > 0
                
            except OSError:
                # Some filesystems may not support names this long
                pytest.skip("Filesystem doesn't support long filenames")

    def test_unicode_filename_handling(self) -> None:
        """Test handling of Unicode filenames."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create files with Unicode names
            unicode_files = [
                "测试文件.txt",        # Chinese
                "тест.txt",           # Cyrillic  
                "δοκιμή.txt",         # Greek
                "🎉emoji🎈file.txt",   # Emoji
                "café_résumé.txt",    # Accented characters
            ]
            
            created_files: list[str] = []
            for filename in unicode_files:
                try:
                    file_path = temp_path / filename
                    _ = file_path.write_text(f"Content of {filename}")
                    created_files.append(filename)
                except (OSError, UnicodeError):
                    # Some filesystems may not support certain Unicode characters
                    continue
            
            if created_files:
                scanner = DirectoryScanner()
                calculator = SizeCalculator(scanner=scanner)
                
                files = list(scanner.scan_directory(temp_path))
                file_names = {f.name for f in files}
                
                # All created files should be found
                for created_file in created_files:
                    assert created_file in file_names
                
                total_size = calculator.calculate_size(temp_path)
                assert total_size > 0

    def test_zero_byte_files(self) -> None:
        """Test handling of zero-byte files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create mix of zero-byte and normal files
            (temp_path / "empty1.txt").touch()
            (temp_path / "empty2.txt").touch()
            _ = (temp_path / "normal.txt").write_text("Some content")
            (temp_path / "empty3.txt").touch()
            
            scanner = DirectoryScanner()
            calculator = SizeCalculator(scanner=scanner)
            
            files = list(scanner.scan_directory(temp_path))
            assert len(files) == 4
            
            # Calculate total size
            total_size = calculator.calculate_size(temp_path)
            
            # Should equal size of the one non-empty file
            normal_file_size = (temp_path / "normal.txt").stat().st_size
            assert total_size == normal_file_size

    def test_special_characters_in_paths(self) -> None:
        """Test handling of special characters in paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create directories and files with special characters
            special_names = [
                "file with spaces.txt",
                "file-with-dashes.txt", 
                "file_with_underscores.txt",
                "file.with.dots.txt",
                "file(with)parens.txt",
                "file[with]brackets.txt",
            ]
            
            created_files: list[str] = []
            for filename in special_names:
                try:
                    file_path = temp_path / filename
                    _ = file_path.write_text(f"Content of {filename}")
                    created_files.append(filename)
                except OSError:
                    # Some characters might not be supported
                    continue
            
            if created_files:
                scanner = DirectoryScanner()
                calculator = SizeCalculator(scanner=scanner)
                
                files = list(scanner.scan_directory(temp_path))
                file_names = {f.name for f in files}
                
                # All created files should be found
                for created_file in created_files:
                    assert created_file in file_names
                
                # Size calculation should work
                total_size = calculator.calculate_size(temp_path)
                assert total_size > 0

    def test_maximum_directory_depth(self) -> None:
        """Test behavior at maximum practical directory depth."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create deep nesting (limited to avoid filesystem limits)
            current_path = temp_path
            max_depth = 100
            
            try:
                for level in range(max_depth):
                    next_dir = current_path / "d"
                    next_dir.mkdir()
                    current_path = next_dir
                    
                    # Add a file every 10 levels
                    if level % 10 == 0:
                        file_path = current_path / f"file_{level}.txt"
                        _ = file_path.write_text(f"File at level {level}")
                
                # Test scanning with depth limit
                scanner_limited = DirectoryScanner(max_depth=50)
                files_limited = list(scanner_limited.scan_directory(temp_path))
                
                scanner_unlimited = DirectoryScanner()
                files_unlimited = list(scanner_unlimited.scan_directory(temp_path))
                
                # Limited scan should find fewer files
                assert len(files_limited) <= len(files_unlimited)
                
            except OSError:
                # Some filesystems have depth limits
                pytest.skip("Filesystem depth limit reached")