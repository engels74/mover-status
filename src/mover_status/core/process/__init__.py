"""Process detection module for identifying and monitoring mover processes."""

from __future__ import annotations

from .detector import ProcessDetector, ProcessFilter, ProcessMonitor
from .error_handling import (
    ProcessDetectionError,
    ProcessPermissionError,
    ProcessNotFoundError,
    ProcessAccessDeniedError,
    ProcessTimeoutError,
    SystemResourceError,
    ErrorHandler,
    PermissionManager,
    RetryManager,
    GracefulDegradationManager,
)
from .models import ProcessInfo, ProcessStatus
from .pattern_matcher import (
    PatternMatcher,
    RegexMatcher,
    WildcardMatcher,
    CustomMatcher,
    ProcessGrouper,
    ProcessHierarchyDetector,
    FilterableProcessDetector,
)
from .unraid_detector import UnraidMoverDetector

__all__ = [
    "ProcessDetector",
    "ProcessFilter",
    "ProcessMonitor",
    "ProcessInfo",
    "ProcessStatus",
    "PatternMatcher",
    "RegexMatcher",
    "WildcardMatcher",
    "CustomMatcher",
    "ProcessGrouper",
    "ProcessHierarchyDetector",
    "FilterableProcessDetector",
    "UnraidMoverDetector",
    "ProcessDetectionError",
    "ProcessPermissionError",
    "ProcessNotFoundError",
    "ProcessAccessDeniedError",
    "ProcessTimeoutError",
    "SystemResourceError",
    "ErrorHandler",
    "PermissionManager",
    "RetryManager",
    "GracefulDegradationManager",
]
