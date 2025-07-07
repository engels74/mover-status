"""Performance tests for notification system components."""

from __future__ import annotations

import asyncio
import time
import pytest
from typing import TYPE_CHECKING, override
from collections.abc import Mapping, Coroutine

from mover_status.notifications.base.provider import NotificationProvider
from mover_status.notifications.base.registry import ProviderRegistry, ProviderMetadata
from mover_status.notifications.manager.dispatcher import AsyncDispatcher, DispatchStatus, DispatchResult
from mover_status.notifications.models.message import Message

if TYPE_CHECKING:
    pass


class PerformanceMockProvider(NotificationProvider):
    """Mock provider optimized for performance testing."""
    
    def __init__(self, config: Mapping[str, object], name: str = "perf_mock") -> None:
        super().__init__(config)
        self.name: str = name
        self.send_calls: list[Message] = []
        processing_time_val = config.get("processing_time", 0.001)
        self.processing_time: float = float(processing_time_val) if isinstance(processing_time_val, (int, float)) else 0.001
        self.call_count: int = 0
        
    @override
    async def send_notification(self, message: Message) -> bool:
        """Mock send notification with configurable processing time."""
        if self.processing_time > 0:
            await asyncio.sleep(self.processing_time)
            
        self.call_count += 1
        self.send_calls.append(message)
        return True
        
    @override
    def validate_config(self) -> None:
        """Mock validate config - no-op for performance."""
        pass
        
    @override
    def get_provider_name(self) -> str:
        """Mock get provider name."""
        return self.name


class TestNotificationPerformance:
    """Performance tests for notification system."""
    
    @pytest.mark.asyncio
    async def test_dispatcher_throughput_performance(self) -> None:
        """Test dispatcher throughput under various loads."""
        test_scenarios = [
            {"messages": 100, "providers": 1, "workers": 2},
            {"messages": 500, "providers": 3, "workers": 5},
            {"messages": 1000, "providers": 5, "workers": 10},
        ]
        
        for scenario in test_scenarios:
            message_count = scenario["messages"]
            provider_count = scenario["providers"]
            worker_count = scenario["workers"]
            
            # Setup providers
            providers: list[PerformanceMockProvider] = []
            for i in range(provider_count):
                provider = PerformanceMockProvider(
                    {"processing_time": 0.001}, 
                    f"perf_provider_{i}"
                )
                providers.append(provider)
            
            # Setup dispatcher
            dispatcher = AsyncDispatcher(
                max_workers=worker_count, 
                queue_size=message_count * 2
            )
            
            for i, provider in enumerate(providers):
                dispatcher.register_provider(f"perf_provider_{i}", provider)
            
            await dispatcher.start()
            
            try:
                # Generate messages
                messages: list[Message] = []
                for i in range(message_count):
                    message = Message(
                        title=f"Perf Test {i}",
                        content=f"Performance test message {i}",
                        priority="normal"
                    )
                    messages.append(message)
                
                # Measure dispatch performance
                start_time = time.time()
                
                # Dispatch all messages concurrently
                tasks: list[Coroutine[object, object, DispatchResult]] = []
                provider_names = [f"perf_provider_{i}" for i in range(provider_count)]
                
                for message in messages:
                    task = dispatcher.dispatch_message(message, provider_names)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks)
                
                end_time = time.time()
                total_time = end_time - start_time
                
                # Performance metrics
                messages_per_second = message_count / total_time
                total_deliveries = message_count * provider_count
                deliveries_per_second = total_deliveries / total_time
                
                # Performance assertions
                min_msg_per_sec = 50  # Minimum messages per second
                min_del_per_sec = 100  # Minimum deliveries per second
                
                assert messages_per_second > min_msg_per_sec, (
                    f"Scenario {scenario}: Message throughput too low: "
                    f"{messages_per_second:.1f} msg/s (min: {min_msg_per_sec})"
                )
                
                assert deliveries_per_second > min_del_per_sec, (
                    f"Scenario {scenario}: Delivery throughput too low: "
                    f"{deliveries_per_second:.1f} del/s (min: {min_del_per_sec})"
                )
                
                # Verify all messages were processed successfully
                for result in results:
                    assert result.status == DispatchStatus.SUCCESS
                
                # Verify all providers received all messages
                for provider in providers:
                    assert len(provider.send_calls) == message_count
                    
                print(f"Scenario {scenario}: {messages_per_second:.1f} msg/s, "
                      + f"{deliveries_per_second:.1f} del/s, {total_time:.3f}s total")
                
            finally:
                await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_registry_performance(self) -> None:
        """Test provider registry performance with many providers."""
        registry = ProviderRegistry()
        
        # Test provider registration performance
        provider_count = 1000
        
        start_time = time.time()
        
        for i in range(provider_count):
            metadata = ProviderMetadata(
                name=f"provider_{i}",
                description=f"Performance test provider {i}",
                version="1.0.0",
                author="Performance Test",
                provider_class=PerformanceMockProvider
            )
            
            registry.register_provider(
                f"provider_{i}", 
                PerformanceMockProvider, 
                metadata
            )
        
        registration_time = time.time() - start_time
        
        # Performance assertion for registration
        registrations_per_second = provider_count / registration_time
        assert registrations_per_second > 1000, (
            f"Registration too slow: {registrations_per_second:.0f} reg/s"
        )
        
        # Test provider lookup performance
        start_time = time.time()
        
        for i in range(provider_count):
            assert registry.provider_exists(f"provider_{i}")
            metadata = registry.get_provider_metadata(f"provider_{i}")
            assert metadata is not None
        
        lookup_time = time.time() - start_time
        
        # Performance assertion for lookup
        lookups_per_second = provider_count / lookup_time
        assert lookups_per_second > 5000, (
            f"Lookup too slow: {lookups_per_second:.0f} lookups/s"
        )
        
        # Test provider creation performance
        start_time = time.time()
        
        created_providers: list[NotificationProvider] = []
        for i in range(min(100, provider_count)):  # Test subset for creation
            provider = registry.create_provider(f"provider_{i}", {"processing_time": 0.001})
            created_providers.append(provider)
        
        creation_time = time.time() - start_time
        
        # Performance assertion for creation
        creations_per_second = len(created_providers) / creation_time
        assert creations_per_second > 100, (
            f"Creation too slow: {creations_per_second:.0f} creations/s"
        )
        
        print(f"Registry performance: {registrations_per_second:.0f} reg/s, "
              + f"{lookups_per_second:.0f} lookups/s, {creations_per_second:.0f} creations/s")
    
    @pytest.mark.asyncio
    async def test_message_processing_performance(self) -> None:
        """Test message processing performance with various message sizes."""
        provider = PerformanceMockProvider({"processing_time": 0.0001}, "msg_perf_provider")
        
        # Test different message sizes (within Message model constraints)
        message_sizes = [
            {"title_len": 50, "content_len": 200},      # Small
            {"title_len": 100, "content_len": 1000},    # Medium
            {"title_len": 150, "content_len": 2000},    # Large
            {"title_len": 180, "content_len": 3500},    # Very Large (within limits)
        ]
        
        for size_config in message_sizes:
            title = "A" * size_config["title_len"]
            content = "B" * size_config["content_len"]
            
            # Create messages
            message_count = 100
            messages: list[Message] = []
            
            for i in range(message_count):
                message = Message(
                    title=f"{title}_{i}",
                    content=f"{content}_{i}",
                    priority="normal",
                    tags=[f"tag_{i}", "performance", "test"]
                )
                messages.append(message)
            
            # Measure processing time
            start_time = time.time()
            
            for message in messages:
                _ = await provider.send_notification(message)
            
            processing_time = time.time() - start_time
            
            # Calculate metrics
            messages_per_second = message_count / processing_time
            total_bytes = sum(len(msg.title) + len(msg.content) for msg in messages)
            bytes_per_second = total_bytes / processing_time
            
            # Performance assertions
            min_msg_per_sec = 500  # Minimum messages per second
            
            assert messages_per_second > min_msg_per_sec, (
                f"Message size {size_config}: Processing too slow: "
                f"{messages_per_second:.0f} msg/s (min: {min_msg_per_sec})"
            )
            
            print(f"Message size {size_config}: {messages_per_second:.0f} msg/s, "
                  + f"{bytes_per_second / 1024:.1f} KB/s")
    
    @pytest.mark.asyncio
    async def test_concurrent_dispatcher_performance(self) -> None:
        """Test performance with multiple concurrent dispatchers."""
        dispatcher_count = 3
        messages_per_dispatcher = 200
        
        # Setup multiple dispatchers
        dispatchers: list[tuple[AsyncDispatcher, list[PerformanceMockProvider]]] = []
        all_providers: list[PerformanceMockProvider] = []
        
        for d in range(dispatcher_count):
            # Create providers for this dispatcher
            providers: list[PerformanceMockProvider] = []
            for p in range(2):
                provider = PerformanceMockProvider(
                    {"processing_time": 0.001}, 
                    f"dispatcher_{d}_provider_{p}"
                )
                providers.append(provider)
                all_providers.append(provider)
            
            # Setup dispatcher
            dispatcher = AsyncDispatcher(max_workers=3, queue_size=messages_per_dispatcher * 2)
            
            for i, provider in enumerate(providers):
                dispatcher.register_provider(f"dispatcher_{d}_provider_{i}", provider)
            
            dispatchers.append((dispatcher, providers))
        
        # Start all dispatchers
        for dispatcher, _ in dispatchers:
            await dispatcher.start()
        
        try:
            # Measure concurrent dispatch performance
            start_time = time.time()
            
            # Create dispatch tasks for all dispatchers
            all_tasks: list[Coroutine[object, object, DispatchResult]] = []
            
            for d, (dispatcher, providers) in enumerate(dispatchers):
                provider_names = [f"dispatcher_{d}_provider_{i}" for i in range(len(providers))]
                
                for i in range(messages_per_dispatcher):
                    message = Message(
                        title=f"Concurrent Test D{d} M{i}",
                        content=f"Concurrent dispatch test dispatcher {d} message {i}",
                        priority="normal"
                    )
                    
                    task = dispatcher.dispatch_message(message, provider_names)
                    all_tasks.append(task)
            
            # Wait for all dispatches to complete
            results = await asyncio.gather(*all_tasks)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Calculate performance metrics
            total_messages = dispatcher_count * messages_per_dispatcher
            total_deliveries = sum(len(providers) for _, providers in dispatchers) * messages_per_dispatcher
            
            messages_per_second = total_messages / total_time
            deliveries_per_second = total_deliveries / total_time
            
            # Performance assertions
            min_concurrent_msg_per_sec = 100
            min_concurrent_del_per_sec = 200
            
            assert messages_per_second > min_concurrent_msg_per_sec, (
                f"Concurrent dispatch too slow: {messages_per_second:.1f} msg/s "
                f"(min: {min_concurrent_msg_per_sec})"
            )
            
            assert deliveries_per_second > min_concurrent_del_per_sec, (
                f"Concurrent delivery too slow: {deliveries_per_second:.1f} del/s "
                f"(min: {min_concurrent_del_per_sec})"
            )
            
            # Verify all messages were processed successfully
            for result in results:
                assert result.status == DispatchStatus.SUCCESS
            
            # Verify all providers received expected messages
            for provider in all_providers:
                assert len(provider.send_calls) == messages_per_dispatcher
            
            print(f"Concurrent performance: {messages_per_second:.1f} msg/s, "
                  + f"{deliveries_per_second:.1f} del/s with {dispatcher_count} dispatchers")
            
        finally:
            # Stop all dispatchers
            for dispatcher, _ in dispatchers:
                await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_memory_usage_performance(self) -> None:
        """Test memory usage under high load."""
        import gc
        
        # Force garbage collection before test
        _ = gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Setup high-capacity system
        provider = PerformanceMockProvider({"processing_time": 0.0001}, "memory_test_provider")
        dispatcher = AsyncDispatcher(max_workers=5, queue_size=2000)
        dispatcher.register_provider("memory_test_provider", provider)
        
        await dispatcher.start()
        
        try:
            # Process large number of messages
            message_count = 1000
            batch_size = 100
            
            for batch in range(message_count // batch_size):
                # Create batch of messages
                messages: list[Message] = []
                for i in range(batch_size):
                    message_id = batch * batch_size + i
                    message = Message(
                        title=f"Memory Test {message_id}",
                        content=f"Memory usage test message {message_id} with some content",
                        priority="normal",
                        tags=["memory", "test", f"batch_{batch}"]
                    )
                    messages.append(message)
                
                # Dispatch batch
                tasks: list[Coroutine[object, object, DispatchResult]] = []
                for message in messages:
                    task = dispatcher.dispatch_message(message, ["memory_test_provider"])
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks)
                
                # Verify batch processing
                for result in results:
                    assert result.status == DispatchStatus.SUCCESS
                
                # Force garbage collection periodically
                if batch % 5 == 0:
                    _ = gc.collect()
            
            # Final garbage collection
            _ = gc.collect()
            final_objects = len(gc.get_objects())
            
            # Memory usage assertion - be more realistic for async systems
            object_growth = final_objects - initial_objects
            max_object_growth = message_count * 15  # Allow reasonable growth for async processing

            assert object_growth < max_object_growth, (
                f"Excessive memory usage: {object_growth} new objects "
                f"(max allowed: {max_object_growth})"
            )
            
            # Verify all messages were processed
            assert len(provider.send_calls) == message_count
            
            print(f"Memory test: {object_growth} object growth for {message_count} messages")
            
        finally:
            await dispatcher.stop()
            _ = gc.collect()  # Final cleanup
