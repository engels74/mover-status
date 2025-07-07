"""Tests for base message formatter."""

from __future__ import annotations

import pytest
from typing import TYPE_CHECKING, override

from mover_status.plugins.telegram.formatting.base import MessageFormatter
from mover_status.notifications.models.message import Message

if TYPE_CHECKING:
    pass


class ConcreteFormatter(MessageFormatter):
    """Concrete implementation of MessageFormatter for testing."""
    
    @override
    def format_message(self, message: Message) -> str:
        """Simple implementation for testing."""
        return f"{self.format_title(message.title)}: {self.format_content(message.content)}"
    
    @override
    def escape_text(self, text: str) -> str:
        """Simple escape implementation for testing."""
        return text.replace("&", "&amp;")


class TestMessageFormatter:
    """Test suite for MessageFormatter base class."""
    
    @pytest.fixture
    def formatter(self) -> ConcreteFormatter:
        """Create formatter instance for testing."""
        return ConcreteFormatter()
    
    @pytest.fixture
    def test_message(self) -> Message:
        """Test message for formatting."""
        return Message(
            title="Test Title",
            content="Test content with & ampersand",
            priority="high",
            tags=["urgent", "notification"],
            metadata={"source": "test", "version": "1.0"}
        )
    
    def test_format_title(self, formatter: ConcreteFormatter) -> None:
        """Test title formatting."""
        title = "Test & Title"
        result = formatter.format_title(title)
        assert result == "Test &amp; Title"
    
    def test_format_content(self, formatter: ConcreteFormatter) -> None:
        """Test content formatting."""
        content = "Content with & symbols"
        result = formatter.format_content(content)
        assert result == "Content with &amp; symbols"
    
    def test_format_tags_empty(self, formatter: ConcreteFormatter) -> None:
        """Test formatting empty tags list."""
        result = formatter.format_tags([])
        assert result == ""
    
    def test_format_tags_single(self, formatter: ConcreteFormatter) -> None:
        """Test formatting single tag."""
        result = formatter.format_tags(["urgent"])
        assert result == "Tags: urgent"
    
    def test_format_tags_multiple(self, formatter: ConcreteFormatter) -> None:
        """Test formatting multiple tags."""
        result = formatter.format_tags(["urgent", "test & debug"])
        assert result == "Tags: urgent, test &amp; debug"
    
    def test_format_metadata_empty(self, formatter: ConcreteFormatter) -> None:
        """Test formatting empty metadata."""
        result = formatter.format_metadata({})
        assert result == ""
    
    def test_format_metadata_single(self, formatter: ConcreteFormatter) -> None:
        """Test formatting single metadata entry."""
        result = formatter.format_metadata({"key": "value & data"})
        assert result == "key: value &amp; data"
    
    def test_format_metadata_multiple(self, formatter: ConcreteFormatter) -> None:
        """Test formatting multiple metadata entries."""
        metadata = {"source": "test & app", "version": "1.0"}
        result = formatter.format_metadata(metadata)
        lines = result.split("\n")
        assert len(lines) == 2
        assert "source: test &amp; app" in lines
        assert "version: 1.0" in lines
    
    def test_format_priority(self, formatter: ConcreteFormatter) -> None:
        """Test priority formatting."""
        result = formatter.format_priority("high")
        assert result == "Priority: HIGH"
    
    def test_format_priority_with_special_chars(self, formatter: ConcreteFormatter) -> None:
        """Test priority formatting with special characters."""
        result = formatter.format_priority("test & urgent")
        assert result == "Priority: TEST &amp; URGENT"
    
    def test_escape_text(self, formatter: ConcreteFormatter) -> None:
        """Test text escaping."""
        text = "Text with & ampersands"
        result = formatter.escape_text(text)
        assert result == "Text with &amp; ampersands"