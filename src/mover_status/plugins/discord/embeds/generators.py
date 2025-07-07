"""Discord embed generators for rich notifications."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol, override

from mover_status.plugins.discord.webhook.client import DiscordEmbed

if TYPE_CHECKING:
    from mover_status.notifications.models.message import Message

# Progress data structure (based on test fixtures)
class ProgressData(Protocol):
    """Protocol for progress data."""
    bytes_transferred: int
    total_size: int
    timestamp: float


class EmbedGenerator(ABC):
    """Abstract base class for Discord embed generators."""
    
    @abstractmethod
    def generate_embed(self, message: Message) -> DiscordEmbed:
        """Generate a Discord embed from a message.
        
        Args:
            message: The notification message
            
        Returns:
            Discord embed object
        """


class StatusEmbedGenerator(EmbedGenerator):
    """Standard status embed generator with priority-based styling."""
    
    def __init__(self, *, include_timestamp: bool = True) -> None:
        """Initialize status embed generator.
        
        Args:
            include_timestamp: Whether to include timestamp in embeds
        """
        self.include_timestamp: bool = include_timestamp
        self._color_map: dict[str, int] = {
            "low": 0x00FF00,      # Green
            "normal": 0x0099FF,   # Blue  
            "high": 0xFF9900,     # Orange
            "urgent": 0xFF0000,   # Red
        }
    
    @override
    def generate_embed(self, message: Message) -> DiscordEmbed:
        """Generate standard status embed.
        
        Args:
            message: The notification message
            
        Returns:
            Discord embed with status information
        """
        embed = DiscordEmbed(
            title=message.title,
            description=message.content,
            color=self._color_map.get(message.priority, 0x0099FF),
            timestamp=datetime.now(timezone.utc).isoformat() if self.include_timestamp else None,
        )
        
        # Add priority field
        embed.fields.append({
            "name": "Priority",
            "value": message.priority.title(),
            "inline": True,
        })
        
        # Add tags if present
        if message.tags:
            embed.fields.append({
                "name": "Tags",
                "value": ", ".join(message.tags),
                "inline": True,
            })
        
        # Add metadata fields (limit to avoid Discord limits)
        for key, value in message.metadata.items():
            if len(embed.fields) >= 23:  # Leave room for priority and tags
                break
            
            embed.fields.append({
                "name": key.replace("_", " ").title(),
                "value": str(value),
                "inline": True,
            })
        
        return embed


class ProgressEmbedGenerator(EmbedGenerator):
    """Progress embed generator with visual progress indicators."""
    
    def __init__(
        self,
        *,
        include_timestamp: bool = True,
        show_speed: bool = True,
        show_eta: bool = True,
        progress_bar_length: int = 20,
    ) -> None:
        """Initialize progress embed generator.
        
        Args:
            include_timestamp: Whether to include timestamp in embeds
            show_speed: Whether to show transfer speed
            show_eta: Whether to show estimated time of arrival
            progress_bar_length: Length of progress bar in characters
        """
        self.include_timestamp: bool = include_timestamp
        self.show_speed: bool = show_speed
        self.show_eta: bool = show_eta
        self.progress_bar_length: int = progress_bar_length
        
        self._status_colors: dict[str, int] = {
            "started": 0x00FF00,    # Green
            "in_progress": 0x0099FF,  # Blue
            "completed": 0x00CC00,  # Bright green
            "failed": 0xFF0000,     # Red
            "paused": 0xFFCC00,     # Yellow
            "cancelled": 0x999999,  # Gray
        }
    
    @override
    def generate_embed(self, message: Message) -> DiscordEmbed:
        """Generate progress embed with visual indicators.
        
        Args:
            message: The notification message with progress data
            
        Returns:
            Discord embed with progress visualization
        """
        # Extract progress data from message metadata
        progress_data = self._extract_progress_data(message.metadata)
        
        # Determine status and color
        status = message.metadata.get("status", "in_progress")
        color = self._status_colors.get(status, 0x0099FF)
        
        embed = DiscordEmbed(
            title=message.title,
            description=message.content,
            color=color,
            timestamp=datetime.now(timezone.utc).isoformat() if self.include_timestamp else None,
        )
        
        if progress_data:
            # Add progress bar
            progress_bar = self._create_progress_bar(
                progress_data["bytes_transferred"],
                progress_data["total_size"],
            )
            
            # Add progress percentage
            percentage = self._calculate_percentage(
                progress_data["bytes_transferred"],
                progress_data["total_size"],
            )
            
            embed.fields.append({
                "name": "Progress",
                "value": f"{progress_bar} {percentage:.1f}%",
                "inline": False,
            })
            
            # Add size information
            embed.fields.append({
                "name": "Size",
                "value": f"{self._format_bytes(progress_data['bytes_transferred'])} / {self._format_bytes(progress_data['total_size'])}",
                "inline": True,
            })
            
            # Add speed if available and enabled
            if self.show_speed and "speed_bps" in progress_data:
                speed_text = self._format_bytes(progress_data["speed_bps"]) + "/s"
                embed.fields.append({
                    "name": "Speed",
                    "value": speed_text,
                    "inline": True,
                })
            
            # Add ETA if available and enabled
            if self.show_eta and "eta_seconds" in progress_data:
                eta_text = self._format_duration(progress_data["eta_seconds"])
                embed.fields.append({
                    "name": "ETA",
                    "value": eta_text,
                    "inline": True,
                })
        
        # Add status field
        embed.fields.append({
            "name": "Status",
            "value": status.replace("_", " ").title(),
            "inline": True,
        })
        
        # Add tags if present
        if message.tags:
            embed.fields.append({
                "name": "Tags",
                "value": ", ".join(message.tags),
                "inline": True,
            })
        
        return embed
    
    def _extract_progress_data(self, metadata: dict[str, str]) -> dict[str, int] | None:
        """Extract progress data from metadata.
        
        Args:
            metadata: Message metadata dictionary
            
        Returns:
            Progress data dictionary or None if not available
        """
        try:
            bytes_transferred = int(metadata.get("bytes_transferred", 0))
            total_size = int(metadata.get("total_size", 0))
            
            if total_size == 0:
                return None
            
            progress_data: dict[str, int] = {
                "bytes_transferred": bytes_transferred,
                "total_size": total_size,
            }
            
            # Optional fields
            if "speed_bps" in metadata:
                progress_data["speed_bps"] = int(metadata["speed_bps"])
            
            if "eta_seconds" in metadata:
                progress_data["eta_seconds"] = int(metadata["eta_seconds"])
            
            return progress_data
            
        except (ValueError, TypeError):
            return None
    
    def _create_progress_bar(self, bytes_transferred: int, total_size: int) -> str:
        """Create ASCII progress bar.
        
        Args:
            bytes_transferred: Number of bytes transferred
            total_size: Total size in bytes
            
        Returns:
            ASCII progress bar string
        """
        if total_size == 0:
            return "█" * self.progress_bar_length
        
        percentage = bytes_transferred / total_size
        filled_length = int(self.progress_bar_length * percentage)
        
        # Use Unicode block characters for better visualization
        filled_bar = "█" * filled_length
        empty_bar = "░" * (self.progress_bar_length - filled_length)
        
        return f"[{filled_bar}{empty_bar}]"
    
    def _calculate_percentage(self, bytes_transferred: int, total_size: int) -> float:
        """Calculate progress percentage.
        
        Args:
            bytes_transferred: Number of bytes transferred
            total_size: Total size in bytes
            
        Returns:
            Percentage as float (0.0 to 100.0)
        """
        if total_size == 0:
            return 100.0
        
        return (bytes_transferred / total_size) * 100.0
    
    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes into human-readable string.
        
        Args:
            bytes_value: Number of bytes
            
        Returns:
            Human-readable size string
        """
        if bytes_value == 0:
            return "0 B"
        
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        unit_index = int(math.floor(math.log(bytes_value, 1024)))
        
        # Clamp to available units
        unit_index = min(unit_index, len(units) - 1)
        
        size: float = bytes_value / (1024 ** unit_index)
        
        if size >= 100:
            return f"{size:.0f} {units[unit_index]}"
        elif size >= 10:
            return f"{size:.1f} {units[unit_index]}"
        else:
            return f"{size:.2f} {units[unit_index]}"
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to human-readable string.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Human-readable duration string
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            return f"{hours}h {remaining_minutes}m"


class ProcessStatusEmbedGenerator(EmbedGenerator):
    """Process status embed generator with system resource information."""
    
    def __init__(self, *, include_timestamp: bool = True) -> None:
        """Initialize process status embed generator.
        
        Args:
            include_timestamp: Whether to include timestamp in embeds
        """
        self.include_timestamp: bool = include_timestamp
        
        self._status_colors: dict[str, int] = {
            "running": 0x00FF00,    # Green
            "stopped": 0xFF0000,    # Red
            "paused": 0xFFCC00,     # Yellow
            "starting": 0x0099FF,   # Blue
            "stopping": 0xFF9900,   # Orange
            "unknown": 0x999999,    # Gray
        }
    
    @override
    def generate_embed(self, message: Message) -> DiscordEmbed:
        """Generate process status embed.
        
        Args:
            message: The notification message with process data
            
        Returns:
            Discord embed with process information
        """
        # Extract process data from message metadata
        process_data = self._extract_process_data(message.metadata)
        
        # Determine status and color
        status = message.metadata.get("status", "unknown")
        color = self._status_colors.get(status, 0x999999)
        
        embed = DiscordEmbed(
            title=message.title,
            description=message.content,
            color=color,
            timestamp=datetime.now(timezone.utc).isoformat() if self.include_timestamp else None,
        )
        
        # Add process status
        embed.fields.append({
            "name": "Status",
            "value": status.replace("_", " ").title(),
            "inline": True,
        })
        
        if process_data:
            # Add process ID
            if "pid" in process_data and isinstance(process_data["pid"], int):
                embed.fields.append({
                    "name": "PID",
                    "value": str(process_data["pid"]),
                    "inline": True,
                })
            
            # Add command/name
            if "command" in process_data and isinstance(process_data["command"], str):
                embed.fields.append({
                    "name": "Command",
                    "value": f"`{process_data['command']}`",
                    "inline": False,
                })
            elif "name" in process_data and isinstance(process_data["name"], str):
                embed.fields.append({
                    "name": "Process",
                    "value": process_data["name"],
                    "inline": True,
                })
            
            # Add resource usage
            if "cpu_percent" in process_data and isinstance(process_data["cpu_percent"], (int, float)):
                embed.fields.append({
                    "name": "CPU",
                    "value": f"{process_data['cpu_percent']:.1f}%",
                    "inline": True,
                })
            
            if "memory_mb" in process_data and isinstance(process_data["memory_mb"], (int, float)):
                memory_text = self._format_memory(float(process_data["memory_mb"]))
                embed.fields.append({
                    "name": "Memory",
                    "value": memory_text,
                    "inline": True,
                })
            
            # Add working directory
            if "working_directory" in process_data and isinstance(process_data["working_directory"], str):
                embed.fields.append({
                    "name": "Working Directory",
                    "value": f"`{process_data['working_directory']}`",
                    "inline": False,
                })
            
            # Add user
            if "user" in process_data and isinstance(process_data["user"], str):
                embed.fields.append({
                    "name": "User",
                    "value": process_data["user"],
                    "inline": True,
                })
            
            # Add start time
            if "start_time" in process_data and isinstance(process_data["start_time"], str):
                embed.fields.append({
                    "name": "Started",
                    "value": process_data["start_time"],
                    "inline": True,
                })
        
        # Add tags if present
        if message.tags:
            embed.fields.append({
                "name": "Tags",
                "value": ", ".join(message.tags),
                "inline": True,
            })
        
        return embed
    
    def _extract_process_data(self, metadata: dict[str, str]) -> dict[str, str | int | float] | None:
        """Extract process data from metadata.
        
        Args:
            metadata: Message metadata dictionary
            
        Returns:
            Process data dictionary or None if not available
        """
        process_data: dict[str, str | int | float] = {}
        
        # Extract available process fields
        if "pid" in metadata:
            try:
                process_data["pid"] = int(metadata["pid"])
            except (ValueError, TypeError):
                pass
        
        if "command" in metadata:
            process_data["command"] = metadata["command"]
        
        if "name" in metadata:
            process_data["name"] = metadata["name"]
        
        if "cpu_percent" in metadata:
            try:
                process_data["cpu_percent"] = float(metadata["cpu_percent"])
            except (ValueError, TypeError):
                pass
        
        if "memory_mb" in metadata:
            try:
                process_data["memory_mb"] = float(metadata["memory_mb"])
            except (ValueError, TypeError):
                pass
        
        if "working_directory" in metadata:
            process_data["working_directory"] = metadata["working_directory"]
        
        if "user" in metadata:
            process_data["user"] = metadata["user"]
        
        if "start_time" in metadata:
            process_data["start_time"] = metadata["start_time"]
        
        return process_data if process_data else None
    
    def _format_memory(self, memory_mb: float) -> str:
        """Format memory usage in MB to human-readable string.
        
        Args:
            memory_mb: Memory usage in MB
            
        Returns:
            Human-readable memory string
        """
        if memory_mb < 1024:
            return f"{memory_mb:.1f} MB"
        else:
            memory_gb = memory_mb / 1024
            return f"{memory_gb:.2f} GB"