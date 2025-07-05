"""Mover Status Monitor - A modern Python 3.13 application for monitoring Unraid mover processes."""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "engels74"
__email__ = "141435164+engels74@users.noreply.github.com"
__description__ = "A modern, modular Python 3.13 application that monitors the Unraid mover process, calculates progress metrics, and delivers status notifications through a plugin-based provider system."

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__description__",
    "main",
]


def main() -> None:
    """Main entry point for the mover status monitor application."""
    from mover_status.__main__ import main as _main
    _main()
