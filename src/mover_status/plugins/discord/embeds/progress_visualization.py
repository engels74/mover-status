"""Progress visualization components for Discord embeds."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mover_status.notifications.models.message import Message


class TransferHealth(Enum):
    """Transfer health status levels."""
    
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    CRITICAL = "critical"


class TransferStage(Enum):
    """Transfer stage indicators."""
    
    INITIALIZING = "initializing"
    TRANSFERRING = "transferring"
    VERIFYING = "verifying"
    COMPLETING = "completing"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class ProgressVisualizationConfig:
    """Configuration for progress visualization components."""
    
    # Status badge settings
    use_status_badges: bool = True
    use_health_indicators: bool = True
    use_stage_badges: bool = True
    
    # Progress bar settings
    use_enhanced_progress_bars: bool = True
    progress_bar_length: int = 20
    use_color_coding: bool = True
    show_health_segments: bool = True
    
    # Timeline settings
    show_trend_indicators: bool = True
    show_rate_history: bool = True
    show_milestones: bool = True
    
    # Milestone settings
    milestone_thresholds: list[float] | None = None
    
    def __post_init__(self) -> None:
        """Initialize default milestone thresholds."""
        if self.milestone_thresholds is None:
            self.milestone_thresholds = [25.0, 50.0, 75.0, 90.0, 95.0]


class StatusBadgeGenerator:
    """Generates status badges and health indicators for Discord embeds."""
    
    def __init__(self, config: ProgressVisualizationConfig) -> None:
        """Initialize status badge generator.
        
        Args:
            config: Visualization configuration
        """
        self.config: ProgressVisualizationConfig = config
        
        # Status badges mapping
        self._status_badges: dict[str, str] = {
            "started": "🟢",
            "in_progress": "🔵",
            "completed": "✅",
            "failed": "❌",
            "paused": "⏸️",
            "cancelled": "⏹️",
            "stalled": "⚠️",
            "retrying": "🔄",
        }
        
        # Health indicators
        self._health_indicators: dict[TransferHealth, str] = {
            TransferHealth.EXCELLENT: "💚",
            TransferHealth.GOOD: "💙",
            TransferHealth.AVERAGE: "💛",
            TransferHealth.POOR: "🧡",
            TransferHealth.CRITICAL: "❤️",
        }
        
        # Stage badges
        self._stage_badges: dict[TransferStage, str] = {
            TransferStage.INITIALIZING: "🔄",
            TransferStage.TRANSFERRING: "📤",
            TransferStage.VERIFYING: "🔍",
            TransferStage.COMPLETING: "⏳",
            TransferStage.COMPLETED: "✅",
            TransferStage.PAUSED: "⏸️",
            TransferStage.CANCELLED: "⏹️",
            TransferStage.FAILED: "❌",
        }
    
    def get_status_badge(self, status: str) -> str:
        """Get status badge for given status.
        
        Args:
            status: Transfer status
            
        Returns:
            Status badge emoji
        """
        return self._status_badges.get(status, "❓")
    
    def get_health_indicator(self, health: TransferHealth) -> str:
        """Get health indicator for given health level.
        
        Args:
            health: Transfer health level
            
        Returns:
            Health indicator emoji
        """
        return self._health_indicators.get(health, "❓")
    
    def get_stage_badge(self, stage: TransferStage) -> str:
        """Get stage badge for given transfer stage.
        
        Args:
            stage: Transfer stage
            
        Returns:
            Stage badge emoji
        """
        return self._stage_badges.get(stage, "❓")
    
    def assess_transfer_health(self, message: Message) -> TransferHealth:
        """Assess transfer health based on message metadata.
        
        Args:
            message: Notification message with progress data
            
        Returns:
            Transfer health assessment
        """
        metadata = message.metadata
        
        # Extract relevant metrics
        try:
            speed_bps = int(metadata.get("speed_bps", 0))
            expected_speed = int(metadata.get("expected_speed_bps", 0))
            stall_count = int(metadata.get("stall_count", 0))
            retry_count = int(metadata.get("retry_count", 0))
            
            # Calculate health score based on various factors
            health_score = 100.0
            
            # Speed performance (40% of score)
            if expected_speed > 0:
                speed_ratio = speed_bps / expected_speed
                if speed_ratio >= 0.9:
                    health_score -= 0  # Excellent
                elif speed_ratio >= 0.75:
                    health_score -= 15  # Good
                elif speed_ratio >= 0.5:
                    health_score -= 30  # Average
                elif speed_ratio >= 0.3:
                    health_score -= 50  # Poor
                else:
                    health_score -= 70  # Critical
            
            # Stall penalty (30% of score)
            if stall_count > 0:
                stall_penalty = min(stall_count * 5, 30)
                health_score -= stall_penalty
            
            # Retry penalty (30% of score)
            if retry_count > 0:
                retry_penalty = min(retry_count * 10, 30)
                health_score -= retry_penalty
            
            # Determine health level
            if health_score >= 90:
                return TransferHealth.EXCELLENT
            elif health_score >= 75:
                return TransferHealth.GOOD
            elif health_score >= 50:
                return TransferHealth.AVERAGE
            elif health_score >= 25:
                return TransferHealth.POOR
            else:
                return TransferHealth.CRITICAL
                
        except (ValueError, TypeError):
            # Default to average if we can't assess
            return TransferHealth.AVERAGE
    
    def determine_transfer_stage(self, message: Message) -> TransferStage:
        """Determine transfer stage from message metadata.
        
        Args:
            message: Notification message with progress data
            
        Returns:
            Transfer stage
        """
        metadata = message.metadata
        status = metadata.get("status", "").lower()
        
        # Map status to stage
        stage_mapping = {
            "initializing": TransferStage.INITIALIZING,
            "starting": TransferStage.INITIALIZING,
            "transferring": TransferStage.TRANSFERRING,
            "in_progress": TransferStage.TRANSFERRING,
            "verifying": TransferStage.VERIFYING,
            "completing": TransferStage.COMPLETING,
            "completed": TransferStage.COMPLETED,
            "done": TransferStage.COMPLETED,
            "paused": TransferStage.PAUSED,
            "cancelled": TransferStage.CANCELLED,
            "failed": TransferStage.FAILED,
            "error": TransferStage.FAILED,
        }
        
        return stage_mapping.get(status, TransferStage.TRANSFERRING)


class EnhancedProgressBarGenerator:
    """Generates enhanced progress bars with health indicators and color coding."""
    
    def __init__(self, config: ProgressVisualizationConfig) -> None:
        """Initialize enhanced progress bar generator.
        
        Args:
            config: Visualization configuration
        """
        self.config: ProgressVisualizationConfig = config
        
        # Progress bar characters for different health levels
        self._health_chars: dict[TransferHealth, str] = {
            TransferHealth.EXCELLENT: "█",
            TransferHealth.GOOD: "█",
            TransferHealth.AVERAGE: "▓",
            TransferHealth.POOR: "▒",
            TransferHealth.CRITICAL: "░",
        }
        
        # Empty progress character
        self._empty_char: str = "░"
    
    def create_enhanced_progress_bar(
        self,
        bytes_transferred: int,
        total_size: int,
        health: TransferHealth,
        milestones: list[float] | None = None,
    ) -> str:
        """Create enhanced progress bar with health indicators.
        
        Args:
            bytes_transferred: Number of bytes transferred
            total_size: Total size in bytes
            health: Transfer health level
            milestones: List of milestone percentages
            
        Returns:
            Enhanced progress bar string
        """
        if total_size == 0:
            filled_char = self._health_chars[health] if self.config.show_health_segments else "█"
            return f"[{filled_char * self.config.progress_bar_length}]"
        
        percentage = (bytes_transferred / total_size) * 100.0
        filled_length = int(self.config.progress_bar_length * percentage / 100.0)
        
        # Build progress bar with health-based character
        if self.config.show_health_segments:
            filled_char = self._health_chars[health]
        else:
            filled_char = "█"
        
        filled_bar = filled_char * filled_length
        empty_bar = self._empty_char * (self.config.progress_bar_length - filled_length)
        
        # Add milestone markers if enabled
        if self.config.show_milestones and milestones:
            progress_bar = self._add_milestone_markers(
                filled_bar + empty_bar,
                percentage,
                milestones,
            )
        else:
            progress_bar = filled_bar + empty_bar
        
        return f"[{progress_bar}]"
    
    def _add_milestone_markers(
        self,
        progress_bar: str,
        current_percentage: float,
        milestones: list[float],
    ) -> str:
        """Add milestone markers to progress bar.
        
        Args:
            progress_bar: Base progress bar string
            current_percentage: Current progress percentage
            milestones: List of milestone percentages
            
        Returns:
            Progress bar with milestone markers
        """
        bar_chars = list(progress_bar)
        
        for milestone in milestones:
            if milestone <= current_percentage:
                # Mark achieved milestones
                marker_pos = int((milestone / 100.0) * len(bar_chars))
                if 0 <= marker_pos < len(bar_chars):
                    bar_chars[marker_pos] = "●"
            else:
                # Mark upcoming milestones
                marker_pos = int((milestone / 100.0) * len(bar_chars))
                if 0 <= marker_pos < len(bar_chars):
                    bar_chars[marker_pos] = "○"
        
        return "".join(bar_chars)


class TimelineVisualizationGenerator:
    """Generates timeline visualizations and trend indicators."""
    
    def __init__(self, config: ProgressVisualizationConfig) -> None:
        """Initialize timeline visualization generator.
        
        Args:
            config: Visualization configuration
        """
        self.config: ProgressVisualizationConfig = config
        
        # Trend indicators
        self._trend_indicators: dict[str, str] = {
            "increasing": "📈",
            "decreasing": "📉",
            "stable": "➡️",
            "volatile": "〰️",
        }
    
    def generate_trend_indicator(self, message: Message) -> str:
        """Generate trend indicator based on transfer metrics.
        
        Args:
            message: Notification message with progress data
            
        Returns:
            Trend indicator string
        """
        metadata = message.metadata
        
        try:
            # Extract rate history if available
            current_speed = int(metadata.get("speed_bps", 0))
            avg_speed = int(metadata.get("avg_speed_bps", current_speed))
            
            # Calculate trend
            if current_speed > avg_speed * 1.15:
                trend = "increasing"
            elif current_speed < avg_speed * 0.85:
                trend = "decreasing"
            elif abs(current_speed - avg_speed) < avg_speed * 0.05:
                trend = "stable"
            else:
                trend = "volatile"
            
            indicator = self._trend_indicators.get(trend, "➡️")
            
            if self.config.show_rate_history:
                return f"{indicator} {self._format_trend_text(trend)}"
            else:
                return indicator
                
        except (ValueError, TypeError):
            return "➡️"
    
    def generate_mini_timeline(self, message: Message) -> str:
        """Generate mini timeline visualization.
        
        Args:
            message: Notification message with progress data
            
        Returns:
            Mini timeline string
        """
        metadata = message.metadata
        
        try:
            # Extract timeline data if available
            timeline_data = metadata.get("timeline_data", "")
            if timeline_data:
                # Parse and visualize timeline data
                return self._create_ascii_timeline(timeline_data)
            else:
                # Create simple timeline based on progress
                bytes_transferred = int(metadata.get("bytes_transferred", 0))
                total_size = int(metadata.get("total_size", 0))
                
                if total_size > 0:
                    percentage = (bytes_transferred / total_size) * 100.0
                    return self._create_simple_timeline(percentage)
                
        except (ValueError, TypeError):
            pass
        
        return "⏱️ Timeline unavailable"
    
    def _format_trend_text(self, trend: str) -> str:
        """Format trend text description.
        
        Args:
            trend: Trend type
            
        Returns:
            Formatted trend text
        """
        trend_text = {
            "increasing": "Accelerating",
            "decreasing": "Slowing",
            "stable": "Steady",
            "volatile": "Variable",
        }
        
        return trend_text.get(trend, "Unknown")
    
    def _create_ascii_timeline(self, timeline_data: str) -> str:  # pyright: ignore[reportUnusedParameter]
        """Create ASCII timeline from timeline data.
        
        Args:
            timeline_data: Raw timeline data
            
        Returns:
            ASCII timeline visualization
        """
        # Simple implementation - could be enhanced based on actual data format
        return "⏱️ ▁▂▃▅▆▇█▇▆▅▃▂▁"
    
    def _create_simple_timeline(self, percentage: float) -> str:
        """Create simple timeline based on percentage.
        
        Args:
            percentage: Progress percentage
            
        Returns:
            Simple timeline visualization
        """
        timeline_chars = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        char_index = min(int(percentage / 12.5), len(timeline_chars) - 1)
        
        # Create ascending timeline
        timeline = ""
        for i in range(8):
            if i <= char_index:
                timeline += timeline_chars[i]
            else:
                timeline += "▁"
        
        return f"⏱️ {timeline}"


class MilestoneTracker:
    """Tracks and visualizes progress milestones."""
    
    def __init__(self, config: ProgressVisualizationConfig) -> None:
        """Initialize milestone tracker.
        
        Args:
            config: Visualization configuration
        """
        self.config: ProgressVisualizationConfig = config
        
        # Milestone markers
        self._milestone_markers: dict[str, str] = {
            "achieved": "✅",
            "current": "🎯",
            "upcoming": "⭕",
        }
    
    def generate_milestone_display(self, message: Message) -> str:
        """Generate milestone display string.
        
        Args:
            message: Notification message with progress data
            
        Returns:
            Milestone display string
        """
        metadata = message.metadata
        
        try:
            bytes_transferred = int(metadata.get("bytes_transferred", 0))
            total_size = int(metadata.get("total_size", 0))
            
            if total_size == 0:
                return "🎯 No milestones available"
            
            percentage = (bytes_transferred / total_size) * 100.0
            
            # Generate milestone status
            milestone_display: list[str] = []
            milestones = self.config.milestone_thresholds or []
            
            for milestone in milestones:
                if percentage >= milestone:
                    marker = self._milestone_markers["achieved"]
                    milestone_display.append(f"{marker} {milestone:.0f}%")
                elif abs(percentage - milestone) < 5.0:
                    marker = self._milestone_markers["current"]
                    milestone_display.append(f"{marker} {milestone:.0f}%")
                else:
                    marker = self._milestone_markers["upcoming"]
                    milestone_display.append(f"{marker} {milestone:.0f}%")
            
            return "🎯 " + " ".join(milestone_display[:3])  # Show first 3 milestones
            
        except (ValueError, TypeError):
            return "🎯 Milestone tracking unavailable"
    
    def get_next_milestone(self, message: Message) -> float | None:
        """Get the next milestone percentage.
        
        Args:
            message: Notification message with progress data
            
        Returns:
            Next milestone percentage or None
        """
        metadata = message.metadata
        
        try:
            bytes_transferred = int(metadata.get("bytes_transferred", 0))
            total_size = int(metadata.get("total_size", 0))
            
            if total_size == 0:
                return None
            
            percentage = (bytes_transferred / total_size) * 100.0
            milestones = self.config.milestone_thresholds or []
            
            # Find next milestone
            for milestone in milestones:
                if percentage < milestone:
                    return milestone
            
            return None
            
        except (ValueError, TypeError):
            return None