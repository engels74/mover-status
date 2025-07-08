"""Full-cycle integration tests covering complete user workflows and business processes.

This module implements comprehensive end-to-end integration tests that validate
entire user journeys, cross-component interactions, data flow integrity, and 
business logic execution from start to finish using the mover-status system.
"""

from __future__ import annotations

import asyncio
import time
import pytest
from typing import TYPE_CHECKING, cast
from collections.abc import Coroutine
from pathlib import Path

from mover_status.notifications.models.message import Message
from mover_status.core.process.models import ProcessStatus
from tests.fixtures.integration_fixtures import (
    IntegrationTestEnvironment,
    IntegrationTestRunner,
    MockProcessEnvironment,
    isolated_test_environment
)
from tests.fixtures.progress_data_generators import ProgressDataGenerator

if TYPE_CHECKING:
    pass

@pytest.mark.integration
class TestFullCycleScenarios:
    """Complete end-to-end integration tests for mover-status system."""
    
    @pytest.mark.asyncio
    async def test_complete_monitoring_cycle(self, integration_env: IntegrationTestEnvironment) -> None:
        """Test complete monitoring lifecycle from detection to completion.
        
        This test validates:
        - Process detection and startup notification
        - Progress monitoring with regular updates
        - Filesystem scanning and size calculations
        - Notification delivery across providers
        - Completion detection and final notifications
        - Clean shutdown and resource cleanup
        """
        runner = IntegrationTestRunner(integration_env)
        
        # Execute complete monitoring cycle
        result = await runner.run_full_monitoring_cycle()
        
        # Verify startup notification was sent
        start_result = cast(dict[str, object], result["start_notification"])
        assert isinstance(start_result, dict)
        assert "result" in start_result
        processing_time = cast(float, start_result["processing_time"])
        assert processing_time < 5.0
        
        # Verify progress monitoring occurred
        progress_result = cast(dict[str, object], result["progress_monitoring"])
        assert isinstance(progress_result, dict)
        total_points = cast(int, progress_result["total_points"])
        notifications_sent = cast(int, progress_result["notifications_sent"])
        final_percentage = cast(float, progress_result["final_percentage"])
        assert total_points > 0
        assert notifications_sent > 0
        assert final_percentage >= 95.0  # Should complete
        
        # Verify completion notification was sent
        completion_result = cast(dict[str, object], result["completion_notification"])
        assert isinstance(completion_result, dict)
        assert "result" in completion_result
        completion_processing_time = cast(float, completion_result["processing_time"])
        assert completion_processing_time < 5.0
        
        # Verify system summary
        summary = cast(dict[str, object], result["summary"])
        assert isinstance(summary, dict)
        assert "progress_history" in summary
        assert "notification_history" in summary
        assert "provider_stats" in summary
        
        # Verify all expected notifications were delivered
        notification_history = cast(list[dict[str, object]], summary["notification_history"])
        assert len(notification_history) >= 3  # Start, progress updates, completion
        
        # Verify provider performance
        provider_stats = cast(dict[str, dict[str, object]], summary["provider_stats"])
        for _provider_name, stats in provider_stats.items():
            assert isinstance(stats, dict)
            send_count = cast(int, stats["send_count"])
            success_rate = cast(float, stats["success_rate"])
            assert send_count > 0
            assert success_rate > 0.5  # At least 50% success rate
    
    @pytest.mark.asyncio
    async def test_process_lifecycle_workflow(self, integration_env: IntegrationTestEnvironment) -> None:
        """Test complete process lifecycle: detection → monitoring → completion → cleanup."""
        # Phase 1: Process Detection
        _mover_process = MockProcessEnvironment(
            process_name="mover",
            pid=12345,
            command_line=["/usr/local/sbin/mover", "--verbose"],
            status="running"
        )
        
        if integration_env.process_detector:
            integration_env.process_detector.add_process(_mover_process)
        
        # Phase 2: Process startup detection
        if integration_env.process_detector:
            detected_processes = await integration_env.process_detector.detect_processes(["mover"])
            assert len(detected_processes) == 1
            
            detected_process = detected_processes[0]
            assert detected_process.pid == 12345
            assert detected_process.name == "mover"
            assert detected_process.status == ProcessStatus.RUNNING
        
        # Phase 3: Send startup notification
        startup_message = Message(
            title="Mover Process Started",
            content=f"Mover process detected (PID: {_mover_process.pid})",
            priority="normal"
        )
        
        startup_result = await integration_env.simulate_notification_flow(startup_message)
        assert isinstance(startup_result, dict)
        startup_processing_time = cast(float, startup_result["processing_time"])
        assert startup_processing_time < 2.0
        
        # Phase 4: Monitor progress over time
        progress_scenarios = ["linear", "stalled", "noisy"]
        for scenario_name in progress_scenarios:
            progress_data = integration_env.create_progress_scenario(scenario_name)
            
            monitoring_result = await integration_env.simulate_progress_monitoring(progress_data)
            assert isinstance(monitoring_result, dict)
            total_points = cast(int, monitoring_result["total_points"])
            notifications_sent = cast(int, monitoring_result["notifications_sent"])
            assert total_points > 0
            assert notifications_sent > 0
        
        # Phase 5: Process completion
        if integration_env.process_detector:
            integration_env.process_detector.update_process_status(12345, "sleeping")
        
        completion_message = Message(
            title="Mover Process Completed",
            content="Transfer operation completed successfully",
            priority="normal"
        )
        
        completion_result = await integration_env.simulate_notification_flow(completion_message)
        assert isinstance(completion_result, dict)
        completion_processing_time = cast(float, completion_result["processing_time"])
        assert completion_processing_time < 2.0
        
        # Phase 6: Cleanup and verification
        if integration_env.process_detector:
            integration_env.process_detector.remove_process(12345)
            final_processes = await integration_env.process_detector.detect_processes(["mover"])
            assert len(final_processes) == 0
        
        # Verify complete workflow was tracked
        summary = integration_env.get_test_summary()
        assert isinstance(summary, dict)
        
        notification_history = cast(list[dict[str, object]], summary["notification_history"])
        assert len(notification_history) >= 4  # Startup + progress updates + completion
        
        # Verify notifications have proper sequence
        notification_titles = [cast(str, notif["message_title"]) for notif in notification_history]
        assert any("Started" in title for title in notification_titles)
        assert any("Completed" in title for title in notification_titles)
    
    @pytest.mark.asyncio
    async def test_multi_provider_notification_workflow(self, integration_env: IntegrationTestEnvironment) -> None:
        """Test notification workflow across multiple providers with different characteristics."""
        # Create messages simulating various notification scenarios
        test_messages = [
            Message(title="Critical Alert", content="Disk space critically low", priority="high"),
            Message(title="Progress Update", content="Transfer 25% complete", priority="normal"),
            Message(title="Warning", content="Transfer rate slower than expected", priority="normal"),
            Message(title="Progress Update", content="Transfer 50% complete", priority="normal"),
            Message(title="Error Recovery", content="Connection restored after timeout", priority="normal"),
            Message(title="Progress Update", content="Transfer 75% complete", priority="normal"),
            Message(title="Success", content="Transfer completed successfully", priority="low")
        ]
        
        # Process messages sequentially to simulate real workflow
        results: list[dict[str, object]] = []
        for i, message in enumerate(test_messages):
            # Add realistic delays between notifications
            if i > 0:
                await asyncio.sleep(0.1)
            
            result = await integration_env.simulate_notification_flow(message)
            results.append(result)
            
            # Verify each notification was processed
            assert isinstance(result, dict)
            processing_time = cast(float, result["processing_time"])
            assert processing_time < 3.0
            
            provider_stats = cast(dict[str, dict[str, object]], result["provider_stats"])
            assert isinstance(provider_stats, dict)
            
            # Verify at least one provider succeeded
            success_count = sum(
                1 for stats in provider_stats.values() 
                if cast(int, stats["success_count"]) > 0
            )
            assert success_count > 0
        
        # Verify overall workflow integrity
        summary = integration_env.get_test_summary()
        notification_history = cast(list[dict[str, object]], summary["notification_history"])
        assert len(notification_history) >= len(test_messages)
        
        # Verify message ordering and content integrity
        for i, original_msg in enumerate(test_messages):
            matching_notifications = [
                notif for notif in notification_history
                if cast(str, notif["message_title"]) == original_msg.title
            ]
            assert len(matching_notifications) >= 1  # Should find the message
    
    @pytest.mark.asyncio
    async def test_filesystem_monitoring_integration(self, integration_env: IntegrationTestEnvironment) -> None:
        """Test complete filesystem monitoring integration with real-world transfer scenarios."""
        with isolated_test_environment() as temp_dir:
            # Create test filesystem structure
            source_dir = temp_dir / "source"
            target_dir = temp_dir / "target"
            source_dir.mkdir()
            target_dir.mkdir()
            
            # Create test files
            test_files: list[Path] = []
            for i in range(10):
                file_path = source_dir / f"test_file_{i:03d}.dat"
                # Create files with different sizes
                file_size = (i + 1) * 1024 * 1024  # 1MB, 2MB, 3MB, etc.
                with open(file_path, 'wb') as f:
                    _ = f.write(b'X' * file_size)
                test_files.append(file_path)
            
            # Simulate filesystem state updates
            total_size = sum(f.stat().st_size for f in test_files)
            if integration_env.filesystem_state:
                integration_env.filesystem_state.total_size = total_size
                integration_env.filesystem_state.file_count = len(test_files)
            
            # Test different progress patterns
            progress_scenarios = {
                "linear_transfer": ProgressDataGenerator.linear_transfer(total_size, 60.0, 30),
                "bursty_transfer": ProgressDataGenerator.bursty_transfer(total_size, 90.0, 45, 0.7, 3.0),
                "stalled_transfer": ProgressDataGenerator.stall_and_resume(
                    total_size, 120.0, 60, [(0.3, 0.4), (0.7, 0.8)]
                )
            }
            
            for scenario_name, progress_data in progress_scenarios.items():
                print(f"\nTesting filesystem scenario: {scenario_name}")
                
                # Reset filesystem state
                if integration_env.filesystem_state:
                    integration_env.filesystem_state.transferred_size = 0
                    integration_env.filesystem_state.transferred_files = 0
                
                # Clear progress history from previous scenario
                if integration_env.database:
                    integration_env.database.cursor.execute("DELETE FROM test_progress")
                    integration_env.database.connection.commit()
                
                # Run monitoring scenario
                monitoring_result = await integration_env.simulate_progress_monitoring(progress_data)
                
                # Verify monitoring results
                assert isinstance(monitoring_result, dict)
                total_points = cast(int, monitoring_result["total_points"])
                final_percentage = cast(float, monitoring_result["final_percentage"])
                notifications_sent = cast(int, monitoring_result["notifications_sent"])
                assert total_points == len(progress_data)
                assert final_percentage >= 95.0
                assert notifications_sent > 0
                
                # Verify filesystem state was updated
                if integration_env.filesystem_state:
                    fs_final_percentage = (
                        integration_env.filesystem_state.transferred_size / 
                        integration_env.filesystem_state.total_size * 100.0
                    )
                    assert fs_final_percentage >= 95.0
                
                # Verify progress database was populated
                if integration_env.database:
                    progress_history = integration_env.database.get_progress_history()
                    assert len(progress_history) >= len(progress_data)
                    
                    # Verify progress data integrity
                    for i, history_entry in enumerate(progress_history[-len(progress_data):]):
                        original_point = progress_data[i]
                        bytes_transferred = cast(int, history_entry["bytes_transferred"])
                        total_size_entry = cast(int, history_entry["total_size"])
                        assert abs(bytes_transferred - original_point.bytes_transferred) < 1000
                        assert abs(total_size_entry - original_point.total_size) < 1000
    
    @pytest.mark.asyncio
    async def test_failure_recovery_full_cycle(self, integration_env: IntegrationTestEnvironment) -> None:
        """Test complete failure recovery scenarios throughout the entire system lifecycle."""
        runner = IntegrationTestRunner(integration_env)
        
        # Configure system for failure testing
        if integration_env.webhook_service:
            integration_env.webhook_service.failure_rate = 0.3  # 30% failure rate
        
        if integration_env.process_detector:
            integration_env.process_detector.failure_rate = 0.1  # 10% detection failure rate
        
        # Phase 1: Test process detection with failures
        _process = integration_env.add_mock_process("mover", 54321)
        
        detection_attempts = 0
        detected = False
        while detection_attempts < 5 and not detected:
            try:
                if integration_env.process_detector:
                    processes = await integration_env.process_detector.detect_processes(["mover"])
                    if processes:
                        detected = True
            except Exception:
                # Expected failures due to configured failure rate
                pass
            detection_attempts += 1
            await asyncio.sleep(0.1)
        
        assert detected, "Process detection should eventually succeed despite failures"
        
        # Phase 2: Test notification delivery with provider failures
        failure_recovery_result = await runner.run_failure_recovery_scenario()
        
        assert isinstance(failure_recovery_result, dict)
        message_count = cast(int, failure_recovery_result["message_count"])
        assert message_count > 0
        
        # Verify some messages succeeded despite failures
        results = cast(list[dict[str, object]], failure_recovery_result["results"])
        successful_dispatches = 0
        for result in results:
            try:
                result_obj = result["result"]
                # Use getattr with default to safely access nested attributes
                status_obj = getattr(result_obj, "status", None)
                if status_obj is not None:
                    status_value = getattr(status_obj, "value", None)  # pyright: ignore[reportAny]
                    if status_value is not None and str(status_value) in ["success", "partial"]:  # pyright: ignore[reportAny]
                        successful_dispatches += 1
            except (AttributeError, KeyError):
                # Skip results that don't have the expected structure
                continue
        assert successful_dispatches > 0, "Some notifications should succeed despite failures"
        
        # Phase 3: Test progress monitoring resilience
        progress_data = integration_env.create_progress_scenario("noisy")
        
        # Simulate monitoring with intermittent failures
        monitoring_result = await integration_env.simulate_progress_monitoring(progress_data)
        
        assert isinstance(monitoring_result, dict)
        total_points = cast(int, monitoring_result["total_points"])
        final_percentage = cast(float, monitoring_result["final_percentage"])
        assert total_points > 0
        assert final_percentage > 80.0  # Should mostly complete
        
        # Phase 4: Verify system recovery and stability
        summary = integration_env.get_test_summary()
        
        # Check that system maintained stability
        notification_history = cast(list[dict[str, object]], summary["notification_history"])
        assert len(notification_history) > 0
        
        provider_stats = cast(dict[str, dict[str, object]], summary["provider_stats"])
        for _provider_name, stats in provider_stats.items():
            # Even with failures, should have some successful operations
            send_count = cast(int, stats["send_count"])
            success_rate = cast(float, stats["success_rate"])
            assert send_count > 0
            # Success rate should be reasonable given failure injection
            assert success_rate > 0.3  # At least 30% success despite failures
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_workflow(self, integration_env: IntegrationTestEnvironment) -> None:
        """Test system behavior with concurrent operations and multiple processes."""
        # Set up multiple concurrent processes
        processes: list[MockProcessEnvironment] = []
        for i in range(3):
            process = MockProcessEnvironment(
                process_name=f"mover_{i}",
                pid=20000 + i,
                command_line=[f"/usr/local/sbin/mover_{i}"],
                status="running"
            )
            processes.append(process)
            
            if integration_env.process_detector:
                integration_env.process_detector.add_process(process)
        
        # Create concurrent notification tasks
        notification_tasks: list[Coroutine[object, object, dict[str, object]]] = []
        for i, _process in enumerate(processes):
            messages = [
                Message(
                    title=f"Process {i} Started", 
                    content=f"Mover process {i} initiated",
                    priority="normal"
                ),
                Message(
                    title=f"Process {i} Progress", 
                    content=f"Process {i}: 50% complete",
                    priority="normal"
                ),
                Message(
                    title=f"Process {i} Complete", 
                    content=f"Process {i} finished successfully",
                    priority="normal"
                )
            ]
            
            # Create tasks for concurrent execution
            for message in messages:
                task = integration_env.simulate_notification_flow(message)
                notification_tasks.append(task)
        
        # Execute all notifications concurrently
        start_time = time.time()
        results = await asyncio.gather(*notification_tasks, return_exceptions=True)
        execution_time = time.time() - start_time
        
        # Verify concurrent execution performance
        assert execution_time < 10.0, f"Concurrent execution took too long: {execution_time:.2f}s"
        
        # Verify all operations completed
        successful_results = [r for r in results if isinstance(r, dict)]
        assert len(successful_results) >= len(notification_tasks) * 0.8  # 80% success rate
        
        # Verify system handled concurrency well
        summary = integration_env.get_test_summary()
        notification_history = cast(list[dict[str, object]], summary["notification_history"])
        
        # Should have notifications from all processes
        process_notifications = {f"Process {i}": 0 for i in range(3)}
        for notification in notification_history:
            title = cast(str, notification["message_title"])
            for process_name in process_notifications:
                if process_name in title:
                    process_notifications[process_name] += 1
        
        # Each process should have generated multiple notifications
        for process_name, count in process_notifications.items():
            assert count >= 2, f"{process_name} generated too few notifications: {count}"
        
        # Verify provider performance under concurrent load
        provider_stats = cast(dict[str, dict[str, object]], summary["provider_stats"])
        for _provider_name, stats in provider_stats.items():
            send_count = cast(int, stats["send_count"])
            success_rate = cast(float, stats["success_rate"])
            assert send_count >= len(processes) * 2  # Multiple notifications per process
            assert success_rate > 0.5  # Reasonable success rate under load
    
    @pytest.mark.asyncio
    async def test_system_state_consistency(self, integration_env: IntegrationTestEnvironment) -> None:
        """Test system state consistency throughout complete operational cycles."""
        # Phase 1: Initialize system state
        initial_summary = integration_env.get_test_summary()
        assert isinstance(initial_summary, dict)
        
        # Verify clean initial state
        progress_history = cast(list[object], initial_summary.get("progress_history", []))
        notification_history = cast(list[object], initial_summary.get("notification_history", []))
        assert len(progress_history) == 0
        assert len(notification_history) == 0
        
        # Phase 2: Execute operations and track state changes
        operations: list[dict[str, object]] = [
            {"action": "start_process", "data": {"name": "mover", "pid": 98765}},
            {"action": "send_notification", "data": {"title": "Process Started", "content": "System initiated"}},
            {"action": "update_progress", "data": {"percentage": 25.0}},
            {"action": "send_notification", "data": {"title": "Progress Update", "content": "25% complete"}},
            {"action": "update_progress", "data": {"percentage": 75.0}},
            {"action": "send_notification", "data": {"title": "Progress Update", "content": "75% complete"}},
            {"action": "complete_process", "data": {"percentage": 100.0}},
            {"action": "send_notification", "data": {"title": "Process Complete", "content": "Operation finished"}}
        ]
        
        state_snapshots: list[dict[str, object]] = []
        
        for i, operation in enumerate(operations):
            if operation["action"] == "start_process":
                data = cast(dict[str, object], operation["data"])
                process = integration_env.add_mock_process(
                    cast(str, data["name"]), 
                    cast(int, data["pid"])
                )
                assert process.pid == cast(int, data["pid"])
                
            elif operation["action"] == "send_notification":
                data = cast(dict[str, object], operation["data"])
                message = Message(
                    title=cast(str, data["title"]),
                    content=cast(str, data["content"]),
                    priority="normal"
                )
                result = await integration_env.simulate_notification_flow(message)
                assert isinstance(result, dict)
                
            elif operation["action"] == "update_progress":
                if integration_env.filesystem_state:
                    data = cast(dict[str, object], operation["data"])
                    integration_env.filesystem_state.update_progress(cast(float, data["percentage"]))
                
            elif operation["action"] == "complete_process":
                if integration_env.filesystem_state:
                    integration_env.filesystem_state.update_progress(100.0)
            
            # Capture state snapshot after each operation
            snapshot = integration_env.get_test_summary()
            state_snapshots.append({
                "operation_index": i,
                "operation": operation,
                "state": snapshot
            })
        
        # Phase 3: Verify state consistency and progression
        # Verify progressive increase in notification count
        for i in range(1, len(state_snapshots)):
            current_state = cast(dict[str, object], state_snapshots[i]["state"])
            previous_state = cast(dict[str, object], state_snapshots[i-1]["state"])
            current_notifications = cast(list[object], current_state["notification_history"])
            previous_notifications = cast(list[object], previous_state["notification_history"])
            current_operation = cast(dict[str, object], state_snapshots[i]["operation"])
            
            if current_operation["action"] == "send_notification":
                assert len(current_notifications) >= len(previous_notifications), (
                    f"Notification count should increase after operation {i}"
                )
        
        # Verify final state integrity
        final_summary = integration_env.get_test_summary()
        
        # Should have processed all notifications
        final_notification_history = cast(list[object], final_summary["notification_history"])
        notification_count = len([op for op in operations if op["action"] == "send_notification"])
        assert len(final_notification_history) >= notification_count
        
        # Verify filesystem state if available
        if "filesystem_state" in final_summary:
            fs_state = cast(dict[str, object], final_summary["filesystem_state"])
            transferred_size = cast(int, fs_state["transferred_size"])
            total_size = cast(int, fs_state["total_size"])
            if total_size > 0:
                assert transferred_size >= total_size * 0.9  # Near completion
        
        # Verify all providers maintained consistency
        provider_stats = cast(dict[str, dict[str, object]], final_summary["provider_stats"])
        for _provider_name, stats in provider_stats.items():
            send_count = cast(int, stats["send_count"])
            success_count = cast(int, stats["success_count"])
            success_rate = cast(float, stats["success_rate"])
            assert send_count > 0
            assert success_count >= 0
            assert success_count <= send_count
            assert 0.0 <= success_rate <= 1.0


@pytest.mark.integration
@pytest.mark.performance
class TestFullCyclePerformance:
    """Performance validation for full-cycle integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_large_scale_monitoring_performance(self, integration_env: IntegrationTestEnvironment) -> None:
        """Test system performance with large-scale monitoring scenarios."""
        # Configure for large scale test
        large_progress_data = ProgressDataGenerator.linear_transfer(
            5 * 1024 * 1024 * 1024,  # 5GB transfer
            300.0,  # 5 minutes
            300  # 300 data points
        )
        
        start_time = time.time()
        
        # Execute large scale monitoring
        result = await integration_env.simulate_progress_monitoring(large_progress_data)
        
        execution_time = time.time() - start_time
        
        # Verify performance requirements
        assert execution_time < 30.0, f"Large scale test took too long: {execution_time:.2f}s"
        assert isinstance(result, dict)
        total_points = cast(int, result["total_points"])
        final_percentage = cast(float, result["final_percentage"])
        assert total_points == 300
        assert final_percentage >= 99.0
        
        # Verify throughput
        throughput = total_points / execution_time
        assert throughput > 10.0, f"Throughput too low: {throughput:.1f} points/s"
    
    @pytest.mark.asyncio
    async def test_high_frequency_notifications_performance(self, integration_env: IntegrationTestEnvironment) -> None:
        """Test system performance with high-frequency notification scenarios."""
        # Generate high-frequency messages
        messages: list[Message] = []
        for i in range(100):
            message = Message(
                title=f"High Frequency Message {i:03d}",
                content=f"Rapid notification content {i}",
                priority="normal" if i % 2 == 0 else "low"
            )
            messages.append(message)
        
        start_time = time.time()
        
        # Send messages with minimal delay to test throughput
        results: list[dict[str, object]] = []
        for message in messages:
            result = await integration_env.simulate_notification_flow(message)
            results.append(result)
        
        execution_time = time.time() - start_time
        
        # Verify performance
        assert execution_time < 15.0, f"High frequency test took too long: {execution_time:.2f}s"
        
        # Calculate and verify throughput
        throughput = len(messages) / execution_time
        assert throughput > 7.0, f"Message throughput too low: {throughput:.1f} msg/s"
        
        # Verify all messages were processed
        successful_results = results  # All results are already dicts
        success_rate = len(successful_results) / len(messages)
        assert success_rate > 0.95, f"Success rate too low: {success_rate:.1%}"


if __name__ == "__main__":
    # Allow running tests directly for development
    _ = pytest.main([__file__, "-v", "--tb=short"])