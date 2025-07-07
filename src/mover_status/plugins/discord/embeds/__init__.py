"""Discord embed generation for rich notifications."""

from __future__ import annotations

from mover_status.plugins.discord.embeds.generators import (
    EmbedGenerator,
    ProgressEmbedGenerator,
    ProcessStatusEmbedGenerator,
    StatusEmbedGenerator,
)
from mover_status.plugins.discord.embeds.progress_visualization import (
    EnhancedProgressBarGenerator,
    MilestoneTracker,
    ProgressVisualizationConfig,
    StatusBadgeGenerator,
    TimelineVisualizationGenerator,
    TransferHealth,
    TransferStage,
)

__all__ = [
    "EmbedGenerator",
    "ProgressEmbedGenerator", 
    "ProcessStatusEmbedGenerator",
    "StatusEmbedGenerator",
    # Progress visualization components
    "EnhancedProgressBarGenerator",
    "MilestoneTracker",
    "ProgressVisualizationConfig",
    "StatusBadgeGenerator",
    "TimelineVisualizationGenerator",
    "TransferHealth",
    "TransferStage",
]