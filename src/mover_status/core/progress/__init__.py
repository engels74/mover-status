"""Progress calculation module for computing transfer progress and ETC estimates."""

from __future__ import annotations

from .percentage_calculator import ProgressPercentageCalculator
from .transfer_rate_calculator import (
    TransferRateCalculator,
    RateUnit,
    SmoothingMethod,
)
from .etc_estimator import (
    ETCEstimator,
    EstimationMethod,
    ETCResult,
)
from .history_manager import (
    HistoryManager,
    MovingAverageType,
    RetentionPolicy,
    DataPoint,
    HistoryStats,
)
from .calculator import (
    ProgressCalculator,
    ProgressMetrics,
)

__all__ = [
    "ProgressPercentageCalculator",
    "TransferRateCalculator",
    "RateUnit",
    "SmoothingMethod",
    "ETCEstimator",
    "EstimationMethod",
    "ETCResult",
    "HistoryManager",
    "MovingAverageType",
    "RetentionPolicy",
    "DataPoint",
    "HistoryStats",
    "ProgressCalculator",
    "ProgressMetrics",
]
