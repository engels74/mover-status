"""Tests for HTML message formatter."""

from __future__ import annotations

import pytest
from typing import TYPE_CHECKING

from mover_status.plugins.telegram.formatting.html import HTMLFormatter
from mover_status.notifications.models.message import Message

if TYPE_CHECKING:
    pass


class TestHTMLFormatter:
    """Test suite for HTMLFormatter."""
    
    @pytest.fixture
    def formatter(self) -> HTMLFormatter:
        """Create HTML formatter instance for testing."""
        return HTMLFormatter()
    
    @pytest.fixture
    def basic_message(self) -> Message:
        """Basic test message."""
        return Message(
            title="Test Notification",
            content="This is a test message.",
            priority="normal"
        )
    
    @pytest.fixture
    def complex_message(self) -> Message:
        """Complex test message with all fields."""
        return Message(
            title="Complex <Test> & Notification",
            content="Content with <tags> & \"quotes\"",
            priority="urgent",
            tags=["test", "html & formatting"],
            metadata={"source": "test <app>", "version": "1.0"}
        )
    
    def test_format_basic_message(self, formatter: HTMLFormatter, basic_message: Message) -> None:
        """Test formatting a basic message."""
        result = formatter.format_message(basic_message)
        lines = result.split("\n")
        
        assert "<b>Test Notification</b>" in lines
        assert "This is a test message." in lines
    
    def test_format_complex_message(self, formatter: HTMLFormatter, complex_message: Message) -> None:
        """Test formatting a complex message with all features."""
        result = formatter.format_message(complex_message)
        
        # Check title escaping and bold formatting
        assert "<b>Complex &lt;Test&gt; &amp; Notification</b>" in result
        
        # Check content escaping
        assert "Content with &lt;tags&gt; &amp; &quot;quotes&quot;" in result
        
        # Check priority formatting with styling
        assert "🚨 Priority: URGENT" in result
        
        # Check tags formatting
        assert "<i>🏷️ Tags: test, html &amp; formatting</i>" in result
        
        # Check metadata formatting
        assert "source: test &lt;app&gt;" in result
        assert "version: 1.0" in result
    
    def test_escape_text(self, formatter: HTMLFormatter) -> None:
        """Test HTML text escaping."""
        text = "Text with <tags> & \"quotes\" and 'apostrophes'"
        result = formatter.escape_text(text)
        expected = "Text with &lt;tags&gt; &amp; &quot;quotes&quot; and &#x27;apostrophes&#x27;"
        assert result == expected
    
    def test_format_priority_urgent(self, formatter: HTMLFormatter) -> None:
        """Test urgent priority formatting."""
        result = formatter.format_priority_styled("urgent")
        assert result == "<b><u>🚨 Priority: URGENT</u></b>"
    
    def test_format_priority_high(self, formatter: HTMLFormatter) -> None:
        """Test high priority formatting."""
        result = formatter.format_priority_styled("high")
        assert result == "<b>⚠️ Priority: HIGH</b>"
    
    def test_format_priority_low(self, formatter: HTMLFormatter) -> None:
        """Test low priority formatting."""
        result = formatter.format_priority_styled("low")
        assert result == "<i>ℹ️ Priority: LOW</i>"
    
    def test_format_priority_normal(self, formatter: HTMLFormatter) -> None:
        """Test normal priority formatting."""
        result = formatter.format_priority_styled("normal")
        assert result == "Priority: NORMAL"
    
    def test_format_tags_styled(self, formatter: HTMLFormatter) -> None:
        """Test styled tags formatting."""
        tags = ["urgent", "test & debug"]
        result = formatter.format_tags_styled(tags)
        assert result == "<i>🏷️ Tags: urgent, test &amp; debug</i>"
    
    def test_format_tags_styled_empty(self, formatter: HTMLFormatter) -> None:
        """Test styled tags formatting with empty list."""
        result = formatter.format_tags_styled([])
        assert result == ""
    
    def test_format_code(self, formatter: HTMLFormatter) -> None:
        """Test code block formatting."""
        code = "print('Hello <world>')"
        result = formatter.format_code(code)
        assert result == "<pre><code>print(&#x27;Hello &lt;world&gt;&#x27;)</code></pre>"
    
    def test_format_inline_code(self, formatter: HTMLFormatter) -> None:
        """Test inline code formatting."""
        code = "variable <name>"
        result = formatter.format_inline_code(code)
        assert result == "<code>variable &lt;name&gt;</code>"
    
    def test_format_link_with_text(self, formatter: HTMLFormatter) -> None:
        """Test link formatting with custom text."""
        url = "https://example.com"
        text = "Example <Site>"
        result = formatter.format_link(url, text)
        assert result == '<a href="https://example.com">Example &lt;Site&gt;</a>'
    
    def test_format_link_without_text(self, formatter: HTMLFormatter) -> None:
        """Test link formatting without custom text."""
        url = "https://example.com"
        result = formatter.format_link(url)
        assert result == '<a href="https://example.com">https://example.com</a>'
    
    def test_format_mention_with_user_id(self, formatter: HTMLFormatter) -> None:
        """Test mention formatting with user ID."""
        username = "test_user"
        user_id = 123456789
        result = formatter.format_mention(username, user_id)
        assert result == '<a href="tg://user?id=123456789">@test_user</a>'
    
    def test_format_mention_without_user_id(self, formatter: HTMLFormatter) -> None:
        """Test mention formatting without user ID."""
        username = "test <user>"
        result = formatter.format_mention(username)
        assert result == "@test &lt;user&gt;"
    
    def test_format_bold(self, formatter: HTMLFormatter) -> None:
        """Test bold text formatting."""
        text = "Bold <text>"
        result = formatter.format_bold(text)
        assert result == "<b>Bold &lt;text&gt;</b>"
    
    def test_format_italic(self, formatter: HTMLFormatter) -> None:
        """Test italic text formatting."""
        text = "Italic <text>"
        result = formatter.format_italic(text)
        assert result == "<i>Italic &lt;text&gt;</i>"
    
    def test_format_underline(self, formatter: HTMLFormatter) -> None:
        """Test underlined text formatting."""
        text = "Underlined <text>"
        result = formatter.format_underline(text)
        assert result == "<u>Underlined &lt;text&gt;</u>"
    
    def test_format_strikethrough(self, formatter: HTMLFormatter) -> None:
        """Test strikethrough text formatting."""
        text = "Strikethrough <text>"
        result = formatter.format_strikethrough(text)
        assert result == "<s>Strikethrough &lt;text&gt;</s>"
    
    def test_message_without_content(self, formatter: HTMLFormatter) -> None:
        """Test formatting message without content."""
        message = Message(title="Title Only", content=" ", priority="normal")  # Minimal content
        result = formatter.format_message(message)
        lines = result.split("\n")
        
        assert "<b>Title Only</b>" in lines
        assert " " in lines  # Space content should be present
    
    def test_message_without_tags(self, formatter: HTMLFormatter) -> None:
        """Test formatting message without tags."""
        message = Message(
            title="Test Title",
            content="Test content",
            priority="normal",
            tags=[]
        )
        result = formatter.format_message(message)
        
        assert "Tags:" not in result
    
    def test_message_without_metadata(self, formatter: HTMLFormatter) -> None:
        """Test formatting message without metadata."""
        message = Message(
            title="Test Title",
            content="Test content",
            priority="normal",
            metadata={}
        )
        result = formatter.format_message(message)
        
        assert "source:" not in result
        assert "version:" not in result