"""Sophisticated pattern matching algorithms for process identification and filtering."""

from __future__ import annotations

import fnmatch
import logging
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import TYPE_CHECKING, Callable, override

if TYPE_CHECKING:
    from .detector import ProcessDetector
    from .models import ProcessInfo

logger = logging.getLogger(__name__)


class PatternMatcher(ABC):
    """Abstract base class for process pattern matching.
    
    This class defines the interface for different pattern matching strategies
    including regex, wildcard, and custom matching functions.
    """
    
    @abstractmethod
    def match(self, process: ProcessInfo) -> bool:
        """Check if a process matches the pattern.
        
        Args:
            process: ProcessInfo to check against the pattern
            
        Returns:
            True if process matches the pattern, False otherwise
        """
        pass
    
    @abstractmethod
    def get_pattern(self) -> str:
        """Get the pattern string used for matching.
        
        Returns:
            String representation of the pattern
        """
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get a human-readable description of the matcher.
        
        Returns:
            String description of what the matcher does
        """
        pass


class RegexMatcher(PatternMatcher):
    """Pattern matcher using regular expressions.
    
    Provides flexible pattern matching using Python's re module with support
    for case sensitivity options and compiled regex patterns for performance.
    """
    
    def __init__(self, pattern: str, case_sensitive: bool = False) -> None:
        """Initialize the regex matcher.

        Args:
            pattern: Regular expression pattern to match against
            case_sensitive: Whether matching should be case sensitive

        Raises:
            re.error: If the pattern is not a valid regular expression
        """
        self._pattern: str = pattern
        self._case_sensitive: bool = case_sensitive

        # Compile the regex pattern for performance
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            self._compiled_pattern: re.Pattern[str] = re.compile(pattern, flags)
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}': {e}")
            raise

        logger.debug(f"Created RegexMatcher with pattern '{pattern}', case_sensitive={case_sensitive}")
    
    @override
    def match(self, process: ProcessInfo) -> bool:
        """Check if process matches the regex pattern.
        
        Searches both the process name and command line for matches.
        
        Args:
            process: ProcessInfo to check
            
        Returns:
            True if process matches the regex pattern
        """
        # Check both name and command for matches
        text_to_search = f"{process.name} {process.command}"
        return bool(self._compiled_pattern.search(text_to_search))
    
    @override
    def get_pattern(self) -> str:
        """Get the regex pattern string."""
        return self._pattern
    
    @override
    def get_description(self) -> str:
        """Get description of the regex matcher."""
        case_desc = "case-sensitive" if self._case_sensitive else "case-insensitive"
        return f"Regex matcher (pattern: '{self._pattern}', {case_desc})"


class WildcardMatcher(PatternMatcher):
    """Pattern matcher using shell-style wildcards.
    
    Supports * (matches any sequence) and ? (matches single character) wildcards
    using Python's fnmatch module for familiar shell-like pattern matching.
    """
    
    def __init__(self, pattern: str, case_sensitive: bool = False) -> None:
        """Initialize the wildcard matcher.

        Args:
            pattern: Wildcard pattern (* and ? supported)
            case_sensitive: Whether matching should be case sensitive
        """
        self._pattern: str = pattern
        self._case_sensitive: bool = case_sensitive

        # Convert pattern to lowercase for case-insensitive matching
        self._match_pattern: str = pattern if case_sensitive else pattern.lower()

        logger.debug(f"Created WildcardMatcher with pattern '{pattern}', case_sensitive={case_sensitive}")
    
    @override
    def match(self, process: ProcessInfo) -> bool:
        """Check if process matches the wildcard pattern.
        
        Searches both the process name and command line for matches.
        
        Args:
            process: ProcessInfo to check
            
        Returns:
            True if process matches the wildcard pattern
        """
        # Prepare text for matching
        name = process.name if self._case_sensitive else process.name.lower()
        command = process.command if self._case_sensitive else process.command.lower()
        
        # Check both name and command for matches
        return (fnmatch.fnmatch(name, self._match_pattern) or 
                fnmatch.fnmatch(command, self._match_pattern))
    
    @override
    def get_pattern(self) -> str:
        """Get the wildcard pattern string."""
        return self._pattern
    
    @override
    def get_description(self) -> str:
        """Get description of the wildcard matcher."""
        case_desc = "case-sensitive" if self._case_sensitive else "case-insensitive"
        return f"Wildcard matcher (pattern: '{self._pattern}', {case_desc})"


class CustomMatcher(PatternMatcher):
    """Pattern matcher using custom matching functions.
    
    Allows for complex, user-defined matching logic that can consider any
    aspect of the ProcessInfo object including resource usage, timing, etc.
    """
    
    def __init__(self, match_func: Callable[[ProcessInfo], bool], description: str) -> None:
        """Initialize the custom matcher.

        Args:
            match_func: Function that takes ProcessInfo and returns bool
            description: Human-readable description of the matcher
        """
        self._match_func: Callable[[ProcessInfo], bool] = match_func
        self._description: str = description

        logger.debug(f"Created CustomMatcher: {description}")
    
    @override
    def match(self, process: ProcessInfo) -> bool:
        """Check if process matches using the custom function.
        
        Args:
            process: ProcessInfo to check
            
        Returns:
            Result of the custom matching function
        """
        try:
            return self._match_func(process)
        except Exception as e:
            logger.warning(f"Custom matcher function failed for process {process.pid}: {e}")
            return False
    
    @override
    def get_pattern(self) -> str:
        """Get pattern description for custom matcher."""
        return f"<custom function: {self._description}>"
    
    @override
    def get_description(self) -> str:
        """Get description of the custom matcher."""
        return f"Custom matcher: {self._description}"


class ProcessGrouper:
    """Groups processes based on various criteria.
    
    Provides functionality to group processes by name, pattern matching,
    resource usage, or other custom criteria for analysis and monitoring.
    """
    
    def __init__(self) -> None:
        """Initialize the process grouper."""
        logger.debug("Created ProcessGrouper")
    
    def group_by_name(self, processes: list[ProcessInfo]) -> dict[str, list[ProcessInfo]]:
        """Group processes by their name.
        
        Args:
            processes: List of ProcessInfo objects to group
            
        Returns:
            Dictionary mapping process names to lists of ProcessInfo objects
        """
        groups: dict[str, list[ProcessInfo]] = defaultdict(list)
        
        for process in processes:
            groups[process.name].append(process)
        
        logger.debug(f"Grouped {len(processes)} processes into {len(groups)} name-based groups")
        return dict(groups)
    
    def group_by_pattern(self, processes: list[ProcessInfo], matcher: PatternMatcher) -> tuple[list[ProcessInfo], list[ProcessInfo]]:
        """Group processes by pattern matcher.
        
        Args:
            processes: List of ProcessInfo objects to group
            matcher: PatternMatcher to use for grouping
            
        Returns:
            Tuple of (matched_processes, unmatched_processes)
        """
        matched: list[ProcessInfo] = []
        unmatched: list[ProcessInfo] = []
        
        for process in processes:
            if matcher.match(process):
                matched.append(process)
            else:
                unmatched.append(process)
        
        logger.debug(f"Pattern matching: {len(matched)} matched, {len(unmatched)} unmatched")
        return matched, unmatched
    
    def group_by_resource_usage(self, processes: list[ProcessInfo], cpu_threshold: float = 50.0, memory_threshold: float = 100.0) -> dict[str, list[ProcessInfo]]:
        """Group processes by resource usage levels.
        
        Args:
            processes: List of ProcessInfo objects to group
            cpu_threshold: CPU percentage threshold for high usage
            memory_threshold: Memory MB threshold for high usage
            
        Returns:
            Dictionary with keys: 'high_cpu', 'high_memory', 'high_both', 'normal'
        """
        groups: dict[str, list[ProcessInfo]] = {
            'high_cpu': [],
            'high_memory': [],
            'high_both': [],
            'normal': []
        }
        
        for process in processes:
            cpu_high = process.cpu_percent is not None and process.cpu_percent > cpu_threshold
            memory_high = process.memory_mb is not None and process.memory_mb > memory_threshold
            
            if cpu_high and memory_high:
                groups['high_both'].append(process)
            elif cpu_high:
                groups['high_cpu'].append(process)
            elif memory_high:
                groups['high_memory'].append(process)
            else:
                groups['normal'].append(process)
        
        logger.debug(f"Resource usage grouping: {sum(len(g) for g in groups.values())} processes grouped")
        return groups


class ProcessHierarchyDetector:
    """Detects and maps process hierarchies and relationships.
    
    Analyzes process parent-child relationships and builds hierarchical
    structures for understanding process dependencies and relationships.
    """
    
    def __init__(self) -> None:
        """Initialize the hierarchy detector."""
        logger.debug("Created ProcessHierarchyDetector")
    
    def build_hierarchy(self, processes: list[ProcessInfo]) -> dict[int, list[int]]:
        """Build process hierarchy mapping.
        
        Note: This is a simplified implementation. In a real system,
        you would use psutil to get parent PID information.
        
        Args:
            processes: List of ProcessInfo objects
            
        Returns:
            Dictionary mapping parent PIDs to lists of child PIDs
        """
        # This is a placeholder implementation
        # In reality, you would use psutil.Process(pid).ppid() to get parent PIDs
        hierarchy: dict[int, list[int]] = defaultdict(list[int])

        logger.debug(f"Built hierarchy for {len(processes)} processes")
        return dict(hierarchy)


class FilterableProcessDetector:
    """Process detector with configurable filtering capabilities.
    
    Wraps a base ProcessDetector and applies multiple pattern matchers
    to filter results based on various criteria.
    """
    
    def __init__(self, base_detector: ProcessDetector) -> None:
        """Initialize the filterable detector.

        Args:
            base_detector: Base ProcessDetector to wrap
        """
        self.base_detector: ProcessDetector = base_detector
        self.filters: list[PatternMatcher] = []

        logger.debug("Created FilterableProcessDetector")
    
    def add_filter(self, matcher: PatternMatcher) -> None:
        """Add a pattern matcher filter.
        
        Args:
            matcher: PatternMatcher to add as a filter
        """
        self.filters.append(matcher)
        logger.debug(f"Added filter: {matcher.get_description()}")
    
    def remove_filter(self, matcher: PatternMatcher) -> None:
        """Remove a pattern matcher filter.
        
        Args:
            matcher: PatternMatcher to remove
        """
        if matcher in self.filters:
            self.filters.remove(matcher)
            logger.debug(f"Removed filter: {matcher.get_description()}")
    
    def clear_filters(self) -> None:
        """Remove all filters."""
        self.filters.clear()
        logger.debug("Cleared all filters")
    
    def list_filtered_processes(self) -> list[ProcessInfo]:
        """List processes with all filters applied.
        
        Returns:
            List of ProcessInfo objects that match all filters
        """
        all_processes = self.base_detector.list_processes()
        
        if not self.filters:
            return all_processes

        filtered_processes: list[ProcessInfo] = []
        for process in all_processes:
            # Process must match ALL filters
            if all(matcher.match(process) for matcher in self.filters):
                filtered_processes.append(process)

        logger.debug(f"Filtered {len(all_processes)} processes to {len(filtered_processes)}")
        return filtered_processes
    
    def find_filtered_processes(self, pattern: str) -> list[ProcessInfo]:
        """Find processes matching pattern with filters applied.
        
        Args:
            pattern: Pattern to search for
            
        Returns:
            List of ProcessInfo objects matching pattern and all filters
        """
        matching_processes = self.base_detector.find_processes(pattern)
        
        if not self.filters:
            return matching_processes

        filtered_processes: list[ProcessInfo] = []
        for process in matching_processes:
            if all(matcher.match(process) for matcher in self.filters):
                filtered_processes.append(process)

        logger.debug(f"Pattern search with filters: {len(filtered_processes)} results")
        return filtered_processes
