"""Async integration tests for logging infrastructure.

Tests the logging system's compatibility with asyncio:
- Correlation ID tracking across async tasks
- Context managers in async functions
- Concurrent async logging
- Thread-to-async context propagation
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import threading
import uuid
from typing import TypedDict, cast

import pytest


class LogEntry(TypedDict):
    """Structure of log entries returned by StructuredFormatter."""
    timestamp: str
    level: str
    message: str
    # Optional fields
    correlation_id: str | None
    operation: str | None
    user: str | None
    priority: str | None
    name: str | None
    args: tuple[object, ...] | None
    exc_info: tuple[object, ...] | None
    exc_text: str | None
    stack_info: str | None
    lineno: int | None
    funcName: str | None
    filename: str | None
    module: str | None
    pathname: str | None
    process: int | None
    processName: str | None
    relativeCreated: float | None
    thread: int | None
    threadName: str | None
    msecs: float | None
    created: float | None
    taskName: str | None

from mover_status.utils.logging import (
    ContextCapturingFilter,
    LogFormat,
    LogLevel,
    StructuredFormatter,
    correlation_id_context,
    get_correlation_id,
    log_field_context,
    log_level_context,
    set_correlation_id,
)


class TestAsyncLogging:
    """Test logging in async contexts."""
    
    def setup_method(self) -> None:
        """Setup method called before each test."""
        # Clear any existing correlation ID to ensure test isolation
        from mover_status.utils.logging import clear_correlation_id
        clear_correlation_id()
    
    @pytest.mark.asyncio
    async def test_correlation_id_async_isolation(self) -> None:
        """Test that correlation IDs are isolated between async tasks."""
        logger = logging.getLogger("test.async.correlation")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Capture output
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Track task results
        results: dict[str, list[str]] = {}
        
        async def async_task(task_id: str) -> None:
            """Async task that sets and uses correlation ID."""
            correlation_id = f"async-{task_id}-{uuid.uuid4().hex[:8]}"
            set_correlation_id(correlation_id)
            
            # Log initial message
            logger.info(f"Task {task_id} started")
            
            # Simulate async work
            await asyncio.sleep(0.01)
            
            # Verify correlation ID is preserved
            assert get_correlation_id() == correlation_id
            logger.info(f"Task {task_id} middle")
            
            # More async work
            await asyncio.sleep(0.01)
            
            # Final verification
            assert get_correlation_id() == correlation_id
            logger.info(f"Task {task_id} completed")
            
            # Store correlation ID for verification
            results[task_id] = [correlation_id]
        
        # Run multiple async tasks concurrently
        tasks = [
            async_task(f"task-{i}")
            for i in range(5)
        ]
        _ = await asyncio.gather(*tasks)
        
        # Parse and verify output
        _ = output.seek(0)
        lines = output.readlines()
        
        # Group logs by correlation ID
        logs_by_correlation: dict[str, list[LogEntry]] = {}
        for line in lines:
            log_entry: LogEntry = cast(LogEntry, json.loads(line))
            correlation_id: str | None = log_entry.get("correlation_id")
            if correlation_id:
                if correlation_id not in logs_by_correlation:
                    logs_by_correlation[correlation_id] = []
                logs_by_correlation[correlation_id].append(log_entry)
        
        # Verify each task had isolated correlation ID
        assert len(logs_by_correlation) == 5  # 5 different correlation IDs
        
        # Each correlation ID should have exactly 3 log entries
        for correlation_id, logs in logs_by_correlation.items():
            assert len(logs) == 3
            messages = [log["message"] for log in logs]
            # Extract task ID from first message
            task_id: str = messages[0].split()[1]
            assert messages == [
                f"Task {task_id} started",
                f"Task {task_id} middle",
                f"Task {task_id} completed"
            ]
    
    @pytest.mark.asyncio
    async def test_async_context_managers(self) -> None:
        """Test context managers in async functions."""
        logger = logging.getLogger("test.async.context")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        # Capture output
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        async def async_operation() -> None:
            """Async operation using context managers."""
            # Test correlation ID context
            with correlation_id_context("async-op-123"):
                logger.info("Starting async operation")
                
                # Test field context
                with log_field_context({"operation": "data_fetch", "user": "async_user"}):
                    await asyncio.sleep(0.01)
                    logger.info("Fetching data")
                    
                    # Test log level context
                    with log_level_context(logger, LogLevel.DEBUG):
                        logger.debug("Debug info in async context")
                        await asyncio.sleep(0.01)
                
                logger.info("Async operation completed")
        
        # Run async operation
        await async_operation()
        
        # Verify output
        _ = output.seek(0)
        lines = output.readlines()
        assert len(lines) == 4
        
        # All should have correlation ID
        for line in lines:
            log_entry: LogEntry = cast(LogEntry, json.loads(line))
            assert log_entry["correlation_id"] == "async-op-123"
        
        # Check specific messages
        log1: LogEntry = cast(LogEntry, json.loads(lines[0]))
        assert "operation" not in log1
        
        log2: LogEntry = cast(LogEntry, json.loads(lines[1]))  # pyright: ignore[reportUnreachable]
        assert log2["operation"] == "data_fetch"
        assert log2["user"] == "async_user"
        
        log3: LogEntry = cast(LogEntry, json.loads(lines[2]))
        assert log3["level"] == "DEBUG"
        assert log3["operation"] == "data_fetch"
    
    @pytest.mark.asyncio
    async def test_nested_async_tasks(self) -> None:
        """Test correlation ID propagation in nested async tasks."""
        logger = logging.getLogger("test.async.nested")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Capture output
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        async def child_task(name: str) -> str:
            """Child async task."""
            # Should inherit correlation ID from parent
            correlation_id = get_correlation_id()
            logger.info(f"Child task {name} running")
            await asyncio.sleep(0.01)
            return correlation_id or "none"
        
        async def parent_task(task_id: int) -> None:
            """Parent async task that spawns children."""
            with correlation_id_context(f"parent-{task_id}"):
                logger.info(f"Parent task {task_id} started")
                
                # Spawn child tasks
                child_results = await asyncio.gather(
                    child_task(f"{task_id}-A"),
                    child_task(f"{task_id}-B"),
                    child_task(f"{task_id}-C")
                )
                
                # All children should have same correlation ID
                assert all(cid == f"parent-{task_id}" for cid in child_results)
                logger.info(f"Parent task {task_id} completed")
        
        # Run multiple parent tasks
        _ = await asyncio.gather(
            parent_task(1),
            parent_task(2),
            parent_task(3)
        )
        
        # Verify output
        _ = output.seek(0)
        lines = output.readlines()
        
        # Group by correlation ID
        logs_by_parent: dict[str, list[str]] = {}
        for line in lines:
            log_entry: LogEntry = cast(LogEntry, json.loads(line))
            correlation_id = log_entry.get("correlation_id")
            message = log_entry["message"]
            if correlation_id is None:
                continue
            
            if correlation_id not in logs_by_parent:
                logs_by_parent[correlation_id] = []
            logs_by_parent[correlation_id].append(message)
        
        # Each parent should have 5 messages (1 start + 3 children + 1 complete)
        assert len(logs_by_parent) == 3
        for parent_id, messages in logs_by_parent.items():
            _ = parent_id  # iteration variable needed for dict comprehension
            assert len(messages) == 5
            # Verify parent messages are first and last
            assert "started" in messages[0]
            assert "completed" in messages[-1]
    
    @pytest.mark.asyncio
    async def test_async_exception_handling(self) -> None:
        """Test logging in async exception handlers."""
        logger = logging.getLogger("test.async.exception")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Capture output
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        async def failing_operation() -> None:
            """Async operation that fails."""
            with correlation_id_context("failing-op"):
                logger.info("Starting risky operation")
                await asyncio.sleep(0.01)
                raise ValueError("Async operation failed")
        
        # Run and catch exception
        try:
            await failing_operation()
        except ValueError:
            # Log exception with same correlation ID
            with correlation_id_context("failing-op"):
                logger.exception("Operation failed as expected")
        
        # Verify both logs have same correlation ID
        _ = output.seek(0)
        lines = output.readlines()
        assert len(lines) == 2
        
        for line in lines:
            log_entry: LogEntry = cast(LogEntry, json.loads(line))
            assert log_entry["correlation_id"] == "failing-op"
        
        # Second log should be ERROR level
        log2: LogEntry = cast(LogEntry, json.loads(lines[1]))
        assert log2["level"] == "ERROR"
    
    @pytest.mark.asyncio
    async def test_thread_to_async_context_propagation(self) -> None:
        """Test context propagation from threads to async tasks."""
        logger = logging.getLogger("test.async.thread_propagation")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Capture output
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Event to coordinate thread and async execution
        thread_ready = threading.Event()
        async_complete = threading.Event()
        correlation_id_in_async: str | None = None
        
        async def async_part() -> None:
            """Async part that should NOT inherit thread context."""
            nonlocal correlation_id_in_async
            # This should not have the thread's correlation ID
            correlation_id_in_async = get_correlation_id()
            logger.info("Async task running")
            async_complete.set()
        
        def thread_function() -> None:
            """Thread function that sets correlation ID."""
            # Set correlation ID in thread
            set_correlation_id("thread-correlation")
            logger.info("Thread running")
            thread_ready.set()
            
            # Wait for async to complete
            _ = async_complete.wait()
            
            # Thread should still have its correlation ID
            assert get_correlation_id() == "thread-correlation"
            logger.info("Thread completed")
        
        # Start thread
        thread = threading.Thread(target=thread_function)
        thread.start()
        
        # Wait for thread to set context
        _ = thread_ready.wait()
        
        # Run async task (should have independent context)
        await async_part()
        
        # Wait for thread to complete
        _ = thread.join()
        
        # Verify contexts were isolated
        assert correlation_id_in_async is None  # Async didn't inherit thread context
        
        # Check logs
        _ = output.seek(0)
        lines = output.readlines()
        
        thread_logs: list[str] = []
        async_logs: list[str] = []
        
        for line in lines:
            log_entry: LogEntry = cast(LogEntry, json.loads(line))
            if log_entry.get("correlation_id") == "thread-correlation":
                thread_logs.append(log_entry["message"])
            else:
                async_logs.append(log_entry["message"])
        
        assert len(thread_logs) == 2
        assert len(async_logs) == 1
        assert "Async task running" in async_logs[0]
    
    @pytest.mark.asyncio
    async def test_async_gather_with_contexts(self) -> None:
        """Test multiple async operations with different contexts using gather."""
        logger = logging.getLogger("test.async.gather")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Capture output
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        handler.setFormatter(formatter)
        
        # Add context capturing filter to ensure context is captured at log time
        context_filter = ContextCapturingFilter()
        logger.addFilter(context_filter)
        
        logger.addHandler(handler)
        
        async def operation_a() -> None:
            """Operation A with its own context."""
            with correlation_id_context("op-a"):
                with log_field_context({"operation": "A", "priority": "high"}):
                    logger.info("Operation A starting")
                    await asyncio.sleep(0.02)
                    logger.info("Operation A completed")
        
        async def operation_b() -> None:
            """Operation B with different context."""
            with correlation_id_context("op-b"):
                with log_field_context({"operation": "B", "priority": "medium"}):
                    logger.info("Operation B starting")
                    await asyncio.sleep(0.01)
                    logger.info("Operation B completed")
        
        async def operation_c() -> None:
            """Operation C with minimal context."""
            with correlation_id_context("op-c"):
                logger.info("Operation C starting")
                await asyncio.sleep(0.015)
                logger.info("Operation C completed")
        
        # Run all operations concurrently
        _ = await asyncio.gather(
            operation_a(),
            operation_b(),
            operation_c()
        )
        
        # Parse output
        _ = output.seek(0)
        lines = output.readlines()
        
        # Group by operation
        ops: dict[str, list[LogEntry]] = {"A": [], "B": [], "C": []}
        
        for line in lines:
            log_entry: LogEntry = cast(LogEntry, json.loads(line))
            op = log_entry.get("operation") or "C"  # C doesn't have operation field
            ops[op].append(log_entry)
        
        # Verify each operation
        assert len(ops["A"]) == 2
        assert all(log["correlation_id"] == "op-a" for log in ops["A"])
        assert all(log["priority"] == "high" for log in ops["A"])
        
        assert len(ops["B"]) == 2
        assert all(log["correlation_id"] == "op-b" for log in ops["B"])
        assert all(log["priority"] == "medium" for log in ops["B"])
        
        assert len(ops["C"]) == 2
        assert all(log["correlation_id"] == "op-c" for log in ops["C"])
        assert all("priority" not in log for log in ops["C"])
    
    @pytest.mark.asyncio
    async def test_async_timeout_logging(self) -> None:
        """Test logging when async operations timeout."""
        logger = logging.getLogger("test.async.timeout")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Capture output
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        async def slow_operation() -> None:
            """Operation that takes too long."""
            with correlation_id_context("slow-op"):
                logger.info("Starting slow operation")
                await asyncio.sleep(5)  # This will timeout
                logger.info("This should not be logged")
        
        # Run with timeout
        try:
            await asyncio.wait_for(slow_operation(), timeout=0.1)
        except asyncio.TimeoutError:
            # Log timeout with same correlation ID for tracking
            with correlation_id_context("slow-op"):
                logger.error("Operation timed out")
        
        # Verify output
        _ = output.seek(0)
        lines = output.readlines()
        assert len(lines) == 2
        
        # Both logs should have same correlation ID
        log1: LogEntry = cast(LogEntry, json.loads(lines[0]))
        log2: LogEntry = cast(LogEntry, json.loads(lines[1]))
        
        assert log1["correlation_id"] == "slow-op"
        assert log2["correlation_id"] == "slow-op"
        assert log1["message"] == "Starting slow operation"
        assert log2["message"] == "Operation timed out"
        assert log2["level"] == "ERROR"


class TestAsyncPerformance:
    """Test performance characteristics in async contexts."""
    
    @pytest.mark.asyncio
    async def test_async_logging_overhead(self) -> None:
        """Test logging overhead in async operations."""
        logger = logging.getLogger("test.async.performance")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Use null handler
        handler = logging.NullHandler()
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        
        # Measure baseline async operation
        iterations = 1000
        
        async def baseline_operation() -> None:
            """Baseline async operation without logging."""
            await asyncio.sleep(0)  # Yield control
        
        start_time = asyncio.get_event_loop().time()
        for _ in range(iterations):
            await baseline_operation()
        baseline_duration = asyncio.get_event_loop().time() - start_time
        
        # Measure with logging
        async def logged_operation() -> None:
            """Async operation with logging."""
            logger.info("Async operation")
            await asyncio.sleep(0)
        
        start_time = asyncio.get_event_loop().time()
        for _ in range(iterations):
            await logged_operation()
        logged_duration = asyncio.get_event_loop().time() - start_time
        
        # Measure with context
        async def context_operation() -> None:
            """Async operation with logging context."""
            with correlation_id_context("perf-test"):
                logger.info("Async operation with context")
                await asyncio.sleep(0)
        
        start_time = asyncio.get_event_loop().time()
        for _ in range(iterations):
            await context_operation()
        context_duration = asyncio.get_event_loop().time() - start_time
        
        # Calculate overhead
        logging_overhead = (logged_duration - baseline_duration) / baseline_duration
        context_overhead = (context_duration - baseline_duration) / baseline_duration
        
        # Overhead should be reasonable (less than 800% to account for system variability)
        assert logging_overhead < 8.0, f"Logging overhead too high: {logging_overhead:.1%}"
        assert context_overhead < 8.0, f"Context overhead too high: {context_overhead:.1%}"
        
        print(f"\nAsync performance:")
        print(f"  Baseline: {baseline_duration:.3f}s")
        print(f"  With logging: {logged_duration:.3f}s ({logging_overhead:.1%} overhead)")
        print(f"  With context: {context_duration:.3f}s ({context_overhead:.1%} overhead)")


if __name__ == "__main__":
    # Run async tests
    _ = pytest.main([__file__, "-v", "-s", "-k", "not Performance"])
    print("\n" + "="*50)
    print("Running async performance tests:")
    print("="*50)
    _ = pytest.main([__file__, "-v", "-s", "-k", "Performance"]) 