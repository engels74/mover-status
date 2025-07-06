"""Test suite for process pattern matching logic."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from mover_status.core.process.models import ProcessInfo, ProcessStatus
from mover_status.core.process.pattern_matcher import (
    PatternMatcher,
    RegexMatcher,
    WildcardMatcher,
    CustomMatcher,
    ProcessGrouper,
    ProcessHierarchyDetector,
    FilterableProcessDetector,
)

if TYPE_CHECKING:
    pass


class TestPatternMatcher:
    """Test the abstract PatternMatcher interface."""

    def test_pattern_matcher_is_abstract(self) -> None:
        """Test that PatternMatcher is an abstract base class."""
        from abc import ABC
        assert issubclass(PatternMatcher, ABC)
        
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            _ = PatternMatcher()  # type: ignore[abstract]

    def test_pattern_matcher_has_required_methods(self) -> None:
        """Test that PatternMatcher defines required abstract methods."""
        abstract_methods = PatternMatcher.__abstractmethods__
        
        expected_methods = {
            'match',
            'get_pattern',
            'get_description'
        }
        
        assert abstract_methods == expected_methods


class TestRegexMatcher:
    """Test the RegexMatcher implementation."""

    def test_regex_matcher_creation(self) -> None:
        """Test creating a RegexMatcher."""
        pattern = r"mover.*"
        matcher = RegexMatcher(pattern)
        
        assert matcher.get_pattern() == pattern
        assert "regex" in matcher.get_description().lower()

    def test_regex_matcher_valid_pattern(self) -> None:
        """Test RegexMatcher with valid regex pattern."""
        matcher = RegexMatcher(r"mover\d*")
        
        # Create test processes
        mover_process = self._create_process(123, "mover", "/usr/local/sbin/mover")
        mover2_process = self._create_process(124, "mover2", "/usr/local/sbin/mover2")
        other_process = self._create_process(125, "bash", "/bin/bash")
        
        assert matcher.match(mover_process)
        assert matcher.match(mover2_process)
        assert not matcher.match(other_process)

    def test_regex_matcher_invalid_pattern(self) -> None:
        """Test RegexMatcher with invalid regex pattern."""
        with pytest.raises(re.error):
            _ = RegexMatcher(r"[invalid")

    def test_regex_matcher_case_sensitivity(self) -> None:
        """Test RegexMatcher case sensitivity options."""
        case_sensitive_matcher = RegexMatcher(r"MOVER", case_sensitive=True)
        case_insensitive_matcher = RegexMatcher(r"MOVER", case_sensitive=False)
        
        process = self._create_process(123, "mover", "/usr/local/sbin/mover")
        
        assert not case_sensitive_matcher.match(process)
        assert case_insensitive_matcher.match(process)

    def _create_process(self, pid: int, name: str, command: str) -> ProcessInfo:
        """Helper to create ProcessInfo for testing."""
        return ProcessInfo(
            pid=pid,
            name=name,
            command=command,
            start_time=datetime.now(),
            status=ProcessStatus.RUNNING
        )


class TestWildcardMatcher:
    """Test the WildcardMatcher implementation."""

    def test_wildcard_matcher_creation(self) -> None:
        """Test creating a WildcardMatcher."""
        pattern = "mover*"
        matcher = WildcardMatcher(pattern)
        
        assert matcher.get_pattern() == pattern
        assert "wildcard" in matcher.get_description().lower()

    def test_wildcard_matcher_asterisk(self) -> None:
        """Test WildcardMatcher with asterisk wildcard."""
        matcher = WildcardMatcher("mover*")
        
        mover_process = self._create_process(123, "mover", "/usr/local/sbin/mover")
        mover_backup = self._create_process(124, "mover-backup", "/usr/local/sbin/mover-backup")
        other_process = self._create_process(125, "bash", "/bin/bash")
        
        assert matcher.match(mover_process)
        assert matcher.match(mover_backup)
        assert not matcher.match(other_process)

    def test_wildcard_matcher_question_mark(self) -> None:
        """Test WildcardMatcher with question mark wildcard."""
        matcher = WildcardMatcher("mover?")
        
        mover1 = self._create_process(123, "mover1", "/usr/local/sbin/mover1")
        mover2 = self._create_process(124, "mover2", "/usr/local/sbin/mover2")
        mover_long = self._create_process(125, "mover-backup", "/usr/local/sbin/mover-backup")
        
        assert matcher.match(mover1)
        assert matcher.match(mover2)
        assert not matcher.match(mover_long)

    def _create_process(self, pid: int, name: str, command: str) -> ProcessInfo:
        """Helper to create ProcessInfo for testing."""
        return ProcessInfo(
            pid=pid,
            name=name,
            command=command,
            start_time=datetime.now(),
            status=ProcessStatus.RUNNING
        )


class TestCustomMatcher:
    """Test the CustomMatcher implementation."""

    def test_custom_matcher_creation(self) -> None:
        """Test creating a CustomMatcher with custom function."""
        def is_mover(process: ProcessInfo) -> bool:
            return "mover" in process.name.lower()
        
        matcher = CustomMatcher(is_mover, "Custom mover matcher")
        
        assert matcher.get_description() == "Custom matcher: Custom mover matcher"

    def test_custom_matcher_function(self) -> None:
        """Test CustomMatcher with custom matching function."""
        def high_cpu_process(process: ProcessInfo) -> bool:
            return process.cpu_percent is not None and process.cpu_percent > 50.0
        
        matcher = CustomMatcher(high_cpu_process, "High CPU processes")
        
        high_cpu = ProcessInfo(
            pid=123, name="test", command="test", start_time=datetime.now(),
            cpu_percent=75.0
        )
        low_cpu = ProcessInfo(
            pid=124, name="test2", command="test2", start_time=datetime.now(),
            cpu_percent=25.0
        )
        no_cpu = ProcessInfo(
            pid=125, name="test3", command="test3", start_time=datetime.now()
        )
        
        assert matcher.match(high_cpu)
        assert not matcher.match(low_cpu)
        assert not matcher.match(no_cpu)


class TestProcessGrouper:
    """Test the ProcessGrouper functionality."""

    def test_process_grouper_creation(self) -> None:
        """Test creating a ProcessGrouper."""
        grouper = ProcessGrouper()
        assert grouper is not None

    def test_group_by_name(self) -> None:
        """Test grouping processes by name."""
        grouper = ProcessGrouper()
        
        processes = [
            self._create_process(123, "mover", "/usr/local/sbin/mover"),
            self._create_process(124, "mover", "/usr/local/sbin/mover2"),
            self._create_process(125, "bash", "/bin/bash"),
            self._create_process(126, "bash", "/bin/bash -c 'test'"),
        ]
        
        groups = grouper.group_by_name(processes)
        
        assert len(groups) == 2
        assert "mover" in groups
        assert "bash" in groups
        assert len(groups["mover"]) == 2
        assert len(groups["bash"]) == 2

    def test_group_by_pattern(self) -> None:
        """Test grouping processes by pattern matcher."""
        grouper = ProcessGrouper()
        matcher = WildcardMatcher("mover*")
        
        processes = [
            self._create_process(123, "mover", "/usr/local/sbin/mover"),
            self._create_process(124, "mover-backup", "/usr/local/sbin/mover-backup"),
            self._create_process(125, "bash", "/bin/bash"),
        ]
        
        matched, unmatched = grouper.group_by_pattern(processes, matcher)
        
        assert len(matched) == 2
        assert len(unmatched) == 1
        assert matched[0].name == "mover"
        assert matched[1].name == "mover-backup"
        assert unmatched[0].name == "bash"

    def _create_process(self, pid: int, name: str, command: str) -> ProcessInfo:
        """Helper to create ProcessInfo for testing."""
        return ProcessInfo(
            pid=pid,
            name=name,
            command=command,
            start_time=datetime.now(),
            status=ProcessStatus.RUNNING
        )


class TestProcessHierarchyDetector:
    """Test the ProcessHierarchyDetector functionality."""

    def test_hierarchy_detector_creation(self) -> None:
        """Test creating a ProcessHierarchyDetector."""
        detector = ProcessHierarchyDetector()
        assert detector is not None

    def test_detect_parent_child_relationships(self) -> None:
        """Test detecting parent-child relationships."""
        detector = ProcessHierarchyDetector()
        
        # Mock processes with parent-child relationships
        parent = ProcessInfo(
            pid=100, name="parent", command="/usr/bin/parent",
            start_time=datetime.now(), status=ProcessStatus.RUNNING
        )
        child1 = ProcessInfo(
            pid=101, name="child1", command="/usr/bin/child1",
            start_time=datetime.now(), status=ProcessStatus.RUNNING
        )
        child2 = ProcessInfo(
            pid=102, name="child2", command="/usr/bin/child2",
            start_time=datetime.now(), status=ProcessStatus.RUNNING
        )
        
        processes = [parent, child1, child2]
        
        # Mock the hierarchy detection (would normally use psutil)
        hierarchy = detector.build_hierarchy(processes)
        
        assert hierarchy is not None
        assert isinstance(hierarchy, dict)


class TestFilterableProcessDetector:
    """Test the FilterableProcessDetector functionality."""

    def test_filterable_detector_creation(self) -> None:
        """Test creating a FilterableProcessDetector."""
        base_detector = Mock()
        detector = FilterableProcessDetector(base_detector)
        
        assert detector.base_detector == base_detector

    def test_add_filter(self) -> None:
        """Test adding filters to the detector."""
        base_detector = Mock()
        detector = FilterableProcessDetector(base_detector)
        
        matcher = WildcardMatcher("mover*")
        detector.add_filter(matcher)
        
        assert len(detector.filters) == 1
        assert detector.filters[0] == matcher

    def test_filtered_process_detection(self) -> None:
        """Test process detection with filters applied."""
        base_detector = Mock()
        base_detector.list_processes.return_value = [  # pyright: ignore[reportAny]
            ProcessInfo(pid=123, name="mover", command="/usr/local/sbin/mover", start_time=datetime.now()),
            ProcessInfo(pid=124, name="bash", command="/bin/bash", start_time=datetime.now()),
            ProcessInfo(pid=125, name="mover-backup", command="/usr/local/sbin/mover-backup", start_time=datetime.now()),
        ]
        
        detector = FilterableProcessDetector(base_detector)
        matcher = WildcardMatcher("mover*")
        detector.add_filter(matcher)
        
        filtered_processes = detector.list_filtered_processes()
        
        assert len(filtered_processes) == 2
        assert all("mover" in p.name for p in filtered_processes)
