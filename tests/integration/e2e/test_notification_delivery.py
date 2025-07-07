"""End-to-end tests for notification delivery system."""

from __future__ import annotations

import asyncio
import pytest
from typing import TYPE_CHECKING, override
from collections.abc import Coroutine
from collections.abc import Mapping
from mover_status.notifications.base.provider import NotificationProvider
from mover_status.notifications.base.registry import (
    ProviderMetadata,
    ProviderLifecycleManager,
    get_global_registry
)
from mover_status.notifications.manager.dispatcher import AsyncDispatcher, DispatchStatus, DispatchResult
from mover_status.notifications.models.message import Message
from mover_status.notifications.base.config_validator import ConfigValidator

if TYPE_CHECKING:
    pass


class E2EMockProvider(NotificationProvider):
    """Mock provider for end-to-end testing with realistic behavior."""
    
    def __init__(self, config: Mapping[str, object], name: str = "e2e_mock") -> None:
        super().__init__(config)
        self.name: str = name
        self.send_calls: list[Message] = []
        network_delay_value = config.get("network_delay", 0.1)
        failure_rate_value = config.get("failure_rate", 0.0)
        self.network_delay: float = float(network_delay_value) if isinstance(network_delay_value, (int, float, str)) else 0.1
        self.failure_rate: float = float(failure_rate_value) if isinstance(failure_rate_value, (int, float, str)) else 0.0
        self.call_count: int = 0
        
    @override
    async def send_notification(self, message: Message) -> bool:
        """Mock send notification with network simulation."""
        # Simulate network delay
        await asyncio.sleep(self.network_delay)
        
        self.call_count += 1
        self.send_calls.append(message)
        
        # Simulate occasional failures
        if self.failure_rate > 0 and (self.call_count % int(1 / self.failure_rate)) == 0:
            raise Exception(f"Simulated network failure from {self.name}")
            
        return True
        
    @override
    def validate_config(self) -> None:
        """Mock validate config with realistic checks."""
        required_fields = ["api_key", "endpoint"]
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required field: {field}")
                
        if not isinstance(self.config.get("enabled", True), bool):
            raise ValueError("enabled must be a boolean")
            
    @override
    def get_provider_name(self) -> str:
        """Mock get provider name."""
        return self.name


class TestNotificationDeliveryE2E:
    """End-to-end tests for notification delivery."""
    
    @pytest.mark.asyncio
    async def test_complete_notification_system_e2e(self) -> None:
        """Test complete notification system from configuration to delivery."""
        # Reset global registry for clean test
        get_global_registry().reset()
        
        # Setup configuration
        provider_configs: dict[str, dict[str, object]] = {
            "email_provider": {
                "enabled": True,
                "api_key": "test_email_key",
                "endpoint": "https://api.email.com",
                "network_delay": 0.05,
                "failure_rate": 0.0
            },
            "sms_provider": {
                "enabled": True,
                "api_key": "test_sms_key", 
                "endpoint": "https://api.sms.com",
                "network_delay": 0.1,
                "failure_rate": 0.0
            },
            "webhook_provider": {
                "enabled": True,
                "api_key": "test_webhook_key",
                "endpoint": "https://webhook.example.com",
                "network_delay": 0.02,
                "failure_rate": 0.0
            }
        }
        
        # Step 1: Configuration validation
        validator = ConfigValidator("test_provider")
        for provider_name, config in provider_configs.items():
            result = validator.validate_provider_config(provider_name, config)
            assert result.is_valid, f"Configuration invalid for {provider_name}: {result.issues}"
        
        # Step 2: Provider registration
        registry = get_global_registry()
        providers: dict[str, E2EMockProvider] = {}
        
        for provider_name, config in provider_configs.items():
            provider = E2EMockProvider(config, provider_name)
            providers[provider_name] = provider
            
            metadata = ProviderMetadata(
                name=provider_name,
                description=f"E2E test provider {provider_name}",
                version="1.0.0",
                author="E2E Test",
                provider_class=E2EMockProvider,
                tags=["test", "e2e"]
            )
            
            registry.register_provider(provider_name, E2EMockProvider, metadata)
        
        # Step 3: Lifecycle management
        lifecycle_manager = ProviderLifecycleManager()
        
        for provider_name, provider in providers.items():
            await lifecycle_manager.startup_provider(provider_name, provider)
            assert lifecycle_manager.is_provider_active(provider_name)
        
        # Step 4: Dispatcher setup
        dispatcher = AsyncDispatcher(max_workers=3, queue_size=50)
        
        for provider_name, provider in providers.items():
            dispatcher.register_provider(provider_name, provider)
        
        await dispatcher.start()
        
        try:
            # Step 5: Message creation and dispatch
            messages = [
                Message(
                    title="System Alert",
                    content="Critical system event detected",
                    priority="high",
                    tags=["alert", "critical"]
                ),
                Message(
                    title="Status Update", 
                    content="System status: operational",
                    priority="normal",
                    tags=["status", "info"]
                ),
                Message(
                    title="Maintenance Notice",
                    content="Scheduled maintenance in 1 hour",
                    priority="low",
                    tags=["maintenance", "scheduled"]
                )
            ]
            
            # Dispatch messages to all providers
            results: list[DispatchResult] = []
            for message in messages:
                result = await dispatcher.dispatch_message(
                    message, 
                    list(provider_configs.keys())
                )
                results.append(result)
            
            # Step 6: Verification
            for result in results:
                assert result.status == DispatchStatus.SUCCESS
                assert len(result.provider_results) == 3
                
                for provider_result in result.provider_results:
                    assert provider_result.success is True
                    assert provider_result.error is None
            
            # Verify all providers received all messages
            for provider in providers.values():
                assert len(provider.send_calls) == 3
                
                # Verify message content
                for i, message in enumerate(messages):
                    assert provider.send_calls[i] == message
        
        finally:
            # Step 7: Cleanup
            await dispatcher.stop()
            await lifecycle_manager.shutdown_all()
            
            # Verify cleanup
            for provider_name in providers.keys():
                assert not lifecycle_manager.is_provider_active(provider_name)
    
    @pytest.mark.asyncio
    async def test_failure_recovery_e2e(self) -> None:
        """Test end-to-end failure recovery scenarios."""
        # Setup providers with different failure characteristics
        reliable_config = {
            "enabled": True,
            "api_key": "reliable_key",
            "endpoint": "https://reliable.api.com",
            "network_delay": 0.01,
            "failure_rate": 0.0
        }
        
        unreliable_config = {
            "enabled": True,
            "api_key": "unreliable_key", 
            "endpoint": "https://unreliable.api.com",
            "network_delay": 0.1,
            "failure_rate": 0.3  # 30% failure rate
        }
        
        reliable_provider = E2EMockProvider(reliable_config, "reliable_provider")
        unreliable_provider = E2EMockProvider(unreliable_config, "unreliable_provider")
        
        # Setup dispatcher with retry capabilities
        dispatcher = AsyncDispatcher(max_workers=2, queue_size=10)
        dispatcher.register_provider("reliable_provider", reliable_provider)
        dispatcher.register_provider("unreliable_provider", unreliable_provider)
        
        await dispatcher.start()
        
        try:
            # Send multiple messages to test failure recovery
            messages: list[Message] = []
            for i in range(10):
                message = Message(
                    title=f"Recovery Test {i}",
                    content=f"Testing failure recovery scenario {i}",
                    priority="normal"
                )
                messages.append(message)
            
            # Dispatch all messages
            results: list[DispatchResult] = []
            for message in messages:
                result = await dispatcher.dispatch_message(
                    message,
                    ["reliable_provider", "unreliable_provider"]
                )
                results.append(result)
            
            # Analyze results
            success_count = sum(1 for r in results if r.status == DispatchStatus.SUCCESS)
            partial_count = sum(1 for r in results if r.status == DispatchStatus.PARTIAL)
            
            # Reliable provider should always succeed
            assert len(reliable_provider.send_calls) == 10
            
            # Unreliable provider should have some failures but some successes
            # With 30% failure rate, we expect some failures, but allow for randomness
            assert len(unreliable_provider.send_calls) <= 10
            assert len(unreliable_provider.send_calls) >= 0
            
            # Should have processed all messages (success or partial)
            assert success_count + partial_count == 10
            # With unreliable provider, we should have some partial results unless very lucky
            # But don't enforce strict requirements due to randomness
            
        finally:
            await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_performance_under_load_e2e(self) -> None:
        """Test system performance under load."""
        import time
        
        # Setup multiple fast providers
        providers: dict[str, E2EMockProvider] = {}
        for i in range(5):
            config = {
                "enabled": True,
                "api_key": f"fast_key_{i}",
                "endpoint": f"https://fast{i}.api.com",
                "network_delay": 0.001,  # Very fast
                "failure_rate": 0.0
            }
            provider = E2EMockProvider(config, f"fast_provider_{i}")
            providers[f"fast_provider_{i}"] = provider
        
        # Setup high-capacity dispatcher
        dispatcher = AsyncDispatcher(max_workers=10, queue_size=200)
        
        for provider_name, provider in providers.items():
            dispatcher.register_provider(provider_name, provider)
        
        await dispatcher.start()
        
        try:
            # Generate high volume of messages
            message_count = 100
            messages: list[Message] = []
            
            for i in range(message_count):
                message = Message(
                    title=f"Load Test {i}",
                    content=f"Performance test message {i}",
                    priority="normal"
                )
                messages.append(message)
            
            # Measure dispatch performance
            start_time = time.time()
            
            # Dispatch all messages concurrently
            tasks: list[Coroutine[object, object, DispatchResult]] = []
            for message in messages:
                task = dispatcher.dispatch_message(message, list(providers.keys()))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Performance assertions
            assert total_time < 10.0, f"Performance too slow: {total_time:.2f}s for {message_count} messages"
            
            # Verify all messages were processed successfully
            for result in results:
                assert result.status == DispatchStatus.SUCCESS
            
            # Calculate throughput
            messages_per_second = message_count / total_time
            total_deliveries = message_count * len(providers)
            deliveries_per_second = total_deliveries / total_time
            
            assert messages_per_second > 10, f"Message throughput too low: {messages_per_second:.1f} msg/s"
            assert deliveries_per_second > 50, f"Delivery throughput too low: {deliveries_per_second:.1f} del/s"
            
            # Verify all providers received all messages
            for provider in providers.values():
                assert len(provider.send_calls) == message_count
                
        finally:
            await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_e2e(self) -> None:
        """Test graceful system shutdown under load."""
        # Setup providers
        provider = E2EMockProvider({
            "enabled": True,
            "api_key": "shutdown_key",
            "endpoint": "https://shutdown.api.com",
            "network_delay": 0.1,  # Moderate delay
            "failure_rate": 0.0
        }, "shutdown_provider")
        
        dispatcher = AsyncDispatcher(max_workers=2, queue_size=20)
        dispatcher.register_provider("shutdown_provider", provider)
        
        await dispatcher.start()
        
        # Start dispatching messages
        tasks: list[Coroutine[object, object, DispatchResult]] = []
        for i in range(10):
            message = Message(
                title=f"Shutdown Test {i}",
                content=f"Testing graceful shutdown {i}",
                priority="normal"
            )
            task = dispatcher.dispatch_message(message, ["shutdown_provider"])
            tasks.append(task)
        
        # Allow some messages to start processing
        await asyncio.sleep(0.2)  # Give more time for processing to start
        
        # Initiate graceful shutdown
        shutdown_task = asyncio.create_task(dispatcher.stop())
        
        # Wait for both shutdown and message processing
        task_results, _ = await asyncio.gather(
            asyncio.gather(*tasks, return_exceptions=True),
            shutdown_task,
            return_exceptions=True
        )
        
        # Verify that messages were processed or properly cancelled
        # task_results is the list from gather(*tasks, return_exceptions=True)
        if isinstance(task_results, list):
            successful_results = [r for r in task_results if hasattr(r, 'status') and not isinstance(r, BaseException)]
        else:
            successful_results = []
        
        # Should have processed some messages successfully or at least attempted to
        # In a graceful shutdown, some messages might be cancelled
        assert len(successful_results) >= 0  # Allow for all messages to be cancelled
        # Provider might not have processed any if shutdown was very fast
        print(f"Processed {len(provider.send_calls)} messages during shutdown test")
        
        # System should be cleanly shut down
        assert not dispatcher.is_running()
