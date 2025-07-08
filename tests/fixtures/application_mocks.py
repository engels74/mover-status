"""Application-level mocks for integration testing."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, NamedTuple
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock
from dataclasses import dataclass, field
from pathlib import Path
import tempfile
import shutil

from mover_status.notifications.manager.dispatcher import AsyncDispatcher

if TYPE_CHECKING:
    from mover_status.core.process.models import ProcessInfo


class MockFileSystemEntry(NamedTuple):
    """Mock filesystem entry for testing."""
    path: str
    size: int
    is_directory: bool
    modified_time: float


@dataclass
class MockApplicationState:
    """Mock application state for integration testing."""
    
    is_running: bool = False
    current_process: ProcessInfo | None = None
    last_scan_time: float = 0.0
    total_bytes_scanned: int = 0
    files_scanned: int = 0
    errors_encountered: list[str] = field(default_factory=list)
    notifications_sent: int = 0
    error_count: int = 0
    
    def reset(self) -> None:
        """Reset state to defaults."""
        self.is_running = False
        self.current_process = None
        self.last_scan_time = 0.0
        self.total_bytes_scanned = 0
        self.files_scanned = 0
        self.errors_encountered.clear()
        self.notifications_sent = 0
        self.error_count = 0


@dataclass
class MockFilesystemLayout:
    """Mock filesystem layout for testing."""
    
    root_path: Path
    entries: list[MockFileSystemEntry] = field(default_factory=list)
    total_size: int = 0
    
    @classmethod
    def create_test_layout(cls, root_path: Path, file_count: int = 100) -> MockFilesystemLayout:
        """Create test filesystem layout."""
        layout = cls(root_path=root_path)
        
        # Create directory structure
        dirs = [
            "data/movies", "data/tv", "data/music", "data/photos",
            "cache", "tmp", "logs"
        ]
        
        for dir_path in dirs:
            full_path = root_path / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            
            layout.entries.append(MockFileSystemEntry(
                path=str(full_path),
                size=0,
                is_directory=True,
                modified_time=time.time()
            ))
        
        # Create files
        for i in range(file_count):
            dir_choice = dirs[i % len(dirs)]
            file_path = root_path / dir_choice / f"file_{i:04d}.bin"
            file_size = 1024 * 1024 * (i % 100 + 1)  # 1-100 MB files
            
            # Create actual file for more realistic testing
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(b'0' * min(file_size, 1024))  # Write small amount to create file
            
            layout.entries.append(MockFileSystemEntry(
                path=str(file_path),
                size=file_size,
                is_directory=False,
                modified_time=time.time() - (i * 3600)  # Stagger modification times
            ))
            
            layout.total_size += file_size
        
        return layout
    
    def get_files_by_pattern(self, pattern: str) -> list[MockFileSystemEntry]:
        """Get files matching pattern."""
        return [
            entry for entry in self.entries 
            if not entry.is_directory and pattern in entry.path
        ]
    
    def get_total_file_size(self) -> int:
        """Get total size of all files."""
        return sum(entry.size for entry in self.entries if not entry.is_directory)


class MockProcessDetector:
    """Mock process detector for integration testing."""
    
    def __init__(self) -> None:
        self.processes: dict[int, ProcessInfo] = {}
        self.detection_delay: float = 0.1
        self.failure_rate: float = 0.0
        self.detection_calls: int = 0
        
    async def detect_processes(self, process_names: list[str]) -> list[ProcessInfo]:
        """Mock process detection."""
        self.detection_calls += 1
        await asyncio.sleep(self.detection_delay)
        
        # Simulate occasional failures
        if self.failure_rate > 0 and (time.time() % 1.0) < self.failure_rate:
            raise RuntimeError("Process detection failed")
        
        # Return processes matching the names
        results = []
        for process in self.processes.values():
            if process.name in process_names:
                results.append(process)
        
        return results
    
    def add_process(self, process: ProcessInfo) -> None:
        """Add process to be detected."""
        self.processes[process.pid] = process
    
    def remove_process(self, pid: int) -> None:
        """Remove process."""
        self.processes.pop(pid, None)
    
    def clear_processes(self) -> None:
        """Clear all processes."""
        self.processes.clear()


class MockFilesystemScanner:
    """Mock filesystem scanner for integration testing."""
    
    def __init__(self, layout: MockFilesystemLayout) -> None:
        self.layout = layout
        self.scan_delay: float = 0.01  # Delay per file to simulate scanning
        self.failure_rate: float = 0.0
        self.scan_calls: int = 0
        self.bytes_scanned: int = 0
        self.files_scanned: int = 0
        
    async def scan_directory(self, path: Path, recursive: bool = True) -> AsyncGenerator[MockFileSystemEntry, None]:
        """Mock directory scanning."""
        self.scan_calls += 1
        
        # Filter entries under the given path
        path_str = str(path)
        relevant_entries = [
            entry for entry in self.layout.entries
            if entry.path.startswith(path_str)
        ]
        
        for entry in relevant_entries:
            # Simulate scan delay
            await asyncio.sleep(self.scan_delay)
            
            # Simulate occasional failures
            if self.failure_rate > 0 and (time.time() % 1.0) < self.failure_rate:
                raise RuntimeError(f"Failed to scan {entry.path}")
            
            self.bytes_scanned += entry.size
            if not entry.is_directory:
                self.files_scanned += 1
            
            yield entry
    
    def get_scan_statistics(self) -> dict[str, int]:
        """Get scanning statistics."""
        return {
            "scan_calls": self.scan_calls,
            "bytes_scanned": self.bytes_scanned,
            "files_scanned": self.files_scanned,
            "total_files": len([e for e in self.layout.entries if not e.is_directory]),
            "total_directories": len([e for e in self.layout.entries if e.is_directory])
        }


class MockMonitorOrchestrator:
    """Mock monitor orchestrator for integration testing."""
    
    def __init__(self) -> None:
        self.state: MockApplicationState = MockApplicationState()
        self.process_detector: MockProcessDetector = MockProcessDetector()
        self.filesystem_scanner: MockFilesystemScanner | None = None
        self.monitoring_interval: float = 5.0
        self.is_monitoring: bool = False
        self._monitoring_task: asyncio.Task[None] | None = None
        
        # Hooks for testing
        self.on_process_detected: AsyncMock = AsyncMock()
        self.on_process_completed: AsyncMock = AsyncMock()
        self.on_progress_update: AsyncMock = AsyncMock()
        self.on_error: AsyncMock = AsyncMock()
    
    def set_filesystem_layout(self, layout: MockFilesystemLayout) -> None:
        """Set filesystem layout for scanning."""
        self.filesystem_scanner = MockFilesystemScanner(layout)
    
    async def start_monitoring(self) -> None:
        """Start monitoring loop."""
        if self.is_monitoring:
            return
            
        self.is_monitoring = True
        self.state.is_running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
    
    async def stop_monitoring(self) -> None:
        """Stop monitoring loop."""
        self.is_monitoring = False
        self.state.is_running = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                # Detect processes
                processes = await self.process_detector.detect_processes(["mover"])
                
                if processes and not self.state.current_process:
                    # New process detected
                    self.state.current_process = processes[0]
                    await self.on_process_detected(processes[0])
                    
                elif not processes and self.state.current_process:
                    # Process completed
                    completed_process = self.state.current_process
                    self.state.current_process = None
                    await self.on_process_completed(completed_process)
                
                # Scan filesystem if we have a current process
                if self.state.current_process and self.filesystem_scanner:
                    await self._update_progress()
                
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                error_msg = f"Monitoring error: {e}"
                self.state.errors_encountered.append(error_msg)
                await self.on_error(error_msg)
                await asyncio.sleep(1.0)  # Brief pause on error
    
    async def _update_progress(self) -> None:
        """Update progress by scanning filesystem."""
        if not self.filesystem_scanner:
            return
            
        scan_start = time.time()
        current_bytes = 0
        current_files = 0
        
        # Simulate partial scan for progress
        scan_root = self.filesystem_scanner.layout.root_path
        async for entry in self.filesystem_scanner.scan_directory(scan_root):
            if not entry.is_directory:
                current_bytes += entry.size
                current_files += 1
                
                # Break early to simulate ongoing transfer
                if current_files >= 10:  # Limit scan for testing
                    break
        
        self.state.last_scan_time = time.time()
        self.state.total_bytes_scanned = current_bytes
        self.state.files_scanned = current_files
        
        progress_info = {
            "bytes_scanned": current_bytes,
            "files_scanned": current_files,
            "scan_duration": time.time() - scan_start
        }
        
        await self.on_progress_update(progress_info)
    
    def get_state(self) -> MockApplicationState:
        """Get current application state."""
        return self.state
    
    def add_mock_process(self, name: str, pid: int) -> ProcessInfo:
        """Add mock process for detection."""
        from mover_status.core.process.models import ProcessInfo, ProcessStatus
        from datetime import datetime
        
        process = ProcessInfo(
            pid=pid,
            name=name,
            command=f"/usr/local/sbin/{name}",
            start_time=datetime.fromtimestamp(time.time()),
            cpu_percent=15.0,
            memory_mb=8.5,
            status=ProcessStatus.RUNNING
        )
        
        self.process_detector.add_process(process)
        return process


class MockApplicationRunner:
    """Mock application runner for end-to-end testing."""
    
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path
        self.orchestrator = MockMonitorOrchestrator()
        self.dispatcher: AsyncDispatcher | None = None
        self.is_running = False
        self.run_count = 0
        self.error_count = 0
        
        # Test hooks
        self.on_startup: AsyncMock = AsyncMock()
        self.on_shutdown: AsyncMock = AsyncMock()
        self.on_cycle_complete: AsyncMock = AsyncMock()
    
    async def run_once(self) -> dict[str, object]:
        """Run application once and return results."""
        self.run_count += 1
        start_time = time.time()
        
        try:
            await self.on_startup()
            
            # Start monitoring
            await self.orchestrator.start_monitoring()
            
            # Let it run briefly
            await asyncio.sleep(0.5)
            
            # Stop monitoring
            await self.orchestrator.stop_monitoring()
            
            await self.on_shutdown()
            
            runtime = time.time() - start_time
            state = self.orchestrator.get_state()
            
            result = {
                "success": True,
                "runtime": runtime,
                "run_count": self.run_count,
                "error_count": self.error_count,
                "state": {
                    "is_running": state.is_running,
                    "files_scanned": state.files_scanned,
                    "bytes_scanned": state.total_bytes_scanned,
                    "errors": len(state.errors_encountered),
                    "notifications_sent": state.notifications_sent
                }
            }
            
            await self.on_cycle_complete(result)
            return result
            
        except Exception as e:
            self.error_count += 1
            error_result = {
                "success": False,
                "error": str(e),
                "runtime": time.time() - start_time,
                "run_count": self.run_count,
                "error_count": self.error_count
            }
            await self.on_cycle_complete(error_result)
            return error_result
    
    async def run_continuous(self, duration: float) -> dict[str, object]:
        """Run application continuously for specified duration."""
        self.is_running = True
        start_time = time.time()
        cycles = 0
        
        try:
            await self.orchestrator.start_monitoring()
            
            while self.is_running and (time.time() - start_time) < duration:
                await asyncio.sleep(1.0)
                cycles += 1
            
            await self.orchestrator.stop_monitoring()
            
            return {
                "success": True,
                "duration": time.time() - start_time,
                "cycles": cycles,
                "final_state": self.orchestrator.get_state()
            }
            
        except Exception as e:
            self.error_count += 1
            return {
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time,
                "cycles": cycles
            }
        finally:
            self.is_running = False
    
    def stop(self) -> None:
        """Stop continuous running."""
        self.is_running = False
    
    def set_filesystem_layout(self, layout: MockFilesystemLayout) -> None:
        """Set filesystem layout for testing."""
        self.orchestrator.set_filesystem_layout(layout)
    
    def add_mock_process(self, name: str = "mover", pid: int = 12345) -> ProcessInfo:
        """Add mock process for testing."""
        return self.orchestrator.add_mock_process(name, pid)


class IntegrationTestScenarioRunner:
    """Runner for complex integration test scenarios."""
    
    def __init__(self) -> None:
        self.temp_dir: Path | None = None
        self.filesystem_layout: MockFilesystemLayout | None = None
        self.app_runner: MockApplicationRunner | None = None
        
    async def setup(self, file_count: int = 50) -> None:
        """Set up test scenario."""
        # Create temporary directory
        self.temp_dir = Path(tempfile.mkdtemp(prefix="integration_test_"))
        
        # Create filesystem layout
        self.filesystem_layout = MockFilesystemLayout.create_test_layout(
            self.temp_dir, file_count
        )
        
        # Create app runner
        self.app_runner = MockApplicationRunner()
        self.app_runner.set_filesystem_layout(self.filesystem_layout)
    
    async def teardown(self) -> None:
        """Clean up test scenario."""
        if self.app_runner:
            self.app_runner.stop()
            
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def run_complete_workflow(self) -> dict[str, object]:
        """Run complete workflow test."""
        if not self.app_runner:
            raise RuntimeError("Test scenario not set up")
            
        # Add mock process to be detected
        process = self.app_runner.add_mock_process("mover", 12345)
        
        # Run application once
        result = await self.app_runner.run_once()
        
        return {
            "workflow_result": result,
            "process_info": {
                "pid": process.pid,
                "name": process.name,
                "status": process.status
            },
            "filesystem_stats": self.filesystem_layout.get_total_file_size() if self.filesystem_layout else 0
        }
    
    async def run_failure_scenario(self, failure_type: str = "process_detection") -> dict[str, object]:
        """Run failure scenario test."""
        if not self.app_runner:
            raise RuntimeError("Test scenario not set up")
            
        # Configure failure
        if failure_type == "process_detection":
            self.app_runner.orchestrator.process_detector.failure_rate = 1.0
        elif failure_type == "filesystem_scan":
            if self.app_runner.orchestrator.filesystem_scanner:
                self.app_runner.orchestrator.filesystem_scanner.failure_rate = 1.0
        
        # Run and expect failure
        result = await self.app_runner.run_once()
        
        return {
            "failure_type": failure_type,
            "result": result,
            "expected_failure": not result["success"]
        }
    
    async def run_performance_test(self, duration: float = 10.0) -> dict[str, object]:
        """Run performance test."""
        if not self.app_runner:
            raise RuntimeError("Test scenario not set up")
            
        # Add process and run continuously
        process = self.app_runner.add_mock_process("mover", 12345)
        result = await self.app_runner.run_continuous(duration)
        
        state = self.app_runner.orchestrator.get_state()
        
        return {
            "performance_result": result,
            "metrics": {
                "files_per_second": state.files_scanned / duration if duration > 0 else 0,
                "bytes_per_second": state.total_bytes_scanned / duration if duration > 0 else 0,
                "error_rate": state.error_count / max(1, self.app_runner.run_count),
                "detection_calls": self.app_runner.orchestrator.process_detector.detection_calls
            }
        }