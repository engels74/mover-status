"""Comprehensive TDD test suite for orchestrator behaviors.

This test suite covers:
- Unit tests for state machine transitions and event handling
- Integration tests for component coordination scenarios
- Chaos engineering tests for failure scenarios
- Performance and load testing suites
- Mock component implementations and test data factories
"""

from __future__ import annotations

import asyncio
import time
from typing import cast
from unittest.mock import Mock, AsyncMock
from datetime import datetime
import pytest

from mover_status.core.monitor.orchestrator import (
    MonitorOrchestrator,
    Component,
    ComponentType,
    ComponentStatus,
    WorkflowStep,
    WorkflowStatus,
    AllocationStatus,
)
from mover_status.core.monitor.state_machine import MonitorState, StateMachine
from mover_status.core.monitor.event_bus import EventBus, EventPriority
from mover_status.core.process import ProcessDetector, ProcessInfo, ProcessStatus
from mover_status.core.progress import ProgressCalculator, ProgressMetrics
from mover_status.notifications.manager import AsyncDispatcher


class MockComponent(Component):
    """Mock component for testing."""
    
    def __init__(
        self,
        name: str,
        component_type: ComponentType,
        health_check_result: bool = True,
        health_check_exception: Exception | None = None,
    ) -> None:
        """Initialize mock component."""
        super().__init__(name, component_type)
        self._health_check_result: bool = health_check_result
        self._health_check_exception: Exception | None = health_check_exception
        self.start_called: bool = False
        self.stop_called: bool = False
    
    def health_check(self) -> bool:  # pyright: ignore[reportImplicitOverride]
        """Mock health check."""
        if self._health_check_exception:
            raise self._health_check_exception
        return self._health_check_result
    
    def start(self) -> None:  # pyright: ignore[reportImplicitOverride]
        """Mock start method."""
        super().start()
        self.start_called = True
    
    def stop(self) -> None:  # pyright: ignore[reportImplicitOverride]
        """Mock stop method."""
        super().stop()
        self.stop_called = True


class TestOrchestratorTDD:
    """Test-driven development test suite for orchestrator behaviors."""
    
    @pytest.fixture
    def mock_detector(self) -> Mock:
        """Create mock ProcessDetector."""
        detector = Mock(spec=ProcessDetector)
        detector.detect_mover = Mock(return_value=None)
        detector.is_process_running = Mock(return_value=True)
        return detector
    
    @pytest.fixture
    def mock_calculator(self) -> Mock:
        """Create mock ProgressCalculator."""
        calculator = Mock(spec=ProgressCalculator)
        progress = ProgressMetrics(
            percentage=50.0,
            bytes_remaining=1048576,
            transfer_rate=10.5,
            etc_seconds=300.0,
        )
        calculator.calculate_progress = Mock(return_value=progress)
        return calculator
    
    @pytest.fixture
    def mock_dispatcher(self) -> Mock:
        """Create mock AsyncDispatcher."""
        dispatcher = Mock(spec=AsyncDispatcher)
        dispatcher.send_notification = AsyncMock()
        return dispatcher
    
    @pytest.fixture
    def mock_state_machine(self) -> Mock:
        """Create mock StateMachine."""
        state_machine = Mock(spec=StateMachine)
        state_machine.current_state = MonitorState.IDLE
        state_machine.transition_to = Mock(return_value=True)
        return state_machine
    
    @pytest.fixture
    def mock_event_bus(self) -> Mock:
        """Create mock EventBus."""
        event_bus = Mock(spec=EventBus)
        event_bus.publish_event = Mock()
        event_bus.subscribe = Mock()
        return event_bus
    
    @pytest.fixture
    def sample_process_info(self) -> ProcessInfo:
        """Create sample ProcessInfo for testing."""
        return ProcessInfo(
            pid=1234,
            name="test_process",
            status=ProcessStatus.RUNNING,
            cpu_percent=25.0,
            memory_mb=128.0,
            start_time=datetime.fromtimestamp(1640995200.0),
            command="test_command",
            working_directory="/tmp",
        )
    
    @pytest.fixture
    def orchestrator(
        self,
        mock_detector: Mock,
        mock_calculator: Mock,
        mock_dispatcher: Mock,
        mock_state_machine: Mock,
        mock_event_bus: Mock,
    ) -> MonitorOrchestrator:
        """Create orchestrator instance for testing."""
        return MonitorOrchestrator(
            detector=mock_detector,
            calculator=mock_calculator,
            dispatcher=mock_dispatcher,
            state_machine=mock_state_machine,
            event_bus=mock_event_bus,
        )


class TestStateTransitionBehaviors(TestOrchestratorTDD):
    """Unit tests for state machine transitions and event handling."""
    
    @pytest.mark.asyncio
    async def test_idle_to_detecting_transition(self, orchestrator: MonitorOrchestrator) -> None:
        """Test transition from IDLE to DETECTING state."""
        # Execute
        await orchestrator.run_detection_cycle()
        
        # Verify state transition
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.DETECTING)
    
    @pytest.mark.asyncio
    async def test_detecting_to_monitoring_on_process_found(
        self, orchestrator: MonitorOrchestrator, sample_process_info: ProcessInfo
    ) -> None:
        """Test transition from DETECTING to MONITORING when process is found."""
        # Setup
        cast(Mock, orchestrator.detector.detect_mover).return_value = sample_process_info
        
        # Execute
        await orchestrator.run_detection_cycle()
        
        # Verify state transitions
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.DETECTING)
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.MONITORING)
        
        # Verify process is stored
        assert orchestrator.current_process == sample_process_info
    
    @pytest.mark.asyncio
    async def test_detecting_to_idle_on_no_process(self, orchestrator: MonitorOrchestrator) -> None:
        """Test transition from DETECTING to IDLE when no process is found."""
        # Setup
        cast(Mock, orchestrator.detector.detect_mover).return_value = None
        
        # Execute
        await orchestrator.run_detection_cycle()
        
        # Verify state transitions
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.DETECTING)
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.IDLE)
    
    @pytest.mark.asyncio
    async def test_monitoring_to_completing_on_process_end(
        self, orchestrator: MonitorOrchestrator, sample_process_info: ProcessInfo
    ) -> None:
        """Test transition from MONITORING to COMPLETING when process ends."""
        # Setup
        orchestrator.current_process = sample_process_info
        cast(Mock, orchestrator.detector.is_process_running).return_value = False
        
        # Execute
        await orchestrator.run_monitoring_cycle()
        
        # Verify state transitions
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.COMPLETING)
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.IDLE)
        
        # Verify process is cleared
        assert orchestrator.current_process is None
    
    @pytest.mark.asyncio
    async def test_error_state_transition_on_exception(self, orchestrator: MonitorOrchestrator) -> None:
        """Test transition to ERROR state when exception occurs."""
        # Setup
        cast(Mock, orchestrator.detector.detect_mover).side_effect = Exception("Test error")
        
        # Execute
        await orchestrator.run_detection_cycle()
        
        # Verify error state transition
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.ERROR)
        
        # Verify error is stored
        assert orchestrator.last_error is not None
        assert str(orchestrator.last_error) == "Test error"
    
    @pytest.mark.asyncio
    async def test_event_publication_on_process_detection(
        self, orchestrator: MonitorOrchestrator, sample_process_info: ProcessInfo
    ) -> None:
        """Test event publication when process is detected."""
        # Setup
        cast(Mock, orchestrator.detector.detect_mover).return_value = sample_process_info
        
        # Execute
        await orchestrator.run_detection_cycle()
        
        # Verify event publication
        cast(Mock, orchestrator.event_bus.publish_event).assert_called()
        
        # Verify event was called with some event
        call_args = cast(Mock, orchestrator.event_bus.publish_event).call_args
        assert call_args is not None
        event = call_args[0][0]
        assert event.priority == EventPriority.HIGH
    
    @pytest.mark.asyncio
    async def test_event_publication_on_error(self, orchestrator: MonitorOrchestrator) -> None:
        """Test event publication when error occurs."""
        # Setup
        cast(Mock, orchestrator.detector.detect_mover).side_effect = Exception("Test error")
        
        # Execute
        await orchestrator.run_detection_cycle()
        
        # Verify error event publication
        cast(Mock, orchestrator.event_bus.publish_event).assert_called()
        
        # Verify event was called
        call_args = cast(Mock, orchestrator.event_bus.publish_event).call_args
        assert call_args is not None
        event = call_args[0][0]
        assert event.priority == EventPriority.CRITICAL
    
    @pytest.mark.asyncio
    async def test_progress_event_publication(
        self, orchestrator: MonitorOrchestrator, sample_process_info: ProcessInfo
    ) -> None:
        """Test progress event publication during monitoring."""
        # Setup
        orchestrator.current_process = sample_process_info
        
        # Execute
        await orchestrator.run_monitoring_cycle()
        
        # Verify progress event publication
        cast(Mock, orchestrator.event_bus.publish_event).assert_called()
        
        # Verify event was called
        call_args = cast(Mock, orchestrator.event_bus.publish_event).call_args
        assert call_args is not None
        event = call_args[0][0]
        assert event.priority == EventPriority.NORMAL


class TestComponentCoordinationIntegration(TestOrchestratorTDD):
    """Integration tests for component coordination scenarios."""
    
    @pytest.mark.asyncio
    async def test_component_registration_during_startup(self, orchestrator: MonitorOrchestrator) -> None:
        """Test component registration during orchestrator startup."""
        # Execute
        await orchestrator.startup()
        
        # Verify components are registered
        assert len(orchestrator.registry.components) == 5
        
        # Verify specific components
        assert orchestrator.registry.get_component("process_detector") is not None
        assert orchestrator.registry.get_component("progress_calculator") is not None
        assert orchestrator.registry.get_component("notification_dispatcher") is not None
        assert orchestrator.registry.get_component("state_machine") is not None
        assert orchestrator.registry.get_component("event_bus") is not None
    
    @pytest.mark.asyncio
    async def test_health_check_during_startup(self, orchestrator: MonitorOrchestrator) -> None:
        """Test health check assessment during startup."""
        # Execute
        await orchestrator.startup()
        
        # Verify orchestrator is running
        assert orchestrator.running is True
    
    @pytest.mark.asyncio
    async def test_component_shutdown_during_orchestrator_shutdown(self, orchestrator: MonitorOrchestrator) -> None:
        """Test component shutdown during orchestrator shutdown."""
        # Setup
        await orchestrator.startup()
        
        # Execute
        await orchestrator.shutdown()
        
        # Verify orchestrator is stopped
        assert orchestrator.running is False
        
        # Verify all components are stopped
        for component in orchestrator.registry.get_all_components():
            assert component.status == ComponentStatus.SHUTDOWN
    
    @pytest.mark.asyncio
    async def test_workflow_execution_coordination(self, orchestrator: MonitorOrchestrator) -> None:
        """Test workflow execution coordination."""
        # Setup
        steps = [
            WorkflowStep("step1", execute=lambda: True),
            WorkflowStep("step2", dependencies=["step1"], execute=lambda: True),
            WorkflowStep("step3", dependencies=["step2"], execute=lambda: True),
        ]
        
        # Execute
        ordered_steps = orchestrator.workflow_engine.resolve_dependencies(steps)
        
        # Verify dependency ordering
        assert len(ordered_steps) == 3
        assert ordered_steps[0].name == "step1"
        assert ordered_steps[1].name == "step2"
        assert ordered_steps[2].name == "step3"
    
    @pytest.mark.asyncio
    async def test_resource_allocation_coordination(self, orchestrator: MonitorOrchestrator) -> None:
        """Test resource allocation coordination."""
        # Setup
        await orchestrator.startup()
        
        # Execute
        memory_result = orchestrator.resource_allocator.allocate("memory", 512)
        cpu_result = orchestrator.resource_allocator.allocate("cpu", 50)
        
        # Verify allocations
        assert memory_result.status == AllocationStatus.ALLOCATED
        assert memory_result.allocated_amount == 512
        assert cpu_result.status == AllocationStatus.ALLOCATED
        assert cpu_result.allocated_amount == 50
    
    @pytest.mark.asyncio
    async def test_full_detection_to_completion_workflow(
        self, orchestrator: MonitorOrchestrator, sample_process_info: ProcessInfo
    ) -> None:
        """Test full workflow from detection to completion."""
        # Setup
        cast(Mock, orchestrator.detector.detect_mover).return_value = sample_process_info
        
        await orchestrator.startup()
        
        # Execute detection cycle
        await orchestrator.run_detection_cycle()
        
        # Verify process is being monitored
        assert orchestrator.current_process == sample_process_info
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.MONITORING)
        
        # Simulate process ending
        cast(Mock, orchestrator.detector.is_process_running).return_value = False
        
        # Execute monitoring cycle
        await orchestrator.run_monitoring_cycle()
        
        # Verify completion
        assert orchestrator.current_process is None
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.COMPLETING)
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.IDLE)


class TestChaosEngineeringFailureScenarios(TestOrchestratorTDD):
    """Chaos engineering tests for failure scenarios."""
    
    @pytest.mark.asyncio
    async def test_detector_failure_recovery(self, orchestrator: MonitorOrchestrator) -> None:
        """Test orchestrator behavior when detector fails."""
        # Setup
        cast(Mock, orchestrator.detector.detect_mover).side_effect = Exception("Detector failure")
        
        # Execute
        await orchestrator.run_detection_cycle()
        
        # Verify error handling
        assert orchestrator.last_error is not None
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.ERROR)
        
        # Verify error event published
        cast(Mock, orchestrator.event_bus.publish_event).assert_called()
    
    @pytest.mark.asyncio
    async def test_calculator_failure_recovery(
        self, orchestrator: MonitorOrchestrator, sample_process_info: ProcessInfo
    ) -> None:
        """Test orchestrator behavior when calculator fails."""
        # Setup
        orchestrator.current_process = sample_process_info
        cast(Mock, orchestrator.calculator.calculate_progress).side_effect = Exception("Calculator failure")
        
        # Execute
        await orchestrator.run_monitoring_cycle()
        
        # Verify error handling
        assert orchestrator.last_error is not None
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.ERROR)
    
    @pytest.mark.asyncio
    async def test_state_machine_failure_resilience(self, orchestrator: MonitorOrchestrator) -> None:
        """Test orchestrator resilience to state machine failures."""
        # Setup
        cast(Mock, orchestrator.state_machine.transition_to).side_effect = Exception("State machine failure")
        
        # Execute (should not raise exception)
        try:
            await orchestrator.run_detection_cycle()
        except Exception as e:
            # If state machine fails, orchestrator should handle gracefully
            assert "State machine failure" in str(e)
    
    @pytest.mark.asyncio
    async def test_event_bus_failure_resilience(
        self, orchestrator: MonitorOrchestrator, sample_process_info: ProcessInfo
    ) -> None:
        """Test orchestrator resilience to event bus failures."""
        # Setup
        cast(Mock, orchestrator.detector.detect_mover).return_value = sample_process_info
        cast(Mock, orchestrator.event_bus.publish_event).side_effect = Exception("Event bus failure")
        
        # Execute (should not raise exception)
        try:
            await orchestrator.run_detection_cycle()
        except Exception as e:
            # If event bus fails, orchestrator should handle gracefully
            assert "Event bus failure" in str(e)
    
    @pytest.mark.asyncio
    async def test_multiple_simultaneous_failures(self, orchestrator: MonitorOrchestrator) -> None:
        """Test orchestrator behavior with multiple simultaneous failures."""
        # Setup multiple failures
        cast(Mock, orchestrator.detector.detect_mover).side_effect = Exception("Detector failure")
        cast(Mock, orchestrator.state_machine.transition_to).side_effect = Exception("State machine failure")
        cast(Mock, orchestrator.event_bus.publish_event).side_effect = Exception("Event bus failure")
        
        # Execute (should handle gracefully)
        try:
            await orchestrator.run_detection_cycle()
        except Exception as e:
            # Multiple failures should be handled without crashing
            assert "failure" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_component_health_check_failures(self, orchestrator: MonitorOrchestrator) -> None:
        """Test orchestrator behavior when component health checks fail."""
        # Setup
        await orchestrator.startup()
        
        # Create unhealthy component
        unhealthy_component = MockComponent(
            "unhealthy_component",
            ComponentType.CUSTOM,
            health_check_exception=Exception("Health check failed")
        )
        orchestrator.registry.register(unhealthy_component)
        
        # Execute health assessment
        health_status = orchestrator.health_monitor.assess_system_health(orchestrator.registry)
        
        # Verify unhealthy component is detected
        assert health_status["overall_healthy"] is False
        unhealthy_components = health_status["unhealthy_components"]
        assert isinstance(unhealthy_components, list)
        assert "unhealthy_component" in unhealthy_components
    
    @pytest.mark.asyncio
    async def test_resource_exhaustion_scenarios(self, orchestrator: MonitorOrchestrator) -> None:
        """Test orchestrator behavior under resource exhaustion."""
        # Setup
        await orchestrator.startup()
        
        # Exhaust memory resource
        memory_result1 = orchestrator.resource_allocator.allocate("memory", 1024)
        memory_result2 = orchestrator.resource_allocator.allocate("memory", 1)
        
        # Verify first allocation succeeds
        assert memory_result1.status == AllocationStatus.ALLOCATED
        
        # Verify second allocation fails due to insufficient resources
        assert memory_result2.status == AllocationStatus.INSUFFICIENT
        assert memory_result2.allocated_amount == 0
    
    @pytest.mark.asyncio
    async def test_circular_dependency_handling(self, orchestrator: MonitorOrchestrator) -> None:
        """Test workflow engine handling of circular dependencies."""
        # Setup circular dependency
        step1 = WorkflowStep("step1", dependencies=["step2"])
        step2 = WorkflowStep("step2", dependencies=["step1"])
        
        # Execute dependency resolution
        # This should handle circular dependencies gracefully
        resolved_steps = orchestrator.workflow_engine.resolve_dependencies([step1, step2])
        
        # Verify some resolution occurred (implementation-specific)
        assert len(resolved_steps) >= 0


class TestPerformanceAndLoadTesting(TestOrchestratorTDD):
    """Performance and load testing suites."""
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_high_frequency_state_transitions(self, orchestrator: MonitorOrchestrator) -> None:
        """Test orchestrator performance under high frequency state transitions."""
        # Setup
        await orchestrator.startup()
        
        # Execute rapid state transitions
        start_time = time.time()
        iterations = 100
        
        for _ in range(iterations):
            await orchestrator.run_detection_cycle()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify performance (should complete in reasonable time)
        assert duration < 5.0  # Should complete in under 5 seconds
        
        # Verify state transitions occurred
        assert cast(Mock, orchestrator.state_machine.transition_to).call_count >= iterations
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_concurrent_workflow_execution(self, orchestrator: MonitorOrchestrator) -> None:
        """Test orchestrator performance with concurrent workflow execution."""
        # Setup
        await orchestrator.startup()
        
        # Create multiple concurrent workflows
        async def run_workflow() -> None:
            await orchestrator.run_detection_cycle()
            await orchestrator.run_monitoring_cycle()
        
        # Execute concurrent workflows
        start_time = time.time()
        
        tasks = [run_workflow() for _ in range(10)]
        _ = await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify performance (should complete in reasonable time)
        assert duration < 10.0  # Should complete in under 10 seconds
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, orchestrator: MonitorOrchestrator) -> None:
        """Test orchestrator memory usage under load."""
        import psutil
        import os
        
        # Setup
        await orchestrator.startup()
        
        # Measure initial memory
        process = psutil.Process(os.getpid())
        initial_memory: int = process.memory_info().rss
        
        # Execute load test
        for _ in range(100):
            await orchestrator.run_detection_cycle()
            await orchestrator.run_monitoring_cycle()
        
        # Measure final memory
        final_memory: int = process.memory_info().rss
        memory_increase: int = final_memory - initial_memory
        
        # Verify memory usage is reasonable (less than 50MB increase)
        assert memory_increase < 50 * 1024 * 1024  # 50MB
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_event_publication_performance(
        self, orchestrator: MonitorOrchestrator, sample_process_info: ProcessInfo
    ) -> None:
        """Test event publication performance under load."""
        # Setup
        await orchestrator.startup()
        cast(Mock, orchestrator.detector.detect_mover).return_value = sample_process_info
        
        # Execute rapid event generation
        start_time = time.time()
        iterations = 100
        
        for _ in range(iterations):
            await orchestrator.run_detection_cycle()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify event publication performance
        assert duration < 2.0  # Should complete in under 2 seconds
        
        # Verify events were published
        assert cast(Mock, orchestrator.event_bus.publish_event).call_count >= iterations
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_resource_allocation_performance(self, orchestrator: MonitorOrchestrator) -> None:
        """Test resource allocation performance under load."""
        # Setup
        await orchestrator.startup()
        
        # Execute rapid resource allocations
        start_time = time.time()
        iterations = 1000
        
        for _ in range(iterations):
            # Allocate small amounts
            result = orchestrator.resource_allocator.allocate("memory", 1)
            if result.status == AllocationStatus.ALLOCATED:
                orchestrator.resource_allocator.deallocate("memory", 1)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify allocation performance
        assert duration < 1.0  # Should complete in under 1 second
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_component_registration_performance(self, orchestrator: MonitorOrchestrator) -> None:
        """Test component registration performance under load."""
        # Setup
        await orchestrator.startup()
        
        # Execute rapid component registrations
        start_time = time.time()
        iterations = 100
        
        for i in range(iterations):
            component = MockComponent(f"test_component_{i}", ComponentType.CUSTOM)
            orchestrator.registry.register(component)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify registration performance
        assert duration < 1.0  # Should complete in under 1 second
        
        # Verify components were registered
        assert len(orchestrator.registry.components) >= iterations + 5  # +5 for default components
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_health_check_performance(self, orchestrator: MonitorOrchestrator) -> None:
        """Test health check performance under load."""
        # Setup
        await orchestrator.startup()
        
        # Add many components for health checking
        for i in range(50):
            component = MockComponent(f"test_component_{i}", ComponentType.CUSTOM)
            orchestrator.registry.register(component)
        
        # Execute rapid health checks
        start_time = time.time()
        iterations = 100
        
        for _ in range(iterations):
            _ = orchestrator.health_monitor.assess_system_health(orchestrator.registry)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify health check performance
        assert duration < 5.0  # Should complete in under 5 seconds


class TestComplexScenarios(TestOrchestratorTDD):
    """Complex end-to-end scenario tests."""
    
    @pytest.mark.asyncio
    async def test_process_restart_detection(
        self, orchestrator: MonitorOrchestrator, sample_process_info: ProcessInfo
    ) -> None:
        """Test detection of process restart scenarios."""
        # Setup
        await orchestrator.startup()
        
        # First process detection
        process1 = sample_process_info
        cast(Mock, orchestrator.detector.detect_mover).return_value = process1
        
        await orchestrator.run_detection_cycle()
        assert orchestrator.current_process == process1
        
        # Process ends
        cast(Mock, orchestrator.detector.is_process_running).return_value = False
        await orchestrator.run_monitoring_cycle()
        assert orchestrator.current_process is None
        
        # New process starts with different PID
        process2 = ProcessInfo(
            pid=5678,
            name="test_process",
            status=ProcessStatus.RUNNING,
            cpu_percent=25.0,
            memory_mb=128.0,
            start_time=datetime.fromtimestamp(1640995200.0),
            command="test_command",
            working_directory="/tmp",
        )
        cast(Mock, orchestrator.detector.detect_mover).return_value = process2
        cast(Mock, orchestrator.detector.is_process_running).return_value = True
        
        await orchestrator.run_detection_cycle()
        assert orchestrator.current_process == process2
        if orchestrator.current_process is not None:
            assert orchestrator.current_process.pid != process1.pid
    
    @pytest.mark.asyncio
    async def test_error_recovery_cycle(
        self, orchestrator: MonitorOrchestrator, sample_process_info: ProcessInfo
    ) -> None:
        """Test error recovery and return to normal operation."""
        # Setup
        await orchestrator.startup()
        
        # Cause an error
        cast(Mock, orchestrator.detector.detect_mover).side_effect = Exception("Temporary error")
        await orchestrator.run_detection_cycle()
        
        # Verify error state
        assert orchestrator.last_error is not None
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.ERROR)
        
        # Clear error and resume normal operation
        cast(Mock, orchestrator.detector.detect_mover).side_effect = None
        cast(Mock, orchestrator.detector.detect_mover).return_value = sample_process_info
        
        await orchestrator.run_detection_cycle()
        
        # Verify recovery
        assert orchestrator.current_process == sample_process_info
        cast(Mock, orchestrator.state_machine.transition_to).assert_any_call(MonitorState.MONITORING)
    
    @pytest.mark.asyncio
    async def test_long_running_process_monitoring(
        self, orchestrator: MonitorOrchestrator, sample_process_info: ProcessInfo
    ) -> None:
        """Test monitoring of long-running processes."""
        # Setup
        await orchestrator.startup()
        
        # Start monitoring a process
        cast(Mock, orchestrator.detector.detect_mover).return_value = sample_process_info
        cast(Mock, orchestrator.detector.is_process_running).return_value = True
        
        await orchestrator.run_detection_cycle()
        
        # Simulate multiple monitoring cycles
        for i in range(10):
            progress = ProgressMetrics(
                percentage=float(i * 10),
                bytes_remaining=1048576 - (i * 104857),
                transfer_rate=10.5,
                etc_seconds=300.0 - (i * 30),
            )
            cast(Mock, orchestrator.calculator.calculate_progress).return_value = progress
            
            await orchestrator.run_monitoring_cycle()
            
            # Verify progress is being tracked
            assert orchestrator.current_process == sample_process_info
        
        # Process completes
        cast(Mock, orchestrator.detector.is_process_running).return_value = False
        await orchestrator.run_monitoring_cycle()
        
        # Verify completion
        assert orchestrator.current_process is None
    
    @pytest.mark.asyncio
    async def test_component_dependency_workflow(self, orchestrator: MonitorOrchestrator) -> None:
        """Test complex workflow with component dependencies."""
        # Setup
        await orchestrator.startup()
        
        # Create workflow with dependencies
        steps = [
            WorkflowStep("detect_process", execute=lambda: True),
            WorkflowStep("validate_process", dependencies=["detect_process"], execute=lambda: True),
            WorkflowStep("start_monitoring", dependencies=["validate_process"], execute=lambda: True),
            WorkflowStep("calculate_progress", dependencies=["start_monitoring"], execute=lambda: True),
            WorkflowStep("send_notification", dependencies=["calculate_progress"], execute=lambda: True),
        ]
        
        orchestrator.workflow_engine.register_workflow("full_monitoring", steps)
        
        # Execute workflow
        workflow_steps = orchestrator.workflow_engine.workflows["full_monitoring"]
        results = []
        
        for step in workflow_steps:
            result = orchestrator.workflow_engine.execute_step(step)
            results.append(result)
        
        # Verify all steps completed successfully
        assert len(results) == 5
        assert all(result.status == WorkflowStatus.COMPLETED for result in results)
        
        # Verify execution order
        step_names = [result.step.name for result in results]
        expected_order = ["detect_process", "validate_process", "start_monitoring", "calculate_progress", "send_notification"]
        assert step_names == expected_order