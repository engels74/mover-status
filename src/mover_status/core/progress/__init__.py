"""Progress calculation module for computing transfer progress and ETC estimates."""

from __future__ import annotations

from .percentage_calculator import ProgressPercentageCalculator
from .transfer_rate_calculator import (
    TransferRateCalculator,
    RateUnit,
    SmoothingMethod,
)

__all__ = [
    "ProgressPercentageCalculator",
    "TransferRateCalculator",
    "RateUnit",
    "SmoothingMethod",
    # TODO: Add more progress classes when implemented
    # "ETCEstimator",
]
