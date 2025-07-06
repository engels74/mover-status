"""Performance and stress tests for filesystem operations."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mover_status.core.data.filesystem.scanner import DirectoryScanner
from mover_status.core.data.filesystem.size_calculator import SizeCalculator

if TYPE_CHECKING:
    pass


class TestFilesystemPerformanceBenchmarks:
    """Performance benchmark tests for filesystem operations."""

    def test_large_file_count_performance(self) -> None:
        """Test performance with very large number of files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create many files for performance testing
            num_files = 1000
            file_size = 1024  # 1KB each
            
            start_time = time.time()
            for i in range(num_files):
                file_path = temp_path / f"file_{i:04d}.txt"
                _ = file_path.write_bytes(b"x" * file_size)
            setup_time = time.time() - start_time
            
            print(f"Created {num_files} files in {setup_time:.3f} seconds")
            
            # Test scanning performance
            scanner = DirectoryScanner()
            
            start_time = time.time()
            files = list(scanner.scan_directory(temp_path))
            scan_time = time.time() - start_time
            
            # Test size calculation performance
            calculator = SizeCalculator(scanner=scanner)
            
            start_time = time.time()
            total_size = calculator.calculate_size(temp_path)
            calc_time = time.time() - start_time
            
            # Verify results
            assert len(files) == num_files
            assert total_size == num_files * file_size
            
            # Performance assertions
            assert scan_time < 10.0  # Should scan 1000 files in under 10 seconds
            assert calc_time < 15.0  # Should calculate size in under 15 seconds
            
            print(f"Scanned {len(files)} files in {scan_time:.3f}s")
            print(f"Calculated size {total_size} bytes in {calc_time:.3f}s")

    def test_memory_usage_large_directory(self) -> None:
        """Test memory efficiency with large directory structures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create nested structure with many files
            depth = 10
            files_per_level = 50
            
            for level in range(depth):
                level_dir = temp_path
                for sublevel in range(level + 1):
                    level_dir = level_dir / f"level_{sublevel}"
                    level_dir.mkdir(exist_ok=True)
                
                # Create files at this level
                for file_num in range(files_per_level):
                    file_path = level_dir / f"file_{file_num}.txt"
                    _ = file_path.write_text(f"Content at level {level}, file {file_num}")
            
            # Test memory-efficient iteration
            scanner = DirectoryScanner()
            calculator = SizeCalculator(scanner=scanner)
            
            # Progress tracking should be memory efficient
            file_count = 0
            last_size = 0
            
            for current_size, _ in calculator.calculate_size_with_progress(temp_path):
                file_count += 1
                assert current_size >= last_size  # Size should only increase
                last_size = current_size
                
                # This should not consume excessive memory
                if file_count % 100 == 0:
                    print(f"Processed {file_count} files, current size: {current_size}")
            
            # Verify all files were processed
            expected_files = depth * files_per_level
            assert file_count == expected_files

    def test_cache_efficiency_benchmark(self) -> None:
        """Benchmark cache efficiency across multiple operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create moderate-sized directory structure
            num_dirs = 10
            files_per_dir = 20
            
            for dir_num in range(num_dirs):
                subdir = temp_path / f"dir_{dir_num:02d}"
                subdir.mkdir()
                
                for file_num in range(files_per_dir):
                    file_path = subdir / f"file_{file_num:02d}.txt"
                    content = f"Content for dir {dir_num}, file {file_num}" * 10
                    _ = file_path.write_text(content)
            
            # Test with cache enabled
            calculator_cached = SizeCalculator(cache_enabled=True)
            
            # First calculation (cold cache)
            start_time = time.time()
            size1 = calculator_cached.calculate_size(temp_path)
            first_time = time.time() - start_time
            
            # Second calculation (warm cache)
            start_time = time.time()
            size2 = calculator_cached.calculate_size(temp_path)
            second_time = time.time() - start_time
            
            # Third calculation on subdirectory (partial cache hit)
            subdir_path = temp_path / "dir_05"
            start_time = time.time()
            subdir_size = calculator_cached.calculate_size(subdir_path)
            subdir_time = time.time() - start_time
            
            # Verify correctness
            assert size1 == size2
            assert subdir_size > 0
            
            # Cache should provide significant speedup
            assert second_time <= first_time
            
            # Check cache statistics
            stats = calculator_cached.get_cache_stats()
            assert stats["file_cache_hits"] > 0
            assert stats["total_cache_entries"] > 0
            
            print(f"Cold cache: {first_time:.3f}s, Warm cache: {second_time:.3f}s")
            print(f"Cache stats: {stats}")

    def test_exclusion_filter_performance(self) -> None:
        """Test performance impact of exclusion filters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create mix of files to include and exclude
            file_patterns = [
                "document_{}.txt",
                "temp_{}.tmp",
                "cache_{}.cache",
                "log_{}.log",
                "backup_{}.bak",
                "source_{}.py",
                "data_{}.json",
                "config_{}.ini",
            ]
            
            files_per_pattern = 50
            
            for pattern in file_patterns:
                for i in range(files_per_pattern):
                    file_path = temp_path / pattern.format(i)
                    _ = file_path.write_text(f"Content {i}")
            
            # Test without exclusions
            scanner_no_filter = DirectoryScanner()
            start_time = time.time()
            files_no_filter = list(scanner_no_filter.scan_directory(temp_path))
            no_filter_time = time.time() - start_time
            
            # Test with default exclusions
            scanner_default = DirectoryScanner()  # Uses DefaultExclusionFilter
            start_time = time.time()
            files_default = list(scanner_default.scan_directory(temp_path))
            default_filter_time = time.time() - start_time
            
            # Test with extensive custom exclusions
            from mover_status.core.data.filesystem.exclusions import ExclusionFilter
            custom_filter = ExclusionFilter()
            custom_filter.add_patterns(["*.tmp", "*.cache", "*.log", "*.bak"])
            custom_filter.add_extensions([".ini"])
            
            scanner_custom = DirectoryScanner(exclusion_filter=custom_filter)
            start_time = time.time()
            files_custom = list(scanner_custom.scan_directory(temp_path))
            custom_filter_time = time.time() - start_time
            
            # Verify filtering worked
            total_files = len(file_patterns) * files_per_pattern
            assert len(files_no_filter) == total_files
            assert len(files_default) < total_files
            assert len(files_custom) < total_files
            
            # Performance should be reasonable even with filters
            assert default_filter_time < 5.0
            assert custom_filter_time < 5.0
            
            print(f"No filter: {len(files_no_filter)} files in {no_filter_time:.3f}s")
            print(f"Default filter: {len(files_default)} files in {default_filter_time:.3f}s")
            print(f"Custom filter: {len(files_custom)} files in {custom_filter_time:.3f}s")


class TestFilesystemStressTesting:
    """Stress tests for filesystem operations under extreme conditions."""

    def test_deeply_nested_directory_stress(self) -> None:
        """Test with extremely deep directory nesting."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create very deep nesting
            max_depth = 200
            current_path = temp_path
            
            try:
                for depth in range(max_depth):
                    # Create directory at each level
                    next_dir = current_path / f"d{depth}"
                    next_dir.mkdir()
                    
                    # Create a file at every 20 levels
                    if depth % 20 == 0:
                        file_path = current_path / f"file_at_depth_{depth}.txt"
                        _ = file_path.write_text(f"File at depth {depth}")
                    
                    current_path = next_dir
                
                # Test scanning with depth limits
                for max_scan_depth in [50, 100, 150]:
                    scanner = DirectoryScanner(max_depth=max_scan_depth)
                    
                    start_time = time.time()
                    files = list(scanner.scan_directory(temp_path))
                    scan_time = time.time() - start_time
                    
                    # Should complete in reasonable time
                    assert scan_time < 5.0
                    
                    # Should respect depth limit
                    expected_files = (max_scan_depth // 20) + 1
                    assert len(files) <= expected_files
                    
                    print(f"Depth {max_scan_depth}: {len(files)} files in {scan_time:.3f}s")
                    
            except OSError:
                # Some filesystems have depth limits
                pytest.skip("Filesystem depth limit reached")

    def test_many_empty_directories_stress(self) -> None:
        """Test with many empty directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create many empty directories
            num_empty_dirs = 500
            
            for i in range(num_empty_dirs):
                empty_dir = temp_path / f"empty_{i:04d}"
                empty_dir.mkdir()
                
                # Create nested empty directories
                nested_empty = empty_dir / "nested"
                nested_empty.mkdir()
            
            # Add a few files scattered throughout
            for i in range(0, num_empty_dirs, 50):
                file_path = temp_path / f"empty_{i:04d}" / "file.txt"
                _ = file_path.write_text("Lonely file")
            
            scanner = DirectoryScanner()
            calculator = SizeCalculator(scanner=scanner)
            
            # Test scanning performance with many empty directories
            start_time = time.time()
            files = list(scanner.scan_directory(temp_path))
            scan_time = time.time() - start_time
            
            # Test size calculation with mostly empty structure
            start_time = time.time()
            total_size = calculator.calculate_size(temp_path)
            calc_time = time.time() - start_time
            
            # Should find only the few actual files
            expected_files = num_empty_dirs // 50
            assert len(files) == expected_files
            
            # Size should only account for actual files
            assert total_size > 0
            
            # Should handle empty directories efficiently
            assert scan_time < 10.0
            assert calc_time < 10.0
            
            print(f"Scanned {num_empty_dirs} empty dirs, found {len(files)} files in {scan_time:.3f}s")

    def test_mixed_file_sizes_stress(self) -> None:
        """Test with extreme variation in file sizes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create files with varied sizes
            file_sizes = [
                0,           # Empty file
                1,           # 1 byte
                1024,        # 1 KB
                1024 * 10,   # 10 KB
                1024 * 100,  # 100 KB
                1024 * 1024, # 1 MB
            ]
            
            total_expected_size = 0
            file_count = 0
            
            for size_category, size in enumerate(file_sizes):
                for file_num in range(10):  # 10 files per size category
                    file_path = temp_path / f"size_{size_category}_{file_num}.dat"
                    
                    if size == 0:
                        file_path.touch()
                    else:
                        _ = file_path.write_bytes(b"x" * size)
                    
                    total_expected_size += size
                    file_count += 1
            
            calculator = SizeCalculator()
            
            # Test size calculation with varied file sizes
            start_time = time.time()
            calculated_size = calculator.calculate_size(temp_path)
            calc_time = time.time() - start_time
            
            # Test progress tracking
            progress_count = 0
            start_time = time.time()
            for current_size, current_file in calculator.calculate_size_with_progress(temp_path):
                progress_count += 1
            progress_time = time.time() - start_time
            
            # Verify correctness
            assert calculated_size == total_expected_size
            assert progress_count == file_count
            
            # Performance should be reasonable
            assert calc_time < 5.0
            assert progress_time < 10.0
            
            print(f"Calculated size {calculated_size} bytes for {file_count} varied files")
            print(f"Calculation time: {calc_time:.3f}s, Progress time: {progress_time:.3f}s")

    def test_symlink_resolution_stress(self) -> None:
        """Test symlink resolution under stress conditions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create base files and directories
            base_dir = temp_path / "base"
            base_dir.mkdir()
            
            num_files = 20
            for i in range(num_files):
                file_path = base_dir / f"file_{i}.txt"
                _ = file_path.write_text(f"Content {i}")
            
            # Create many symlinks if system supports them
            symlinks_dir = temp_path / "symlinks"
            symlinks_dir.mkdir()
            
            symlinks_created = 0
            try:
                # Create file symlinks
                for i in range(num_files):
                    original = base_dir / f"file_{i}.txt"
                    link = symlinks_dir / f"link_to_file_{i}.txt"
                    os.symlink(original, link)
                    symlinks_created += 1
                
                # Create directory symlinks
                for i in range(5):
                    link_dir = symlinks_dir / f"link_to_base_{i}"
                    os.symlink(base_dir, link_dir)
                    symlinks_created += 1
                
                # Create some circular symlinks (should be handled gracefully)
                circular1 = symlinks_dir / "circular1"
                circular2 = symlinks_dir / "circular2"
                os.symlink(circular2, circular1)
                os.symlink(circular1, circular2)
                symlinks_created += 2
                
            except OSError:
                # Symlinks not supported, skip this test
                pytest.skip("Symlinks not supported on this system")
            
            if symlinks_created > 0:
                # Test with symlink following enabled
                scanner_follow = DirectoryScanner(
                    follow_symlinks=True,
                    max_symlink_depth=20
                )
                calculator_follow = SizeCalculator(scanner=scanner_follow)
                
                start_time = time.time()
                files_follow = list(scanner_follow.scan_directory(temp_path))
                scan_time_follow = time.time() - start_time
                
                start_time = time.time()
                size_follow = calculator_follow.calculate_size(temp_path)
                calc_time_follow = time.time() - start_time
                
                # Test with symlink following disabled
                scanner_no_follow = DirectoryScanner(follow_symlinks=False)
                calculator_no_follow = SizeCalculator(scanner=scanner_no_follow)
                
                start_time = time.time()
                files_no_follow = list(scanner_no_follow.scan_directory(temp_path))
                scan_time_no_follow = time.time() - start_time
                
                start_time = time.time()
                size_no_follow = calculator_no_follow.calculate_size(temp_path)
                calc_time_no_follow = time.time() - start_time
                
                # Verify symlink handling
                assert len(files_follow) > len(files_no_follow)
                assert size_follow >= size_no_follow
                
                # Performance should be reasonable even with many symlinks
                assert scan_time_follow < 10.0
                assert calc_time_follow < 10.0
                assert scan_time_no_follow < 5.0
                assert calc_time_no_follow < 5.0
                
                print(f"With symlinks: {len(files_follow)} files, {size_follow} bytes")
                print(f"Without symlinks: {len(files_no_follow)} files, {size_no_follow} bytes")


class TestFilesystemConcurrency:
    """Test filesystem operations under concurrent access patterns."""

    def test_concurrent_size_calculations(self) -> None:
        """Test multiple size calculations on the same directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test structure
            for i in range(100):
                file_path = temp_path / f"file_{i:03d}.txt"
                _ = file_path.write_text(f"Content for file {i}")
            
            # Create multiple calculators (simulating concurrent usage)
            calculators = [SizeCalculator() for _ in range(5)]
            
            # Perform calculations "concurrently" (sequentially but rapidly)
            results = []
            times = []
            
            for calc in calculators:
                start_time = time.time()
                size = calc.calculate_size(temp_path)
                duration = time.time() - start_time
                
                results.append(size)
                times.append(duration)
            
            # All results should be identical
            assert all(size == results[0] for size in results)
            
            # Performance should be consistent
            avg_time = sum(times) / len(times)
            for duration in times:
                assert abs(duration - avg_time) < avg_time * 0.5  # Within 50% of average
            
            print(f"Concurrent calculations: {results[0]} bytes")
            print(f"Times: {[f'{t:.3f}s' for t in times]}")

    def test_cache_isolation(self) -> None:
        """Test that different calculator instances have isolated caches."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            for i in range(50):
                file_path = temp_path / f"file_{i:02d}.txt"
                _ = file_path.write_text(f"Content {i}")
            
            # Create calculators with different configurations
            calc_cached = SizeCalculator(cache_enabled=True)
            calc_no_cache = SizeCalculator(cache_enabled=False)
            
            # Perform calculations
            size_cached = calc_cached.calculate_size(temp_path)
            size_no_cache = calc_no_cache.calculate_size(temp_path)
            
            # Results should be identical
            assert size_cached == size_no_cache
            
            # Check cache statistics
            cached_stats = calc_cached.get_cache_stats()
            no_cache_stats = calc_no_cache.get_cache_stats()
            
            # Cached calculator should have cache entries
            assert cached_stats["total_cache_entries"] > 0
            
            # Non-cached calculator should have no cache entries
            assert no_cache_stats["total_cache_entries"] == 0
            
            print(f"Cached stats: {cached_stats}")
            print(f"No-cache stats: {no_cache_stats}")