"""Integration tests for complete notification flow scenarios."""

from __future__ import annotations

import asyncio
import time
import pytest
from typing import TYPE_CHECKING, override
from collections.abc import Mapping, Coroutine
from unittest.mock import AsyncMock

from mover_status.notifications.base.provider import NotificationProvider
from mover_status.notifications.base.registry import ProviderRegistry, ProviderMetadata
from mover_status.notifications.manager.dispatcher import AsyncDispatcher, DispatchStatus, DispatchResult
from mover_status.notifications.models.message import Message
from tests.fixtures.notification_mocks import (
    ReliableMockProvider,
    UnreliableMockProvider,
    NotificationTestUtils
)

if TYPE_CHECKING:
    pass


class IntegrationMockProvider(NotificationProvider):
    """Mock provider for integration testing with realistic behavior."""
    
    def __init__(self, config: Mapping[str, object], name: str = "integration_mock") -> None:
        super().__init__(config)
        self.name: str = name
        self.send_calls: list[Message] = []
        self.should_fail: bool = False
        self.delay: float = 0.0
        self.failure_count: int = 0
        self.max_failures: int = 0
        
    @override
    async def send_notification(self, message: Message) -> bool:
        """Mock send notification with realistic delays and failures."""
        if self.delay > 0:
            await asyncio.sleep(self.delay)
            
        self.send_calls.append(message)
        
        if self.should_fail and self.failure_count < self.max_failures:
            self.failure_count += 1
            raise Exception(f"Integration mock failure from {self.name}")
            
        return True
        
    @override
    def validate_config(self) -> None:
        """Mock validate config."""
        if not self.config.get("enabled", True):
            raise ValueError("Provider not enabled")
            
    @override
    def get_provider_name(self) -> str:
        """Mock get provider name."""
        return self.name


class TestNotificationFlowIntegration:
    """Integration tests for complete notification flow."""
    
    @pytest.mark.asyncio
    async def test_complete_notification_flow(self) -> None:
        """Test complete flow from registration to delivery."""
        # Setup registry
        registry = ProviderRegistry()
        
        # Create providers
        provider1 = IntegrationMockProvider({"enabled": True}, "provider1")
        provider2 = IntegrationMockProvider({"enabled": True}, "provider2")
        
        # Register providers with metadata
        metadata1 = ProviderMetadata(
            name="provider1",
            description="Test provider 1",
            version="1.0.0",
            author="Test",
            provider_class=IntegrationMockProvider
        )
        metadata2 = ProviderMetadata(
            name="provider2", 
            description="Test provider 2",
            version="1.0.0",
            author="Test",
            provider_class=IntegrationMockProvider
        )
        
        registry.register_provider("provider1", IntegrationMockProvider, metadata1)
        registry.register_provider("provider2", IntegrationMockProvider, metadata2)
        
        # Setup dispatcher
        dispatcher = AsyncDispatcher(max_workers=2, queue_size=10)
        dispatcher.register_provider("provider1", provider1)
        dispatcher.register_provider("provider2", provider2)
        
        await dispatcher.start()
        
        try:
            # Create and dispatch message
            message = Message(
                title="Integration Test",
                content="Testing complete notification flow",
                priority="high"
            )
            
            result = await dispatcher.dispatch_message(message, ["provider1", "provider2"])
            
            # Verify successful delivery
            assert result.status == DispatchStatus.SUCCESS
            assert result.delivery_id is not None
            assert len(result.provider_results) == 2
            
            # Verify both providers received the message
            assert len(provider1.send_calls) == 1
            assert len(provider2.send_calls) == 1
            assert provider1.send_calls[0] == message
            assert provider2.send_calls[0] == message
            
        finally:
            await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_partial_failure_scenario(self) -> None:
        """Test scenario where some providers fail."""
        # Setup providers with one that fails
        provider1 = IntegrationMockProvider({"enabled": True}, "reliable_provider")
        provider2 = IntegrationMockProvider({"enabled": True}, "failing_provider")
        provider2.should_fail = True
        provider2.max_failures = 10  # Always fail
        
        # Setup dispatcher
        dispatcher = AsyncDispatcher(max_workers=2, queue_size=10)
        dispatcher.register_provider("reliable_provider", provider1)
        dispatcher.register_provider("failing_provider", provider2)
        
        await dispatcher.start()
        
        try:
            message = Message(
                title="Partial Failure Test",
                content="Testing partial failure handling",
                priority="normal"
            )
            
            result = await dispatcher.dispatch_message(
                message, 
                ["reliable_provider", "failing_provider"]
            )
            
            # Should be partial success
            assert result.status == DispatchStatus.PARTIAL
            assert len(result.provider_results) == 2
            
            # Verify reliable provider succeeded
            reliable_result = next(
                r for r in result.provider_results 
                if r.provider_name == "reliable_provider"
            )
            assert reliable_result.success is True
            assert len(provider1.send_calls) == 1
            
            # Verify failing provider failed
            failing_result = next(
                r for r in result.provider_results 
                if r.provider_name == "failing_provider"
            )
            assert failing_result.success is False
            assert failing_result.error is not None
            
        finally:
            await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_high_volume_scenario(self) -> None:
        """Test high-volume message processing."""
        # Setup multiple providers
        providers: list[IntegrationMockProvider] = []
        for i in range(3):
            provider = IntegrationMockProvider({"enabled": True}, f"provider_{i}")
            provider.delay = 0.01  # Small delay to simulate real work
            providers.append(provider)
        
        # Setup dispatcher with higher capacity
        dispatcher = AsyncDispatcher(max_workers=5, queue_size=100)
        for i, provider in enumerate(providers):
            dispatcher.register_provider(f"provider_{i}", provider)
        
        await dispatcher.start()
        
        try:
            # Send multiple messages concurrently
            messages: list[Message] = []
            tasks: list[Coroutine[object, object, DispatchResult]] = []
            
            for i in range(20):
                message = Message(
                    title=f"High Volume Test {i}",
                    content=f"Message {i} content",
                    priority="normal"
                )
                messages.append(message)
                
                # Dispatch to all providers
                provider_names = [f"provider_{j}" for j in range(3)]
                task = dispatcher.dispatch_message(message, provider_names)
                tasks.append(task)
            
            # Wait for all dispatches to complete
            results = await asyncio.gather(*tasks)
            
            # Verify all messages were processed successfully
            for result in results:
                assert result.status == DispatchStatus.SUCCESS
                assert len(result.provider_results) == 3
            
            # Verify each provider received all messages
            for provider in providers:
                assert len(provider.send_calls) == 20
                
        finally:
            await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_provider_lifecycle_integration(self) -> None:
        """Test provider lifecycle management integration."""
        from mover_status.notifications.base.registry import ProviderLifecycleManager
        
        # Create lifecycle manager
        lifecycle_manager = ProviderLifecycleManager()
        
        # Create providers with startup/shutdown hooks
        provider1 = IntegrationMockProvider({"enabled": True}, "lifecycle_provider1")
        provider2 = IntegrationMockProvider({"enabled": True}, "lifecycle_provider2")
        
        # Mock startup/shutdown hooks
        startup_hook1 = AsyncMock()
        shutdown_hook1 = AsyncMock()
        startup_hook2 = AsyncMock()
        shutdown_hook2 = AsyncMock()
        
        # Add hooks
        lifecycle_manager.add_startup_hook("lifecycle_provider1", startup_hook1)
        lifecycle_manager.add_shutdown_hook("lifecycle_provider1", shutdown_hook1)
        lifecycle_manager.add_startup_hook("lifecycle_provider2", startup_hook2)
        lifecycle_manager.add_shutdown_hook("lifecycle_provider2", shutdown_hook2)
        
        # Start providers
        await lifecycle_manager.startup_provider("lifecycle_provider1", provider1)
        await lifecycle_manager.startup_provider("lifecycle_provider2", provider2)
        
        # Verify startup hooks were called
        startup_hook1.assert_called_once_with(provider1)
        startup_hook2.assert_called_once_with(provider2)
        
        # Verify providers are active
        assert lifecycle_manager.is_provider_active("lifecycle_provider1")
        assert lifecycle_manager.is_provider_active("lifecycle_provider2")
        
        # Shutdown all providers
        await lifecycle_manager.shutdown_all()
        
        # Verify shutdown hooks were called
        shutdown_hook1.assert_called_once_with(provider1)
        shutdown_hook2.assert_called_once_with(provider2)
        
        # Verify providers are no longer active
        assert not lifecycle_manager.is_provider_active("lifecycle_provider1")
        assert not lifecycle_manager.is_provider_active("lifecycle_provider2")

    @pytest.mark.asyncio
    async def test_configuration_validation_integration(self) -> None:
        """Test configuration validation integration."""
        from mover_status.notifications.base.config_validator import ConfigValidator

        # Create validator
        validator = ConfigValidator("config_test_provider")

        # Test valid configuration
        valid_config = {
            "enabled": True,
            "timeout": 30,
            "retry_attempts": 3
        }

        _ = IntegrationMockProvider(valid_config, "config_test_provider")

        # Validate configuration
        result = validator.validate_provider_config("config_test_provider", valid_config)
        assert result.is_valid
        assert len(result.issues) == 0

        # Test invalid configuration
        invalid_config = {
            "enabled": "not_a_boolean",  # Invalid type
            "timeout": -1,  # Invalid value
        }

        result = validator.validate_provider_config("config_test_provider", invalid_config)
        assert not result.is_valid
        assert len(result.issues) > 0

    @pytest.mark.asyncio
    async def test_enhanced_provider_scenarios(self) -> None:
        """Test scenarios using enhanced mock providers."""
        scenarios = NotificationTestUtils.create_test_scenarios()

        for scenario in scenarios:
            print(f"\nTesting scenario: {scenario.name} - {scenario.description}")

            # Setup dispatcher
            dispatcher = AsyncDispatcher(max_workers=5, queue_size=scenario.message_count * 2)

            for provider_name, provider in scenario.providers.items():
                dispatcher.register_provider(provider_name, provider)

            await dispatcher.start()

            try:
                # Create test messages
                messages = NotificationTestUtils.create_test_messages(
                    scenario.message_count,
                    f"Scenario_{scenario.name}"
                )

                # Measure processing time
                start_time = time.time()

                # Dispatch messages
                tasks: list[Coroutine[object, object, DispatchResult]] = []
                provider_names = list(scenario.providers.keys())

                for message in messages:
                    task = dispatcher.dispatch_message(message, provider_names)
                    tasks.append(task)

                _ = await asyncio.gather(*tasks)

                processing_time = time.time() - start_time

                # Analyze results
                analysis = NotificationTestUtils.analyze_test_results(
                    scenario.providers,
                    processing_time
                )

                # Verify scenario expectations
                assert processing_time <= scenario.max_processing_time, (
                    f"Scenario {scenario.name} took too long: {processing_time:.2f}s "
                    f"(max: {scenario.max_processing_time}s)"
                )

                success_rate = analysis["overall_success_rate"]
                expected_rate = scenario.expected_success_rate
                assert isinstance(success_rate, (int, float)), f"Success rate should be numeric, got {type(success_rate)}"
                assert isinstance(expected_rate, (int, float)), f"Expected rate should be numeric, got {type(expected_rate)}"
                assert success_rate >= expected_rate, (
                    f"Scenario {scenario.name} success rate too low: "
                    f"{success_rate:.1%} (expected: {expected_rate:.1%})"
                )

                # Verify all messages were processed
                total_expected = scenario.message_count * len(scenario.providers)
                assert analysis["total_messages"] == total_expected

                print(f"  Success rate: {analysis['overall_success_rate']:.1f}%")
                print(f"  Processing time: {processing_time:.2f}s")
                print(f"  Throughput: {analysis['messages_per_second']:.1f} msg/s")

            finally:
                await dispatcher.stop()

    @pytest.mark.asyncio
    async def test_provider_failure_patterns(self) -> None:
        """Test specific failure patterns and recovery."""
        configs = NotificationTestUtils.create_provider_configs()

        # Create provider with specific failure patterns
        unreliable_provider = UnreliableMockProvider(configs["unreliable"], "pattern_test")
        reliable_provider = ReliableMockProvider(configs["reliable"], "reliable_backup")

        dispatcher = AsyncDispatcher(max_workers=2, queue_size=20)
        dispatcher.register_provider("pattern_test", unreliable_provider)
        dispatcher.register_provider("reliable_backup", reliable_provider)

        await dispatcher.start()

        try:
            # Create messages with failure-triggering patterns
            failure_messages = [
                Message(title="Error in system", content="This should trigger failure", priority="high"),
                Message(title="Timeout occurred", content="Another failure trigger", priority="normal"),
                Message(title="Normal message", content="This should succeed", priority="low"),
                Message(title="System failure", content="Yet another failure", priority="high"),
                Message(title="Success story", content="This should work fine", priority="normal"),
            ]

            results: list[DispatchResult] = []
            for message in failure_messages:
                result = await dispatcher.dispatch_message(
                    message,
                    ["pattern_test", "reliable_backup"]
                )
                results.append(result)

            # Analyze failure patterns
            pattern_failures = 0
            reliable_successes = 0

            for result in results:
                # Check if unreliable provider failed due to patterns
                pattern_result = next(
                    r for r in result.provider_results
                    if r.provider_name == "pattern_test"
                )
                if not pattern_result.success:
                    pattern_failures += 1

                # Reliable provider should always succeed
                reliable_result = next(
                    r for r in result.provider_results
                    if r.provider_name == "reliable_backup"
                )
                if reliable_result.success:
                    reliable_successes += 1

            # Verify failure patterns worked
            assert pattern_failures >= 3, f"Expected at least 3 pattern failures, got {pattern_failures}"
            assert reliable_successes == 5, f"Expected 5 reliable successes, got {reliable_successes}"

        finally:
            await dispatcher.stop()
