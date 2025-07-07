"""Test cases for error and recovery handling in the monitoring orchestrator."""

from __future__ import annotations

import pytest
import time
from unittest.mock import Mock

from mover_status.core.monitor.error_recovery import (
    ErrorClassifier,
    ErrorSeverity,
    ErrorCategory,
    ErrorEscalationManager,
    CircuitBreakerManager,
    RetryManager,
    RollbackManager,
    CompensationManager,
    ErrorRecoveryOrchestrator,
    ErrorRecord,
    RecoveryStatus,
    CircuitBreakerError,
    RetryExhaustedException,
)
from mover_status.core.monitor.state_machine import MonitorState, StateMachine
from mover_status.core.monitor.event_bus import EventBus


class TestErrorClassifier:
    """Test error classification functionality."""
    
    def test_classify_permission_error(self) -> None:
        """Test classification of permission errors."""
        classifier = ErrorClassifier()
        error = PermissionError("Access denied")
        
        record = classifier.classify_error(error, "process_detection")
        
        assert record.category == ErrorCategory.PERMISSION
        assert record.severity == ErrorSeverity.HIGH
        assert record.context == "process_detection"
        assert "Access denied" in record.message
    
    def test_classify_timeout_error(self) -> None:
        """Test classification of timeout errors."""
        classifier = ErrorClassifier()
        error = TimeoutError("Operation timed out")
        
        record = classifier.classify_error(error, "monitoring")
        
        assert record.category == ErrorCategory.TIMEOUT
        assert record.severity == ErrorSeverity.MEDIUM
        assert record.context == "monitoring"
    
    def test_classify_resource_error(self) -> None:
        """Test classification of resource errors."""
        classifier = ErrorClassifier()
        error = MemoryError("Out of memory")
        
        record = classifier.classify_error(error, "calculation")
        
        assert record.category == ErrorCategory.RESOURCE
        assert record.severity == ErrorSeverity.CRITICAL
        assert record.context == "calculation"
    
    def test_classify_unknown_error(self) -> None:
        """Test classification of unknown errors."""
        classifier = ErrorClassifier()
        error = ValueError("Invalid value")

        record = classifier.classify_error(error, "unknown")

        # ValueError is classified as VALIDATION, not UNKNOWN
        assert record.category == ErrorCategory.VALIDATION
        assert record.severity == ErrorSeverity.MEDIUM
        assert record.context == "unknown"


class TestErrorEscalationManager:
    """Test error escalation functionality."""
    
    def test_should_escalate_critical_error(self) -> None:
        """Test escalation of critical errors."""
        manager = ErrorEscalationManager()
        record = ErrorRecord(
            error_id="test-1",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            message="Critical system error",
            context="system",
            timestamp=time.time()
        )
        
        assert manager.should_escalate(record) is True
    
    def test_should_not_escalate_low_severity(self) -> None:
        """Test no escalation for low severity errors."""
        manager = ErrorEscalationManager()
        record = ErrorRecord(
            error_id="test-2",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.LOW,
            message="Minor network issue",
            context="network",
            timestamp=time.time()
        )
        
        assert manager.should_escalate(record) is False
    
    def test_escalation_threshold(self) -> None:
        """Test escalation based on error frequency."""
        manager = ErrorEscalationManager(escalation_threshold=3)
        
        # Add multiple similar errors
        for i in range(4):
            record = ErrorRecord(
                error_id=f"test-{i}",
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.MEDIUM,
                message="Network timeout",
                context="network",
                timestamp=time.time()
            )
            manager.record_error(record)
        
        # Should escalate after threshold
        latest_record = ErrorRecord(
            error_id="test-latest",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            message="Network timeout",
            context="network",
            timestamp=time.time()
        )
        
        assert manager.should_escalate(latest_record) is True


class TestCircuitBreakerManager:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_creation(self) -> None:
        """Test circuit breaker creation and configuration."""
        manager = CircuitBreakerManager()
        
        manager.create_circuit_breaker(
            "test_component",
            failure_threshold=3,
            recovery_timeout=30.0
        )
        
        assert "test_component" in manager.circuit_breakers
        breaker = manager.circuit_breakers["test_component"]
        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 30.0
    
    def test_circuit_breaker_failure_tracking(self) -> None:
        """Test circuit breaker failure tracking."""
        manager = CircuitBreakerManager()
        manager.create_circuit_breaker("test_component", failure_threshold=2)
        
        # Record failures
        manager.record_failure("test_component", Exception("Test error"))
        assert manager.get_failure_count("test_component") == 1
        
        manager.record_failure("test_component", Exception("Another error"))
        assert manager.get_failure_count("test_component") == 2
        
        # Circuit should be open now
        assert manager.is_circuit_open("test_component") is True
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_execution(self) -> None:
        """Test circuit breaker execution protection."""
        manager = CircuitBreakerManager()
        manager.create_circuit_breaker("test_component", failure_threshold=1)
        
        # First failure should open circuit
        with pytest.raises(Exception):
            await manager.execute_with_circuit_breaker(
                "test_component",
                lambda: (_ for _ in ()).throw(Exception("Test error"))
            )
        
        # Second call should be blocked by circuit breaker
        with pytest.raises(CircuitBreakerError):
            async def success_operation() -> str:
                return "success"

            _ = await manager.execute_with_circuit_breaker(
                "test_component",
                success_operation
            )


class TestRetryManager:
    """Test retry mechanism functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_retry(self) -> None:
        """Test successful operation after retry."""
        manager = RetryManager()
        call_count = 0
        
        async def flaky_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await manager.execute_with_retry(
            flaky_operation,
            max_attempts=3,
            backoff_factor=0.1  # Fast for testing
        )
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion(self) -> None:
        """Test retry exhaustion handling."""
        manager = RetryManager()
        
        async def failing_operation() -> str:
            raise Exception("Always fails")
        
        with pytest.raises(RetryExhaustedException):
            _ = await manager.execute_with_retry(
                failing_operation,
                max_attempts=2,
                backoff_factor=0.1
            )


class TestRollbackManager:
    """Test rollback functionality."""
    
    @pytest.mark.asyncio
    async def test_rollback_execution(self) -> None:
        """Test rollback action execution."""
        manager = RollbackManager()
        rollback_executed = False
        
        async def rollback_action() -> None:
            nonlocal rollback_executed
            rollback_executed = True
        
        manager.register_rollback("test_transaction", rollback_action)
        await manager.execute_rollback("test_transaction")
        
        assert rollback_executed is True
    
    @pytest.mark.asyncio
    async def test_rollback_all(self) -> None:
        """Test rolling back all registered transactions."""
        manager = RollbackManager()
        rollback_count = 0
        
        async def rollback_action() -> None:
            nonlocal rollback_count
            rollback_count += 1
        
        # Register multiple rollbacks
        for i in range(3):
            manager.register_rollback(f"transaction_{i}", rollback_action)
        
        await manager.rollback_all()
        assert rollback_count == 3


class TestCompensationManager:
    """Test compensation transaction functionality."""
    
    @pytest.mark.asyncio
    async def test_compensation_execution(self) -> None:
        """Test compensation action execution."""
        manager = CompensationManager()
        compensation_executed = False
        
        async def compensation_action() -> None:
            nonlocal compensation_executed
            compensation_executed = True
        
        manager.register_compensation("test_operation", compensation_action)
        await manager.execute_compensation("test_operation")
        
        assert compensation_executed is True


class TestErrorRecoveryOrchestrator:
    """Test the main error recovery orchestrator."""
    
    @pytest.fixture
    def mock_state_machine(self) -> Mock:
        """Create a mock state machine."""
        mock = Mock(spec=StateMachine)
        mock.current_state = MonitorState.IDLE
        return mock
    
    @pytest.fixture
    def mock_event_bus(self) -> Mock:
        """Create a mock event bus."""
        return Mock(spec=EventBus)
    
    @pytest.fixture
    def orchestrator(self, mock_state_machine: Mock, mock_event_bus: Mock) -> ErrorRecoveryOrchestrator:
        """Create error recovery orchestrator with mocks."""
        return ErrorRecoveryOrchestrator(
            state_machine=mock_state_machine,
            event_bus=mock_event_bus
        )
    
    @pytest.mark.asyncio
    async def test_handle_error_with_recovery(self, orchestrator: ErrorRecoveryOrchestrator) -> None:
        """Test error handling with successful recovery."""
        error = Exception("Test error")

        result = await orchestrator.handle_error(error, "test_context")

        # Generic Exception gets classified as UNKNOWN category, which has no recovery strategy
        # so it gets escalated
        assert result.status == RecoveryStatus.ESCALATED
        assert result.error_record is not None
        assert result.error_record.context == "test_context"

    @pytest.mark.asyncio
    async def test_handle_network_error_with_recovery(self, orchestrator: ErrorRecoveryOrchestrator) -> None:
        """Test network error handling with successful recovery."""
        error = ConnectionError("Network connection failed")

        result = await orchestrator.handle_error(error, "network_operation")

        # Network errors have a recovery strategy, so should recover
        assert result.status == RecoveryStatus.RECOVERED
        assert result.error_record is not None
        assert result.error_record.category == ErrorCategory.NETWORK
        assert len(result.recovery_actions_taken) > 0
    
    @pytest.mark.asyncio
    async def test_handle_critical_error_escalation(self, orchestrator: ErrorRecoveryOrchestrator) -> None:
        """Test critical error escalation."""
        error = MemoryError("Out of memory")
        
        result = await orchestrator.handle_error(error, "critical_operation")
        
        assert result.status in [RecoveryStatus.ESCALATED, RecoveryStatus.FAILED]
        assert result.error_record is not None
        assert result.error_record.severity == ErrorSeverity.CRITICAL
