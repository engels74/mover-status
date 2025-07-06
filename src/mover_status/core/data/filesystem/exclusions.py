"""Advanced exclusion pattern system for filesystem operations."""

from __future__ import annotations

import fnmatch
import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class PatternType(str, Enum):
    """Enumeration for different pattern types."""
    
    GLOB = "glob"
    REGEX = "regex"
    EXTENSION = "extension"
    EXACT = "exact"
    GITIGNORE = "gitignore"


class ExclusionPattern(ABC):
    """Base class for exclusion patterns."""
    
    def __init__(self, pattern: str, case_sensitive: bool = True) -> None:
        """Initialize the exclusion pattern.
        
        Args:
            pattern: The pattern string
            case_sensitive: Whether pattern matching is case-sensitive
        """
        self.pattern: str = pattern
        self.case_sensitive: bool = case_sensitive
    
    @abstractmethod
    def matches(self, path: Path) -> bool:
        """Check if the pattern matches the given path.
        
        Args:
            path: Path to check
            
        Returns:
            True if the pattern matches, False otherwise
        """
        pass
    
    @abstractmethod
    def compile(self) -> None:
        """Compile the pattern for performance optimization."""
        pass


class GlobPattern(ExclusionPattern):
    """Glob-style pattern matcher using fnmatch."""
    
    def __init__(self, pattern: str, case_sensitive: bool = True) -> None:
        """Initialize the glob pattern."""
        super().__init__(pattern, case_sensitive)
        self._compiled: str | None = None
    
    def compile(self) -> None:
        """Compile the glob pattern."""
        if not self.case_sensitive:
            self._compiled = self.pattern.lower()
        else:
            self._compiled = self.pattern
    
    def matches(self, path: Path) -> bool:
        """Check if the glob pattern matches the path.
        
        Args:
            path: Path to check
            
        Returns:
            True if the pattern matches, False otherwise
        """
        if self._compiled is None:
            self.compile()
        
        target = path.name if self.case_sensitive else path.name.lower()
        assert self._compiled is not None  # Should never be None after compile()
        return fnmatch.fnmatch(target, self._compiled)


class RegexPattern(ExclusionPattern):
    """Regular expression pattern matcher."""
    
    def __init__(self, pattern: str, case_sensitive: bool = True) -> None:
        """Initialize the regex pattern."""
        super().__init__(pattern, case_sensitive)
        self._compiled: re.Pattern[str] | None = None
    
    def compile(self) -> None:
        """Compile the regex pattern."""
        flags = 0 if self.case_sensitive else re.IGNORECASE
        self._compiled = re.compile(self.pattern, flags)
    
    def matches(self, path: Path) -> bool:
        """Check if the regex pattern matches the path.
        
        Args:
            path: Path to check
            
        Returns:
            True if the pattern matches, False otherwise
        """
        if self._compiled is None:
            self.compile()
        
        assert self._compiled is not None  # Should never be None after compile()
        return bool(self._compiled.search(path.name))


class ExtensionPattern(ExclusionPattern):
    """File extension pattern matcher."""
    
    def __init__(self, pattern: str, case_sensitive: bool = True) -> None:
        """Initialize the extension pattern."""
        super().__init__(pattern, case_sensitive)
        self._compiled: str | None = None
    
    def compile(self) -> None:
        """Compile the extension pattern."""
        # Normalize extension (ensure it starts with a dot)
        ext = self.pattern if self.pattern.startswith('.') else f'.{self.pattern}'
        self._compiled = ext if self.case_sensitive else ext.lower()
    
    def matches(self, path: Path) -> bool:
        """Check if the extension pattern matches the path.
        
        Args:
            path: Path to check
            
        Returns:
            True if the pattern matches, False otherwise
        """
        if self._compiled is None:
            self.compile()
        
        # Only match files, not directories
        if path.is_dir():
            return False
        
        target_ext = path.suffix if self.case_sensitive else path.suffix.lower()
        assert self._compiled is not None  # Should never be None after compile()
        return target_ext == self._compiled


class ExactPattern(ExclusionPattern):
    """Exact name pattern matcher."""
    
    def __init__(self, pattern: str, case_sensitive: bool = True) -> None:
        """Initialize the exact pattern."""
        super().__init__(pattern, case_sensitive)
        self._compiled: str | None = None
    
    def compile(self) -> None:
        """Compile the exact pattern."""
        self._compiled = self.pattern if self.case_sensitive else self.pattern.lower()
    
    def matches(self, path: Path) -> bool:
        """Check if the exact pattern matches the path.
        
        Args:
            path: Path to check
            
        Returns:
            True if the pattern matches, False otherwise
        """
        if self._compiled is None:
            self.compile()
        
        target = path.name if self.case_sensitive else path.name.lower()
        assert self._compiled is not None  # Should never be None after compile()
        return target == self._compiled


class GitignorePattern(ExclusionPattern):
    """Git-style ignore pattern matcher."""
    
    def __init__(self, pattern: str, case_sensitive: bool = True) -> None:
        """Initialize the gitignore pattern."""
        super().__init__(pattern, case_sensitive)
        self._compiled: re.Pattern[str] | None = None
    
    def compile(self) -> None:
        """Compile the gitignore pattern."""
        # Convert gitignore pattern to regex
        pattern = self.pattern
        
        # Handle negation (not implemented in this basic version)
        if pattern.startswith('!'):
            pattern = pattern[1:]
        
        # Handle directory-only patterns
        if pattern.endswith('/'):
            pattern = pattern[:-1]
        
        # Convert glob patterns to regex
        pattern = pattern.replace('.', r'\.')
        pattern = pattern.replace('*', '[^/]*')
        pattern = pattern.replace('?', '[^/]')
        
        # Handle ** patterns (match any path)
        pattern = pattern.replace('[^/]*[^/]*', '.*')
        
        flags = 0 if self.case_sensitive else re.IGNORECASE
        self._compiled = re.compile(f'^{pattern}$', flags)
    
    def matches(self, path: Path) -> bool:
        """Check if the gitignore pattern matches the path.
        
        Args:
            path: Path to check
            
        Returns:
            True if the pattern matches, False otherwise
        """
        if self._compiled is None:
            self.compile()
        
        assert self._compiled is not None  # Should never be None after compile()
        return bool(self._compiled.match(path.name))


class ExclusionFilter:
    """Advanced exclusion filter system supporting multiple pattern types."""
    
    def __init__(self, case_sensitive: bool = True) -> None:
        """Initialize the exclusion filter.
        
        Args:
            case_sensitive: Whether pattern matching is case-sensitive
        """
        self.case_sensitive: bool = case_sensitive
        self._patterns: list[ExclusionPattern] = []
        self._compiled: bool = False
    
    def add_pattern(self, pattern: str, pattern_type: PatternType = PatternType.GLOB) -> None:
        """Add an exclusion pattern.
        
        Args:
            pattern: Pattern string
            pattern_type: Type of pattern to add
        """
        pattern_class = self._get_pattern_class(pattern_type)
        exclusion_pattern = pattern_class(pattern, self.case_sensitive)
        self._patterns.append(exclusion_pattern)
        self._compiled = False
    
    def add_patterns(self, patterns: Iterable[str], pattern_type: PatternType = PatternType.GLOB) -> None:
        """Add multiple exclusion patterns.
        
        Args:
            patterns: Iterable of pattern strings
            pattern_type: Type of patterns to add
        """
        for pattern in patterns:
            self.add_pattern(pattern, pattern_type)
    
    def add_extensions(self, extensions: Iterable[str]) -> None:
        """Add file extension patterns.
        
        Args:
            extensions: Iterable of file extensions (with or without leading dot)
        """
        self.add_patterns(extensions, PatternType.EXTENSION)
    
    def add_exact_names(self, names: Iterable[str]) -> None:
        """Add exact name patterns.
        
        Args:
            names: Iterable of exact names to exclude
        """
        self.add_patterns(names, PatternType.EXACT)
    
    def add_regex_patterns(self, patterns: Iterable[str]) -> None:
        """Add regular expression patterns.
        
        Args:
            patterns: Iterable of regex pattern strings
        """
        self.add_patterns(patterns, PatternType.REGEX)
    
    def add_gitignore_patterns(self, patterns: Iterable[str]) -> None:
        """Add git-style ignore patterns.
        
        Args:
            patterns: Iterable of gitignore pattern strings
        """
        self.add_patterns(patterns, PatternType.GITIGNORE)
    
    def compile(self) -> None:
        """Compile all patterns for performance optimization."""
        for pattern in self._patterns:
            pattern.compile()
        self._compiled = True
    
    def should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded.
        
        Args:
            path: Path to check
            
        Returns:
            True if the path should be excluded, False otherwise
        """
        if not self._compiled:
            self.compile()
        
        return any(pattern.matches(path) for pattern in self._patterns)
    
    def clear(self) -> None:
        """Clear all exclusion patterns."""
        self._patterns.clear()
        self._compiled = False
    
    def get_pattern_count(self) -> int:
        """Get the number of patterns configured.
        
        Returns:
            Number of patterns
        """
        return len(self._patterns)
    
    def _get_pattern_class(self, pattern_type: PatternType) -> type[ExclusionPattern]:
        """Get the pattern class for the given pattern type.
        
        Args:
            pattern_type: Type of pattern
            
        Returns:
            Pattern class
        """
        pattern_classes = {
            PatternType.GLOB: GlobPattern,
            PatternType.REGEX: RegexPattern,
            PatternType.EXTENSION: ExtensionPattern,
            PatternType.EXACT: ExactPattern,
            PatternType.GITIGNORE: GitignorePattern,
        }
        
        return pattern_classes[pattern_type]


class DefaultExclusionFilter(ExclusionFilter):
    """Exclusion filter with sensible defaults for common use cases."""
    
    def __init__(self, case_sensitive: bool = True) -> None:
        """Initialize with default exclusion patterns.
        
        Args:
            case_sensitive: Whether pattern matching is case-sensitive
        """
        super().__init__(case_sensitive)
        self._add_default_patterns()
    
    def _add_default_patterns(self) -> None:
        """Add default exclusion patterns."""
        # Common system directories
        self.add_exact_names([
            ".snapshots",
            ".Recycle.Bin",
            "@eaDir",
            "System Volume Information",
            "$RECYCLE.BIN",
            "lost+found",
            ".Trash",
            ".DS_Store",
        ])
        
        # Common cache and temp directories
        self.add_glob_patterns([
            ".cache",
            ".tmp",
            "*.tmp",
            "*.temp",
            "thumbs.db",
            "desktop.ini",
        ])
        
        # Development directories
        self.add_exact_names([
            ".git",
            ".svn",
            ".hg",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".coverage",
            ".tox",
            ".venv",
            "venv",
            ".env",
        ])
    
    def add_glob_patterns(self, patterns: Iterable[str]) -> None:
        """Add glob patterns (convenience method).
        
        Args:
            patterns: Iterable of glob pattern strings
        """
        self.add_patterns(patterns, PatternType.GLOB)