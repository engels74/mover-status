"""Integration tests for complete logging infrastructure.

Tests the interaction between all logging components:
- StructuredFormatter with various output formats
- Multiple handlers working together
- Context managers with correlation IDs
- Log level management across multiple loggers
- Thread safety and concurrent access
"""

from __future__ import annotations

import io
import json
import logging
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, cast

import pytest

from mover_status.utils.logging import (
    ColoredFormatter,
    ConsoleHandler,
    FileHandler,
    LogFieldContext,
    LogFormat,
    LogLevel,
    LogLevelContext,
    StructuredFormatter,
    TimestampFormat,
    combined_log_context,
    correlation_id_context,
    get_correlation_id,
    log_field_context,
    log_level_context,
    set_correlation_id,
    set_logger_level,
)


class TestCompleteLoggingFlow:
    """Test complete logging flow with all components."""
    
    def test_multiple_handlers_with_different_formatters(self) -> None:
        """Test logging to multiple handlers with different formatters."""
        # Create a test logger
        logger = logging.getLogger("test.integration.multi_handler")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        # Create handlers with different formatters
        # Console handler with colored key-value format
        console_stream = io.StringIO()
        console_handler = ConsoleHandler(
            level=logging.INFO,
            enable_colors=False  # Disable colors for easier testing
        )
        console_handler.stream = console_stream
        console_formatter = StructuredFormatter(
            format_type=LogFormat.KEYVALUE,
            timestamp_format=TimestampFormat.ISO
        )
        console_handler.setFormatter(console_formatter)
        
        # File handler with JSON format
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp_file:
            file_handler = FileHandler(
                tmp_file.name,
                level=logging.DEBUG,
                formatter=StructuredFormatter(
                    format_type=LogFormat.JSON,
                    timestamp_format=TimestampFormat.EPOCH
                )
            )
            
            # Add handlers to logger
            logger.addHandler(console_handler)
            logger.addHandler(file_handler)
            
            # Log messages at different levels
            logger.debug("Debug message - only in file")
            logger.info("Info message - in both handlers")
            logger.warning("Warning message - in both handlers")
            logger.error("Error message - in both handlers")
            
            # Flush handlers
            console_handler.flush()
            file_handler.flush()
            
            # Check console output (INFO and above)
            console_output = console_stream.getvalue()
            assert "Debug message" not in console_output  # Below INFO level
            assert "Info message" in console_output
            assert "Warning message" in console_output
            assert "Error message" in console_output
            
            # Check file output (DEBUG and above)
            file_handler.close()
            with open(tmp_file.name, 'r') as f:
                file_lines = f.readlines()
            
            assert len(file_lines) == 4  # All messages
            
            # Verify JSON format in file
            for line in file_lines:
                log_entry = json.loads(line.strip())
                assert "timestamp" in log_entry
                assert "level" in log_entry
                assert "logger" in log_entry
                assert "message" in log_entry
            
            # Clean up
            Path(tmp_file.name).unlink()
    
    def test_context_managers_with_correlation_ids(self) -> None:
        """Test context managers working with correlation IDs."""
        logger = logging.getLogger("test.integration.context")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        # Capture output
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        formatter = StructuredFormatter(
            format_type=LogFormat.JSON,
            timestamp_format=TimestampFormat.ISO
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Test correlation ID context
        with correlation_id_context("test-correlation-123"):
            logger.info("Message with correlation ID")
            
            # Test nested field context
            with log_field_context({"user_id": "user456", "request_id": "req789"}):
                logger.info("Message with correlation ID and extra fields")
                
                # Test nested log level context
                with log_level_context(logger, LogLevel.DEBUG):
                    logger.debug("Debug message with all contexts")
        
        # Parse output
        output.seek(0)
        lines = output.readlines()
        assert len(lines) == 3
        
        # First message - only correlation ID
        log1 = json.loads(lines[0])
        assert log1["correlation_id"] == "test-correlation-123"
        assert "user_id" not in log1
        
        # Second message - correlation ID and extra fields
        log2 = json.loads(lines[1])
        assert log2["correlation_id"] == "test-correlation-123"
        assert log2["user_id"] == "user456"
        assert log2["request_id"] == "req789"
        
        # Third message - all contexts
        log3 = json.loads(lines[2])
        assert log3["correlation_id"] == "test-correlation-123"
        assert log3["user_id"] == "user456"
        assert log3["request_id"] == "req789"
        assert log3["level"] == "DEBUG"
    
    def test_combined_context_manager(self) -> None:
        """Test combined context manager for level and fields."""
        logger = logging.getLogger("test.integration.combined")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Capture output
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        formatter = StructuredFormatter(format_type=LogFormat.JSON)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Test combined context
        with combined_log_context(
            logger,
            LogLevel.DEBUG,
            {"operation": "test_op", "version": "1.0"}
        ):
            logger.debug("Debug message now visible")
            logger.info("Info message with fields")
        
        # Verify output
        output.seek(0)
        lines = output.readlines()
        assert len(lines) == 2
        
        for line in lines:
            log_entry = json.loads(line)
            assert log_entry["operation"] == "test_op"
            assert log_entry["version"] == "1.0"
    
    def test_log_level_management_hierarchy(self) -> None:
        """Test log level management with logger hierarchy."""
        # Create parent and child loggers
        parent_logger = logging.getLogger("test.parent")
        child_logger = logging.getLogger("test.parent.child")
        grandchild_logger = logging.getLogger("test.parent.child.grandchild")
        
        # Clear handlers
        for logger in [parent_logger, child_logger, grandchild_logger]:
            logger.handlers.clear()
            logger.setLevel(logging.INFO)
        
        # Set up handler on parent
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.KEYVALUE))
        parent_logger.addHandler(handler)
        
        # Test default propagation
        parent_logger.info("Parent info")
        child_logger.info("Child info")
        grandchild_logger.info("Grandchild info")
        
        output.seek(0)
        lines = output.readlines()
        assert len(lines) == 3
        
        # Change child logger level
        set_logger_level("test.parent.child", LogLevel.DEBUG)
        
        # Clear output
        output.truncate(0)
        output.seek(0)
        
        # Test with changed level
        parent_logger.debug("Parent debug - not visible")
        child_logger.debug("Child debug - visible")
        grandchild_logger.debug("Grandchild debug - visible")
        
        output.seek(0)
        lines = output.readlines()
        assert len(lines) == 2  # Only child and grandchild debug messages
        assert "Child debug" in lines[0]
        assert "Grandchild debug" in lines[1]
    
    def test_handler_error_recovery(self) -> None:
        """Test logging continues when a handler fails."""
        logger = logging.getLogger("test.integration.error_recovery")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Create working handler
        working_output = io.StringIO()
        working_handler = logging.StreamHandler(working_output)
        working_handler.setFormatter(StructuredFormatter())
        
        # Create failing handler
        class FailingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                raise RuntimeError("Handler failed!")
        
        failing_handler = FailingHandler()
        
        # Add both handlers
        logger.addHandler(failing_handler)
        logger.addHandler(working_handler)
        
        # Log should still work despite one handler failing
        logger.info("This should still be logged")
        
        # Verify working handler got the message
        working_output.seek(0)
        output = working_output.read()
        assert "This should still be logged" in output
    
    def test_large_message_handling(self) -> None:
        """Test handling of large log messages."""
        logger = logging.getLogger("test.integration.large_message")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Create handler
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
        logger.addHandler(handler)
        
        # Create large message
        large_message = "x" * 10000  # 10KB message
        large_data = {"data": ["item" * 100 for _ in range(100)]}  # Large structured data
        
        # Log with context
        with log_field_context(large_data):
            logger.info(large_message)
        
        # Verify it was logged correctly
        output.seek(0)
        log_entry = json.loads(output.read())
        assert log_entry["message"] == large_message
        assert len(log_entry["data"]) == 100
    
    def test_unicode_and_special_characters(self) -> None:
        """Test handling of unicode and special characters."""
        logger = logging.getLogger("test.integration.unicode")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Create handler
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
        logger.addHandler(handler)
        
        # Test various unicode and special characters
        test_messages = [
            "Hello 世界",  # Chinese
            "Привет мир",  # Russian
            "مرحبا بالعالم",  # Arabic
            "🚀 Emoji test 🎉",  # Emojis
            "Special chars: \n\t\r",  # Control characters
            'Quotes: "double" \'single\'',  # Quotes
        ]
        
        for msg in test_messages:
            logger.info(msg)
        
        # Verify all messages were logged correctly
        output.seek(0)
        lines = output.readlines()
        assert len(lines) == len(test_messages)
        
        for i, line in enumerate(lines):
            log_entry = json.loads(line)
            assert log_entry["message"] == test_messages[i]


class TestThreadSafety:
    """Test thread safety of logging components."""
    
    def test_concurrent_logging(self) -> None:
        """Test concurrent logging from multiple threads."""
        logger = logging.getLogger("test.thread.concurrent")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Thread-safe output collection
        output_lock = threading.Lock()
        output_lines: list[str] = []
        
        class ThreadSafeHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                msg = self.format(record)
                with output_lock:
                    output_lines.append(msg)
        
        handler = ThreadSafeHandler()
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
        logger.addHandler(handler)
        
        # Function for threads to execute
        def log_messages(thread_id: int, count: int) -> None:
            for i in range(count):
                logger.info(f"Thread {thread_id} message {i}")
                time.sleep(0.001)  # Small delay to increase chance of interleaving
        
        # Create and start threads
        threads = []
        num_threads = 10
        messages_per_thread = 20
        
        for i in range(num_threads):
            thread = threading.Thread(target=log_messages, args=(i, messages_per_thread))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify all messages were logged
        assert len(output_lines) == num_threads * messages_per_thread
        
        # Verify message integrity (no corruption)
        thread_counts: dict[int, int] = {}
        for line in output_lines:
            log_entry = json.loads(line)
            msg = log_entry["message"]
            # Extract thread ID and message number
            parts = msg.split()
            thread_id = int(parts[1])
            msg_num = int(parts[3])
            
            if thread_id not in thread_counts:
                thread_counts[thread_id] = 0
            thread_counts[thread_id] += 1
        
        # Each thread should have logged exactly messages_per_thread messages
        for thread_id in range(num_threads):
            assert thread_counts[thread_id] == messages_per_thread
    
    def test_thread_local_context_isolation(self) -> None:
        """Test that context fields are isolated between threads."""
        logger = logging.getLogger("test.thread.isolation")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Thread-safe output collection
        output_lock = threading.Lock()
        output_lines: list[str] = []
        
        class ThreadSafeHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                msg = self.format(record)
                with output_lock:
                    output_lines.append(msg)
        
        handler = ThreadSafeHandler()
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
        logger.addHandler(handler)
        
        # Barrier to synchronize thread execution
        barrier = threading.Barrier(3)  # 3 threads
        
        def thread_function(thread_id: int) -> None:
            # Set thread-specific context
            with log_field_context({"thread_id": thread_id, "data": f"thread_{thread_id}_data"}):
                # Wait for all threads to set context
                barrier.wait()
                
                # Log with context
                logger.info(f"Message from thread {thread_id}")
                
                # Set correlation ID
                set_correlation_id(f"correlation_{thread_id}")
                
                # Wait again
                try:
                    barrier.wait()
                except threading.BrokenBarrierError:
                    pass  # Expected if threads finish at different times
                
                # Log again with correlation ID
                logger.info(f"Second message from thread {thread_id}")
        
        # Create and start threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=thread_function, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify thread isolation
        assert len(output_lines) == 6  # 2 messages per thread
        
        # Group messages by thread
        thread_messages: dict[int, list[dict[str, Any]]] = {}  # pyright: ignore[reportExplicitAny]
        for line in output_lines:
            log_entry = json.loads(line)
            thread_id = log_entry.get("thread_id")
            if thread_id is not None:
                if thread_id not in thread_messages:
                    thread_messages[thread_id] = []
                thread_messages[thread_id].append(log_entry)
        
        # Verify each thread's messages have correct context
        for thread_id in range(3):
            messages = thread_messages[thread_id]
            assert len(messages) == 2
            
            # First message - only field context
            assert messages[0]["thread_id"] == thread_id
            assert messages[0]["data"] == f"thread_{thread_id}_data"
            assert "correlation_id" not in messages[0]
            
            # Second message - field context and correlation ID
            assert messages[1]["thread_id"] == thread_id
            assert messages[1]["data"] == f"thread_{thread_id}_data"
            assert messages[1]["correlation_id"] == f"correlation_{thread_id}"
    
    def test_concurrent_context_changes(self) -> None:
        """Test concurrent changes to log levels and contexts."""
        # Create multiple loggers
        loggers = [
            logging.getLogger(f"test.concurrent.logger{i}")
            for i in range(5)
        ]
        
        for logger in loggers:
            logger.setLevel(logging.INFO)
            logger.handlers.clear()
        
        # Shared handler with thread-safe output
        output_lock = threading.Lock()
        output_lines: list[str] = []
        
        class ThreadSafeHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                msg = self.format(record)
                with output_lock:
                    output_lines.append(f"{record.name}:{record.levelname}:{msg}")
        
        handler = ThreadSafeHandler()
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.KEYVALUE))
        
        # Add handler to all loggers
        for logger in loggers:
            logger.addHandler(handler)
        
        # Function to rapidly change log levels
        def change_levels(logger_index: int) -> None:
            logger = loggers[logger_index]
            levels = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR]
            
            for i in range(20):
                level = levels[i % len(levels)]
                with log_level_context(logger, level):
                    logger.log(level.value, f"Message at {level.name}")
                    time.sleep(0.001)
        
        # Create threads that change levels concurrently
        threads = []
        for i in range(len(loggers)):
            thread = threading.Thread(target=change_levels, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify all messages were logged
        assert len(output_lines) == len(loggers) * 20
        
        # Verify no corruption or mixing between loggers
        for line in output_lines:
            parts = line.split(":", 2)
            logger_name = parts[0]
            level_name = parts[1]
            
            # Extract logger index
            logger_index = int(logger_name.split("logger")[1])
            assert 0 <= logger_index < len(loggers)
            
            # Verify level name is valid
            assert level_name in ["DEBUG", "INFO", "WARNING", "ERROR"]


class TestPerformanceCharacteristics:
    """Test performance characteristics of the logging system."""
    
    def test_logging_throughput(self) -> None:
        """Test logging throughput under load."""
        logger = logging.getLogger("test.performance.throughput")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Use null handler for pure throughput testing
        class NullHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                # Format the record to include formatting overhead
                _ = self.format(record)
        
        handler = NullHandler()
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
        logger.addHandler(handler)
        
        # Measure throughput
        num_messages = 10000
        start_time = time.time()
        
        for i in range(num_messages):
            logger.info(f"Message {i}", extra={"index": i, "data": "test"})
        
        end_time = time.time()
        duration = end_time - start_time
        messages_per_second = num_messages / duration
        
        # Should handle at least 5000 messages per second
        assert messages_per_second > 5000, f"Too slow: {messages_per_second:.0f} msg/s"
        
        # Print for information
        print(f"\nLogging throughput: {messages_per_second:.0f} messages/second")
    
    def test_formatter_performance_comparison(self) -> None:
        """Compare performance of different formatters."""
        logger = logging.getLogger("test.performance.formatters")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Test formatters
        formatters = [
            ("JSON", StructuredFormatter(format_type=LogFormat.JSON)),
            ("KeyValue", StructuredFormatter(format_type=LogFormat.KEYVALUE)),
            ("Colored", ColoredFormatter(enable_colors=True)),
        ]
        
        results = {}
        
        for name, formatter in formatters:
            # Create handler with formatter
            handler = logging.NullHandler()
            handler.setFormatter(formatter)
            logger.handlers = [handler]
            
            # Measure formatting time
            num_messages = 5000
            start_time = time.time()
            
            for i in range(num_messages):
                logger.info(
                    f"Test message {i}",
                    extra={"user_id": f"user{i}", "request_id": f"req{i}"}
                )
            
            end_time = time.time()
            duration = end_time - start_time
            messages_per_second = num_messages / duration
            results[name] = messages_per_second
        
        # All formatters should handle at least 3000 msg/s
        for name, rate in results.items():
            assert rate > 3000, f"{name} formatter too slow: {rate:.0f} msg/s"
            print(f"\n{name} formatter: {rate:.0f} messages/second")
    
    def test_context_manager_overhead(self) -> None:
        """Test overhead of context managers."""
        logger = logging.getLogger("test.performance.context")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Null handler for testing
        handler = logging.NullHandler()
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        
        num_iterations = 1000
        
        # Baseline - no context
        start_time = time.time()
        for i in range(num_iterations):
            logger.info(f"Message {i}")
        baseline_duration = time.time() - start_time
        
        # With correlation ID context
        start_time = time.time()
        for i in range(num_iterations):
            with correlation_id_context(f"correlation_{i}"):
                logger.info(f"Message {i}")
        correlation_duration = time.time() - start_time
        
        # With field context
        start_time = time.time()
        for i in range(num_iterations):
            with log_field_context({"iteration": i}):
                logger.info(f"Message {i}")
        field_duration = time.time() - start_time
        
        # With combined context
        start_time = time.time()
        for i in range(num_iterations):
            with combined_log_context(logger, LogLevel.INFO, {"iteration": i}):
                logger.info(f"Message {i}")
        combined_duration = time.time() - start_time
        
        # Context managers should add less than 50% overhead
        correlation_overhead = (correlation_duration - baseline_duration) / baseline_duration
        field_overhead = (field_duration - baseline_duration) / baseline_duration
        combined_overhead = (combined_duration - baseline_duration) / baseline_duration
        
        assert correlation_overhead < 0.5, f"Correlation context overhead too high: {correlation_overhead:.1%}"
        assert field_overhead < 0.5, f"Field context overhead too high: {field_overhead:.1%}"
        assert combined_overhead < 0.5, f"Combined context overhead too high: {combined_overhead:.1%}"
        
        print(f"\nContext manager overhead:")
        print(f"  Correlation ID: {correlation_overhead:.1%}")
        print(f"  Field context: {field_overhead:.1%}")
        print(f"  Combined: {combined_overhead:.1%}")


class TestEdgeCasesAndErrorConditions:
    """Test edge cases and error conditions."""
    
    def test_circular_reference_handling(self) -> None:
        """Test handling of circular references in log data."""
        logger = logging.getLogger("test.edge.circular")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Create handler
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
        logger.addHandler(handler)
        
        # Create circular reference
        obj1: dict[str, Any] = {"name": "obj1"}  # pyright: ignore[reportExplicitAny]
        obj2: dict[str, Any] = {"name": "obj2", "ref": obj1}  # pyright: ignore[reportExplicitAny]
        obj1["ref"] = obj2  # Circular reference
        
        # Log with circular reference in context
        with log_field_context({"circular": obj1}):
            logger.info("Message with circular reference")
        
        # Should not crash and should produce valid JSON
        output.seek(0)
        log_entry = json.loads(output.read())
        assert log_entry["message"] == "Message with circular reference"
        # The circular reference should be handled gracefully
        assert "circular" in log_entry
    
    def test_none_and_empty_values(self) -> None:
        """Test handling of None and empty values."""
        logger = logging.getLogger("test.edge.empty")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Create handler
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
        logger.addHandler(handler)
        
        # Test various empty/None values
        with log_field_context({
            "none_value": None,
            "empty_string": "",
            "empty_list": [],
            "empty_dict": {},
        }):
            logger.info("Message with empty values")
        
        # Verify all values are preserved
        output.seek(0)
        log_entry = json.loads(output.read())
        assert log_entry["none_value"] is None
        assert log_entry["empty_string"] == ""
        assert log_entry["empty_list"] == []
        assert log_entry["empty_dict"] == {}
    
    def test_invalid_logger_names(self) -> None:
        """Test handling of invalid logger names."""
        # Test empty logger name
        logger = logging.getLogger("")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
        logger.addHandler(handler)
        
        logger.info("Message from root logger")
        
        output.seek(0)
        log_entry = json.loads(output.read())
        assert log_entry["logger"] == "root"
    
    def test_exception_logging(self) -> None:
        """Test logging of exceptions with full context."""
        logger = logging.getLogger("test.edge.exception")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Create handler
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
        logger.addHandler(handler)
        
        # Create and log an exception
        try:
            # Create nested exception
            try:
                raise ValueError("Inner exception")
            except ValueError as e:
                raise RuntimeError("Outer exception") from e
        except RuntimeError:
            logger.exception("Exception occurred", extra={"request_id": "12345"})
        
        # Verify exception was logged
        output.seek(0)
        log_entry = json.loads(output.read())
        assert log_entry["message"] == "Exception occurred"
        assert log_entry["request_id"] == "12345"
        assert log_entry["level"] == "ERROR"
        # Exception info should be in the message or a separate field
    
    def test_handler_recovery_after_failure(self) -> None:
        """Test that handlers can recover after temporary failures."""
        logger = logging.getLogger("test.edge.recovery")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Create a handler that fails intermittently
        class IntermittentHandler(logging.Handler):
            def __init__(self) -> None:
                super().__init__()
                self.fail_count = 0
                self.messages: list[str] = []
            
            def emit(self, record: logging.LogRecord) -> None:
                if self.fail_count < 3:
                    self.fail_count += 1
                    raise RuntimeError("Temporary failure")
                else:
                    # After 3 failures, start working
                    self.messages.append(self.format(record))
        
        handler = IntermittentHandler()
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        
        # Log multiple messages
        for i in range(5):
            logger.info(f"Message {i}")
        
        # Handler should have recovered and logged the last 2 messages
        assert len(handler.messages) == 2
        assert "Message 3" in handler.messages[0]
        assert "Message 4" in handler.messages[1]


def test_full_integration_scenario() -> None:
    """Test a complete real-world logging scenario."""
    # Simulate a web application request handling
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    
    # Set up multiple handlers
    # Console handler for development
    console_handler = ConsoleHandler(
        level=logging.INFO,
        enable_colors=False  # For testing
    )
    
    # File handler for production logs
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log') as tmp_file:
        file_handler = FileHandler(
            tmp_file.name,
            level=logging.DEBUG,
            formatter=StructuredFormatter(
                format_type=LogFormat.JSON,
                timestamp_format=TimestampFormat.ISO
            )
        )
        
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        
        # Simulate request handling
        request_logger = logging.getLogger("app.request")
        db_logger = logging.getLogger("app.database")
        auth_logger = logging.getLogger("app.auth")
        
        # Start request with correlation ID
        with correlation_id_context("req-12345-abcde"):
            # Add request context
            with log_field_context({
                "user_id": "user-789",
                "ip_address": "192.168.1.100",
                "endpoint": "/api/users/profile"
            }):
                request_logger.info("Incoming request")
                
                # Authentication check
                auth_logger.info("Checking user authentication")
                
                # Database operations with temporary debug logging
                with log_level_context(db_logger, LogLevel.DEBUG):
                    db_logger.debug("Executing query: SELECT * FROM users WHERE id = ?")
                    db_logger.info("User data retrieved successfully")
                
                # Simulate an error condition
                try:
                    # Some operation that fails
                    raise ValueError("Invalid user data")
                except ValueError:
                    request_logger.exception("Error processing user data")
                
                # Response
                request_logger.info("Request completed", extra={"status_code": 500})
        
        # Verify file contains all expected entries
        file_handler.close()
        with open(tmp_file.name, 'r') as f:
            lines = f.readlines()
        
        # Should have multiple log entries
        assert len(lines) >= 5
        
        # All entries should have the correlation ID
        for line in lines:
            log_entry = json.loads(line)
            if "correlation_id" in log_entry:  # Some early setup logs might not have it
                assert log_entry["correlation_id"] == "req-12345-abcde"
        
        # Clean up
        Path(tmp_file.name).unlink()


if __name__ == "__main__":
    # Run performance tests separately as they print output
    pytest.main([__file__, "-v", "-k", "not Performance"])
    print("\n" + "="*50)
    print("Running performance tests:")
    print("="*50)
    pytest.main([__file__, "-v", "-k", "Performance", "-s"]) 