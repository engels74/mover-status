"""Tests for Discord embed generators."""

from __future__ import annotations

import pytest

from mover_status.plugins.discord.embeds.generators import (
    ProgressEmbedGenerator,
    ProcessStatusEmbedGenerator,
    StatusEmbedGenerator,
)
from mover_status.notifications.models.message import Message


class TestStatusEmbedGenerator:
    """Test cases for StatusEmbedGenerator."""
    
    @pytest.fixture
    def generator(self) -> StatusEmbedGenerator:
        """Create status embed generator."""
        return StatusEmbedGenerator()
    
    @pytest.fixture
    def sample_message(self) -> Message:
        """Sample notification message."""
        return Message(
            title="Test Notification",
            content="This is a test notification",
            priority="normal",
            tags=["test", "notification"],
            metadata={"source": "test", "environment": "dev"},
        )
    
    def test_generates_basic_embed(self, generator: StatusEmbedGenerator, sample_message: Message) -> None:
        """Test basic embed generation."""
        embed = generator.generate_embed(sample_message)
        
        assert embed.title == "Test Notification"
        assert embed.description == "This is a test notification"
        assert embed.color == 0x0099FF  # Blue for normal priority
        assert embed.timestamp is not None
    
    def test_priority_colors(self, generator: StatusEmbedGenerator) -> None:
        """Test priority color mapping."""
        test_cases = [
            ("low", 0x00FF00),      # Green
            ("normal", 0x0099FF),   # Blue
            ("high", 0xFF9900),     # Orange
            ("urgent", 0xFF0000),   # Red
        ]
        
        for priority, expected_color in test_cases:
            message = Message(
                title="Test",
                content="Test content",
                priority=priority,  # pyright: ignore[reportArgumentType]
            )
            embed = generator.generate_embed(message)
            assert embed.color == expected_color
    
    def test_includes_priority_field(self, generator: StatusEmbedGenerator, sample_message: Message) -> None:
        """Test priority field inclusion."""
        embed = generator.generate_embed(sample_message)
        
        priority_field = next((f for f in embed.fields if f["name"] == "Priority"), None)
        assert priority_field is not None
        assert priority_field["value"] == "Normal"
        assert priority_field["inline"] is True
    
    def test_includes_tags_field(self, generator: StatusEmbedGenerator, sample_message: Message) -> None:
        """Test tags field inclusion."""
        embed = generator.generate_embed(sample_message)
        
        tags_field = next((f for f in embed.fields if f["name"] == "Tags"), None)
        assert tags_field is not None
        assert tags_field["value"] == "test, notification"
        assert tags_field["inline"] is True
    
    def test_includes_metadata_fields(self, generator: StatusEmbedGenerator, sample_message: Message) -> None:
        """Test metadata field inclusion."""
        embed = generator.generate_embed(sample_message)
        
        source_field = next((f for f in embed.fields if f["name"] == "Source"), None)
        assert source_field is not None
        assert source_field["value"] == "test"
        
        env_field = next((f for f in embed.fields if f["name"] == "Environment"), None)
        assert env_field is not None
        assert env_field["value"] == "dev"
    
    def test_respects_field_limit(self, generator: StatusEmbedGenerator) -> None:
        """Test field limit is respected."""
        # Create message with many metadata fields
        metadata = {f"field_{i}": f"value_{i}" for i in range(30)}
        message = Message(
            title="Test",
            content="Test content",
            tags=["tag1", "tag2"],
            metadata=metadata,
        )
        
        embed = generator.generate_embed(message)
        
        # Should have at most 25 fields (Discord limit)
        assert len(embed.fields) <= 25
    
    def test_without_timestamp(self) -> None:
        """Test generator without timestamp."""
        generator = StatusEmbedGenerator(include_timestamp=False)
        message = Message(title="Test", content="Test content")
        
        embed = generator.generate_embed(message)
        assert embed.timestamp is None
    
    def test_empty_tags_and_metadata(self, generator: StatusEmbedGenerator) -> None:
        """Test with empty tags and metadata."""
        message = Message(title="Test", content="Test content")
        
        embed = generator.generate_embed(message)
        
        # Should only have priority field
        assert len(embed.fields) == 1
        assert embed.fields[0]["name"] == "Priority"


class TestProgressEmbedGenerator:
    """Test cases for ProgressEmbedGenerator."""
    
    @pytest.fixture
    def generator(self) -> ProgressEmbedGenerator:
        """Create progress embed generator."""
        return ProgressEmbedGenerator()
    
    @pytest.fixture
    def progress_message(self) -> Message:
        """Sample progress notification message."""
        return Message(
            title="File Transfer",
            content="Transferring large file",
            priority="normal",
            tags=["transfer", "file"],
            metadata={
                "status": "in_progress",
                "bytes_transferred": "52428800",  # 50MB
                "total_size": "104857600",        # 100MB
                "speed_bps": "1048576",           # 1MB/s
                "eta_seconds": "50",
            },
        )
    
    def test_generates_progress_embed(self, generator: ProgressEmbedGenerator, progress_message: Message) -> None:
        """Test progress embed generation."""
        embed = generator.generate_embed(progress_message)
        
        assert embed.title == "File Transfer"
        assert embed.description == "Transferring large file"
        assert embed.color == 0x0099FF  # Blue for in_progress
        assert embed.timestamp is not None
    
    def test_progress_bar_generation(self, generator: ProgressEmbedGenerator, progress_message: Message) -> None:
        """Test progress bar field generation."""
        embed = generator.generate_embed(progress_message)
        
        progress_field = next((f for f in embed.fields if f["name"] == "Progress"), None)
        assert progress_field is not None
        progress_value = str(progress_field["value"])
        assert "50.0%" in progress_value
        assert "[" in progress_value  # Progress bar
        assert "█" in progress_value  # Filled part
        assert "░" in progress_value  # Empty part
    
    def test_size_field(self, generator: ProgressEmbedGenerator, progress_message: Message) -> None:
        """Test size field generation."""
        embed = generator.generate_embed(progress_message)
        
        size_field = next((f for f in embed.fields if f["name"] == "Size"), None)
        assert size_field is not None
        size_value = str(size_field["value"])
        assert "50.0 MB / 100 MB" in size_value
    
    def test_speed_field(self, generator: ProgressEmbedGenerator, progress_message: Message) -> None:
        """Test speed field generation."""
        embed = generator.generate_embed(progress_message)
        
        speed_field = next((f for f in embed.fields if f["name"] == "Speed"), None)
        assert speed_field is not None
        speed_value = str(speed_field["value"])
        assert "1.00 MB/s" in speed_value
    
    def test_eta_field(self, generator: ProgressEmbedGenerator, progress_message: Message) -> None:
        """Test ETA field generation."""
        embed = generator.generate_embed(progress_message)
        
        eta_field = next((f for f in embed.fields if f["name"] == "ETA"), None)
        assert eta_field is not None
        eta_value = str(eta_field["value"])
        assert "50s" in eta_value
    
    def test_status_colors(self, generator: ProgressEmbedGenerator) -> None:
        """Test status color mapping."""
        test_cases = [
            ("started", 0x00FF00),     # Green
            ("in_progress", 0x0099FF), # Blue
            ("completed", 0x00CC00),   # Bright green
            ("failed", 0xFF0000),      # Red
            ("paused", 0xFFCC00),      # Yellow
            ("cancelled", 0x999999),   # Gray
        ]
        
        for status, expected_color in test_cases:
            message = Message(
                title="Test",
                content="Test content",
                metadata={"status": status},
            )
            embed = generator.generate_embed(message)
            assert embed.color == expected_color
    
    def test_progress_bar_edge_cases(self, generator: ProgressEmbedGenerator) -> None:
        """Test progress bar with edge cases."""
        # Test 0% progress
        message_0 = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "0",
                "total_size": "1000",
            },
        )
        embed_0 = generator.generate_embed(message_0)
        progress_field_0 = next((f for f in embed_0.fields if f["name"] == "Progress"), None)
        assert progress_field_0 is not None
        progress_value_0 = str(progress_field_0["value"])
        assert "0.0%" in progress_value_0
        
        # Test 100% progress
        message_100 = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "1000",
                "total_size": "1000",
            },
        )
        embed_100 = generator.generate_embed(message_100)
        progress_field_100 = next((f for f in embed_100.fields if f["name"] == "Progress"), None)
        assert progress_field_100 is not None
        progress_value_100 = str(progress_field_100["value"])
        assert "100.0%" in progress_value_100
    
    def test_byte_formatting(self, generator: ProgressEmbedGenerator) -> None:
        """Test byte formatting in various units."""
        test_cases = [
            ("1024", "1.00 KB"),
            ("1048576", "1.00 MB"),
            ("1073741824", "1.00 GB"),
            ("1099511627776", "1.00 TB"),
        ]
        
        for bytes_str, expected_format in test_cases:
            message = Message(
                title="Test",
                content="Test content",
                metadata={
                    "bytes_transferred": bytes_str,
                    "total_size": bytes_str,
                },
            )
            embed = generator.generate_embed(message)
            size_field = next((f for f in embed.fields if f["name"] == "Size"), None)
            assert size_field is not None
            size_value = str(size_field["value"])
            assert expected_format in size_value
    
    def test_duration_formatting(self, generator: ProgressEmbedGenerator) -> None:
        """Test duration formatting."""
        test_cases = [
            ("30", "30s"),
            ("90", "1m 30s"),
            ("3661", "1h 1m"),
        ]
        
        for eta_str, expected_format in test_cases:
            message = Message(
                title="Test",
                content="Test content",
                metadata={
                    "bytes_transferred": "50",
                    "total_size": "100",
                    "eta_seconds": eta_str,
                },
            )
            embed = generator.generate_embed(message)
            eta_field = next((f for f in embed.fields if f["name"] == "ETA"), None)
            assert eta_field is not None
            eta_value = str(eta_field["value"])
            assert expected_format in eta_value
    
    def test_invalid_progress_data(self, generator: ProgressEmbedGenerator) -> None:
        """Test handling of invalid progress data."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "invalid",
                "total_size": "also_invalid",
            },
        )
        
        embed = generator.generate_embed(message)
        
        # Should still generate embed, just without progress fields
        assert embed.title == "Test"
        progress_field = next((f for f in embed.fields if f["name"] == "Progress"), None)
        assert progress_field is None
    
    def test_zero_total_size(self, generator: ProgressEmbedGenerator) -> None:
        """Test handling of zero total size."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "0",
                "total_size": "0",
            },
        )
        
        embed = generator.generate_embed(message)
        
        # Should not include progress fields for zero-size transfers
        progress_field = next((f for f in embed.fields if f["name"] == "Progress"), None)
        assert progress_field is None
    
    def test_generator_options(self) -> None:
        """Test generator configuration options."""
        generator = ProgressEmbedGenerator(
            include_timestamp=False,
            show_speed=False,
            show_eta=False,
            progress_bar_length=10,
        )
        
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "bytes_transferred": "50",
                "total_size": "100",
                "speed_bps": "1000",
                "eta_seconds": "50",
            },
        )
        
        embed = generator.generate_embed(message)
        
        # Should not include timestamp
        assert embed.timestamp is None
        
        # Should not include speed or ETA fields
        speed_field = next((f for f in embed.fields if f["name"] == "Speed"), None)
        assert speed_field is None
        
        eta_field = next((f for f in embed.fields if f["name"] == "ETA"), None)
        assert eta_field is None
        
        # Progress bar should be shorter
        progress_field = next((f for f in embed.fields if f["name"] == "Progress"), None)
        assert progress_field is not None
        # Count progress bar characters (should be 10 + 2 for brackets)
        progress_value = str(progress_field["value"])
        progress_bar_part = progress_value.split(" ")[0]
        assert len(progress_bar_part) == 12  # [██████████] = 12 chars


class TestProcessStatusEmbedGenerator:
    """Test cases for ProcessStatusEmbedGenerator."""
    
    @pytest.fixture
    def generator(self) -> ProcessStatusEmbedGenerator:
        """Create process status embed generator."""
        return ProcessStatusEmbedGenerator()
    
    @pytest.fixture
    def process_message(self) -> Message:
        """Sample process notification message."""
        return Message(
            title="Process Update",
            content="Application status changed",
            priority="normal",
            tags=["process", "monitoring"],
            metadata={
                "status": "running",
                "pid": "1234",
                "command": "python app.py",
                "name": "MyApp",
                "cpu_percent": "15.5",
                "memory_mb": "256.7",
                "working_directory": "/home/user/app",
                "user": "appuser",
                "start_time": "2024-01-15T10:30:00Z",
            },
        )
    
    def test_generates_process_embed(self, generator: ProcessStatusEmbedGenerator, process_message: Message) -> None:
        """Test process embed generation."""
        embed = generator.generate_embed(process_message)
        
        assert embed.title == "Process Update"
        assert embed.description == "Application status changed"
        assert embed.color == 0x00FF00  # Green for running
        assert embed.timestamp is not None
    
    def test_status_colors(self, generator: ProcessStatusEmbedGenerator) -> None:
        """Test status color mapping."""
        test_cases = [
            ("running", 0x00FF00),   # Green
            ("stopped", 0xFF0000),   # Red
            ("paused", 0xFFCC00),    # Yellow
            ("starting", 0x0099FF),  # Blue
            ("stopping", 0xFF9900),  # Orange
            ("unknown", 0x999999),   # Gray
        ]
        
        for status, expected_color in test_cases:
            message = Message(
                title="Test",
                content="Test content",
                metadata={"status": status},
            )
            embed = generator.generate_embed(message)
            assert embed.color == expected_color
    
    def test_process_fields(self, generator: ProcessStatusEmbedGenerator, process_message: Message) -> None:
        """Test process field generation."""
        embed = generator.generate_embed(process_message)
        
        # Check status field
        status_field = next((f for f in embed.fields if f["name"] == "Status"), None)
        assert status_field is not None
        assert status_field["value"] == "Running"
        
        # Check PID field
        pid_field = next((f for f in embed.fields if f["name"] == "PID"), None)
        assert pid_field is not None
        assert pid_field["value"] == "1234"
        
        # Check command field
        command_field = next((f for f in embed.fields if f["name"] == "Command"), None)
        assert command_field is not None
        command_value = str(command_field["value"])
        assert "`python app.py`" in command_value
        
        # Check CPU field
        cpu_field = next((f for f in embed.fields if f["name"] == "CPU"), None)
        assert cpu_field is not None
        cpu_value = str(cpu_field["value"])
        assert "15.5%" in cpu_value
        
        # Check Memory field
        memory_field = next((f for f in embed.fields if f["name"] == "Memory"), None)
        assert memory_field is not None
        memory_value = str(memory_field["value"])
        assert "256.7 MB" in memory_value
        
        # Check Working Directory field
        wd_field = next((f for f in embed.fields if f["name"] == "Working Directory"), None)
        assert wd_field is not None
        wd_value = str(wd_field["value"])
        assert "`/home/user/app`" in wd_value
        
        # Check User field
        user_field = next((f for f in embed.fields if f["name"] == "User"), None)
        assert user_field is not None
        assert user_field["value"] == "appuser"
        
        # Check Started field
        started_field = next((f for f in embed.fields if f["name"] == "Started"), None)
        assert started_field is not None
        assert started_field["value"] == "2024-01-15T10:30:00Z"
    
    def test_memory_formatting(self, generator: ProcessStatusEmbedGenerator) -> None:
        """Test memory formatting."""
        test_cases = [
            ("100.5", "100.5 MB"),
            ("1024.0", "1.00 GB"),
            ("2048.5", "2.00 GB"),
        ]
        
        for memory_str, expected_format in test_cases:
            message = Message(
                title="Test",
                content="Test content",
                metadata={
                    "status": "running",
                    "memory_mb": memory_str,
                },
            )
            embed = generator.generate_embed(message)
            memory_field = next((f for f in embed.fields if f["name"] == "Memory"), None)
            assert memory_field is not None
            memory_value = str(memory_field["value"])
            assert expected_format in memory_value
    
    def test_minimal_process_data(self, generator: ProcessStatusEmbedGenerator) -> None:
        """Test with minimal process data."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={"status": "running"},
        )
        
        embed = generator.generate_embed(message)
        
        # Should only have status field
        status_field = next((f for f in embed.fields if f["name"] == "Status"), None)
        assert status_field is not None
        assert status_field["value"] == "Running"
    
    def test_invalid_process_data(self, generator: ProcessStatusEmbedGenerator) -> None:
        """Test handling of invalid process data."""
        message = Message(
            title="Test",
            content="Test content",
            metadata={
                "status": "running",
                "pid": "invalid",
                "cpu_percent": "not_a_number",
                "memory_mb": "also_invalid",
            },
        )
        
        embed = generator.generate_embed(message)
        
        # Should still generate embed, just without invalid fields
        assert embed.title == "Test"
        status_field = next((f for f in embed.fields if f["name"] == "Status"), None)
        assert status_field is not None
        
        # Invalid fields should not be present
        pid_field = next((f for f in embed.fields if f["name"] == "PID"), None)
        assert pid_field is None
        
        cpu_field = next((f for f in embed.fields if f["name"] == "CPU"), None)
        assert cpu_field is None
        
        memory_field = next((f for f in embed.fields if f["name"] == "Memory"), None)
        assert memory_field is None
    
    def test_process_name_vs_command(self, generator: ProcessStatusEmbedGenerator) -> None:
        """Test process name vs command field precedence."""
        # Command should take precedence over name
        message_with_both = Message(
            title="Test",
            content="Test content",
            metadata={
                "status": "running",
                "command": "python app.py",
                "name": "MyApp",
            },
        )
        
        embed = generator.generate_embed(message_with_both)
        command_field = next((f for f in embed.fields if f["name"] == "Command"), None)
        assert command_field is not None
        command_value = str(command_field["value"])
        assert "`python app.py`" in command_value
        
        # Name should be used if no command
        message_name_only = Message(
            title="Test",
            content="Test content",
            metadata={
                "status": "running",
                "name": "MyApp",
            },
        )
        
        embed = generator.generate_embed(message_name_only)
        process_field = next((f for f in embed.fields if f["name"] == "Process"), None)
        assert process_field is not None
        assert process_field["value"] == "MyApp"
    
    def test_without_timestamp(self) -> None:
        """Test generator without timestamp."""
        generator = ProcessStatusEmbedGenerator(include_timestamp=False)
        message = Message(
            title="Test",
            content="Test content",
            metadata={"status": "running"},
        )
        
        embed = generator.generate_embed(message)
        assert embed.timestamp is None
    
    def test_with_tags(self, generator: ProcessStatusEmbedGenerator) -> None:
        """Test with tags included."""
        message = Message(
            title="Test",
            content="Test content",
            tags=["process", "monitoring", "production"],
            metadata={"status": "running"},
        )
        
        embed = generator.generate_embed(message)
        tags_field = next((f for f in embed.fields if f["name"] == "Tags"), None)
        assert tags_field is not None
        assert tags_field["value"] == "process, monitoring, production"