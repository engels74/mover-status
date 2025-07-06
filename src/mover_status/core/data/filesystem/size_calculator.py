"""Size calculation for filesystem operations with intelligent caching."""

from __future__ import annotations

import os
from collections.abc import Iterator
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from .scanner import DirectoryScanner

if TYPE_CHECKING:
    pass


class SizeMode(str, Enum):
    """Enumeration for size calculation modes."""
    
    APPARENT = "apparent"  # Apparent size (file content size)
    DISK_USAGE = "disk_usage"  # Actual disk usage (considering filesystem blocks)


class SizeCalculator:
    """Calculator for file and directory sizes with intelligent caching.
    
    Provides efficient size calculation with:
    - Multi-level caching (file-level, directory-level)
    - Cache invalidation based on modification times
    - Integration with DirectoryScanner for exclusion handling
    - Support for different size calculation modes
    - Memory-efficient operation for large directory trees
    """

    def __init__(
        self,
        scanner: DirectoryScanner | None = None,
        mode: SizeMode = SizeMode.APPARENT,
        cache_enabled: bool = True,
    ) -> None:
        """Initialize the size calculator.
        
        Args:
            scanner: Directory scanner instance for file discovery
            mode: Size calculation mode (apparent size vs disk usage)
            cache_enabled: Whether to enable caching for performance
        """
        self.scanner: DirectoryScanner = scanner or DirectoryScanner()
        self.mode: SizeMode = mode
        self.cache_enabled: bool = cache_enabled
        
        # Multi-level caches
        self._file_cache: dict[Path, tuple[int, float]] = {}  # (size, mtime)
        self._directory_cache: dict[Path, tuple[int, float]] = {}  # (size, mtime)

    def calculate_size(self, path: Path) -> int:
        """Calculate the total size of a file or directory.
        
        Args:
            path: Path to calculate size for
            
        Returns:
            Total size in bytes
            
        Raises:
            OSError: If path cannot be accessed
        """
        try:
            if not path.exists():
                raise OSError(f"Path does not exist: {path}")
            
            if path.is_file():
                return self._get_file_size(path)
            elif path.is_dir():
                return self._get_directory_size(path)
            elif path.is_symlink():
                # Handle symlinks - get target size if it exists
                return self._get_symlink_size(path)
            else:
                # Handle other special files (sockets, pipes, etc.)
                return 0
        except (PermissionError, OSError, FileNotFoundError):
            # Return 0 for inaccessible paths instead of raising
            return 0

    def calculate_size_with_progress(self, path: Path) -> Iterator[tuple[int, Path]]:
        """Calculate size with progress reporting.
        
        Args:
            path: Path to calculate size for
            
        Yields:
            Tuples of (cumulative_size, current_file_path)
        """
        if not path.exists():
            raise OSError(f"Path does not exist: {path}")
        
        if path.is_file():
            size = self._get_file_size(path)
            yield size, path
            return
        
        cumulative_size = 0
        for file_path in self.scanner.scan_directory(path):
            try:
                file_size = self._get_file_size(file_path)
                cumulative_size += file_size
                yield cumulative_size, file_path
            except (OSError, PermissionError):
                # Skip files that can't be accessed
                continue

    def invalidate_cache(self, path: Path | None = None) -> None:
        """Invalidate cache entries.
        
        Args:
            path: Specific path to invalidate (None for all)
        """
        if path is None:
            self._file_cache.clear()
            self._directory_cache.clear()
        else:
            # Remove specific path and any subdirectories
            paths_to_remove: list[Path] = []
            for cached_path in self._file_cache:
                if cached_path == path or cached_path.is_relative_to(path):
                    paths_to_remove.append(cached_path)
            for cached_path in paths_to_remove:
                _ = self._file_cache.pop(cached_path, None)
            
            paths_to_remove = []
            for cached_path in self._directory_cache:
                if cached_path == path or cached_path.is_relative_to(path):
                    paths_to_remove.append(cached_path)
            for cached_path in paths_to_remove:
                _ = self._directory_cache.pop(cached_path, None)

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            "file_cache_size": len(self._file_cache),
            "directory_cache_size": len(self._directory_cache),
            "total_cache_entries": len(self._file_cache) + len(self._directory_cache),
        }

    def _get_file_size(self, path: Path) -> int:
        """Get the size of a single file with caching.
        
        Args:
            path: File path
            
        Returns:
            File size in bytes
        """
        if not self.cache_enabled:
            return self._calculate_file_size(path)
        
        try:
            stat = path.stat()
            current_mtime = stat.st_mtime
            
            # Check cache
            if path in self._file_cache:
                cached_size, cached_mtime = self._file_cache[path]
                if cached_mtime == current_mtime:
                    return cached_size
            
            # Calculate and cache
            size = self._calculate_file_size_from_stat(stat)
            self._file_cache[path] = (size, current_mtime)
            return size
            
        except (OSError, PermissionError):
            # Fallback to direct calculation
            return self._calculate_file_size(path)

    def _get_directory_size(self, path: Path) -> int:
        """Get the size of a directory with caching.
        
        Args:
            path: Directory path
            
        Returns:
            Total directory size in bytes
        """
        if not self.cache_enabled:
            return self._calculate_directory_size(path)
        
        try:
            # Get directory modification time
            current_mtime = path.stat().st_mtime
            
            # Check cache
            if path in self._directory_cache:
                cached_size, cached_mtime = self._directory_cache[path]
                if cached_mtime == current_mtime:
                    return cached_size
            
            # Calculate and cache
            size = self._calculate_directory_size(path)
            self._directory_cache[path] = (size, current_mtime)
            return size
            
        except (OSError, PermissionError):
            # Fallback to direct calculation
            return self._calculate_directory_size(path)

    def _calculate_file_size(self, path: Path) -> int:
        """Calculate the size of a single file.
        
        Args:
            path: File path
            
        Returns:
            File size in bytes
        """
        try:
            stat = path.stat()
            return self._calculate_file_size_from_stat(stat)
        except (OSError, PermissionError, FileNotFoundError):
            return 0
    
    def _get_symlink_size(self, path: Path) -> int:
        """Calculate the size of a symlink target.
        
        Args:
            path: Symlink path
            
        Returns:
            Size of the symlink target in bytes, or 0 if broken/inaccessible
        """
        try:
            # Check if the symlink is broken
            if not path.exists():
                return 0
            
            # Get the target of the symlink
            target = path.resolve()
            
            # Recursively calculate size of the target
            if target.is_file():
                return self._get_file_size(target)
            elif target.is_dir():
                return self._get_directory_size(target)
            else:
                return 0
                
        except (OSError, PermissionError, FileNotFoundError, RuntimeError):
            # Handle broken symlinks, permission errors, or resolution errors
            return 0

    def _calculate_file_size_from_stat(self, stat: os.stat_result) -> int:
        """Calculate file size from stat result.
        
        Args:
            stat: os.stat_result object
            
        Returns:
            File size in bytes
        """
        if self.mode == SizeMode.APPARENT:
            return stat.st_size
        else:  # DISK_USAGE
            # Calculate actual disk usage considering filesystem blocks
            # st_blocks is in 512-byte blocks on most systems
            return stat.st_blocks * 512

    def _calculate_directory_size(self, path: Path) -> int:
        """Calculate the total size of a directory.
        
        Args:
            path: Directory path
            
        Returns:
            Total directory size in bytes
        """
        total_size = 0
        for file_path in self.scanner.scan_directory(path):
            try:
                total_size += self._get_file_size(file_path)
            except (OSError, PermissionError):
                # Skip files that can't be accessed
                continue
        return total_size