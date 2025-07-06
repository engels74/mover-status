"""Directory scanner for filesystem operations."""

from __future__ import annotations

import fnmatch
from collections import deque
from collections.abc import Iterator
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from .exclusions import DefaultExclusionFilter, ExclusionFilter

if TYPE_CHECKING:
    pass


class ScanStrategy(str, Enum):
    """Enumeration for directory scanning strategies."""
    
    DEPTH_FIRST = "depth_first"
    BREADTH_FIRST = "breadth_first"


class DirectoryScanner:
    """Scanner for traversing directory trees with configurable exclusions.
    
    Provides recursive directory traversal with support for:
    - Exclusion patterns (glob-style)
    - Depth limiting
    - Different scanning strategies (depth-first vs breadth-first)
    - Graceful error handling for permission issues
    - Configurable symlink handling with loop detection
    - Broken symlink detection and handling
    """

    def __init__(
        self,
        exclusions: set[str] | None = None,
        max_depth: int | None = None,
        strategy: ScanStrategy = ScanStrategy.DEPTH_FIRST,
        exclusion_filter: ExclusionFilter | None = None,
        follow_symlinks: bool = True,
        max_symlink_depth: int = 10,
    ) -> None:
        """Initialize the directory scanner.
        
        Args:
            exclusions: Set of glob patterns to exclude from scanning (legacy)
            max_depth: Maximum depth to scan (None for unlimited)
            strategy: Scanning strategy to use
            exclusion_filter: Advanced exclusion filter (overrides exclusions)
            follow_symlinks: Whether to follow symbolic links
            max_symlink_depth: Maximum depth for symlink resolution to prevent loops
        """
        self.exclusions: set[str] = exclusions or {".snapshots", ".Recycle.Bin", "@eaDir"}
        self.max_depth: int | None = max_depth
        self.strategy: ScanStrategy = strategy
        self.follow_symlinks: bool = follow_symlinks
        self.max_symlink_depth: int = max_symlink_depth
        
        # Use provided exclusion filter or create default one
        if exclusion_filter is not None:
            self.exclusion_filter: ExclusionFilter = exclusion_filter
        elif exclusions:
            # Create filter from legacy exclusions
            self.exclusion_filter = ExclusionFilter()
            self.exclusion_filter.add_patterns(exclusions)
        else:
            # Use default exclusions
            self.exclusion_filter = DefaultExclusionFilter()

    def scan_directory(self, path: Path) -> Iterator[Path]:
        """Yield all files in directory tree, respecting exclusions and depth limits.
        
        Args:
            path: Root directory to scan
            
        Yields:
            Path objects for all files found
        """
        # Track visited paths to detect symlink loops
        visited_paths: set[str] = set()
        
        if self.strategy == ScanStrategy.BREADTH_FIRST:
            yield from self._scan_breadth_first(path, visited_paths)
        else:
            yield from self._scan_depth_first(path, current_depth=0, visited_paths=visited_paths)

    def _scan_depth_first(self, path: Path, current_depth: int = 0, visited_paths: set[str] | None = None) -> Iterator[Path]:
        """Perform depth-first directory traversal.
        
        Args:
            path: Directory path to scan
            current_depth: Current depth in the traversal
            visited_paths: Set of visited paths to detect symlink loops
            
        Yields:
            Path objects for all files found
        """
        if visited_paths is None:
            visited_paths = set()
            
        # Check depth limit
        if self.max_depth is not None and current_depth > self.max_depth:
            return

        try:
            for item in path.iterdir():
                if self._should_exclude(item):
                    continue

                # Handle files (including symlinks to files)
                if self._is_file_like(item):
                    yield item
                    
                # Handle directories (including symlinks to directories)
                elif self._is_directory_like(item):
                    # Check for symlink loops if following symlinks
                    if self.follow_symlinks and item.is_symlink():
                        if not self._should_follow_symlink(item, visited_paths):
                            continue
                    
                    yield from self._scan_depth_first(item, current_depth + 1, visited_paths)
                    
        except (PermissionError, OSError, FileNotFoundError):
            # Handle permission errors, OS errors, and broken symlinks gracefully
            pass

    def _scan_breadth_first(self, path: Path, visited_paths: set[str] | None = None) -> Iterator[Path]:
        """Perform breadth-first directory traversal.
        
        Args:
            path: Root directory to scan
            visited_paths: Set of visited paths to detect symlink loops
            
        Yields:
            Path objects for all files found
        """
        if visited_paths is None:
            visited_paths = set()
            
        # Queue of (path, depth) tuples
        queue: deque[tuple[Path, int]] = deque([(path, 0)])
        
        while queue:
            current_path, current_depth = queue.popleft()
            
            # Check depth limit
            if self.max_depth is not None and current_depth > self.max_depth:
                continue

            try:
                for item in current_path.iterdir():
                    if self._should_exclude(item):
                        continue

                    # Handle files (including symlinks to files)
                    if self._is_file_like(item):
                        yield item
                        
                    # Handle directories (including symlinks to directories)
                    elif self._is_directory_like(item):
                        # Check for symlink loops if following symlinks
                        if self.follow_symlinks and item.is_symlink():
                            if not self._should_follow_symlink(item, visited_paths):
                                continue
                        
                        queue.append((item, current_depth + 1))
                        
            except (PermissionError, OSError, FileNotFoundError):
                # Handle permission errors, OS errors, and broken symlinks gracefully
                continue

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded based on exclusion patterns.
        
        Args:
            path: Path to check
            
        Returns:
            True if path should be excluded, False otherwise
        """
        # Use new exclusion filter if available, fallback to legacy method
        if hasattr(self, 'exclusion_filter'):
            return self.exclusion_filter.should_exclude(path)
        
        # Legacy fallback
        return any(
            fnmatch.fnmatch(path.name, pattern) 
            for pattern in self.exclusions
        )
    
    def _is_file_like(self, path: Path) -> bool:
        """Check if a path is a file or a symlink to a file.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is a file or valid symlink to a file, False otherwise
        """
        try:
            if path.is_file():
                return True
            
            # Check if it's a symlink to a file
            if self.follow_symlinks and path.is_symlink():
                try:
                    # Use stat() to follow symlinks and check if target is a file
                    stat_result = path.stat()
                    return stat_result.st_mode & 0o170000 == 0o100000  # S_IFREG
                except (OSError, FileNotFoundError):
                    # Broken symlink or permission error
                    return False
            
            return False
        except (OSError, FileNotFoundError):
            # Handle permission errors or broken symlinks
            return False
    
    def _is_directory_like(self, path: Path) -> bool:
        """Check if a path is a directory or a symlink to a directory.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is a directory or valid symlink to a directory, False otherwise
        """
        try:
            if path.is_dir():
                return True
            
            # Check if it's a symlink to a directory
            if self.follow_symlinks and path.is_symlink():
                try:
                    # Use stat() to follow symlinks and check if target is a directory
                    stat_result = path.stat()
                    return stat_result.st_mode & 0o170000 == 0o040000  # S_IFDIR
                except (OSError, FileNotFoundError):
                    # Broken symlink or permission error
                    return False
            
            return False
        except (OSError, FileNotFoundError):
            # Handle permission errors or broken symlinks
            return False
    
    def _should_follow_symlink(self, path: Path, visited_paths: set[str]) -> bool:
        """Check if a symlink should be followed, preventing loops.
        
        Args:
            path: Symlink path to check
            visited_paths: Set of visited paths to detect loops
            
        Returns:
            True if symlink should be followed, False otherwise
        """
        if not self.follow_symlinks:
            return False
        
        try:
            # Get the resolved path to check for loops
            resolved_path = str(path.resolve())
            
            # Check if we've already visited this path
            if resolved_path in visited_paths:
                return False
            
            # Check symlink depth to prevent infinite loops
            if len(visited_paths) >= self.max_symlink_depth:
                return False
            
            # Add to visited paths
            visited_paths.add(resolved_path)
            return True
            
        except (OSError, FileNotFoundError, RuntimeError):
            # Handle permission errors, broken symlinks, or resolution errors
            return False