"""Filesystem operations module for directory scanning and size calculations."""

from __future__ import annotations

from .scanner import DirectoryScanner, ScanStrategy

__all__ = [
    "DirectoryScanner",
    "ScanStrategy",
    # TODO: Add additional filesystem classes when implemented
    # "SizeCalculator",
    # "ExclusionManager",
]
