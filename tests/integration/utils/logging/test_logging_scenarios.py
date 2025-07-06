"""Real-world scenario tests for logging infrastructure.

Tests practical usage patterns and common scenarios:
- Web API request handling
- Background job processing
- Microservice communication
- Error tracking and debugging
- Audit logging
- Performance monitoring
"""

from __future__ import annotations

import io
import json
import logging
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    import tempfile

import pytest

from mover_status.utils.logging import (
    ConsoleHandler,
    FileHandler,
    LogFormat,
    LogLevel,
    StructuredFormatter,
    TimestampFormat,
    correlation_id_context,
    create_rotating_file_handler,
    log_field_context,
    set_logger_level,
)


class RequestData(TypedDict):
    """Type for request data."""
    method: str
    path: str
    headers: dict[str, str]
    body: dict[str, Any] | None  # pyright: ignore[reportExplicitAny]


@dataclass
class User:
    """User model for testing."""
    id: str
    username: str
    email: str
    roles: list[str]


class TestWebAPIScenarios:
    """Test logging in web API scenarios."""
    
    def __init__(self) -> None:
        """Initialize test instance variables."""
        self.app_logger: logging.Logger
        self.console_output: io.StringIO  
        self.temp_log: Any  # pyright: ignore[reportExplicitAny] # tempfile typing issue
        self.file_handler: FileHandler
    
    def setup_method(self) -> None:
        """Set up test environment."""
        # Configure application logger
        self.app_logger = logging.getLogger("app")
        self.app_logger.setLevel(logging.DEBUG)
        self.app_logger.handlers.clear()
        
        # Console handler for development
        self.console_output = io.StringIO()
        console_handler = ConsoleHandler(level=logging.INFO, enable_colors=False)
        console_handler.stream = self.console_output
        self.app_logger.addHandler(console_handler)
        
        # File handler for production logs
        self.temp_log = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log')
        file_handler = FileHandler(
            self.temp_log.name,
            level=logging.DEBUG,
            formatter=StructuredFormatter(
                format_type=LogFormat.JSON,
                timestamp_format=TimestampFormat.ISO
            )
        )
        self.app_logger.addHandler(file_handler)
        self.file_handler = file_handler
    
    def teardown_method(self) -> None:
        """Clean up test environment."""
        self.file_handler.close()
        Path(self.temp_log.name).unlink()
    
    def test_api_request_lifecycle(self) -> None:
        """Test complete API request lifecycle logging."""
        # Simulate incoming request
        request: RequestData = {
            "method": "POST",
            "path": "/api/users",
            "headers": {
                "Authorization": "Bearer token123",
                "Content-Type": "application/json"
            },
            "body": {
                "username": "newuser",
                "email": "user@example.com"
            }
        }
        
        # Request handler
        request_id = "req-" + str(int(time.time() * 1000))
        
        with correlation_id_context(request_id):
            # Log request received
            with log_field_context({
                "method": request.get("method"),
                "path": request.get("path"),
                "ip": "192.168.1.100",
                "user_agent": "TestClient/1.0"
            }):
                self.app_logger.info("Request received")
                
                # Authentication
                auth_logger = self.app_logger.getChild("auth")
                auth_logger.info("Authenticating request", extra={"has_token": True})
                
                # Validate input
                validation_logger = self.app_logger.getChild("validation")
                request_body = request.get("body", {})
                if request_body is not None:
                    validation_logger.debug("Validating request body", extra={"fields": list(request_body.keys())})
                
                # Database operation
                db_logger = self.app_logger.getChild("db")
                start_time = time.time()
                if request["body"] is not None:
                    db_logger.info("Creating user", extra={"username": request["body"]["username"]})
                
                # Simulate DB work
                time.sleep(0.01)
                db_duration = time.time() - start_time
                
                # Success
                user_id = "user-12345"
                db_logger.info("User created", extra={
                    "user_id": user_id,
                    "duration_ms": int(db_duration * 1000)
                })
                
                # Response
                self.app_logger.info("Request completed", extra={
                    "status_code": 201,
                    "response_time_ms": int((time.time() - start_time) * 1000)
                })
        
        # Verify structured logs
        self.file_handler.flush()
        with open(self.temp_log.name, 'r') as f:
            logs: list[dict[str, Any]] = [json.loads(line) for line in f.readlines()]  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        
        # All logs should have correlation ID
        assert all(log["correlation_id"] == request_id for log in logs)
        
        # Check specific log entries
        request_log: dict[str, Any] = next(log for log in logs if "Request received" in log["message"])  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        assert request_log["method"] == "POST"
        assert request_log["path"] == "/api/users"
        
        db_create_log: dict[str, Any] = next(log for log in logs if "User created" in log["message"])  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        assert db_create_log["user_id"] == user_id
        assert "duration_ms" in db_create_log
    
    def test_error_handling_and_recovery(self) -> None:
        """Test error handling and recovery logging."""
        request_id = "req-error-test"
        
        with correlation_id_context(request_id):
            with log_field_context({"endpoint": "/api/payment", "user_id": "user-789"}):
                self.app_logger.info("Processing payment request")
                
                try:
                    # Simulate payment processing
                    payment_logger = self.app_logger.getChild("payment")
                    payment_logger.info("Initiating payment", extra={"amount": 99.99, "currency": "USD"})
                    
                    # Simulate external API failure
                    raise ConnectionError("Payment gateway timeout")
                    
                except ConnectionError as e:
                    # Log error with full context
                    self.app_logger.exception("Payment processing failed", extra={
                        "error_type": type(e).__name__,
                        "retry_attempt": 1
                    })
                    
                    # Log recovery attempt
                    self.app_logger.info("Attempting fallback payment processor")
                    
                    # Simulate successful fallback
                    self.app_logger.info("Payment processed via fallback", extra={
                        "processor": "backup_gateway",
                        "transaction_id": "txn-backup-123"
                    })
        
        # Verify error handling
        _ = self.console_output.seek(0)
        console_logs = self.console_output.read()
        assert "Payment processing failed" in console_logs
        assert "Payment processed via fallback" in console_logs
    
    def test_audit_logging(self) -> None:
        """Test audit logging for security-sensitive operations."""
        # Create audit logger with specific configuration
        audit_logger = logging.getLogger("audit")
        audit_logger.setLevel(logging.INFO)
        audit_logger.handlers.clear()
        
        # Separate audit log file
        audit_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_audit.log')
        audit_handler = FileHandler(
            audit_file.name,
            formatter=StructuredFormatter(
                format_type=LogFormat.JSON,
                field_order=["timestamp", "event", "user_id", "ip_address", "result"]
            )
        )
        audit_logger.addHandler(audit_handler)
        
        # Simulate user actions
        user = User(id="user-456", username="admin", email="admin@example.com", roles=["admin"])
        
        with log_field_context({
            "user_id": user.id,
            "username": user.username,
            "ip_address": "10.0.0.50"
        }):
            # Login attempt
            audit_logger.info("User login", extra={
                "event": "LOGIN_ATTEMPT",
                "result": "SUCCESS",
                "auth_method": "password"
            })
            
            # Permission check
            audit_logger.info("Permission check", extra={
                "event": "PERMISSION_CHECK",
                "resource": "user_management",
                "action": "delete_user",
                "result": "ALLOWED"
            })
            
            # Sensitive operation
            with correlation_id_context("audit-op-123"):
                audit_logger.warning("Sensitive operation performed", extra={
                    "event": "USER_DELETED",
                    "target_user_id": "user-999",
                    "result": "SUCCESS"
                })
        
        # Verify audit trail
        audit_handler.close()
        with open(audit_file.name, 'r') as f:
            audit_logs: list[dict[str, Any]] = [json.loads(line) for line in f.readlines()]  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        
        # Check audit entries maintain user context
        assert all(log["user_id"] == user.id for log in audit_logs)
        assert all(log["ip_address"] == "10.0.0.50" for log in audit_logs)
        
        # Verify sensitive operation has correlation ID
        sensitive_op: dict[str, Any] = next(log for log in audit_logs if log["event"] == "USER_DELETED")  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        assert sensitive_op["correlation_id"] == "audit-op-123"
        
        # Clean up
        Path(audit_file.name).unlink()


class TestBackgroundJobScenarios:
    """Test logging in background job processing scenarios."""
    
    def test_batch_job_processing(self) -> None:
        """Test logging for batch job processing."""
        job_logger = logging.getLogger("jobs.batch")
        job_logger.setLevel(logging.INFO)
        job_logger.handlers.clear()
        
        # Rotating file handler for job logs
        job_log = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_jobs.log')
        job_handler = create_rotating_file_handler(
            job_log.name,
            max_bytes=1024 * 1024,  # 1MB
            backup_count=3,
            formatter=StructuredFormatter(format_type=LogFormat.JSON)
        )
        job_logger.addHandler(job_handler)
        
        # Simulate batch job
        job_id = f"job-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        with correlation_id_context(job_id):
            with log_field_context({
                "job_type": "user_export",
                "scheduled_time": datetime.now().isoformat()
            }):
                job_logger.info("Batch job started")
                
                # Process items
                total_items = 100
                batch_size = 10
                processed = 0
                errors = 0
                
                for batch_num in range(0, total_items, batch_size):
                    batch_start = time.time()
                    
                    # Simulate processing
                    for i in range(batch_size):
                        item_id = batch_num + i
                        try:
                            # Simulate occasional errors
                            if item_id % 23 == 0:
                                raise ValueError(f"Invalid data for item {item_id}")
                            
                            # Process item
                            time.sleep(0.001)
                            processed += 1
                            
                        except ValueError as e:
                            errors += 1
                            job_logger.warning(f"Failed to process item", extra={
                                "item_id": item_id,
                                "error": str(e),
                                "batch_num": batch_num // batch_size
                            })
                    
                    # Log batch progress
                    batch_duration = time.time() - batch_start
                    job_logger.info("Batch processed", extra={
                        "batch_num": batch_num // batch_size,
                        "items_in_batch": batch_size,
                        "duration_ms": int(batch_duration * 1000),
                        "total_processed": processed,
                        "total_errors": errors
                    })
                
                # Job summary
                job_logger.info("Batch job completed", extra={
                    "total_items": total_items,
                    "processed": processed,
                    "errors": errors,
                    "success_rate": f"{(processed/total_items)*100:.1f}%"
                })
        
        # Verify job execution
        job_handler.close()
        with open(job_log.name, 'r') as f:
            job_logs: list[dict[str, Any]] = [json.loads(line) for line in f.readlines()]  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        
        # All logs should have job correlation ID
        assert all(log["correlation_id"] == job_id for log in job_logs)
        
        # Check completion summary
        summary: dict[str, Any] = next(log for log in job_logs if "Batch job completed" in log["message"])  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        assert summary["processed"] + summary["errors"] == total_items
        
        # Clean up
        Path(job_log.name).unlink()
    
    def test_async_task_queue_processing(self) -> None:
        """Test logging for async task queue processing."""
        queue_logger = logging.getLogger("queue.worker")
        queue_logger.setLevel(logging.DEBUG)
        queue_logger.handlers.clear()
        
        # Setup handler
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
        queue_logger.addHandler(handler)
        
        # Simulate task queue worker
        worker_id = "worker-01"
        
        # Process multiple tasks
        tasks = [
            {"id": "task-001", "type": "send_email", "priority": "high"},
            {"id": "task-002", "type": "generate_report", "priority": "low"},
            {"id": "task-003", "type": "sync_data", "priority": "medium"},
        ]
        
        for task in tasks:
            with correlation_id_context(task["id"]):
                with log_field_context({
                    "worker_id": worker_id,
                    "task_type": task["type"],
                    "priority": task["priority"]
                }):
                    queue_logger.info("Task received from queue")
                    
                    # Simulate task processing
                    start_time = time.time()
                    
                    if task["type"] == "send_email":
                        queue_logger.debug("Sending email", extra={"recipients": 5})
                        time.sleep(0.01)
                    elif task["type"] == "generate_report":
                        queue_logger.debug("Generating report", extra={"format": "PDF"})
                        time.sleep(0.02)
                    else:
                        queue_logger.debug("Syncing data", extra={"records": 1000})
                        time.sleep(0.015)
                    
                    # Task complete
                    duration = time.time() - start_time
                    queue_logger.info("Task completed", extra={
                        "duration_ms": int(duration * 1000),
                        "status": "success"
                    })
        
        # Verify task processing
        _ = output.seek(0)
        logs: list[dict[str, Any]] = [json.loads(line) for line in output.readlines()]  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        
        # Each task should have 3 logs (received, debug, completed)
        task_logs: dict[str, list[dict[str, Any]]] = {}  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        for log in logs:
            task_id: str = log["correlation_id"]
            if task_id not in task_logs:
                task_logs[task_id] = []
            task_logs[task_id].append(log)
        
        assert len(task_logs) == 3
        for task_id, logs in task_logs.items():
            _ = task_id  # iteration variable needed for dict comprehension
            assert len(logs) == 3
            assert logs[0]["message"] == "Task received from queue"
            assert logs[2]["message"] == "Task completed"


class TestMicroserviceScenarios:
    """Test logging in microservice communication scenarios."""
    
    def test_service_to_service_communication(self) -> None:
        """Test logging across service boundaries."""
        # Service A logger
        service_a = logging.getLogger("service.a")
        service_a.setLevel(logging.INFO)
        service_a.handlers.clear()
        
        # Service B logger
        service_b = logging.getLogger("service.b")
        service_b.setLevel(logging.INFO)
        service_b.handlers.clear()
        
        # Shared output for testing
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
        service_a.addHandler(handler)
        service_b.addHandler(handler)
        
        # Simulate service communication
        request_id = "cross-service-123"
        
        # Service A initiates request
        with correlation_id_context(request_id):
            with log_field_context({"service": "service-a", "version": "1.0.0"}):
                service_a.info("Calling Service B", extra={
                    "target_service": "service-b",
                    "endpoint": "/api/data",
                    "timeout": 30
                })
                
                # Simulate network call
                time.sleep(0.01)
                
                # Service B receives request
                with log_field_context({"service": "service-b", "version": "2.1.0"}):
                    service_b.info("Request received from Service A", extra={
                        "source_service": "service-a",
                        "endpoint": "/api/data"
                    })
                    
                    # Process request
                    service_b.info("Processing data request", extra={
                        "data_type": "user_analytics",
                        "date_range": "last_30_days"
                    })
                    
                    # Return response
                    service_b.info("Response sent", extra={
                        "status_code": 200,
                        "response_size_bytes": 1024
                    })
                
                # Service A receives response
                service_a.info("Response received from Service B", extra={
                    "status_code": 200,
                    "latency_ms": 15
                })
        
        # Verify cross-service tracing
        _ = output.seek(0)
        logs: list[dict[str, Any]] = [json.loads(line) for line in output.readlines()]  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        
        # All logs should have same correlation ID
        assert all(log["correlation_id"] == request_id for log in logs)
        
        # Verify service identification
        service_a_logs: list[dict[str, Any]] = [log for log in logs if log.get("service") == "service-a"]  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        service_b_logs: list[dict[str, Any]] = [log for log in logs if log.get("service") == "service-b"]  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        
        assert len(service_a_logs) == 2  # Call and response
        assert len(service_b_logs) == 3  # Receive, process, send
    
    def test_distributed_transaction_logging(self) -> None:
        """Test logging for distributed transactions."""
        # Create service loggers
        api_logger = logging.getLogger("service.api")
        order_logger = logging.getLogger("service.order")
        payment_logger = logging.getLogger("service.payment")
        inventory_logger = logging.getLogger("service.inventory")
        
        # Configure all loggers
        for logger in [api_logger, order_logger, payment_logger, inventory_logger]:
            logger.setLevel(logging.INFO)
            logger.handlers.clear()
        
        # Shared output
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.JSON))
        
        for logger in [api_logger, order_logger, payment_logger, inventory_logger]:
            logger.addHandler(handler)
        
        # Simulate distributed transaction
        transaction_id = "txn-dist-456"
        
        with correlation_id_context(transaction_id):
            # API Gateway receives order
            with log_field_context({"service": "api-gateway"}):
                api_logger.info("Order request received", extra={
                    "customer_id": "cust-789",
                    "total_amount": 299.99
                })
            
            # Order Service
            with log_field_context({"service": "order-service"}):
                order_logger.info("Creating order", extra={"items": 3})
                order_id = "order-123"
                order_logger.info("Order created", extra={"order_id": order_id})
            
            # Payment Service
            with log_field_context({"service": "payment-service"}):
                payment_logger.info("Processing payment", extra={
                    "amount": 299.99,
                    "method": "credit_card"
                })
                
                # Simulate payment processing
                time.sleep(0.02)
                payment_logger.info("Payment authorized", extra={
                    "authorization_code": "AUTH-789",
                    "transaction_id": "pay-456"
                })
            
            # Inventory Service
            with log_field_context({"service": "inventory-service"}):
                inventory_logger.info("Reserving inventory", extra={"items": 3})
                
                # Simulate inventory check
                inventory_logger.info("Inventory reserved", extra={
                    "reservation_id": "res-789",
                    "warehouse": "warehouse-east"
                })
            
            # Transaction complete
            with log_field_context({"service": "api-gateway"}):
                api_logger.info("Order completed successfully", extra={
                    "order_id": order_id,
                    "total_duration_ms": 35
                })
        
        # Verify distributed transaction
        _ = output.seek(0)
        logs: list[dict[str, Any]] = [json.loads(line) for line in output.readlines()]  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        
        # All logs part of same transaction
        assert all(log["correlation_id"] == transaction_id for log in logs)
        
        # Verify service flow
        services_involved = {log.get("service") for log in logs if "service" in log}
        assert services_involved == {"api-gateway", "order-service", "payment-service", "inventory-service"}


class TestPerformanceMonitoring:
    """Test performance monitoring scenarios."""
    
    def test_request_performance_tracking(self) -> None:
        """Test tracking request performance metrics."""
        perf_logger = logging.getLogger("performance")
        perf_logger.setLevel(logging.INFO)
        perf_logger.handlers.clear()
        
        # Performance log handler
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter(
            format_type=LogFormat.JSON,
            field_order=["timestamp", "endpoint", "method", "duration_ms", "status_code"]
        ))
        perf_logger.addHandler(handler)
        
        # Simulate various endpoint calls
        endpoints = [
            ("/api/users", "GET", 0.015, 200),
            ("/api/users/123", "GET", 0.008, 200),
            ("/api/users", "POST", 0.045, 201),
            ("/api/products", "GET", 0.125, 200),  # Slow query
            ("/api/orders", "POST", 0.035, 500),   # Error
        ]
        
        for endpoint, method, duration, status in endpoints:
            with log_field_context({
                "endpoint": endpoint,
                "method": method,
                "status_code": status
            }):
                # Log performance metrics
                perf_logger.info("Request completed", extra={
                    "duration_ms": int(duration * 1000),
                    "db_queries": 3 if "products" in endpoint else 1,
                    "cache_hit": method == "GET" and status == 200,
                    "response_size_bytes": 2048 if method == "GET" else 256
                })
                
                # Log slow requests
                if duration > 0.1:
                    perf_logger.warning("Slow request detected", extra={
                        "duration_ms": int(duration * 1000),
                        "threshold_ms": 100
                    })
                
                # Log errors
                if status >= 500:
                    perf_logger.error("Request failed", extra={
                        "error_type": "InternalServerError"
                    })
        
        # Analyze performance data
        _ = output.seek(0)
        logs: list[dict[str, Any]] = [json.loads(line) for line in output.readlines()]  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        
        # Calculate metrics
        request_logs: list[dict[str, Any]] = [log for log in logs if log["message"] == "Request completed"]  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        _ = sum(log["duration_ms"] for log in request_logs) / len(request_logs)  # avg_duration not used
        
        # Verify performance tracking
        assert len(request_logs) == 5
        assert any(log["message"] == "Slow request detected" for log in logs)
        assert any(log["level"] == "ERROR" for log in logs)
        
        # Check cache hit tracking
        cached_requests: list[dict[str, Any]] = [log for log in request_logs if log.get("cache_hit", False)]  # pyright: ignore[reportExplicitAny] # log entries contain mixed types
        assert len(cached_requests) == 2  # Two successful GETs


class TestDebuggingScenarios:
    """Test debugging and troubleshooting scenarios."""
    
    def test_debug_mode_activation(self) -> None:
        """Test dynamic debug mode activation."""
        app_logger = logging.getLogger("app.debug")
        app_logger.setLevel(logging.INFO)
        app_logger.handlers.clear()
        
        # Output handler
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter(format_type=LogFormat.KEYVALUE))
        app_logger.addHandler(handler)
        
        # Normal operation
        app_logger.info("Application started")
        app_logger.debug("Debug: This should not appear")
        
        # Simulate issue detected
        app_logger.warning("High memory usage detected")
        
        # Dynamically enable debug mode
        set_logger_level("app.debug", LogLevel.DEBUG)
        
        # Now debug logs appear
        app_logger.debug("Debug: Memory stats", extra={
            "heap_size_mb": 512,
            "used_mb": 450,
            "gc_runs": 15
        })
        
        app_logger.debug("Debug: Active connections", extra={
            "database": 10,
            "cache": 5,
            "api_clients": 25
        })
        
        # Fix applied
        app_logger.info("Memory cleanup completed")
        
        # Disable debug mode
        set_logger_level("app.debug", LogLevel.INFO)
        
        app_logger.debug("Debug: This should not appear either")
        app_logger.info("Normal operation resumed")
        
        # Verify debug activation
        _ = output.seek(0)
        lines = output.readlines()
        
        # Count debug messages
        debug_messages = [line for line in lines if "level=DEBUG" in line]
        assert len(debug_messages) == 2  # Only during debug mode
        
        # Verify debug info was captured
        assert any("Memory stats" in line for line in lines)
        assert any("Active connections" in line for line in lines)


if __name__ == "__main__":
    _ = pytest.main([__file__, "-v", "-s"]) 