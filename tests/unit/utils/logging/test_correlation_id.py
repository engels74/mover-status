"""Test cases for correlation ID tracking system."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from mover_status.utils.logging.correlation_id import (
    CorrelationIdManager,
    CorrelationIdContext,
    correlation_id_context,
    get_correlation_id,
    set_correlation_id,
    generate_correlation_id,
    clear_correlation_id,
    get_correlation_id_manager,
)


class TestCorrelationIdManager:
    """Test CorrelationIdManager functionality."""
    
    def test_manager_initialization(self) -> None:
        """Test manager initialization with default values."""
        manager = CorrelationIdManager()
        
        # Should have no correlation ID initially
        assert manager.get_correlation_id() is None
    
    def test_set_and_get_correlation_id(self) -> None:
        """Test setting and getting correlation ID."""
        manager = CorrelationIdManager()
        test_id = "test-correlation-id-123"
        
        manager.set_correlation_id(test_id)
        assert manager.get_correlation_id() == test_id
    
    def test_generate_correlation_id(self) -> None:
        """Test automatic correlation ID generation."""
        manager = CorrelationIdManager()
        
        generated_id = manager.generate_correlation_id()
        
        # Should be a valid UUID
        assert isinstance(generated_id, str)
        assert len(generated_id) == 36  # UUID format
        assert generated_id.count("-") == 4  # UUID has 4 dashes
        
        # Should be set automatically
        assert manager.get_correlation_id() == generated_id
    
    def test_clear_correlation_id(self) -> None:
        """Test clearing correlation ID."""
        manager = CorrelationIdManager()
        
        manager.set_correlation_id("test-id")
        assert manager.get_correlation_id() == "test-id"
        
        manager.clear_correlation_id()
        assert manager.get_correlation_id() is None
    
    def test_custom_prefix(self) -> None:
        """Test custom prefix for generated IDs."""
        manager = CorrelationIdManager(prefix="req")
        
        generated_id = manager.generate_correlation_id()
        
        assert generated_id.startswith("req-")
        assert len(generated_id) > 4  # "req-" + UUID
    
    def test_thread_local_isolation(self) -> None:
        """Test that correlation IDs are isolated per thread."""
        manager = CorrelationIdManager()
        results: dict[str, str | None] = {}
        
        def thread_work(thread_id: str) -> None:
            test_id = f"thread-{thread_id}-correlation-id"
            manager.set_correlation_id(test_id)
            time.sleep(0.01)  # Small delay to ensure concurrency
            results[thread_id] = manager.get_correlation_id()
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=thread_work, args=(str(i),))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify each thread had its own correlation ID
        for i in range(5):
            thread_id = str(i)
            assert results[thread_id] == f"thread-{thread_id}-correlation-id"
        
        # Main thread should still have no correlation ID
        assert manager.get_correlation_id() is None


class TestCorrelationIdContext:
    """Test CorrelationIdContext context manager functionality."""
    
    def test_context_manager_basic(self) -> None:
        """Test basic context manager functionality."""
        test_id = "context-test-id"
        
        # Clear any existing correlation ID
        clear_correlation_id()
        assert get_correlation_id() is None
        
        with CorrelationIdContext(test_id):
            assert get_correlation_id() == test_id
        
        # Should be cleared after context exit
        assert get_correlation_id() is None
    
    def test_context_manager_with_existing_id(self) -> None:
        """Test context manager with existing correlation ID."""
        original_id = "original-id"
        context_id = "context-id"
        
        set_correlation_id(original_id)
        
        with CorrelationIdContext(context_id):
            assert get_correlation_id() == context_id
        
        # Should restore original ID
        assert get_correlation_id() == original_id
    
    def test_context_manager_with_none_id(self) -> None:
        """Test context manager with None (clear) ID."""
        set_correlation_id("existing-id")
        
        with CorrelationIdContext(None):
            assert get_correlation_id() is None
        
        # Should restore previous ID
        assert get_correlation_id() == "existing-id"
    
    def test_nested_context_managers(self) -> None:
        """Test nested correlation ID contexts."""
        clear_correlation_id()
        
        with CorrelationIdContext("outer-id"):
            assert get_correlation_id() == "outer-id"
            
            with CorrelationIdContext("inner-id"):
                assert get_correlation_id() == "inner-id"
            
            # Should restore outer context
            assert get_correlation_id() == "outer-id"
        
        # Should be cleared after all contexts exit
        assert get_correlation_id() is None
    
    def test_context_manager_exception_handling(self) -> None:
        """Test context manager behavior with exceptions."""
        original_id = "original-id"
        set_correlation_id(original_id)
        
        with pytest.raises(ValueError, match="test exception"):
            with CorrelationIdContext("exception-context-id"):
                assert get_correlation_id() == "exception-context-id"
                raise ValueError("test exception")
        
        # Should restore original ID even after exception
        assert get_correlation_id() == original_id
    
    def test_context_manager_thread_safety(self) -> None:
        """Test context manager thread safety."""
        results: dict[str, list[str | None]] = {}
        
        def thread_work(thread_id: str) -> None:
            thread_results = []
            
            # Set initial ID
            set_correlation_id(f"thread-{thread_id}-initial")
            thread_results.append(get_correlation_id())
            
            # Use context manager
            with CorrelationIdContext(f"thread-{thread_id}-context"):
                thread_results.append(get_correlation_id())
                time.sleep(0.01)  # Small delay to ensure concurrency
                thread_results.append(get_correlation_id())
            
            # After context exit
            thread_results.append(get_correlation_id())
            
            results[thread_id] = thread_results
        
        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=thread_work, args=(str(i),))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify each thread's results
        for i in range(3):
            thread_id = str(i)
            thread_results = results[thread_id]
            
            assert thread_results[0] == f"thread-{thread_id}-initial"
            assert thread_results[1] == f"thread-{thread_id}-context"
            assert thread_results[2] == f"thread-{thread_id}-context"
            assert thread_results[3] == f"thread-{thread_id}-initial"


class TestGlobalFunctions:
    """Test global convenience functions."""
    
    def setup_method(self) -> None:
        """Clear correlation ID before each test."""
        clear_correlation_id()
    
    def test_get_correlation_id_initially_none(self) -> None:
        """Test get_correlation_id returns None initially."""
        assert get_correlation_id() is None
    
    def test_set_and_get_correlation_id(self) -> None:
        """Test setting and getting correlation ID."""
        test_id = "global-test-id"
        
        set_correlation_id(test_id)
        assert get_correlation_id() == test_id
    
    def test_generate_correlation_id(self) -> None:
        """Test correlation ID generation."""
        generated_id = generate_correlation_id()
        
        assert isinstance(generated_id, str)
        assert len(generated_id) == 36  # UUID format
        assert get_correlation_id() == generated_id
    
    def test_generate_correlation_id_with_prefix(self) -> None:
        """Test correlation ID generation with prefix."""
        generated_id = generate_correlation_id(prefix="api")
        
        assert generated_id.startswith("api-")
        assert len(generated_id) > 4
        assert get_correlation_id() == generated_id
    
    def test_clear_correlation_id(self) -> None:
        """Test clearing correlation ID."""
        set_correlation_id("test-id")
        assert get_correlation_id() == "test-id"
        
        clear_correlation_id()
        assert get_correlation_id() is None
    
    def test_correlation_id_context_function(self) -> None:
        """Test correlation_id_context function."""
        test_id = "context-function-test"
        
        assert get_correlation_id() is None
        
        with correlation_id_context(test_id):
            assert get_correlation_id() == test_id
        
        assert get_correlation_id() is None
    
    def test_get_correlation_id_manager(self) -> None:
        """Test getting the global manager instance."""
        manager = get_correlation_id_manager()
        
        assert isinstance(manager, CorrelationIdManager)
        
        # Should be same instance across calls
        assert get_correlation_id_manager() is manager


class TestAsyncSupport:
    """Test async/await support for correlation ID tracking."""
    
    @pytest.mark.asyncio
    async def test_async_context_preservation(self) -> None:
        """Test correlation ID preservation in async contexts."""
        test_id = "async-test-id"
        
        async def async_work() -> str | None:
            await asyncio.sleep(0.01)
            return get_correlation_id()
        
        set_correlation_id(test_id)
        
        # Should preserve correlation ID across async calls
        result = await async_work()
        assert result == test_id
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """Test correlation ID context manager in async contexts."""
        test_id = "async-context-test"
        
        # Clear any existing correlation ID first
        clear_correlation_id()
        
        async def async_work() -> str | None:
            await asyncio.sleep(0.01)
            return get_correlation_id()
        
        with correlation_id_context(test_id):
            result = await async_work()
            assert result == test_id
        
        assert get_correlation_id() is None
    
    @pytest.mark.asyncio
    async def test_concurrent_async_tasks(self) -> None:
        """Test correlation ID isolation in concurrent async tasks."""
        async def async_task(task_id: str) -> str | None:
            correlation_id = f"task-{task_id}"
            set_correlation_id(correlation_id)
            await asyncio.sleep(0.01)
            return get_correlation_id()
        
        # Clear any existing correlation ID first
        clear_correlation_id()
        
        # Run multiple tasks concurrently
        tasks = [async_task(str(i)) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Each task should have its own correlation ID
        for i, result in enumerate(results):
            assert result == f"task-{i}"


class TestIntegrationWithLogging:
    """Test integration with logging system."""
    
    def test_correlation_id_in_structured_logs(self) -> None:
        """Test correlation ID appears in structured log output."""
        import json
        import io
        from mover_status.utils.logging import StructuredFormatter, LogFormat
        
        # Create a logger with structured formatter
        logger = logging.getLogger("test.correlation.structured")
        
        # Create string stream handler with structured formatter
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Clear any existing correlation ID
        clear_correlation_id()
        
        # Test without correlation ID
        logger.info("Message without correlation ID")
        log_line = stream.getvalue().strip()
        log_data = json.loads(log_line)
        assert "correlation_id" not in log_data
        
        # Clear stream
        stream.seek(0)
        stream.truncate(0)
        
        # Test with correlation ID
        test_id = "test-structured-logging-123"
        set_correlation_id(test_id)
        
        logger.info("Message with correlation ID")
        log_line = stream.getvalue().strip()
        log_data = json.loads(log_line)
        
        assert log_data["correlation_id"] == test_id
        assert log_data["message"] == "Message with correlation ID"
        assert log_data["level"] == "INFO"
        
        # Clean up
        logger.removeHandler(handler)
        clear_correlation_id()
    
    def test_correlation_id_with_context_manager(self) -> None:
        """Test correlation ID with context manager in structured logs."""
        import json
        import io
        from mover_status.utils.logging import StructuredFormatter, LogFormat
        
        # Create a logger with structured formatter
        logger = logging.getLogger("test.correlation.context")
        
        # Create string stream handler with structured formatter
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Clear any existing correlation ID
        clear_correlation_id()
        
        test_id = "context-manager-test-456"
        
        with correlation_id_context(test_id):
            logger.info("Message inside context")
            log_line = stream.getvalue().strip()
            log_data = json.loads(log_line)
            
            assert log_data["correlation_id"] == test_id
            assert log_data["message"] == "Message inside context"
        
        # Clear stream for next test
        stream.seek(0)
        stream.truncate(0)
        
        # After context exit, correlation ID should not be present
        logger.info("Message after context")
        log_line = stream.getvalue().strip()
        log_data = json.loads(log_line)
        assert "correlation_id" not in log_data
        
        # Clean up
        logger.removeHandler(handler)
    
    def test_correlation_id_with_key_value_format(self) -> None:
        """Test correlation ID with key-value log format."""
        import io
        from mover_status.utils.logging import StructuredFormatter, LogFormat
        
        # Create a logger with key-value formatter
        logger = logging.getLogger("test.correlation.keyvalue")
        
        # Create string stream handler with key-value formatter
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        formatter = StructuredFormatter(format_type=LogFormat.KEYVALUE)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Test with correlation ID
        test_id = "keyvalue-test-789"
        set_correlation_id(test_id)
        
        logger.info("Key-value test message")
        log_line = stream.getvalue().strip()
        
        # Should contain correlation_id in key-value format
        assert f'correlation_id="{test_id}"' in log_line
        assert 'message="Key-value test message"' in log_line
        assert 'level="INFO"' in log_line
        
        # Clean up
        logger.removeHandler(handler)
        clear_correlation_id()
    
    def test_correlation_id_excluded_from_logs(self) -> None:
        """Test correlation ID can be excluded from log output."""
        import json
        import io
        from mover_status.utils.logging import StructuredFormatter, LogFormat
        
        # Create a logger with structured formatter that excludes correlation_id
        logger = logging.getLogger("test.correlation.excluded")
        
        # Create string stream handler with formatter that excludes correlation_id
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        formatter = StructuredFormatter(
            format_type=LogFormat.JSON,
            exclude_fields=["correlation_id"]
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Test with correlation ID that should be excluded
        test_id = "excluded-correlation-id"
        set_correlation_id(test_id)
        
        logger.info("Message with excluded correlation ID")
        log_line = stream.getvalue().strip()
        log_data = json.loads(log_line)
        
        # Correlation ID should not be present in output
        assert "correlation_id" not in log_data
        assert log_data["message"] == "Message with excluded correlation ID"
        
        # Clean up
        logger.removeHandler(handler)
        clear_correlation_id()


class TestThreadPoolExecutor:
    """Test correlation ID tracking with ThreadPoolExecutor."""
    
    def test_thread_pool_isolation(self) -> None:
        """Test correlation ID isolation in thread pool workers."""
        def worker_task(task_id: str) -> str | None:
            correlation_id = f"worker-{task_id}"
            set_correlation_id(correlation_id)
            time.sleep(0.01)  # Simulate work
            return get_correlation_id()
        
        # Clear main thread correlation ID
        clear_correlation_id()
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(worker_task, str(i)) for i in range(5)]
            results = [future.result() for future in futures]
        
        # Each worker should have its own correlation ID
        for i, result in enumerate(results):
            assert result == f"worker-{i}"
        
        # Main thread should be unaffected
        assert get_correlation_id() is None
    
    def test_thread_pool_with_context_manager(self) -> None:
        """Test correlation ID context manager with thread pool."""
        def worker_task() -> str | None:
            return get_correlation_id()
        
        main_id = "main-thread-id"
        set_correlation_id(main_id)
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker_task) for _ in range(3)]
            results = [future.result() for future in futures]
        
        # Workers should not inherit main thread's correlation ID
        for result in results:
            assert result is None
        
        # Main thread should still have its ID
        assert get_correlation_id() == main_id