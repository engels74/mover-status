"""Configuration manager module for managing configuration lifecycle."""

from __future__ import annotations

from .config_merger import ConfigMerger
from ..exceptions import ConfigMergeError

__all__ = [
    "ConfigMerger",
    "ConfigMergeError",
]
