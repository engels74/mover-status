"""Filesystem operations module for directory scanning and size calculations."""

from __future__ import annotations

from .scanner import DirectoryScanner, ScanStrategy
from .size_calculator import SizeCalculator, SizeMode

__all__ = [
    "DirectoryScanner",
    "ScanStrategy",
    "SizeCalculator",
    "SizeMode",
    # TODO: Add additional filesystem classes when implemented
    # "ExclusionManager",
]
