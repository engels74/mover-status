"""Tests for notification bridge module."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from mover_status.core.monitor.event_bus import EventBus, Event, EventTopic, EventPriority
from mover_status.core.monitor.notification_bridge import (
    NotificationBridge,
    NotificationTemplate,
    NotificationRule,
    NotificationLevel,
    NotificationThrottler,
    NotificationDeduplicator,
    EscalationManager,
    create_notification_bridge
)
from mover_status.notifications.models import Message
from mover_status.core.process import ProcessInfo


class TestNotificationTemplate:
    """Test notification template functionality."""
    
    def test_format_basic_template(self) -> None:
        """Test basic template formatting."""
        template = NotificationTemplate(
            title="Test {name}",
            content="Hello {name}, your status is {status}",
            priority="normal"
        )
        
        message = template.format(name="John", status="active")
        
        assert message.title == "Test John"
        assert message.content == "Hello John, your status is active"
        assert message.priority == "normal"
    
    def test_format_with_tags_and_metadata(self) -> None:
        """Test template with tags and metadata."""
        template = NotificationTemplate(
            title="Test",
            content="Content",
            tags=["test", "example"],
            metadata={"source": "test"}
        )
        
        message = template.format()
        
        assert message.tags == ["test", "example"]
        assert message.metadata == {"source": "test"}


class TestNotificationRule:
    """Test notification rule functionality."""
    
    def test_matches_event_exact(self) -> None:
        """Test exact event pattern matching."""
        template = NotificationTemplate(title="Test", content="Test")
        rule = NotificationRule(
            event_pattern="process.detected",
            level=NotificationLevel.INFO,
            template=template
        )
        
        event = Event(
            topic=EventTopic("process.detected"),
            data={},
            priority=EventPriority.NORMAL
        )
        
        assert rule.matches_event(event) is True
    
    def test_matches_event_wildcard(self) -> None:
        """Test wildcard event pattern matching."""
        template = NotificationTemplate(title="Test", content="Test")
        rule = NotificationRule(
            event_pattern="process.*",
            level=NotificationLevel.INFO,
            template=template
        )
        
        event1 = Event(
            topic=EventTopic("process.detected"),
            data={},
            priority=EventPriority.NORMAL
        )
        event2 = Event(
            topic=EventTopic("system.error"),
            data={},
            priority=EventPriority.NORMAL
        )
        
        assert rule.matches_event(event1) is True
        assert rule.matches_event(event2) is False
    
    def test_disabled_rule_no_match(self) -> None:
        """Test disabled rule doesn't match."""
        template = NotificationTemplate(title="Test", content="Test")
        rule = NotificationRule(
            event_pattern="process.detected",
            level=NotificationLevel.INFO,
            template=template,
            enabled=False
        )
        
        event = Event(
            topic=EventTopic("process.detected"),
            data={},
            priority=EventPriority.NORMAL
        )
        
        assert rule.matches_event(event) is False


class TestNotificationThrottler:
    """Test notification throttling functionality."""
    
    @pytest.mark.asyncio
    async def test_no_throttling(self) -> None:
        """Test behavior when throttling is disabled."""
        throttler = NotificationThrottler()
        
        result = await throttler.should_send("test", 0)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_first_send_allowed(self) -> None:
        """Test first send is always allowed."""
        throttler = NotificationThrottler()
        
        result = await throttler.should_send("test", 60)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_throttling_blocks_rapid_sends(self) -> None:
        """Test throttling blocks rapid consecutive sends."""
        throttler = NotificationThrottler()
        
        # First send should be allowed
        result1 = await throttler.should_send("test", 60)
        assert result1 is True
        
        # Immediate second send should be blocked
        result2 = await throttler.should_send("test", 60)
        assert result2 is False


class TestNotificationDeduplicator:
    """Test notification deduplication functionality."""
    
    @pytest.mark.asyncio
    async def test_first_message_not_duplicate(self) -> None:
        """Test first message is not considered duplicate."""
        deduplicator = NotificationDeduplicator()
        message = Message(title="Test", content="Content", priority="normal")
        
        result = await deduplicator.is_duplicate(message)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_identical_message_is_duplicate(self) -> None:
        """Test identical message is flagged as duplicate."""
        deduplicator = NotificationDeduplicator()
        message = Message(title="Test", content="Content", priority="normal")
        
        # First call
        result1 = await deduplicator.is_duplicate(message)
        assert result1 is False
        
        # Second call with identical message
        result2 = await deduplicator.is_duplicate(message)
        assert result2 is True
    
    @pytest.mark.asyncio
    async def test_different_messages_not_duplicate(self) -> None:
        """Test different messages are not considered duplicates."""
        deduplicator = NotificationDeduplicator()
        message1 = Message(title="Test1", content="Content1", priority="normal")
        message2 = Message(title="Test2", content="Content2", priority="normal")
        
        result1 = await deduplicator.is_duplicate(message1)
        result2 = await deduplicator.is_duplicate(message2)
        
        assert result1 is False
        assert result2 is False


class TestEscalationManager:
    """Test escalation management functionality."""
    
    @pytest.mark.asyncio
    async def test_schedule_escalation(self) -> None:
        """Test scheduling an escalation."""
        manager = EscalationManager()
        callback_called = False
        
        def callback() -> None:
            nonlocal callback_called
            callback_called = True
        
        await manager.schedule_escalation("test", 1, callback)
        await asyncio.sleep(0.2)  # Wait for escalation
        
        assert callback_called is True
    
    @pytest.mark.asyncio
    async def test_cancel_escalation(self) -> None:
        """Test canceling an escalation."""
        manager = EscalationManager()
        callback_called = False
        
        def callback() -> None:
            nonlocal callback_called
            callback_called = True
        
        await manager.schedule_escalation("test", 1, callback)
        await manager.cancel_escalation("test")
        await asyncio.sleep(0.3)  # Wait longer than escalation delay
        
        assert callback_called is False


class TestNotificationBridge:
    """Test notification bridge functionality."""
    
    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        """Create mock event bus."""
        event_bus = MagicMock(spec=EventBus)
        event_bus.register_subscriber = MagicMock()
        return event_bus
    
    @pytest.fixture
    def mock_dispatcher(self) -> AsyncMock:
        """Create mock dispatcher."""
        dispatcher = AsyncMock()
        dispatcher.dispatch_message = AsyncMock()
        return dispatcher
    
    @pytest.fixture
    def notification_bridge(
        self, 
        mock_event_bus: MagicMock, 
        mock_dispatcher: AsyncMock
    ) -> NotificationBridge:
        """Create notification bridge for testing."""
        return NotificationBridge(
            event_bus=mock_event_bus,
            dispatcher=mock_dispatcher
        )
    
    def test_initialization(self, notification_bridge: NotificationBridge) -> None:
        """Test bridge initialization."""
        assert notification_bridge.throttler is not None
        assert notification_bridge.deduplicator is not None
        assert notification_bridge.escalation_manager is not None
        assert len(notification_bridge.rules) > 0
        assert len(notification_bridge.templates) > 0
    
    def test_initialization_with_disabled_features(
        self, 
        mock_event_bus: MagicMock, 
        mock_dispatcher: AsyncMock
    ) -> None:
        """Test bridge initialization with disabled features."""
        bridge = NotificationBridge(
            event_bus=mock_event_bus,
            dispatcher=mock_dispatcher,
            enable_throttling=False,
            enable_deduplication=False,
            enable_escalation=False
        )
        
        assert bridge.throttler is None
        assert bridge.deduplicator is None
        assert bridge.escalation_manager is None
    
    def test_subscribes_to_event_bus(
        self, 
        mock_event_bus: MagicMock, 
        notification_bridge: NotificationBridge
    ) -> None:
        """Test that bridge subscribes to event bus."""
        mock_event_bus.register_subscriber.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_process_detected_event(
        self, 
        notification_bridge: NotificationBridge
    ) -> None:
        """Test handling process detected event."""
        process = ProcessInfo(
            name="test_process",
            pid=12345,
            command="test",
            start_time=datetime.now()
        )
        
        event = Event(
            topic=EventTopic("process.detected"),
            data={"process": process},
            priority=EventPriority.HIGH
        )
        
        await notification_bridge._handle_event(event)
        
        # Verify dispatcher was called
        notification_bridge.dispatcher.dispatch_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_unmatched_event(
        self, 
        notification_bridge: NotificationBridge
    ) -> None:
        """Test handling event that doesn't match any rules."""
        event = Event(
            topic=EventTopic("unknown.event"),
            data={},
            priority=EventPriority.NORMAL
        )
        
        await notification_bridge._handle_event(event)
        
        # Verify dispatcher was not called
        notification_bridge.dispatcher.dispatch_message.assert_not_called()
    
    def test_add_rule(self, notification_bridge: NotificationBridge) -> None:
        """Test adding notification rule."""
        template = NotificationTemplate(title="Test", content="Test")
        rule = NotificationRule(
            event_pattern="test.event",
            level=NotificationLevel.INFO,
            template=template
        )
        
        initial_count = len(notification_bridge.rules)
        notification_bridge.add_rule(rule)
        
        assert len(notification_bridge.rules) == initial_count + 1
        assert rule in notification_bridge.rules
    
    def test_remove_rule(self, notification_bridge: NotificationBridge) -> None:
        """Test removing notification rule."""
        initial_count = len(notification_bridge.rules)
        
        # Remove a rule that exists
        notification_bridge.remove_rule("process.detected")
        
        assert len(notification_bridge.rules) < initial_count
    
    def test_add_template(self, notification_bridge: NotificationBridge) -> None:
        """Test adding notification template."""
        template = NotificationTemplate(title="Custom", content="Custom content")
        
        notification_bridge.add_template("custom", template)
        
        assert "custom" in notification_bridge.templates
        assert notification_bridge.templates["custom"] == template
    
    def test_enable_disable_rule(self, notification_bridge: NotificationBridge) -> None:
        """Test enabling and disabling rules."""
        # Find an existing rule
        rule = next((r for r in notification_bridge.rules if r.event_pattern == "process.detected"), None)
        assert rule is not None
        
        # Disable rule
        notification_bridge.enable_rule("process.detected", False)
        assert rule.enabled is False
        
        # Re-enable rule
        notification_bridge.enable_rule("process.detected", True)
        assert rule.enabled is True
    
    @pytest.mark.asyncio
    async def test_shutdown(self, notification_bridge: NotificationBridge) -> None:
        """Test bridge shutdown."""
        await notification_bridge.shutdown()
        
        # Should not raise any exceptions
        assert True
    
    def test_format_message_with_process_data(
        self, 
        notification_bridge: NotificationBridge
    ) -> None:
        """Test message formatting with process data."""
        process = ProcessInfo(
            name="test_process",
            pid=12345,
            command="test",
            start_time=datetime.now()
        )
        
        event = Event(
            topic=EventTopic("process.detected"),
            data={"process": process},
            priority=EventPriority.HIGH
        )
        
        rule = notification_bridge.rules[0]  # Use first rule
        message = notification_bridge._format_message(event, rule)
        
        assert "test_process" in message.title or "test_process" in message.content
        assert "12345" in message.content
    
    def test_format_message_with_error_data(
        self, 
        notification_bridge: NotificationBridge
    ) -> None:
        """Test message formatting with error data."""
        error = RuntimeError("Test error")
        
        event = Event(
            topic=EventTopic("process.error"),
            data={"error": error},
            priority=EventPriority.CRITICAL
        )
        
        # Find error rule
        rule = next((r for r in notification_bridge.rules if "error" in r.event_pattern), None)
        assert rule is not None
        
        message = notification_bridge._format_message(event, rule)
        
        assert "Test error" in message.content
        assert "RuntimeError" in message.content
    
    def test_format_message_missing_data_fallback(
        self, 
        notification_bridge: NotificationBridge
    ) -> None:
        """Test message formatting fallback for missing data."""
        event = Event(
            topic=EventTopic("process.detected"),
            data={},  # Missing process data
            priority=EventPriority.NORMAL
        )
        
        rule = notification_bridge.rules[0]  # Use first rule
        message = notification_bridge._format_message(event, rule)
        
        # Should fallback to basic message
        assert "Event:" in message.title
        assert event.topic.name in message.title


class TestCreateNotificationBridge:
    """Test notification bridge creation function."""
    
    def test_create_notification_bridge(self) -> None:
        """Test creating notification bridge via helper function."""
        event_bus = MagicMock(spec=EventBus)
        event_bus.register_subscriber = MagicMock()
        dispatcher = AsyncMock()
        
        bridge = create_notification_bridge(
            event_bus=event_bus,
            dispatcher=dispatcher,
            enable_throttling=False
        )
        
        assert isinstance(bridge, NotificationBridge)
        assert bridge.event_bus == event_bus
        assert bridge.dispatcher == dispatcher
        assert bridge.throttler is None  # Disabled via kwargs