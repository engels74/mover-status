"""Notification bridge for orchestrator events and status updates."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, cast, Literal

from .event_bus import EventBus, Event, EventSubscriber
from ...notifications.manager import AsyncDispatcher
from ...notifications.models import Message
from ..process import ProcessInfo
from ..progress import ProgressMetrics

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Types of notification channels."""
    
    EMAIL = "email"
    SMS = "sms"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    SLACK = "slack"


class NotificationLevel(Enum):
    """Notification severity levels."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class NotificationTemplate:
    """Template for notification messages."""
    
    title: str
    content: str
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    
    def format(self, **kwargs: str) -> Message:
        """Format template with provided data.
        
        Args:
            **kwargs: Data to format template with
            
        Returns:
            Formatted message
        """
        formatted_title = self.title.format(**kwargs)
        formatted_content = self.content.format(**kwargs)
        
        return Message(
            title=formatted_title,
            content=formatted_content,
            priority=self.priority,
            tags=self.tags.copy(),
            metadata=self.metadata.copy()
        )


@dataclass
class NotificationRule:
    """Rule for determining when to send notifications."""
    
    event_pattern: str
    level: NotificationLevel
    template: NotificationTemplate
    channels: list[NotificationChannel] = field(default_factory=list)
    enabled: bool = True
    throttle_seconds: int = 0
    escalation_delay: int = 0
    
    def matches_event(self, event: Event) -> bool:
        """Check if event matches this rule.
        
        Args:
            event: Event to check
            
        Returns:
            True if event matches rule
        """
        return self.enabled and event.topic.matches(self.event_pattern)


class NotificationThrottler:
    """Throttles notifications to prevent spam."""
    
    def __init__(self) -> None:
        """Initialize throttler."""
        self._last_sent: dict[str, float] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
    
    async def should_send(self, key: str, throttle_seconds: int) -> bool:
        """Check if notification should be sent.
        
        Args:
            key: Unique key for notification
            throttle_seconds: Throttle period in seconds
            
        Returns:
            True if notification should be sent
        """
        if throttle_seconds <= 0:
            return True
            
        async with self._lock:
            import time
            current_time = time.time()
            
            if key not in self._last_sent:
                self._last_sent[key] = current_time
                return True
            
            if current_time - self._last_sent[key] >= throttle_seconds:
                self._last_sent[key] = current_time
                return True
            
            return False


class NotificationDeduplicator:
    """Deduplicates identical notifications."""
    
    def __init__(self, window_seconds: int = 300) -> None:
        """Initialize deduplicator.
        
        Args:
            window_seconds: Time window for deduplication
        """
        self._window_seconds: int = window_seconds
        self._sent_messages: dict[str, float] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
    
    async def is_duplicate(self, message: Message) -> bool:
        """Check if message is a duplicate.
        
        Args:
            message: Message to check
            
        Returns:
            True if message is a duplicate
        """
        async with self._lock:
            import time
            current_time = time.time()
            
            # Generate message fingerprint
            fingerprint = f"{message.title}:{message.content}:{message.priority}"
            
            # Clean up old entries
            expired_keys = [
                key for key, timestamp in self._sent_messages.items()
                if current_time - timestamp > self._window_seconds
            ]
            for key in expired_keys:
                del self._sent_messages[key]
            
            # Check if message is duplicate
            if fingerprint in self._sent_messages:
                return True
            
            # Record message
            self._sent_messages[fingerprint] = current_time
            return False


class EscalationManager:
    """Manages notification escalation policies."""
    
    def __init__(self) -> None:
        """Initialize escalation manager."""
        self._escalation_timers: dict[str, asyncio.Task[None]] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
    
    async def schedule_escalation(
        self, 
        key: str, 
        delay_seconds: float, 
        callback: Callable[[], None]
    ) -> None:
        """Schedule an escalation.
        
        Args:
            key: Unique key for escalation
            delay_seconds: Delay before escalation
            callback: Callback to execute
        """
        async with self._lock:
            # Cancel existing escalation
            if key in self._escalation_timers:
                _ = self._escalation_timers[key].cancel()
            
            # Schedule new escalation
            task = asyncio.create_task(
                self._escalate_after_delay(delay_seconds, callback)
            )
            self._escalation_timers[key] = task
    
    async def cancel_escalation(self, key: str) -> None:
        """Cancel a scheduled escalation.
        
        Args:
            key: Escalation key to cancel
        """
        async with self._lock:
            if key in self._escalation_timers:
                _ = self._escalation_timers[key].cancel()
                _ = self._escalation_timers.pop(key, None)
    
    async def _escalate_after_delay(
        self, 
        delay_seconds: float, 
        callback: Callable[[], None]
    ) -> None:
        """Execute escalation after delay.
        
        Args:
            delay_seconds: Delay in seconds
            callback: Callback to execute
        """
        try:
            await asyncio.sleep(delay_seconds)
            callback()
        except asyncio.CancelledError:
            pass
    
    async def cancel_all_escalations(self) -> None:
        """Cancel all scheduled escalations."""
        async with self._lock:
            for task in list(self._escalation_timers.values()):
                _ = task.cancel()
            self._escalation_timers.clear()


class NotificationBridge:
    """Bridges orchestrator events to notification system."""
    
    def __init__(
        self,
        event_bus: EventBus,
        dispatcher: AsyncDispatcher,
        *,
        enable_throttling: bool = True,
        enable_deduplication: bool = True,
        enable_escalation: bool = True
    ) -> None:
        """Initialize notification bridge.
        
        Args:
            event_bus: Event bus to subscribe to
            dispatcher: Notification dispatcher
            enable_throttling: Whether to enable throttling
            enable_deduplication: Whether to enable deduplication
            enable_escalation: Whether to enable escalation
        """
        self.event_bus: EventBus = event_bus
        self.dispatcher: AsyncDispatcher = dispatcher
        
        # Initialize components
        self.throttler: NotificationThrottler | None = NotificationThrottler() if enable_throttling else None
        self.deduplicator: NotificationDeduplicator | None = NotificationDeduplicator() if enable_deduplication else None
        self.escalation_manager: EscalationManager | None = EscalationManager() if enable_escalation else None
        
        # Notification rules
        self.rules: list[NotificationRule] = []
        
        # Templates
        self.templates: dict[str, NotificationTemplate] = {}
        
        # Initialize default rules and templates
        self._initialize_default_templates()
        self._initialize_default_rules()
        
        # Subscribe to events
        self._subscribe_to_events()
    
    def _initialize_default_templates(self) -> None:
        """Initialize default notification templates."""
        self.templates["process_detected"] = NotificationTemplate(
            title="Process Detected: {process_name}",
            content=("A new process has been detected and monitoring has started.\n\n"
                   "Process: {process_name}\n"
                   "PID: {process_pid}\n"
                   "Start Time: {start_time}"),
            priority="normal",
            tags=["process", "monitoring", "start"]
        )
        
        self.templates["process_progress"] = NotificationTemplate(
            title="Progress Update: {process_name}",
            content=("Progress update for monitored process.\n\n"
                   "Process: {process_name}\n"
                   "Progress: {progress_percentage:.1f}%\n"
                   "ETA: {eta}"),
            priority="low",
            tags=["process", "progress", "update"]
        )
        
        self.templates["process_completed"] = NotificationTemplate(
            title="Process Completed: {process_name}",
            content=("Process monitoring has completed successfully.\n\n"
                   "Process: {process_name}\n"
                   "Duration: {duration}\n"
                   "Final Status: Completed"),
            priority="high",
            tags=["process", "monitoring", "complete"]
        )
        
        self.templates["process_error"] = NotificationTemplate(
            title="Process Error: {process_name}",
            content=("An error occurred during process monitoring.\n\n"
                   "Process: {process_name}\n"
                   "Error: {error_message}\n"
                   "Time: {error_time}"),
            priority="high",
            tags=["process", "error", "monitoring"]
        )
        
        self.templates["system_error"] = NotificationTemplate(
            title="System Error: {error_type}",
            content=("A system error has occurred.\n\n"
                   "Error Type: {error_type}\n"
                   "Error Message: {error_message}\n"
                   "Component: {component}\n"
                   "Time: {error_time}"),
            priority="urgent",
            tags=["system", "error", "critical"]
        )
    
    def _initialize_default_rules(self) -> None:
        """Initialize default notification rules."""
        # Process detection notifications
        self.rules.append(NotificationRule(
            event_pattern="process.detected",
            level=NotificationLevel.INFO,
            template=self.templates["process_detected"],
            channels=[NotificationChannel.DISCORD, NotificationChannel.TELEGRAM],
            throttle_seconds=60
        ))
        
        # Progress notifications (throttled heavily)
        self.rules.append(NotificationRule(
            event_pattern="process.progress",
            level=NotificationLevel.INFO,
            template=self.templates["process_progress"],
            channels=[NotificationChannel.DISCORD],
            throttle_seconds=300,  # 5 minutes
            enabled=False  # Disabled by default to avoid spam
        ))
        
        # Process completion notifications
        self.rules.append(NotificationRule(
            event_pattern="process.completed",
            level=NotificationLevel.INFO,
            template=self.templates["process_completed"],
            channels=[NotificationChannel.DISCORD, NotificationChannel.TELEGRAM],
            throttle_seconds=30
        ))
        
        # Error notifications
        self.rules.append(NotificationRule(
            event_pattern="process.*.error",
            level=NotificationLevel.ERROR,
            template=self.templates["process_error"],
            channels=[NotificationChannel.DISCORD, NotificationChannel.TELEGRAM],
            throttle_seconds=120,
            escalation_delay=300  # 5 minutes
        ))
        
        # System error notifications
        self.rules.append(NotificationRule(
            event_pattern="system.error",
            level=NotificationLevel.CRITICAL,
            template=self.templates["system_error"],
            channels=[NotificationChannel.DISCORD, NotificationChannel.TELEGRAM],
            throttle_seconds=60,
            escalation_delay=180  # 3 minutes
        ))
    
    def _subscribe_to_events(self) -> None:
        """Subscribe to relevant events."""
        # Create a sync wrapper for async handler
        def sync_handler(event: Event) -> None:
            """Sync wrapper for async event handler."""
            _ = asyncio.create_task(self._handle_event(event))
        
        # Create a subscriber for all events
        try:
            subscriber = EventSubscriber(
                topic="*",
                handler=sync_handler
            )
            self.event_bus.register_subscriber(subscriber)
            logger.info("Subscribed to event bus for notification bridge")
        except Exception as e:
            logger.error(f"Failed to subscribe to event bus: {e}")
    
    async def _handle_event(self, event: Event) -> None:
        """Handle incoming events and dispatch notifications.
        
        Args:
            event: Event to handle
        """
        try:
            # Find matching rules
            matching_rules = [rule for rule in self.rules if rule.matches_event(event)]
            
            if not matching_rules:
                return
            
            # Process each matching rule
            for rule in matching_rules:
                await self._process_notification_rule(event, rule)
                
        except Exception as e:
            logger.error(f"Error handling event for notifications: {e}")
    
    async def _process_notification_rule(self, event: Event, rule: NotificationRule) -> None:
        """Process a single notification rule.
        
        Args:
            event: Event that triggered the rule
            rule: Notification rule to process
        """
        try:
            # Check throttling
            if self.throttler and rule.throttle_seconds > 0:
                throttle_key = f"{rule.event_pattern}:{event.topic.name}"
                if not await self.throttler.should_send(throttle_key, rule.throttle_seconds):
                    logger.debug(f"Throttling notification for {event.topic.name}")
                    return
            
            # Format message
            message = self._format_message(event, rule)
            
            # Check for duplicates
            if self.deduplicator and await self.deduplicator.is_duplicate(message):
                logger.debug(f"Skipping duplicate notification for {event.topic.name}")
                return
            
            # Send notification
            _ = await self.dispatcher.dispatch_message(
                message=message,
                providers=["discord"],  # Default providers
                priority=1
            )
            logger.info(f"Sent notification for event: {event.topic.name}")
            
            # Schedule escalation if needed
            if (self.escalation_manager and 
                rule.escalation_delay > 0 and 
                rule.level in [NotificationLevel.ERROR, NotificationLevel.CRITICAL]):
                
                escalation_key = f"{event.topic.name}:{event.event_id}"
                
                def escalate() -> None:
                    _ = asyncio.create_task(self._escalate_notification(event, rule))
                
                await self.escalation_manager.schedule_escalation(
                    escalation_key,
                    rule.escalation_delay,
                    escalate
                )
            
        except Exception as e:
            logger.error(f"Error processing notification rule: {e}")
    
    def _format_message(self, event: Event, rule: NotificationRule) -> Message:
        """Format event data into notification message.
        
        Args:
            event: Event to format
            rule: Notification rule
            
        Returns:
            Formatted message
        """
        # Extract data from event
        data = event.data.copy() if event.data else {}
        
        # Add common event fields
        data.update({
            "event_topic": event.topic.name,
            "event_id": event.event_id,
            "event_timestamp": event.timestamp,
            "event_priority": event.priority.name
        })
        
        # Format process-specific data
        if "process" in data:
            process = cast(ProcessInfo, data["process"])
            data.update({
                "process_name": process.name,
                "process_pid": process.pid,
                "start_time": process.start_time.isoformat() if process.start_time else "Unknown"
            })
        
        # Format progress-specific data
        if "progress" in data:
            progress = cast(ProgressMetrics, data["progress"])
            data.update({
                "progress_percentage": progress.percentage,
                "eta": "Unknown"  # ETA not implemented in ProgressMetrics yet
            })
        
        # Format error-specific data
        if "error" in data:
            error = data["error"]
            data.update({
                "error_message": str(error),
                "error_type": type(error).__name__,
                "error_time": str(event.timestamp)
            })
        
        # Use template to format message
        try:
            # Convert all values to strings for template formatting
            str_data = {k: str(v) for k, v in data.items()}
            return rule.template.format(**str_data)
        except KeyError as e:
            logger.warning(f"Missing template data for key: {e}")
            # Fallback to basic message
            return Message(
                title=f"Event: {event.topic.name}",
                content=f"Event occurred at {event.timestamp}",
                priority="normal",
                tags=["event", "fallback"]
            )
    
    async def _escalate_notification(self, event: Event, rule: NotificationRule) -> None:
        """Escalate a notification.
        
        Args:
            event: Original event
            rule: Notification rule
        """
        try:
            # Create escalated message
            escalated_message = self._format_message(event, rule)
            escalated_message.title = f"ESCALATED: {escalated_message.title}"
            escalated_message.priority = "high"
            escalated_message.tags.append("escalated")
            
            # Send escalated notification
            _ = await self.dispatcher.dispatch_message(
                message=escalated_message,
                providers=["discord"],
                priority=1
            )
            logger.warning(f"Escalated notification for event: {event.topic.name}")
            
        except Exception as e:
            logger.error(f"Error escalating notification: {e}")
    
    def add_rule(self, rule: NotificationRule) -> None:
        """Add a notification rule.
        
        Args:
            rule: Rule to add
        """
        self.rules.append(rule)
        logger.info(f"Added notification rule for pattern: {rule.event_pattern}")
    
    def remove_rule(self, event_pattern: str) -> None:
        """Remove notification rules matching pattern.
        
        Args:
            event_pattern: Pattern to match
        """
        self.rules = [rule for rule in self.rules if rule.event_pattern != event_pattern]
        logger.info(f"Removed notification rules for pattern: {event_pattern}")
    
    def add_template(self, name: str, template: NotificationTemplate) -> None:
        """Add a notification template.
        
        Args:
            name: Template name
            template: Template to add
        """
        self.templates[name] = template
        logger.info(f"Added notification template: {name}")
    
    def enable_rule(self, event_pattern: str, enabled: bool = True) -> None:
        """Enable or disable notification rules.
        
        Args:
            event_pattern: Pattern to match
            enabled: Whether to enable rules
        """
        for rule in self.rules:
            if rule.event_pattern == event_pattern:
                rule.enabled = enabled
        
        status = "enabled" if enabled else "disabled"
        logger.info(f"Notification rules for pattern '{event_pattern}' {status}")
    
    async def shutdown(self) -> None:
        """Shutdown the notification bridge."""
        logger.info("Shutting down notification bridge")
        
        # Cancel all escalations
        if self.escalation_manager:
            await self.escalation_manager.cancel_all_escalations()
        
        logger.info("Notification bridge shutdown complete")


# Integration function for orchestrator
def create_notification_bridge(
    event_bus: EventBus,
    dispatcher: AsyncDispatcher,
    *,
    enable_throttling: bool = True,
    enable_deduplication: bool = True,
    enable_escalation: bool = True
) -> NotificationBridge:
    """Create and configure notification bridge for orchestrator.
    
    Args:
        event_bus: Event bus from orchestrator
        dispatcher: Notification dispatcher
        enable_throttling: Whether to enable throttling
        enable_deduplication: Whether to enable deduplication
        enable_escalation: Whether to enable escalation
        
    Returns:
        Configured notification bridge
    """
    bridge = NotificationBridge(
        event_bus=event_bus,
        dispatcher=dispatcher,
        enable_throttling=enable_throttling,
        enable_deduplication=enable_deduplication,
        enable_escalation=enable_escalation
    )
    
    logger.info("Created notification bridge for orchestrator")
    return bridge