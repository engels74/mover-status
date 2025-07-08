"""Comprehensive integration test fixtures for mover-status system."""

from __future__ import annotations

import asyncio
import tempfile
import shutil
import os
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from collections.abc import Generator, AsyncGenerator, Mapping
from dataclasses import dataclass, field
from contextlib import asynccontextmanager, contextmanager
import pytest
import pytest_asyncio

from mover_status.notifications.base.registry import get_global_registry, ProviderRegistry
from mover_status.notifications.manager.dispatcher import AsyncDispatcher
from mover_status.core.process.models import ProcessInfo
from mover_status.core.progress.calculator import ProgressCalculator
from mover_status.notifications.models.message import Message
from tests.fixtures.notification_mocks import EnhancedMockProvider, NotificationTestUtils
from tests.fixtures.progress_data_generators import ProgressDataGenerator, ProgressDataPoint

if TYPE_CHECKING:
    pass


@dataclass
class MockProcessEnvironment:
    """Mock process environment for testing."""
    
    process_name: str = "mover"
    pid: int = 12345
    command_line: list[str] = field(default_factory=lambda: ["/usr/local/sbin/mover"])
    start_time: float = field(default_factory=time.time)
    cpu_percent: float = 15.5
    memory_percent: float = 8.2
    status: str = "running"
    
    def to_process_info(self) -> ProcessInfo:
        """Convert to ProcessInfo object."""
        from datetime import datetime
        from mover_status.core.process.models import ProcessStatus
        
        return ProcessInfo(
            pid=self.pid,
            name=self.process_name,
            command=" ".join(self.command_line),
            start_time=datetime.fromtimestamp(self.start_time),
            cpu_percent=self.cpu_percent,
            memory_mb=self.memory_percent,
            status=ProcessStatus.from_string(self.status)
        )


@dataclass 
class MockFilesystemState:
    """Mock filesystem state for testing."""
    
    total_size: int = 1024 * 1024 * 1024  # 1GB
    transferred_size: int = 0
    file_count: int = 1000
    transferred_files: int = 0
    current_file: str = "/data/file1.bin"
    transfer_rate: float = 10.5 * 1024 * 1024  # 10.5 MB/s
    
    def update_progress(self, percentage: float) -> None:
        """Update progress based on percentage."""
        self.transferred_size = int(self.total_size * percentage / 100.0)
        self.transferred_files = int(self.file_count * percentage / 100.0)


@dataclass
class IntegrationTestDatabase:
    """In-memory SQLite database for integration testing."""
    
    connection: sqlite3.Connection
    cursor: sqlite3.Cursor
    
    @classmethod
    def create(cls) -> IntegrationTestDatabase:
        """Create new in-memory test database."""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        
        # Create test tables
        _ = cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                bytes_transferred INTEGER NOT NULL,
                total_size INTEGER NOT NULL,
                percentage REAL NOT NULL,
                transfer_rate REAL NOT NULL
            )
        """)
        
        _ = cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                provider_name TEXT NOT NULL,
                message_title TEXT NOT NULL,
                message_content TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt_count INTEGER DEFAULT 1
            )
        """)
        
        _ = cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                component TEXT NOT NULL,
                resolved BOOLEAN DEFAULT FALSE
            )
        """)
        
        conn.commit()
        return cls(connection=conn, cursor=cursor)
    
    def insert_progress(self, data_point: ProgressDataPoint) -> None:
        """Insert progress data point."""
        percentage = (data_point.bytes_transferred / data_point.total_size) * 100.0
        transfer_rate = data_point.bytes_transferred / max(data_point.timestamp, 0.001)
        
        _ = self.cursor.execute("""
            INSERT INTO test_progress 
            (timestamp, bytes_transferred, total_size, percentage, transfer_rate)
            VALUES (?, ?, ?, ?, ?)
        """, (data_point.timestamp, data_point.bytes_transferred, 
              data_point.total_size, percentage, transfer_rate))
        self.connection.commit()
    
    def insert_notification(self, provider: str, message: Message, status: str) -> None:
        """Insert notification record."""
        _ = self.cursor.execute("""
            INSERT INTO test_notifications 
            (timestamp, provider_name, message_title, message_content, status)
            VALUES (?, ?, ?, ?, ?)
        """, (time.time(), provider, message.title, message.content, status))
        self.connection.commit()
    
    def insert_error(self, error_type: str, message: str, component: str) -> None:
        """Insert error record."""
        _ = self.cursor.execute("""
            INSERT INTO test_errors (timestamp, error_type, error_message, component)
            VALUES (?, ?, ?, ?)
        """, (time.time(), error_type, message, component))
        self.connection.commit()
    
    def get_progress_history(self) -> list[dict[str, str | int | float]]:
        """Get all progress history."""
        _ = self.cursor.execute("SELECT * FROM test_progress ORDER BY timestamp")
        columns = [desc[0] for desc in self.cursor.description]
        rows = self.cursor.fetchall()
        return [dict(zip(columns, row, strict=False)) for row in rows]  # pyright: ignore[reportAny]
    
    def get_notification_history(self) -> list[dict[str, str | int | float]]:
        """Get all notification history."""
        _ = self.cursor.execute("SELECT * FROM test_notifications ORDER BY timestamp")
        columns = [desc[0] for desc in self.cursor.description]
        rows = self.cursor.fetchall()
        return [dict(zip(columns, row, strict=False)) for row in rows]  # pyright: ignore[reportAny]
    
    def close(self) -> None:
        """Close database connection."""
        self.cursor.close()
        self.connection.close()


@runtime_checkable
class MockExternalService(Protocol):
    """Protocol for mock external services."""
    
    async def start(self) -> None:
        """Start the mock service."""
        ...
    
    async def stop(self) -> None:
        """Stop the mock service."""
        ...
    
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        ...


@dataclass
class MockWebhookService:
    """Mock webhook service for testing."""
    
    port: int = 8080
    responses: dict[str, dict[str, str | int | float | bool]] = field(default_factory=dict)
    request_history: list[dict[str, str | int | float]] = field(default_factory=list)
    is_running: bool = False
    failure_rate: float = 0.0
    
    async def start(self) -> None:
        """Start mock webhook service."""
        self.is_running = True
        self.request_history.clear()
        # In real implementation, would start HTTP server
        
    async def stop(self) -> None:
        """Stop mock webhook service."""
        self.is_running = False
        
    def is_healthy(self) -> bool:
        """Check service health."""
        return self.is_running
    
    def add_response(self, endpoint: str, response: dict[str, str | int | float | bool]) -> None:
        """Add mock response for endpoint."""
        self.responses[endpoint] = response
    
    def get_request_history(self) -> list[dict[str, str | int | float]]:
        """Get history of requests."""
        return list(self.request_history)
    
    async def handle_request(self, endpoint: str, _data: dict[str, str | int | float]) -> dict[str, str | int | float | bool]:
        """Handle mock request."""
        # Record request
        self.request_history.append({
            "timestamp": time.time(),
            "endpoint": endpoint,
        })
        
        # Simulate failures if configured
        if self.failure_rate > 0 and time.time() % 1.0 < self.failure_rate:
            raise Exception(f"Mock service failure for {endpoint}")
        
        # Return configured response or default
        return self.responses.get(endpoint, {"status": "ok", "received": True})


@dataclass
class MockProcessDetector:
    """Mock process detector for testing."""
    
    processes: list[MockProcessEnvironment] = field(default_factory=list)
    detection_delay: float = 0.1
    failure_rate: float = 0.0
    
    async def detect_processes(self, process_names: list[str]) -> list[ProcessInfo]:
        """Mock process detection."""
        await asyncio.sleep(self.detection_delay)
        
        # Simulate failure
        if self.failure_rate > 0 and time.time() % 1.0 < self.failure_rate:
            raise Exception("Process detection failed")
        
        # Return matching processes
        results: list[ProcessInfo] = []
        for process in self.processes:
            if process.process_name in process_names:
                results.append(process.to_process_info())
        
        return results
    
    def add_process(self, process: MockProcessEnvironment) -> None:
        """Add mock process."""
        self.processes.append(process)
    
    def remove_process(self, pid: int) -> None:
        """Remove process by PID."""
        self.processes = [p for p in self.processes if p.pid != pid]
    
    def update_process_status(self, pid: int, status: str) -> None:
        """Update process status."""
        for process in self.processes:
            if process.pid == pid:
                process.status = status
                break


class IntegrationTestEnvironment:
    """Complete integration test environment."""
    
    def __init__(self) -> None:
        self.temp_dir: Path | None = None
        self.config_file: Path | None = None
        self.database: IntegrationTestDatabase | None = None
        self.webhook_service: MockWebhookService | None = None
        self.process_detector: MockProcessDetector | None = None
        self.mock_providers: dict[str, EnhancedMockProvider] = {}
        self.dispatcher: AsyncDispatcher | None = None
        self.registry: ProviderRegistry | None = None
        self.filesystem_state: MockFilesystemState | None = None
        self.progress_calculator: ProgressCalculator | None = None
        
    async def setup(self) -> None:
        """Set up complete test environment."""
        # Create temporary directory
        self.temp_dir = Path(tempfile.mkdtemp(prefix="mover_status_test_"))
        
        # Initialize database
        self.database = IntegrationTestDatabase.create()
        
        # Set up mock services
        self.webhook_service = MockWebhookService()
        await self.webhook_service.start()
        
        self.process_detector = MockProcessDetector()
        
        # Set up filesystem state
        self.filesystem_state = MockFilesystemState()
        
        # Create configuration
        await self._create_test_config()
        
        # Set up notification system
        await self._setup_notification_system()
        
        # Set up progress calculator
        self.progress_calculator = ProgressCalculator()
        
    async def teardown(self) -> None:
        """Clean up test environment."""
        # Stop services
        if self.dispatcher:
            await self.dispatcher.stop()
            
        if self.webhook_service:
            await self.webhook_service.stop()
            
        # Clean up database
        if self.database:
            self.database.close()
            
        # Clean up temporary directory
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            
        # Reset global state
        if self.registry:
            self.registry.reset()
    
    async def _create_test_config(self) -> None:
        """Create test configuration file."""
        if not self.temp_dir:
            raise RuntimeError("Temp dir not initialized")
            
        config_data = {
            "monitoring": {
                "interval": 5,
                "detection_timeout": 10,
                "dry_run": False
            },
            "process": {
                "name": "mover",
                "paths": ["/usr/local/sbin/mover"]
            },
            "progress": {
                "min_change_threshold": 1.0,
                "estimation_window": 5,
                "exclusions": ["/.Trash-*"]
            },
            "notifications": {
                "enabled_providers": ["test_reliable", "test_unreliable"],
                "events": ["started", "progress", "completed"],
                "rate_limits": {"progress": 60, "status": 30}
            },
            "providers": {
                "test_reliable": {
                    "enabled": True,
                    "api_key": "test_reliable_key",
                    "endpoint": f"http://localhost:{self.webhook_service.port if self.webhook_service else 8080}/reliable"
                },
                "test_unreliable": {
                    "enabled": True,
                    "api_key": "test_unreliable_key", 
                    "endpoint": f"http://localhost:{self.webhook_service.port if self.webhook_service else 8080}/unreliable"
                }
            },
            "logging": {
                "level": "DEBUG",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        }
        
        self.config_file = self.temp_dir / "test_config.yaml"
        with open(self.config_file, 'w', encoding='utf-8') as f:
            import yaml
            yaml.safe_dump(config_data, f)
    
    async def _setup_notification_system(self) -> None:
        """Set up notification system."""
        # Create mock providers
        self.mock_providers = {
            "test_reliable": EnhancedMockProvider(
                {"enabled": True, "api_key": "test_reliable_key", "endpoint": "http://test"},
                "test_reliable",
                base_delay=0.01,
                failure_rate=0.001
            ),
            "test_unreliable": EnhancedMockProvider(
                {"enabled": True, "api_key": "test_unreliable_key", "endpoint": "http://test"},
                "test_unreliable", 
                base_delay=0.05,
                failure_rate=0.15
            )
        }
        
        # Set up dispatcher
        self.dispatcher = AsyncDispatcher(max_workers=4, queue_size=100)
        
        for provider_name, provider in self.mock_providers.items():
            self.dispatcher.register_provider(provider_name, provider)
        
        await self.dispatcher.start()
        
        # Set up registry
        self.registry = get_global_registry()
        self.registry.reset()
    
    def create_progress_scenario(self, scenario_name: str) -> list[ProgressDataPoint]:
        """Create progress data for testing scenarios."""
        scenarios = {
            "linear": lambda: ProgressDataGenerator.linear_transfer(
                100 * 1024 * 1024, 60.0, 60
            ),
            "stalled": lambda: ProgressDataGenerator.stall_and_resume(
                200 * 1024 * 1024, 120.0, 60, [(0.3, 0.4), (0.7, 0.75)]
            ),
            "noisy": lambda: ProgressDataGenerator.noisy_transfer(
                50 * 1024 * 1024, 30.0, 30, 0.3, 42
            ),
            "bursty": lambda: ProgressDataGenerator.bursty_transfer(
                500 * 1024 * 1024, 300.0, 100, 0.8, 4.0
            )
        }
        
        return scenarios.get(scenario_name, scenarios["linear"])()
    
    def add_mock_process(self, name: str = "mover", pid: int = 12345) -> MockProcessEnvironment:
        """Add mock process to detector."""
        process = MockProcessEnvironment(process_name=name, pid=pid)
        if self.process_detector:
            self.process_detector.add_process(process)
        return process
    
    async def simulate_notification_flow(self, message: Message) -> dict[str, str | int | float | object]:
        """Simulate complete notification flow."""
        if not self.dispatcher:
            raise RuntimeError("Dispatcher not initialized")
            
        start_time = time.time()
        
        # Dispatch message
        result = await self.dispatcher.dispatch_message(
            message, 
            list(self.mock_providers.keys())
        )
        
        processing_time = time.time() - start_time
        
        # Record in database
        if self.database:
            for provider_name in self.mock_providers:
                self.database.insert_notification(
                    provider_name, 
                    message, 
                    result.status.value
                )
        
        return {
            "result": result,
            "processing_time": processing_time,
            "provider_stats": {
                name: {
                    "send_count": provider.stats.send_count,
                    "success_count": provider.stats.success_count,
                    "success_rate": provider.stats.success_rate
                }
                for name, provider in self.mock_providers.items()
            }
        }
    
    async def simulate_progress_monitoring(self, data_points: list[ProgressDataPoint]) -> Mapping[str, object]:
        """Simulate progress monitoring scenario."""
        if not self.database or not self.progress_calculator:
            raise RuntimeError("Environment not properly initialized")
            
        results = {
            "total_points": len(data_points),
            "duration": data_points[-1].timestamp if data_points else 0.0,
            "final_percentage": 0.0,
            "average_rate": 0.0,
            "notifications_sent": 0
        }
        
        last_percentage = 0.0
        notification_threshold = 5.0  # Send notification every 5% progress
        
        for point in data_points:
            # Record progress
            self.database.insert_progress(point)
            
            # Calculate percentage
            percentage = (point.bytes_transferred / point.total_size) * 100.0
            
            # Update filesystem state
            if self.filesystem_state:
                self.filesystem_state.transferred_size = point.bytes_transferred
                self.filesystem_state.total_size = point.total_size
            
            # Check if notification should be sent
            if percentage - last_percentage >= notification_threshold:
                message = Message(
                    title="Progress Update",
                    content=f"Transfer progress: {percentage:.1f}%",
                    priority="normal"
                )
                
                _ = await self.simulate_notification_flow(message)
                results["notifications_sent"] += 1
                last_percentage = percentage
        
        if data_points:
            final_point = data_points[-1]
            results["final_percentage"] = (final_point.bytes_transferred / final_point.total_size) * 100.0
            results["average_rate"] = final_point.bytes_transferred / final_point.timestamp
        
        return results
    
    def get_test_summary(self) -> dict[str, object]:
        """Get comprehensive test summary."""
        if not self.database:
            return {}
            
        return {
            "progress_history": self.database.get_progress_history(),
            "notification_history": self.database.get_notification_history(),
            "provider_stats": {
                name: {
                    "send_count": provider.stats.send_count,
                    "success_count": provider.stats.success_count,
                    "failure_count": provider.stats.failure_count,
                    "success_rate": provider.stats.success_rate,
                    "average_processing_time": provider.stats.average_processing_time
                }
                for name, provider in self.mock_providers.items()
            },
            "webhook_requests": self.webhook_service.get_request_history() if self.webhook_service else [],
            "filesystem_state": {
                "total_size": self.filesystem_state.total_size if self.filesystem_state else 0,
                "transferred_size": self.filesystem_state.transferred_size if self.filesystem_state else 0,
                "transfer_rate": self.filesystem_state.transfer_rate if self.filesystem_state else 0.0
            } if self.filesystem_state else {}
        }


# Pytest fixtures for integration testing

@pytest_asyncio.fixture
async def integration_env() -> AsyncGenerator[IntegrationTestEnvironment, None]:
    """Provide complete integration test environment."""
    env = IntegrationTestEnvironment()
    await env.setup()
    try:
        yield env
    finally:
        await env.teardown()


@pytest.fixture
def mock_process_env() -> Generator[MockProcessEnvironment, None, None]:
    """Provide mock process environment."""
    yield MockProcessEnvironment()


@pytest.fixture
def mock_filesystem() -> Generator[MockFilesystemState, None, None]:
    """Provide mock filesystem state."""
    yield MockFilesystemState()


@pytest.fixture
def test_database() -> Generator[IntegrationTestDatabase, None, None]:
    """Provide test database."""
    db = IntegrationTestDatabase.create()
    try:
        yield db
    finally:
        db.close()


@pytest_asyncio.fixture
async def mock_webhook_service() -> AsyncGenerator[MockWebhookService, None]:
    """Provide mock webhook service."""
    service = MockWebhookService()
    await service.start()
    try:
        yield service
    finally:
        await service.stop()


@pytest.fixture
def progress_scenarios() -> dict[str, list[ProgressDataPoint]]:
    """Provide various progress scenarios for testing."""
    return {
        "linear_fast": ProgressDataGenerator.linear_transfer(10 * 1024 * 1024, 10.0, 10),
        "linear_slow": ProgressDataGenerator.linear_transfer(100 * 1024 * 1024, 120.0, 60), 
        "stalled": ProgressDataGenerator.stall_and_resume(
            50 * 1024 * 1024, 60.0, 30, [(0.4, 0.5), (0.8, 0.85)]
        ),
        "noisy": ProgressDataGenerator.noisy_transfer(25 * 1024 * 1024, 30.0, 30, 0.2, 123),
        "bursty": ProgressDataGenerator.bursty_transfer(200 * 1024 * 1024, 180.0, 60, 0.7, 3.0)
    }


@contextmanager 
def isolated_test_environment(temp_dir: Path | None = None) -> Generator[Path, None, None]:
    """Create isolated test environment with cleanup."""
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="mover_status_isolated_"))
    
    # Set up environment variables
    old_env = os.environ.copy()
    
    try:
        os.environ.update({
            "MOVER_STATUS_CONFIG_DIR": str(temp_dir),
            "MOVER_STATUS_DATA_DIR": str(temp_dir / "data"),
            "MOVER_STATUS_LOG_DIR": str(temp_dir / "logs")
        })
        
        # Create directories
        (temp_dir / "data").mkdir(exist_ok=True)
        (temp_dir / "logs").mkdir(exist_ok=True)
        
        yield temp_dir
        
    finally:
        # Restore environment
        os.environ.clear()
        os.environ.update(old_env)
        
        # Clean up
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@asynccontextmanager
async def mock_external_services() -> AsyncGenerator[dict[str, MockExternalService], None]:
    """Provide collection of mock external services."""
    services: dict[str, MockExternalService] = {
        "webhook": MockWebhookService(),
    }
    
    # Start all services
    for service in services.values():
        await service.start()
    
    try:
        yield services
    finally:
        # Stop all services
        for service in services.values():
            await service.stop()


class IntegrationTestRunner:
    """Helper for running complex integration test scenarios."""
    
    def __init__(self, environment: IntegrationTestEnvironment) -> None:
        self.env: IntegrationTestEnvironment = environment
        
    async def run_full_monitoring_cycle(self, _duration: float = 60.0) -> dict[str, object]:
        """Run complete monitoring cycle test."""
        # Add mock process
        process = self.env.add_mock_process("mover", 12345)
        
        # Create progress scenario
        progress_data = self.env.create_progress_scenario("linear")
        
        # Simulate process startup notification
        start_message = Message(
            title="Mover Started",
            content=f"Mover process started (PID: {process.pid})",
            priority="normal"
        )
        start_result = await self.env.simulate_notification_flow(start_message)
        
        # Simulate progress monitoring
        progress_result = await self.env.simulate_progress_monitoring(progress_data)
        
        # Simulate completion notification
        completion_message = Message(
            title="Mover Completed", 
            content=f"Transfer completed successfully ({progress_result['final_percentage']:.1f}%)",
            priority="normal"
        )
        completion_result = await self.env.simulate_notification_flow(completion_message)
        
        return {
            "start_notification": start_result,
            "progress_monitoring": progress_result,
            "completion_notification": completion_result,
            "summary": self.env.get_test_summary()
        }
    
    async def run_failure_recovery_scenario(self) -> dict[str, object]:
        """Run failure and recovery scenario test."""
        # Configure unreliable service
        if self.env.webhook_service:
            self.env.webhook_service.failure_rate = 0.5  # 50% failure rate
        
        # Send multiple messages to test recovery
        messages = NotificationTestUtils.create_test_messages(10, "FailureTest")
        results: list[dict[str, str | int | float | object]] = []
        
        for message in messages:
            result = await self.env.simulate_notification_flow(message)
            results.append(result)
            
            # Small delay between messages
            await asyncio.sleep(0.1)
        
        return {
            "message_count": len(messages),
            "results": results,
            "summary": self.env.get_test_summary()
        }