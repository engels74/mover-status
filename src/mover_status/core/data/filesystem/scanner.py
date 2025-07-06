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
    """

    def __init__(
        self,
        exclusions: set[str] | None = None,
        max_depth: int | None = None,
        strategy: ScanStrategy = ScanStrategy.DEPTH_FIRST,
        exclusion_filter: ExclusionFilter | None = None,
    ) -> None:
        """Initialize the directory scanner.
        
        Args:
            exclusions: Set of glob patterns to exclude from scanning (legacy)
            max_depth: Maximum depth to scan (None for unlimited)
            strategy: Scanning strategy to use
            exclusion_filter: Advanced exclusion filter (overrides exclusions)
        """
        self.exclusions: set[str] = exclusions or {".snapshots", ".Recycle.Bin", "@eaDir"}
        self.max_depth: int | None = max_depth
        self.strategy: ScanStrategy = strategy
        
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
        if self.strategy == ScanStrategy.BREADTH_FIRST:
            yield from self._scan_breadth_first(path)
        else:
            yield from self._scan_depth_first(path, current_depth=0)

    def _scan_depth_first(self, path: Path, current_depth: int = 0) -> Iterator[Path]:
        """Perform depth-first directory traversal.
        
        Args:
            path: Directory path to scan
            current_depth: Current depth in the traversal
            
        Yields:
            Path objects for all files found
        """
        # Check depth limit
        if self.max_depth is not None and current_depth > self.max_depth:
            return

        try:
            for item in path.iterdir():
                if self._should_exclude(item):
                    continue

                if item.is_file():
                    yield item
                elif item.is_dir():
                    yield from self._scan_depth_first(item, current_depth + 1)
        except (PermissionError, OSError):
            # Handle permission errors and other OS errors gracefully
            pass

    def _scan_breadth_first(self, path: Path) -> Iterator[Path]:
        """Perform breadth-first directory traversal.
        
        Args:
            path: Root directory to scan
            
        Yields:
            Path objects for all files found
        """
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

                    if item.is_file():
                        yield item
                    elif item.is_dir():
                        queue.append((item, current_depth + 1))
            except (PermissionError, OSError):
                # Handle permission errors and other OS errors gracefully
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