"""
Core functionality for the Mover Status Monitor.

This package provides the core functionality for the Mover Status Monitor,
including monitoring, calculation, version checking, and dry run simulation.

The core module has been reorganized for better separation of concerns:
- mover_status.core.monitoring: Core monitoring logic (provider-agnostic)
- mover_status.core.simulation: Dry run simulation (provider-agnostic)
- mover_status.core.calculation: Calculation utilities
- mover_status.core.version: Version checking

This module maintains backward compatibility while providing access to the
new modular structure.
"""

from mover_status.core.calculation import format_bytes
from mover_status.core.version import (
    get_current_version,
    get_latest_version,
    compare_versions,
    check_for_updates,
)
from mover_status.core.monitor import MonitorSession
from mover_status.core.dry_run import (
    generate_test_notification,
    simulate_monitoring_session,
    run_dry_mode,
)

# New modular structure imports
from mover_status.core import monitoring
from mover_status.core import simulation
from mover_status.core import calculation
from mover_status.core import version

__all__ = [
    # Calculation functions
    "format_bytes",

    # Version functions
    "get_current_version",
    "get_latest_version",
    "compare_versions",
    "check_for_updates",

    # Monitoring classes
    "MonitorSession",

    # Dry run functions
    "generate_test_notification",
    "simulate_monitoring_session",
    "run_dry_mode",

    # New modular structure
    "monitoring",
    "simulation",
    "calculation",
    "version",
]