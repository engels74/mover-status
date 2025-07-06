"""Process information models for process detection and monitoring."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from typing import override

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    pass


class ProcessStatus(str, Enum):
    """Enumeration for process status."""
    
    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"
    
    @classmethod
    def from_string(cls, value: str) -> ProcessStatus:
        """Create ProcessStatus from string value.
        
        Args:
            value: String value to convert
            
        Returns:
            ProcessStatus enum value
            
        Raises:
            ValueError: If value is not a valid status
        """
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid process status: '{value}'") from None
    
    @override
    def __str__(self) -> str:
        """Return string representation."""
        return self.value


class ProcessInfo(BaseModel):
    """Information about a process."""
    
    pid: int = Field(..., description="Process ID")
    command: str = Field(..., description="Full command line")
    start_time: datetime = Field(..., description="Process start time")
    name: str = Field(..., description="Process name")
    status: ProcessStatus = Field(default=ProcessStatus.UNKNOWN, description="Process status")
    cpu_percent: float | None = Field(default=None, description="CPU usage percentage")
    memory_mb: float | None = Field(default=None, description="Memory usage in MB")
    working_directory: str | None = Field(default=None, description="Working directory")
    user: str | None = Field(default=None, description="User running the process")
    
    @field_validator("pid")
    @classmethod
    def validate_pid(cls, v: int) -> int:
        """Validate process ID is positive."""
        if v <= 0:
            raise ValueError("PID must be positive")
        return v
    
    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str) -> str:
        """Validate command is not empty."""
        if not v.strip():
            raise ValueError("Command cannot be empty")
        return v
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is not empty."""
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v
    
    @field_validator("cpu_percent")
    @classmethod
    def validate_cpu_percent(cls, v: float | None) -> float | None:
        """Validate CPU percent is non-negative."""
        if v is not None and v < 0:
            raise ValueError("CPU percent must be non-negative")
        return v
    
    @field_validator("memory_mb")
    @classmethod
    def validate_memory_mb(cls, v: float | None) -> float | None:
        """Validate memory MB is non-negative."""
        if v is not None and v < 0:
            raise ValueError("Memory MB must be non-negative")
        return v
    
    def is_mover_process(self) -> bool:
        """Check if this process is a mover process.
        
        Returns:
            True if this appears to be a mover process
        """
        mover_patterns = ["mover", "/usr/local/sbin/mover"]
        command_lower = self.command.lower()
        name_lower = self.name.lower()
        
        return any(pattern in command_lower or pattern in name_lower 
                  for pattern in mover_patterns)
    
    @property
    def age_seconds(self) -> float:
        """Get the age of the process in seconds.
        
        Returns:
            Age in seconds since process start
        """
        return (datetime.now() - self.start_time).total_seconds()
    
    @override
    def __eq__(self, other: object) -> bool:
        """Check equality based on PID and start time."""
        if not isinstance(other, ProcessInfo):
            return False
        return self.pid == other.pid and self.start_time == other.start_time
    
    @override
    def __hash__(self) -> int:
        """Hash based on PID and start time."""
        return hash((self.pid, self.start_time))
    
    @override
    def __str__(self) -> str:
        """String representation of process info."""
        return f"ProcessInfo(pid={self.pid}, name='{self.name}', status={self.status})"
    
    @override
    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"ProcessInfo(pid={self.pid}, name='{self.name}', "
                f"command='{self.command}', status={self.status})")

    model_config = ConfigDict(frozen=True)  # Make immutable for hashing