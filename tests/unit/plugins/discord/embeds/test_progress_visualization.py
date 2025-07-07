"""Tests for Discord progress visualization components."""

from __future__ import annotations

import pytest

from mover_status.notifications.models.message import Message
from mover_status.plugins.discord.embeds.progress_visualization import (
    EnhancedProgressBarGenerator,
    MilestoneTracker,
    ProgressVisualizationConfig,
    StatusBadgeGenerator,
    TimelineVisualizationGenerator,
    TransferHealth,
    TransferStage,
)


class TestProgressVisualizationConfig:
    """Test progress visualization configuration."""
    
    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ProgressVisualizationConfig()
        
        assert config.use_status_badges is True
        assert config.use_health_indicators is True
        assert config.use_stage_badges is True
        assert config.use_enhanced_progress_bars is True
        assert config.progress_bar_length == 20
        assert config.use_color_coding is True
        assert config.show_health_segments is True
        assert config.show_trend_indicators is True
        assert config.show_rate_history is True
        assert config.show_milestones is True
        assert config.milestone_thresholds == [25.0, 50.0, 75.0, 90.0, 95.0]
    
    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        custom_milestones = [10.0, 30.0, 60.0, 90.0]
        config = ProgressVisualizationConfig(
            use_status_badges=False,
            progress_bar_length=15,
            milestone_thresholds=custom_milestones,
        )
        
        assert config.use_status_badges is False
        assert config.progress_bar_length == 15
        assert config.milestone_thresholds == custom_milestones


class TestStatusBadgeGenerator:
    """Test status badge generator."""
    
    @pytest.fixture
    def config(self) -> ProgressVisualizationConfig:
        """Create test configuration."""
        return ProgressVisualizationConfig()
    
    @pytest.fixture
    def generator(self, config: ProgressVisualizationConfig) -> StatusBadgeGenerator:
        """Create status badge generator."""
        return StatusBadgeGenerator(config)
    
    def test_get_status_badge(self, generator: StatusBadgeGenerator) -> None:
        """Test status badge retrieval."""
        assert generator.get_status_badge("started") == "🟢"
        assert generator.get_status_badge("in_progress") == "🔵"
        assert generator.get_status_badge("completed") == "✅"
        assert generator.get_status_badge("failed") == "❌"
        assert generator.get_status_badge("paused") == "⏸️"
        assert generator.get_status_badge("cancelled") == "⏹️"
        assert generator.get_status_badge("stalled") == "⚠️"
        assert generator.get_status_badge("retrying") == "🔄"
        assert generator.get_status_badge("unknown") == "❓"
    
    def test_get_health_indicator(self, generator: StatusBadgeGenerator) -> None:
        """Test health indicator retrieval."""
        assert generator.get_health_indicator(TransferHealth.EXCELLENT) == "💚"
        assert generator.get_health_indicator(TransferHealth.GOOD) == "💙"
        assert generator.get_health_indicator(TransferHealth.AVERAGE) == "💛"
        assert generator.get_health_indicator(TransferHealth.POOR) == "🧡"
        assert generator.get_health_indicator(TransferHealth.CRITICAL) == "❤️"
    
    def test_get_stage_badge(self, generator: StatusBadgeGenerator) -> None:
        """Test stage badge retrieval."""
        assert generator.get_stage_badge(TransferStage.INITIALIZING) == "🔄"
        assert generator.get_stage_badge(TransferStage.TRANSFERRING) == "📤"
        assert generator.get_stage_badge(TransferStage.VERIFYING) == "🔍"
        assert generator.get_stage_badge(TransferStage.COMPLETING) == "⏳"
        assert generator.get_stage_badge(TransferStage.COMPLETED) == "✅"
        assert generator.get_stage_badge(TransferStage.PAUSED) == "⏸️"
        assert generator.get_stage_badge(TransferStage.CANCELLED) == "⏹️"
        assert generator.get_stage_badge(TransferStage.FAILED) == "❌"
    
    def test_assess_transfer_health_excellent(self, generator: StatusBadgeGenerator) -> None:
        """Test excellent transfer health assessment."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "1000000",
                "expected_speed_bps": "1000000",
                "stall_count": "0",
                "retry_count": "0",
            },
        )
        
        health = generator.assess_transfer_health(message)
        assert health == TransferHealth.EXCELLENT
    
    def test_assess_transfer_health_good(self, generator: StatusBadgeGenerator) -> None:
        """Test good transfer health assessment."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "800000",
                "expected_speed_bps": "1000000",
                "stall_count": "0",
                "retry_count": "0",
            },
        )
        
        health = generator.assess_transfer_health(message)
        assert health == TransferHealth.GOOD
    
    def test_assess_transfer_health_average(self, generator: StatusBadgeGenerator) -> None:
        """Test average transfer health assessment."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "600000",
                "expected_speed_bps": "1000000",
                "stall_count": "1",
                "retry_count": "0",
            },
        )
        
        health = generator.assess_transfer_health(message)
        assert health == TransferHealth.AVERAGE
    
    def test_assess_transfer_health_poor(self, generator: StatusBadgeGenerator) -> None:
        """Test poor transfer health assessment."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "400000",
                "expected_speed_bps": "1000000",
                "stall_count": "2",
                "retry_count": "1",
            },
        )
        
        health = generator.assess_transfer_health(message)
        assert health == TransferHealth.POOR
    
    def test_assess_transfer_health_critical(self, generator: StatusBadgeGenerator) -> None:
        """Test critical transfer health assessment."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "100000",
                "expected_speed_bps": "1000000",
                "stall_count": "5",
                "retry_count": "3",
            },
        )
        
        health = generator.assess_transfer_health(message)
        assert health == TransferHealth.CRITICAL
    
    def test_assess_transfer_health_no_expected_speed(self, generator: StatusBadgeGenerator) -> None:
        """Test health assessment without expected speed."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "1000000",
                "stall_count": "0",
                "retry_count": "0",
            },
        )
        
        health = generator.assess_transfer_health(message)
        assert health == TransferHealth.EXCELLENT
    
    def test_assess_transfer_health_invalid_data(self, generator: StatusBadgeGenerator) -> None:
        """Test health assessment with invalid data."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "invalid",
                "expected_speed_bps": "also_invalid",
            },
        )
        
        health = generator.assess_transfer_health(message)
        assert health == TransferHealth.AVERAGE
    
    def test_determine_transfer_stage(self, generator: StatusBadgeGenerator) -> None:
        """Test transfer stage determination."""
        test_cases = [
            ("initializing", TransferStage.INITIALIZING),
            ("starting", TransferStage.INITIALIZING),
            ("transferring", TransferStage.TRANSFERRING),
            ("in_progress", TransferStage.TRANSFERRING),
            ("verifying", TransferStage.VERIFYING),
            ("completing", TransferStage.COMPLETING),
            ("completed", TransferStage.COMPLETED),
            ("done", TransferStage.COMPLETED),
            ("paused", TransferStage.PAUSED),
            ("cancelled", TransferStage.CANCELLED),
            ("failed", TransferStage.FAILED),
            ("error", TransferStage.FAILED),
            ("unknown", TransferStage.TRANSFERRING),
        ]
        
        for status, expected_stage in test_cases:
            message = Message(
                title="Test",
                content="Test content",
                metadata={"status": status},
            )
            
            stage = generator.determine_transfer_stage(message)
            assert stage == expected_stage


class TestEnhancedProgressBarGenerator:
    """Test enhanced progress bar generator."""
    
    @pytest.fixture
    def config(self) -> ProgressVisualizationConfig:
        """Create test configuration."""
        return ProgressVisualizationConfig()
    
    @pytest.fixture
    def generator(self, config: ProgressVisualizationConfig) -> EnhancedProgressBarGenerator:
        """Create enhanced progress bar generator."""
        return EnhancedProgressBarGenerator(config)
    
    def test_create_enhanced_progress_bar_empty(self, generator: EnhancedProgressBarGenerator) -> None:
        """Test enhanced progress bar creation with empty progress."""
        progress_bar = generator.create_enhanced_progress_bar(
            bytes_transferred=0,
            total_size=1000,
            health=TransferHealth.GOOD,
        )
        
        assert progress_bar.startswith("[")
        assert progress_bar.endswith("]")
        assert "░" in progress_bar
        assert len(progress_bar) == 22  # 20 chars + 2 brackets
    
    def test_create_enhanced_progress_bar_half(self, generator: EnhancedProgressBarGenerator) -> None:
        """Test enhanced progress bar creation with half progress."""
        progress_bar = generator.create_enhanced_progress_bar(
            bytes_transferred=500,
            total_size=1000,
            health=TransferHealth.EXCELLENT,
        )
        
        assert progress_bar.startswith("[")
        assert progress_bar.endswith("]")
        assert "█" in progress_bar
        assert "░" in progress_bar
    
    def test_create_enhanced_progress_bar_full(self, generator: EnhancedProgressBarGenerator) -> None:
        """Test enhanced progress bar creation with full progress."""
        progress_bar = generator.create_enhanced_progress_bar(
            bytes_transferred=1000,
            total_size=1000,
            health=TransferHealth.GOOD,
        )
        
        assert progress_bar.startswith("[")
        assert progress_bar.endswith("]")
        assert progress_bar.count("█") == 20
    
    def test_create_enhanced_progress_bar_zero_size(self, generator: EnhancedProgressBarGenerator) -> None:
        """Test enhanced progress bar creation with zero total size."""
        progress_bar = generator.create_enhanced_progress_bar(
            bytes_transferred=0,
            total_size=0,
            health=TransferHealth.CRITICAL,
        )
        
        assert progress_bar.startswith("[")
        assert progress_bar.endswith("]")
        assert progress_bar.count("░") == 20  # Critical health uses empty chars
    
    def test_create_enhanced_progress_bar_different_health(self, generator: EnhancedProgressBarGenerator) -> None:
        """Test enhanced progress bar with different health levels."""
        health_chars = {
            TransferHealth.EXCELLENT: "█",
            TransferHealth.GOOD: "█",
            TransferHealth.AVERAGE: "▓",
            TransferHealth.POOR: "▒",
            TransferHealth.CRITICAL: "░",
        }
        
        for health, expected_char in health_chars.items():
            progress_bar = generator.create_enhanced_progress_bar(
                bytes_transferred=1000,
                total_size=1000,
                health=health,
            )
            
            assert expected_char in progress_bar
    
    def test_create_enhanced_progress_bar_with_milestones(self, generator: EnhancedProgressBarGenerator) -> None:
        """Test enhanced progress bar with milestone markers."""
        progress_bar = generator.create_enhanced_progress_bar(
            bytes_transferred=600,
            total_size=1000,
            health=TransferHealth.GOOD,
            milestones=[25.0, 50.0, 75.0],
        )
        
        assert progress_bar.startswith("[")
        assert progress_bar.endswith("]")
        assert "●" in progress_bar  # Achieved milestone
        assert "○" in progress_bar  # Upcoming milestone
    
    def test_create_enhanced_progress_bar_no_health_segments(self) -> None:
        """Test enhanced progress bar without health segments."""
        config = ProgressVisualizationConfig(show_health_segments=False)
        generator = EnhancedProgressBarGenerator(config)
        
        progress_bar = generator.create_enhanced_progress_bar(
            bytes_transferred=500,
            total_size=1000,
            health=TransferHealth.CRITICAL,
        )
        
        assert "█" in progress_bar  # Should use default char, not critical char
    
    def test_create_enhanced_progress_bar_custom_length(self) -> None:
        """Test enhanced progress bar with custom length."""
        config = ProgressVisualizationConfig(progress_bar_length=10)
        generator = EnhancedProgressBarGenerator(config)
        
        progress_bar = generator.create_enhanced_progress_bar(
            bytes_transferred=500,
            total_size=1000,
            health=TransferHealth.GOOD,
        )
        
        assert len(progress_bar) == 12  # 10 chars + 2 brackets


class TestTimelineVisualizationGenerator:
    """Test timeline visualization generator."""
    
    @pytest.fixture
    def config(self) -> ProgressVisualizationConfig:
        """Create test configuration."""
        return ProgressVisualizationConfig()
    
    @pytest.fixture
    def generator(self, config: ProgressVisualizationConfig) -> TimelineVisualizationGenerator:
        """Create timeline visualization generator."""
        return TimelineVisualizationGenerator(config)
    
    def test_generate_trend_indicator_increasing(self, generator: TimelineVisualizationGenerator) -> None:
        """Test trend indicator generation for increasing speed."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "1200000",
                "avg_speed_bps": "1000000",
            },
        )
        
        trend = generator.generate_trend_indicator(message)
        assert "📈" in trend
        assert "Accelerating" in trend
    
    def test_generate_trend_indicator_decreasing(self, generator: TimelineVisualizationGenerator) -> None:
        """Test trend indicator generation for decreasing speed."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "700000",
                "avg_speed_bps": "1000000",
            },
        )
        
        trend = generator.generate_trend_indicator(message)
        assert "📉" in trend
        assert "Slowing" in trend
    
    def test_generate_trend_indicator_stable(self, generator: TimelineVisualizationGenerator) -> None:
        """Test trend indicator generation for stable speed."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "1000000",
                "avg_speed_bps": "1000000",
            },
        )
        
        trend = generator.generate_trend_indicator(message)
        assert "➡️" in trend
        assert "Steady" in trend
    
    def test_generate_trend_indicator_volatile(self, generator: TimelineVisualizationGenerator) -> None:
        """Test trend indicator generation for volatile speed."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "1100000",
                "avg_speed_bps": "1000000",
            },
        )
        
        trend = generator.generate_trend_indicator(message)
        assert "〰️" in trend
        assert "Variable" in trend
    
    def test_generate_trend_indicator_no_history(self, generator: TimelineVisualizationGenerator) -> None:
        """Test trend indicator generation without rate history."""
        config = ProgressVisualizationConfig(show_rate_history=False)
        generator = TimelineVisualizationGenerator(config)
        
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "1200000",
                "avg_speed_bps": "1000000",
            },
        )
        
        trend = generator.generate_trend_indicator(message)
        assert trend == "📈"  # Just the emoji, no text
    
    def test_generate_trend_indicator_invalid_data(self, generator: TimelineVisualizationGenerator) -> None:
        """Test trend indicator generation with invalid data."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "speed_bps": "invalid",
                "avg_speed_bps": "also_invalid",
            },
        )
        
        trend = generator.generate_trend_indicator(message)
        assert trend == "➡️"
    
    def test_generate_mini_timeline_with_data(self, generator: TimelineVisualizationGenerator) -> None:
        """Test mini timeline generation with timeline data."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "timeline_data": "mock_data",
            },
        )
        
        timeline = generator.generate_mini_timeline(message)
        assert "⏱️" in timeline
        assert "▁▂▃▅▆▇█▇▆▅▃▂▁" in timeline
    
    def test_generate_mini_timeline_simple(self, generator: TimelineVisualizationGenerator) -> None:
        """Test mini timeline generation with simple progress."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "500",
                "total_size": "1000",
            },
        )
        
        timeline = generator.generate_mini_timeline(message)
        assert "⏱️" in timeline
        assert "▁" in timeline
    
    def test_generate_mini_timeline_unavailable(self, generator: TimelineVisualizationGenerator) -> None:
        """Test mini timeline generation when unavailable."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={},
        )
        
        timeline = generator.generate_mini_timeline(message)
        assert timeline == "⏱️ Timeline unavailable"


class TestMilestoneTracker:
    """Test milestone tracker."""
    
    @pytest.fixture
    def config(self) -> ProgressVisualizationConfig:
        """Create test configuration."""
        return ProgressVisualizationConfig()
    
    @pytest.fixture
    def tracker(self, config: ProgressVisualizationConfig) -> MilestoneTracker:
        """Create milestone tracker."""
        return MilestoneTracker(config)
    
    def test_generate_milestone_display(self, tracker: MilestoneTracker) -> None:
        """Test milestone display generation."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "600",
                "total_size": "1000",
            },
        )
        
        display = tracker.generate_milestone_display(message)
        assert "🎯" in display
        assert "✅" in display  # Achieved milestones
        assert "⭕" in display  # Upcoming milestones
    
    def test_generate_milestone_display_early_progress(self, tracker: MilestoneTracker) -> None:
        """Test milestone display with early progress."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "100",
                "total_size": "1000",
            },
        )
        
        display = tracker.generate_milestone_display(message)
        assert "🎯" in display
        assert "⭕" in display  # All upcoming milestones
    
    def test_generate_milestone_display_near_completion(self, tracker: MilestoneTracker) -> None:
        """Test milestone display near completion."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "950",
                "total_size": "1000",
            },
        )
        
        display = tracker.generate_milestone_display(message)
        assert "🎯" in display
        assert "✅" in display  # Most milestones achieved
    
    def test_generate_milestone_display_zero_size(self, tracker: MilestoneTracker) -> None:
        """Test milestone display with zero total size."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "0",
                "total_size": "0",
            },
        )
        
        display = tracker.generate_milestone_display(message)
        assert display == "🎯 No milestones available"
    
    def test_generate_milestone_display_invalid_data(self, tracker: MilestoneTracker) -> None:
        """Test milestone display with invalid data."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "invalid",
                "total_size": "also_invalid",
            },
        )
        
        display = tracker.generate_milestone_display(message)
        assert display == "🎯 Milestone tracking unavailable"
    
    def test_get_next_milestone(self, tracker: MilestoneTracker) -> None:
        """Test getting next milestone."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "600",
                "total_size": "1000",
            },
        )
        
        next_milestone = tracker.get_next_milestone(message)
        assert next_milestone == 75.0
    
    def test_get_next_milestone_near_end(self, tracker: MilestoneTracker) -> None:
        """Test getting next milestone near end."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "960",
                "total_size": "1000",
            },
        )
        
        next_milestone = tracker.get_next_milestone(message)
        assert next_milestone is None
    
    def test_get_next_milestone_zero_size(self, tracker: MilestoneTracker) -> None:
        """Test getting next milestone with zero size."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "0",
                "total_size": "0",
            },
        )
        
        next_milestone = tracker.get_next_milestone(message)
        assert next_milestone is None
    
    def test_get_next_milestone_invalid_data(self, tracker: MilestoneTracker) -> None:
        """Test getting next milestone with invalid data."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "invalid",
                "total_size": "also_invalid",
            },
        )
        
        next_milestone = tracker.get_next_milestone(message)
        assert next_milestone is None
    
    def test_custom_milestone_thresholds(self) -> None:
        """Test milestone tracker with custom thresholds."""
        config = ProgressVisualizationConfig(
            milestone_thresholds=[20.0, 40.0, 60.0, 80.0, 100.0],
        )
        tracker = MilestoneTracker(config)
        
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "500",
                "total_size": "1000",
            },
        )
        
        next_milestone = tracker.get_next_milestone(message)
        assert next_milestone == 60.0