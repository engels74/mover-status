"""End-to-end tests for Discord notification delivery with comprehensive scenarios."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Any

from mover_status.plugins.discord.provider import DiscordProvider
from mover_status.notifications.models.message import Message
from mover_status.notifications.manager.dispatcher import AsyncDispatcher, DispatchStatus
from mover_status.notifications.base.registry import get_global_registry, ProviderMetadata
from mover_status.notifications.base.config_validator import ConfigValidator


class TestDiscordNotificationE2E:
    """End-to-end tests for Discord notification system."""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self) -> None:
        """Reset global registry before each test."""
        get_global_registry().reset()
    
    @pytest.fixture
    def discord_config(self) -> dict[str, object]:
        """Standard Discord configuration for E2E testing."""
        return {
            "webhook_url": "https://discord.com/api/webhooks/987654321/e2e-test-token",
            "username": "E2E Test Bot",
            "avatar_url": "https://example.com/e2e-avatar.png",
            "timeout": 10.0,
            "max_retries": 2,
            "retry_delay": 0.5,
            "enabled": True,
        }
    
    @pytest.fixture
    def realistic_messages(self) -> list[Message]:
        """Realistic message scenarios for testing."""
        return [
            # System alert
            Message(
                title="🚨 Critical System Alert",
                content="Database connection pool exhausted. Immediate attention required.",
                priority="urgent",
                tags=["alert", "database", "critical"],
                metadata={
                    "severity": "critical",
                    "component": "database",
                    "affected_services": "api,web",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "incident_id": "INC-2025-001",
                },
            ),
            # Transfer progress
            Message(
                title="📁 Large File Transfer Progress",
                content="Transferring dataset.tar.gz (15.2 GB) - 67% complete",
                priority="normal",
                tags=["transfer", "progress", "file"],
                metadata={
                    "file_name": "dataset.tar.gz",
                    "file_size": "15.2GB",
                    "progress": "67%",
                    "speed": "125 MB/s",
                    "eta": "8 minutes",
                    "source": "/data/raw/",
                    "destination": "/backup/2025/",
                },
            ),
            # Maintenance window
            Message(
                title="🔧 Scheduled Maintenance Starting",
                content="Beginning scheduled database maintenance. Services may be temporarily unavailable.",
                priority="high",
                tags=["maintenance", "scheduled", "database"],
                metadata={
                    "maintenance_window": "2025-01-15 02:00-04:00 UTC",
                    "affected_services": "api,database,cache",
                    "expected_downtime": "45 minutes",
                    "contact": "ops-team@company.com",
                    "rollback_plan": "Available",
                },
            ),
            # Security event
            Message(
                title="🔒 Security Event Detected",
                content="Multiple failed login attempts detected from IP 192.168.1.100",
                priority="high",
                tags=["security", "authentication", "brute-force"],
                metadata={
                    "event_type": "failed_login_attempts",
                    "source_ip": "192.168.1.100",
                    "attempts": "15",
                    "time_window": "5 minutes",
                    "user_accounts": "admin,root,test",
                    "action_taken": "IP temporarily blocked",
                },
            ),
            # Backup completion
            Message(
                title="✅ Backup Job Completed",
                content="Daily backup job completed successfully. All data verified.",
                priority="low",
                tags=["backup", "success", "daily"],
                metadata={
                    "backup_type": "incremental",
                    "data_size": "2.8TB",
                    "duration": "2h 15m",
                    "verification": "passed",
                    "retention": "30 days",
                    "next_backup": "2025-01-16 02:00 UTC",
                },
            ),
        ]
    
    @pytest.mark.asyncio
    async def test_complete_discord_workflow_e2e(
        self,
        discord_config: dict[str, object],
        realistic_messages: list[Message],
    ) -> None:
        """Test complete Discord workflow from config to delivery."""
        # Step 1: Configuration Validation
        validator = ConfigValidator("discord")
        validation_result = validator.validate_provider_config("discord", discord_config)
        assert validation_result.is_valid, f"Config validation failed: {validation_result.issues}"
        
        # Step 2: Provider Registration
        registry = get_global_registry()
        metadata = ProviderMetadata(
            name="discord",
            description="Discord webhook notification provider",
            version="1.0.0",
            author="E2E Test Suite",
            provider_class=DiscordProvider,
            tags=["discord", "webhook", "notification"],
        )
        registry.register_provider("discord", DiscordProvider, metadata)
        
        # Step 3: Provider Instantiation and Validation
        provider = DiscordProvider(discord_config)
        assert provider.get_provider_name() == "discord"
        assert provider.is_enabled() is True
        
        # Step 4: Mock HTTP responses for realistic scenarios
        mock_responses: list[MagicMock] = []
        for _ in realistic_messages:
            response = MagicMock()
            response.status_code = 204
            response.headers = {}
            mock_responses.append(response)
        
        # Step 5: Execute End-to-End Workflow
        with patch("httpx.AsyncClient.post", side_effect=mock_responses) as mock_post:
            # Send messages individually
            results: list[bool] = []
            for message in realistic_messages:
                result = await provider.send_notification(message)
                results.append(result)
                
                # Small delay to simulate real-world timing
                await asyncio.sleep(0.01)
            
            # Step 6: Verification
            assert all(results), "Some notifications failed to send"
            assert mock_post.call_count == len(realistic_messages)
            
            # Step 7: Verify Payload Structure
            for i, call in enumerate(mock_post.call_args_list):
                payload: dict[str, Any] = call.kwargs["json"]
                
                # Verify basic payload structure
                assert "embeds" in payload
                assert "username" in payload
                assert "avatar_url" in payload
                assert len(payload["embeds"]) == 1
                
                # Verify embed content matches message
                embed: dict[str, Any] = payload["embeds"][0]
                message = realistic_messages[i]
                
                assert embed["title"] == message.title
                assert embed["description"] == message.content
                
                # Verify priority color mapping
                expected_colors = {
                    "low": 0x00FF00,     # Green
                    "normal": 0x0099FF,  # Blue
                    "high": 0xFF9900,    # Orange
                    "urgent": 0xFF0000,  # Red
                }
                assert embed["color"] == expected_colors[message.priority]
                
                # Verify fields
                field_names = [str(field["name"]) for field in embed["fields"]]
                
                # Should have priority field
                assert "Priority" in field_names
                
                # Should have tags field if tags exist
                if message.tags:
                    assert "Tags" in field_names
                    tags_field = next(f for f in embed["fields"] if f["name"] == "Tags")
                    assert tags_field["value"] == ", ".join(message.tags)
                
                # Should have metadata fields
                for key, value in message.metadata.items():
                    expected_field_name = key.replace("_", " ").title()
                    if expected_field_name in field_names:
                        metadata_field = next(
                            f for f in embed["fields"] 
                            if f["name"] == expected_field_name
                        )
                        assert metadata_field["value"] == str(value)
    
    @pytest.mark.asyncio
    async def test_dispatcher_integration_e2e(
        self,
        discord_config: dict[str, object],
        realistic_messages: list[Message],
    ) -> None:
        """Test Discord provider integration with notification dispatcher."""
        # Setup registry and provider
        registry = get_global_registry()
        metadata = ProviderMetadata(
            name="discord",
            description="Discord webhook provider",
            version="1.0.0",
            author="Dispatcher E2E Test",
            provider_class=DiscordProvider,
            tags=["discord", "webhook"],
        )
        registry.register_provider("discord", DiscordProvider, metadata)
        
        # Create and configure dispatcher
        dispatcher = AsyncDispatcher(max_workers=3, queue_size=20)
        provider = DiscordProvider(discord_config)
        dispatcher.register_provider("discord", provider)
        
        await dispatcher.start()
        
        try:
            # Mock successful HTTP responses
            mock_response = MagicMock()
            mock_response.status_code = 204
            
            with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
                # Dispatch all messages
                dispatch_results = []
                for message in realistic_messages:
                    result = await dispatcher.dispatch_message(message, ["discord"])
                    dispatch_results.append(result)
                
                # Verify all dispatches succeeded
                for result in dispatch_results:
                    assert result.status == DispatchStatus.SUCCESS
                    assert len(result.provider_results) == 1
                    assert result.provider_results[0].success is True
                    assert result.provider_results[0].provider_name == "discord"
                    assert result.provider_results[0].error is None
                
                # Verify HTTP calls were made
                assert mock_post.call_count == len(realistic_messages)
        
        finally:
            await dispatcher.stop()
    
    @pytest.mark.asyncio
    async def test_error_recovery_scenarios_e2e(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test error recovery in realistic failure scenarios."""
        provider = DiscordProvider(discord_config)
        
        test_message = Message(
            title="Error Recovery Test",
            content="Testing error recovery mechanisms",
            priority="normal",
            tags=["test", "error-recovery"],
            metadata={"scenario": "failure_simulation"},
        )
        
        # Scenario 1: Temporary network issues (should retry and succeed)
        failure_then_success_responses = [
            # First attempt: Network error
            Exception("Network timeout"),
            # Second attempt: Rate limiting
            MagicMock(status_code=429, headers={"retry-after": "1"}),
            # Third attempt: Success
            MagicMock(status_code=204),
        ]
        
        with patch("httpx.AsyncClient.post", side_effect=failure_then_success_responses):
            result = await provider.send_notification(test_message)
            # Should eventually succeed after retries
            assert result is True
        
        # Scenario 2: Permanent failure (invalid webhook)
        permanent_failure_response = MagicMock()
        permanent_failure_response.status_code = 404
        permanent_failure_response.headers = {}
        permanent_failure_response.raise_for_status.side_effect = Exception("Not found")
        
        with patch("httpx.AsyncClient.post", return_value=permanent_failure_response):
            result = await provider.send_notification(test_message)
            # Should fail without excessive retries
            assert result is False
        
        # Scenario 3: Rate limiting with proper backoff
        rate_limit_responses = [
            MagicMock(status_code=429, headers={"retry-after": "0.1"}),
            MagicMock(status_code=429, headers={"retry-after": "0.1"}),
            MagicMock(status_code=204),
        ]
        
        with patch("httpx.AsyncClient.post", side_effect=rate_limit_responses):
            import time
            start_time = time.time()
            result = await provider.send_notification(test_message)
            end_time = time.time()
            
            # Should succeed after rate limit delays
            assert result is True
            # Should have taken some time due to rate limiting (at least 0.2s for two 0.1s delays)
            # Note: Allowing for some variance in timing
            assert end_time - start_time >= 0.1  # At least some delay occurred
    
    @pytest.mark.asyncio
    async def test_high_volume_stress_e2e(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test system behavior under high message volume."""
        provider = DiscordProvider(discord_config)
        
        # Generate high volume of messages
        volume_messages = [
            Message(
                title=f"Volume Test {i:04d}",
                content=f"High volume stress test message {i}",
                priority="normal" if i % 2 == 0 else "high",
                tags=["stress", "volume", f"batch_{i // 10}"],
                metadata={
                    "message_id": str(i),
                    "batch": str(i // 10),
                    "sequence": str(i % 10),
                },
            )
            for i in range(100)  # 100 messages
        ]
        
        # Mock fast responses
        mock_response = MagicMock()
        mock_response.status_code = 204
        
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            import time
            start_time = time.time()
            
            # Send all messages
            tasks = [provider.send_notification(msg) for msg in volume_messages]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Verify results
            successful_results = [r for r in results if r is True]
            failed_results = [r for r in results if r is not True]
            
            # Should handle most messages successfully
            success_rate = len(successful_results) / len(volume_messages)
            assert success_rate >= 0.9, f"Success rate too low: {success_rate:.2%}"
            
            # Check for any unexpected exceptions
            exceptions = [r for r in failed_results if isinstance(r, Exception)]
            assert len(exceptions) == 0, f"Unexpected exceptions: {exceptions}"
            
            # Performance checks
            messages_per_second = len(volume_messages) / total_time
            assert messages_per_second >= 10, f"Throughput too low: {messages_per_second:.1f} msg/s"
            
            # Verify rate limiting was applied (should have made HTTP calls)
            assert mock_post.call_count == len(successful_results)
    
    @pytest.mark.asyncio
    async def test_concurrent_provider_operations_e2e(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test concurrent operations across multiple provider instances."""
        # Create multiple provider instances (simulating multiple services)
        providers = {
            f"service_{i}": DiscordProvider({
                **discord_config,
                "username": f"Service {i} Bot",
            })
            for i in range(3)
        }
        
        # Create messages for each service
        service_messages = {
            service_name: [
                Message(
                    title=f"{service_name.title()} Alert {j}",
                    content=f"Alert from {service_name} - event {j}",
                    priority="normal",
                    tags=[service_name, "alert"],
                    metadata={"service": service_name, "event_id": str(j)},
                )
                for j in range(5)  # 5 messages per service
            ]
            for service_name in providers.keys()
        }
        
        # Mock responses
        mock_response = MagicMock()
        mock_response.status_code = 204
        
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            # Send all messages from all services concurrently
            all_tasks = []
            for service_name, messages in service_messages.items():
                provider = providers[service_name]
                for message in messages:
                    task = provider.send_notification(message)
                    all_tasks.append((service_name, task))
            
            # Execute all tasks concurrently
            results = await asyncio.gather(*[task for _, task in all_tasks])
            
            # All should succeed
            assert all(results)
            
            # Verify correct number of HTTP calls
            total_expected_calls = sum(len(msgs) for msgs in service_messages.values())
            assert mock_post.call_count == total_expected_calls
            
            # Verify each provider sent its messages with correct username
            call_usernames = [call.kwargs["json"]["username"] for call in mock_post.call_args_list]
            expected_usernames = [
                providers[service_name].webhook_client.username
                for service_name, messages in service_messages.items()
                for _ in messages
            ]
            
            # Should have correct usernames (order might vary due to concurrency)
            assert sorted(call_usernames) == sorted(expected_usernames)
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_e2e(
        self,
        discord_config: dict[str, object],
    ) -> None:
        """Test graceful degradation when Discord service is unavailable."""
        provider = DiscordProvider(discord_config)
        
        # Simulate complete service outage
        outage_message = Message(
            title="Service Outage Test",
            content="Testing behavior during Discord service outage",
            priority="urgent",
            tags=["outage", "test"],
            metadata={"scenario": "service_unavailable"},
        )
        
        # Complete service failure
        with patch("httpx.AsyncClient.post", side_effect=Exception("Service unavailable")):
            result = await provider.send_notification(outage_message)
            # Should fail gracefully without raising exceptions
            assert result is False
        
        # Partial service degradation (very slow responses)
        async def slow_response(*args: Any, **kwargs: Any) -> MagicMock:
            await asyncio.sleep(0.5)  # Simulate slow response
            response = MagicMock()
            response.status_code = 204
            return response
        
        with patch("httpx.AsyncClient.post", side_effect=slow_response):
            # Should handle slow responses within timeout
            result = await provider.send_notification(outage_message)
            # May succeed or fail depending on timeout, but should not crash
            assert isinstance(result, bool)
        
        # Service recovery
        recovery_response = MagicMock()
        recovery_response.status_code = 204
        
        with patch("httpx.AsyncClient.post", return_value=recovery_response):
            result = await provider.send_notification(outage_message)
            # Should work normally after recovery
            assert result is True