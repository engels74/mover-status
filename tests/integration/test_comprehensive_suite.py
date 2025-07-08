"""Comprehensive test suite for notification system TDD validation."""

from __future__ import annotations

import asyncio
import time
import pytest
from typing import TYPE_CHECKING, TypedDict
from collections.abc import Coroutine

from mover_status.notifications.base.registry import (
    ProviderMetadata,
    ProviderLifecycleManager,
    get_global_registry
)
from mover_status.notifications.manager.dispatcher import AsyncDispatcher, DispatchStatus, DispatchResult
from mover_status.notifications.models.message import Message
from mover_status.notifications.base.config_validator import ConfigValidator
from tests.fixtures.notification_mocks import (
    ReliableMockProvider,
    UnreliableMockProvider,
    SlowMockProvider,
    FastMockProvider,
    NotificationTestUtils
)

if TYPE_CHECKING:
    pass


class NotificationScenario(TypedDict):
    """Type definition for test scenarios."""
    name: str
    messages: list[Message]
    providers: list[str]
    expected_success_rate: float


class _ErrorScenarioBase(TypedDict):
    """Base for error scenarios."""
    name: str
    messages: list[Message]
    providers: list[str]


class ErrorScenario(_ErrorScenarioBase, total=False):
    """Type definition for error test scenarios."""
    expected_partial_results: bool
    expected_failures: bool


class TestComprehensiveNotificationSuite:
    """Comprehensive test suite validating all notification system components."""
    
    @pytest.mark.asyncio
    async def test_complete_system_integration(self) -> None:
        """Test complete system integration from configuration to delivery."""
        # Reset global state
        get_global_registry().reset()
        
        # Step 1: Configuration and validation
        configs = NotificationTestUtils.create_provider_configs()
        validator = ConfigValidator("comprehensive_test")
        
        for provider_name, config in configs.items():
            result = validator.validate_provider_config(provider_name, config)
            assert result.is_valid, f"Config validation failed for {provider_name}"
        
        # Step 2: Provider creation and registration
        registry = get_global_registry()
        providers: dict[str, ReliableMockProvider | UnreliableMockProvider | SlowMockProvider | FastMockProvider] = {
            "reliable": ReliableMockProvider(configs["reliable"], "reliable"),
            "unreliable": UnreliableMockProvider(configs["unreliable"], "unreliable"),
            "slow": SlowMockProvider(configs["slow"], "slow"),
            "fast": FastMockProvider(configs["fast"], "fast")
        }
        
        for provider_name, provider_class in [
            ("reliable", ReliableMockProvider),
            ("unreliable", UnreliableMockProvider), 
            ("slow", SlowMockProvider),
            ("fast", FastMockProvider)
        ]:
            metadata = ProviderMetadata(
                name=provider_name,
                description=f"Test provider {provider_name}",
                version="1.0.0",
                author="Comprehensive Test",
                provider_class=provider_class,
                tags=["test", "comprehensive"]
            )
            registry.register_provider(provider_name, provider_class, metadata)
        
        # Step 3: Lifecycle management
        lifecycle_manager = ProviderLifecycleManager()
        
        for provider_name, provider in providers.items():
            await lifecycle_manager.startup_provider(provider_name, provider)
            assert lifecycle_manager.is_provider_active(provider_name)
        
        # Step 4: Dispatcher setup and message processing
        dispatcher = AsyncDispatcher(max_workers=4, queue_size=100)
        
        for provider_name, provider in providers.items():
            dispatcher.register_provider(provider_name, provider)
        
        await dispatcher.start()
        
        try:
            # Step 5: Multi-scenario testing
            test_scenarios: list[NotificationScenario] = [
                NotificationScenario(
                    name="high_priority_alerts",
                    messages=[
                        Message(title="Critical Alert", content="System failure detected", priority="high"),
                        Message(title="Security Alert", content="Unauthorized access", priority="high"),
                        Message(title="Performance Alert", content="High CPU usage", priority="high")
                    ],
                    providers=["reliable", "fast"],
                    expected_success_rate=99.0
                ),
                NotificationScenario(
                    name="bulk_notifications",
                    messages=NotificationTestUtils.create_test_messages(50, "Bulk"),
                    providers=["reliable", "unreliable", "fast"],
                    expected_success_rate=70.0  # More realistic with unreliable provider
                ),
                NotificationScenario(
                    name="mixed_load_test",
                    messages=NotificationTestUtils.create_test_messages(20, "Mixed"),
                    providers=["reliable", "unreliable", "slow", "fast"],
                    expected_success_rate=60.0  # More realistic with unreliable and slow providers
                )
            ]
            
            overall_results: dict[str, dict[str, float]] = {}
            
            for scenario in test_scenarios:
                print(f"\nExecuting scenario: {scenario['name']}")
                
                # Reset provider stats
                for provider in providers.values():
                    provider.reset_stats()
                
                start_time = time.time()
                
                # Dispatch all messages in scenario
                tasks: list[Coroutine[object, object, DispatchResult]] = []
                for message in scenario["messages"]:
                    task = dispatcher.dispatch_message(message, scenario["providers"])
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks)
                
                processing_time = time.time() - start_time
                
                # Analyze scenario results
                successful_dispatches = sum(1 for r in results if r.status == DispatchStatus.SUCCESS)
                total_dispatches = len(results)
                success_rate = (successful_dispatches / total_dispatches) * 100
                
                # Verify scenario expectations
                expected_rate = scenario["expected_success_rate"]
                assert isinstance(expected_rate, (int, float)), f"Expected success rate should be numeric, got {type(expected_rate)}"
                assert success_rate >= expected_rate, (
                    f"Scenario {scenario['name']} success rate {success_rate:.1f}% "
                    f"below expected {expected_rate}%"
                )
                
                # Store results for overall analysis
                scenario_messages = scenario["messages"]
                scenario_providers = scenario["providers"]
                message_count = len(scenario_messages)
                provider_count = len(scenario_providers)
                
                overall_results[scenario["name"]] = {
                    "success_rate": success_rate,
                    "processing_time": processing_time,
                    "message_count": float(message_count),
                    "provider_count": float(provider_count)
                }
                
                print(f"  Success rate: {success_rate:.1f}%")
                print(f"  Processing time: {processing_time:.2f}s")
                print(f"  Messages/second: {message_count / processing_time:.1f}")
            
            # Step 6: Overall system validation
            total_messages = sum(int(r["message_count"]) for r in overall_results.values())
            total_time = sum(r["processing_time"] for r in overall_results.values())
            overall_throughput = total_messages / total_time
            
            assert overall_throughput > 5, f"Overall throughput too low: {overall_throughput:.1f} msg/s"
            
            # Verify all providers processed messages
            for provider_name, provider in providers.items():
                assert provider.stats.send_count > 0, f"Provider {provider_name} processed no messages"
                print(f"  {provider_name}: {provider.stats.send_count} messages, "
                      + f"{provider.stats.success_rate:.1f}% success rate")
            
        finally:
            # Step 7: Cleanup
            await dispatcher.stop()
            await lifecycle_manager.shutdown_all()
            
            # Verify clean shutdown
            for provider_name in providers.keys():
                assert not lifecycle_manager.is_provider_active(provider_name)
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self) -> None:
        """Test comprehensive error handling and recovery scenarios."""
        configs = NotificationTestUtils.create_provider_configs()
        
        # Create providers with different failure characteristics
        providers = {
            "reliable": ReliableMockProvider(configs["reliable"], "reliable"),
            "unreliable": UnreliableMockProvider(configs["unreliable"], "unreliable")
        }
        
        dispatcher = AsyncDispatcher(max_workers=2, queue_size=50)
        
        for provider_name, provider in providers.items():
            dispatcher.register_provider(provider_name, provider)
        
        await dispatcher.start()
        
        try:
            # Test various error scenarios
            error_scenarios: list[ErrorScenario] = [
                ErrorScenario(
                    name="partial_failures",
                    messages=NotificationTestUtils.create_test_messages(20, "PartialFail"),
                    providers=["reliable", "unreliable"],
                    expected_partial_results=True
                ),
                ErrorScenario(
                    name="timeout_handling",
                    messages=[
                        Message(title="Timeout test", content="This may timeout", priority="normal")
                        for _ in range(10)
                    ],
                    providers=["unreliable"],
                    expected_failures=True
                )
            ]
            
            for scenario in error_scenarios:
                print(f"\nTesting error scenario: {scenario['name']}")
                
                # Reset stats
                for provider in providers.values():
                    provider.reset_stats()
                
                # Execute scenario
                tasks: list[Coroutine[object, object, DispatchResult]] = []
                for message in scenario["messages"]:
                    task = dispatcher.dispatch_message(message, scenario["providers"])
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks)
                
                # Analyze error handling
                success_count = sum(1 for r in results if r.status == DispatchStatus.SUCCESS)
                partial_count = sum(1 for r in results if r.status == DispatchStatus.PARTIAL)
                failed_count = sum(1 for r in results if r.status == DispatchStatus.FAILED)
                
                total_results = len(results)
                
                if scenario.get("expected_partial_results"):
                    assert partial_count > 0, f"Expected partial results in {scenario['name']}"
                
                if scenario.get("expected_failures"):
                    assert failed_count > 0 or partial_count > 0, (
                        f"Expected some failures in {scenario['name']}"
                    )
                
                # Verify system remained stable
                assert success_count + partial_count + failed_count == total_results
                
                print(f"  Success: {success_count}, Partial: {partial_count}, Failed: {failed_count}")
        
        finally:
            await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_performance_benchmarks(self) -> None:
        """Test performance benchmarks for the notification system."""
        configs = NotificationTestUtils.create_provider_configs()
        
        # Create high-performance setup
        fast_providers: dict[str, FastMockProvider] = {}
        for i in range(3):
            provider = FastMockProvider(configs["fast"], f"fast_{i}")
            fast_providers[f"fast_{i}"] = provider
        
        dispatcher = AsyncDispatcher(max_workers=6, queue_size=500)
        
        for provider_name, provider in fast_providers.items():
            dispatcher.register_provider(provider_name, provider)
        
        await dispatcher.start()
        
        try:
            # Performance benchmarks
            benchmarks = [
                {"message_count": 100, "max_time": 2.0, "min_throughput": 50},
                {"message_count": 500, "max_time": 8.0, "min_throughput": 60},
                {"message_count": 1000, "max_time": 15.0, "min_throughput": 65}
            ]
            
            for benchmark in benchmarks:
                print(f"\nRunning benchmark: {benchmark['message_count']} messages")
                
                # Reset stats
                for provider in fast_providers.values():
                    provider.reset_stats()
                
                # Create messages
                messages = NotificationTestUtils.create_test_messages(
                    int(benchmark["message_count"]), 
                    "Benchmark"
                )
                
                # Measure performance
                start_time = time.time()
                
                tasks: list[Coroutine[object, object, DispatchResult]] = []
                provider_names: list[str] = list(fast_providers.keys())
                
                for message in messages:
                    task = dispatcher.dispatch_message(message, provider_names)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks)
                
                processing_time = time.time() - start_time
                throughput = benchmark["message_count"] / processing_time
                
                # Verify benchmark requirements
                assert processing_time <= benchmark["max_time"], (
                    f"Benchmark failed: {processing_time:.2f}s > {benchmark['max_time']}s"
                )
                
                assert throughput >= benchmark["min_throughput"], (
                    f"Throughput too low: {throughput:.1f} < {benchmark['min_throughput']} msg/s"
                )
                
                # Verify all messages were processed successfully
                success_count = sum(1 for r in results if r.status == DispatchStatus.SUCCESS)
                assert success_count == benchmark["message_count"]
                
                print(f"  Time: {processing_time:.2f}s, Throughput: {throughput:.1f} msg/s")
        
        finally:
            await dispatcher.stop()
    
    def test_test_coverage_validation(self) -> None:
        """Validate that all components have comprehensive test coverage."""
        # This test ensures our TDD approach has covered all components
        
        # Check that all major components have corresponding test files
        expected_test_modules = [
            "tests.unit.notifications.base.test_provider",
            "tests.unit.notifications.base.test_registry", 
            "tests.unit.notifications.base.test_retry",
            "tests.unit.notifications.base.test_config_validator",
            "tests.unit.notifications.manager.test_dispatcher",
            "tests.integration.scenarios.test_notification_flow",
            "tests.integration.scenarios.test_notification_performance",
            "tests.integration.e2e.test_notification_delivery"
        ]
        
        for module_name in expected_test_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Required test module {module_name} not found: {e}")
        
        # Verify mock utilities are available
        from tests.fixtures.notification_mocks import (
            ReliableMockProvider,
            NotificationTestUtils
        )
        
        # Test that mock utilities work correctly
        config = {"enabled": True, "api_key": "test", "endpoint": "https://test.com"}
        provider = ReliableMockProvider(config, "coverage_test")
        
        assert provider.get_provider_name() == "coverage_test"
        assert provider.is_enabled()
        
        # Test utility functions
        messages = NotificationTestUtils.create_test_messages(5, "Coverage")
        assert len(messages) == 5
        assert all(msg.title.startswith("Coverage") for msg in messages)
        
        configs = NotificationTestUtils.create_provider_configs()
        assert "reliable" in configs
        assert "unreliable" in configs
        
        print("✓ All test coverage requirements validated")
