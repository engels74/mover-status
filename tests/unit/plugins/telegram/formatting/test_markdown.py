"""Tests for Markdown message formatters."""

from __future__ import annotations

import pytest
from typing import TYPE_CHECKING

from mover_status.plugins.telegram.formatting.markdown import MarkdownFormatter, MarkdownV2Formatter
from mover_status.notifications.models.message import Message

if TYPE_CHECKING:
    pass


class TestMarkdownFormatter:
    """Test suite for MarkdownFormatter (legacy mode)."""
    
    @pytest.fixture
    def formatter(self) -> MarkdownFormatter:
        """Create Markdown formatter instance for testing."""
        return MarkdownFormatter()
    
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
        """Complex test message with special characters."""
        return Message(
            title="Complex *Test* & Notification",
            content="Content with _underscores_ & *asterisks*",
            priority="urgent",
            tags=["test", "markdown & formatting"],
            metadata={"source": "test [app]", "version": "1.0"}
        )
    
    def test_format_basic_message(self, formatter: MarkdownFormatter, basic_message: Message) -> None:
        """Test formatting a basic message."""
        result = formatter.format_message(basic_message)
        lines = result.split("\n")
        
        assert "*Test Notification*" in lines
        assert "This is a test message\\." in lines
    
    def test_format_complex_message(self, formatter: MarkdownFormatter, complex_message: Message) -> None:
        """Test formatting a complex message with escaping."""
        result = formatter.format_message(complex_message)
        
        # Check title escaping and bold formatting
        assert "*Complex \\*Test\\* \\& Notification*" in result
        
        # Check content escaping
        assert "Content with \\_underscores\\_ \\& \\*asterisks\\*" in result
        
        # Check priority formatting with styling
        assert "*🚨 Priority: URGENT*" in result
        
        # Check tags formatting
        assert "_🏷️ Tags: test, markdown \\& formatting_" in result
        
        # Check metadata formatting
        assert "source: test \\[app\\]" in result
        assert "version: 1\\.0" in result
    
    def test_escape_text(self, formatter: MarkdownFormatter) -> None:
        """Test Markdown text escaping."""
        text = "Text with *bold* _italic_ [links](url) and #headers"
        result = formatter.escape_text(text)
        expected = "Text with \\*bold\\* \\_italic\\_ \\[links\\]\\(url\\) and \\#headers"
        assert result == expected
    
    def test_format_priority_urgent(self, formatter: MarkdownFormatter) -> None:
        """Test urgent priority formatting."""
        result = formatter.format_priority_styled("urgent")
        assert result == "*🚨 Priority: URGENT*"
    
    def test_format_priority_high(self, formatter: MarkdownFormatter) -> None:
        """Test high priority formatting."""
        result = formatter.format_priority_styled("high")
        assert result == "*⚠️ Priority: HIGH*"
    
    def test_format_priority_low(self, formatter: MarkdownFormatter) -> None:
        """Test low priority formatting."""
        result = formatter.format_priority_styled("low")
        assert result == "_ℹ️ Priority: LOW_"
    
    def test_format_priority_normal(self, formatter: MarkdownFormatter) -> None:
        """Test normal priority formatting."""
        result = formatter.format_priority_styled("normal")
        assert result == "Priority: NORMAL"
    
    def test_format_tags_styled(self, formatter: MarkdownFormatter) -> None:
        """Test styled tags formatting."""
        tags = ["urgent", "test & debug"]
        result = formatter.format_tags_styled(tags)
        assert result == "_🏷️ Tags: urgent, test \\& debug_"
    
    def test_format_code(self, formatter: MarkdownFormatter) -> None:
        """Test code block formatting."""
        code = "print('Hello world')"
        result = formatter.format_code(code)
        assert result == "```\nprint('Hello world')\n```"
    
    def test_format_inline_code(self, formatter: MarkdownFormatter) -> None:
        """Test inline code formatting."""
        code = "variable_name"
        result = formatter.format_inline_code(code)
        assert result == "`variable_name`"
    
    def test_format_link_with_text(self, formatter: MarkdownFormatter) -> None:
        """Test link formatting with custom text."""
        url = "https://example.com"
        text = "Example *Site*"
        result = formatter.format_link(url, text)
        assert result == "[Example \\*Site\\*](https://example.com)"
    
    def test_format_link_without_text(self, formatter: MarkdownFormatter) -> None:
        """Test link formatting without custom text."""
        url = "https://example.com"
        result = formatter.format_link(url)
        assert result == "[https://example.com](https://example.com)"
    
    def test_format_mention_with_user_id(self, formatter: MarkdownFormatter) -> None:
        """Test mention formatting with user ID."""
        username = "test_user"
        user_id = 123456789
        result = formatter.format_mention(username, user_id)
        assert result == "[test\\_user](tg://user?id=123456789)"
    
    def test_format_mention_without_user_id(self, formatter: MarkdownFormatter) -> None:
        """Test mention formatting without user ID."""
        username = "test_user"
        result = formatter.format_mention(username)
        assert result == "@test\\_user"
    
    def test_format_bold(self, formatter: MarkdownFormatter) -> None:
        """Test bold text formatting."""
        text = "Bold *text*"
        result = formatter.format_bold(text)
        assert result == "*Bold \\*text\\**"
    
    def test_format_italic(self, formatter: MarkdownFormatter) -> None:
        """Test italic text formatting."""
        text = "Italic _text_"
        result = formatter.format_italic(text)
        assert result == "_Italic \\_text\\__"


class TestMarkdownV2Formatter:
    """Test suite for MarkdownV2Formatter (new mode)."""
    
    @pytest.fixture
    def formatter(self) -> MarkdownV2Formatter:
        """Create MarkdownV2 formatter instance for testing."""
        return MarkdownV2Formatter()
    
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
        """Complex test message with special characters."""
        return Message(
            title="Complex *Test* & Notification",
            content="Content with _underscores_ & *asterisks*",
            priority="urgent",
            tags=["test", "markdownv2 & formatting"],
            metadata={"source": "test [app]", "version": "1.0"}
        )
    
    def test_format_basic_message(self, formatter: MarkdownV2Formatter, basic_message: Message) -> None:
        """Test formatting a basic message."""
        result = formatter.format_message(basic_message)
        lines = result.split("\n")
        
        assert "*Test Notification*" in lines
        assert "This is a test message\\." in lines
    
    def test_format_complex_message(self, formatter: MarkdownV2Formatter, complex_message: Message) -> None:
        """Test formatting a complex message with escaping."""
        result = formatter.format_message(complex_message)
        
        # Check title escaping and bold formatting
        assert "*Complex \\*Test\\* \\& Notification*" in result
        
        # Check content escaping
        assert "Content with \\_underscores\\_ \\& \\*asterisks\\*" in result
        
        # Check priority formatting
        assert "*🚨 Priority: URGENT*" in result
        
        # Check tags formatting
        assert "_🏷️ Tags: test, markdownv2 \\& formatting_" in result
    
    def test_escape_text(self, formatter: MarkdownV2Formatter) -> None:
        """Test MarkdownV2 text escaping."""
        text = "Text with *bold* _italic_ [links](url) and #headers"
        result = formatter.escape_text(text)
        expected = "Text with \\*bold\\* \\_italic\\_ \\[links\\]\\(url\\) and \\#headers"
        assert result == expected
    
    def test_format_priority_urgent(self, formatter: MarkdownV2Formatter) -> None:
        """Test urgent priority formatting."""
        result = formatter.format_priority_styled("urgent")
        assert result == "*🚨 Priority: URGENT*"
    
    def test_format_priority_high(self, formatter: MarkdownV2Formatter) -> None:
        """Test high priority formatting."""
        result = formatter.format_priority_styled("high")
        assert result == "*⚠️ Priority: HIGH*"
    
    def test_format_priority_low(self, formatter: MarkdownV2Formatter) -> None:
        """Test low priority formatting."""
        result = formatter.format_priority_styled("low")
        assert result == "_ℹ️ Priority: LOW_"
    
    def test_format_code(self, formatter: MarkdownV2Formatter) -> None:
        """Test code block formatting."""
        code = "print('Hello world')"
        result = formatter.format_code(code)
        assert result == "```\nprint('Hello world')\n```"
    
    def test_format_inline_code(self, formatter: MarkdownV2Formatter) -> None:
        """Test inline code formatting."""
        code = "variable_name"
        result = formatter.format_inline_code(code)
        assert result == "`variable_name`"
    
    def test_format_underline(self, formatter: MarkdownV2Formatter) -> None:
        """Test underlined text formatting (MarkdownV2 specific)."""
        text = "Underlined text"
        result = formatter.format_underline(text)
        assert result == "__Underlined text__"
    
    def test_format_strikethrough(self, formatter: MarkdownV2Formatter) -> None:
        """Test strikethrough text formatting (MarkdownV2 specific)."""
        text = "Strikethrough text"
        result = formatter.format_strikethrough(text)
        assert result == "~Strikethrough text~"
    
    def test_format_spoiler(self, formatter: MarkdownV2Formatter) -> None:
        """Test spoiler text formatting (MarkdownV2 specific)."""
        text = "Spoiler text"
        result = formatter.format_spoiler(text)
        assert result == "||Spoiler text||"
    
    def test_format_link_with_text(self, formatter: MarkdownV2Formatter) -> None:
        """Test link formatting with custom text."""
        url = "https://example.com"
        text = "Example *Site*"
        result = formatter.format_link(url, text)
        assert result == "[Example \\*Site\\*](https://example.com)"
    
    def test_format_mention_with_user_id(self, formatter: MarkdownV2Formatter) -> None:
        """Test mention formatting with user ID."""
        username = "test_user"
        user_id = 123456789
        result = formatter.format_mention(username, user_id)
        assert result == "[test\\_user](tg://user?id=123456789)"
    
    def test_format_bold(self, formatter: MarkdownV2Formatter) -> None:
        """Test bold text formatting."""
        text = "Bold *text*"
        result = formatter.format_bold(text)
        assert result == "*Bold \\*text\\**"
    
    def test_format_italic(self, formatter: MarkdownV2Formatter) -> None:
        """Test italic text formatting."""
        text = "Italic _text_"
        result = formatter.format_italic(text)
        assert result == "_Italic \\_text\\__"