"""Test suite for exclusion pattern system."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING


from mover_status.core.data.filesystem.exclusions import (
    DefaultExclusionFilter,
    ExactPattern,
    ExclusionFilter,
    ExtensionPattern,
    GitignorePattern,
    GlobPattern,
    PatternType,
    RegexPattern,
)

if TYPE_CHECKING:
    pass


class TestGlobPattern:
    """Test the GlobPattern class."""
    
    def test_glob_pattern_basic_match(self) -> None:
        """Test basic glob pattern matching."""
        pattern = GlobPattern("*.txt")
        
        assert pattern.matches(Path("file.txt"))
        assert not pattern.matches(Path("file.py"))
        assert not pattern.matches(Path("file.TXT"))  # Case sensitive by default
    
    def test_glob_pattern_case_insensitive(self) -> None:
        """Test case-insensitive glob pattern matching."""
        pattern = GlobPattern("*.txt", case_sensitive=False)
        
        assert pattern.matches(Path("file.txt"))
        assert pattern.matches(Path("file.TXT"))
        assert not pattern.matches(Path("file.py"))
    
    def test_glob_pattern_wildcard(self) -> None:
        """Test wildcard pattern matching."""
        pattern = GlobPattern("test*")
        
        assert pattern.matches(Path("test.txt"))
        assert pattern.matches(Path("test123"))
        assert pattern.matches(Path("test"))
        assert not pattern.matches(Path("mytest"))
    
    def test_glob_pattern_question_mark(self) -> None:
        """Test question mark pattern matching."""
        pattern = GlobPattern("file?.txt")
        
        assert pattern.matches(Path("file1.txt"))
        assert pattern.matches(Path("filea.txt"))
        assert not pattern.matches(Path("file12.txt"))
        assert not pattern.matches(Path("file.txt"))
    
    def test_glob_pattern_brackets(self) -> None:
        """Test bracket pattern matching."""
        pattern = GlobPattern("file[0-9].txt")
        
        assert pattern.matches(Path("file1.txt"))
        assert pattern.matches(Path("file9.txt"))
        assert not pattern.matches(Path("filea.txt"))
        assert not pattern.matches(Path("file10.txt"))


class TestRegexPattern:
    """Test the RegexPattern class."""
    
    def test_regex_pattern_basic_match(self) -> None:
        """Test basic regex pattern matching."""
        pattern = RegexPattern(r".*\.txt$")
        
        assert pattern.matches(Path("file.txt"))
        assert pattern.matches(Path("test.txt"))
        assert not pattern.matches(Path("file.py"))
    
    def test_regex_pattern_case_insensitive(self) -> None:
        """Test case-insensitive regex pattern matching."""
        pattern = RegexPattern(r".*\.txt$", case_sensitive=False)
        
        assert pattern.matches(Path("file.txt"))
        assert pattern.matches(Path("file.TXT"))
        assert not pattern.matches(Path("file.py"))
    
    def test_regex_pattern_advanced(self) -> None:
        """Test advanced regex pattern matching."""
        pattern = RegexPattern(r"^temp_\d{3}\.log$")
        
        assert pattern.matches(Path("temp_123.log"))
        assert pattern.matches(Path("temp_999.log"))
        assert not pattern.matches(Path("temp_12.log"))
        assert not pattern.matches(Path("temp_abc.log"))
    
    def test_regex_pattern_unicode(self) -> None:
        """Test regex pattern with unicode characters."""
        pattern = RegexPattern(r".*_\w+\.txt$")
        
        assert pattern.matches(Path("file_test.txt"))
        assert pattern.matches(Path("file_123.txt"))
        assert not pattern.matches(Path("file-.txt"))


class TestExtensionPattern:
    """Test the ExtensionPattern class."""
    
    def test_extension_pattern_basic_match(self) -> None:
        """Test basic extension pattern matching."""
        pattern = ExtensionPattern(".txt")
        
        assert pattern.matches(Path("file.txt"))
        assert not pattern.matches(Path("file.py"))
        assert not pattern.matches(Path("file.TXT"))  # Case sensitive by default
    
    def test_extension_pattern_case_insensitive(self) -> None:
        """Test case-insensitive extension pattern matching."""
        pattern = ExtensionPattern(".txt", case_sensitive=False)
        
        assert pattern.matches(Path("file.txt"))
        assert pattern.matches(Path("file.TXT"))
        assert not pattern.matches(Path("file.py"))
    
    def test_extension_pattern_without_dot(self) -> None:
        """Test extension pattern without leading dot."""
        pattern = ExtensionPattern("txt")
        
        assert pattern.matches(Path("file.txt"))
        assert not pattern.matches(Path("file.py"))
    
    def test_extension_pattern_directory_exclusion(self) -> None:
        """Test that extension patterns don't match directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a directory with .txt in the name
            (temp_path / "test.txt").mkdir()
            
            pattern = ExtensionPattern(".txt")
            
            assert not pattern.matches(temp_path / "test.txt")
    
    def test_extension_pattern_multiple_dots(self) -> None:
        """Test extension pattern with multiple dots."""
        pattern = ExtensionPattern(".gz")
        
        # This should match the last extension only
        assert pattern.matches(Path("file.tar.gz"))
        assert pattern.matches(Path("file.gz"))
        assert not pattern.matches(Path("file.tar"))


class TestExactPattern:
    """Test the ExactPattern class."""
    
    def test_exact_pattern_basic_match(self) -> None:
        """Test basic exact pattern matching."""
        pattern = ExactPattern("config.ini")
        
        assert pattern.matches(Path("config.ini"))
        assert not pattern.matches(Path("config.txt"))
        assert not pattern.matches(Path("myconfig.ini"))
    
    def test_exact_pattern_case_insensitive(self) -> None:
        """Test case-insensitive exact pattern matching."""
        pattern = ExactPattern("config.ini", case_sensitive=False)
        
        assert pattern.matches(Path("config.ini"))
        assert pattern.matches(Path("CONFIG.INI"))
        assert pattern.matches(Path("Config.Ini"))
        assert not pattern.matches(Path("config.txt"))
    
    def test_exact_pattern_with_special_chars(self) -> None:
        """Test exact pattern with special characters."""
        pattern = ExactPattern("test[1].txt")
        
        assert pattern.matches(Path("test[1].txt"))
        assert not pattern.matches(Path("test1.txt"))
        assert not pattern.matches(Path("test[2].txt"))


class TestGitignorePattern:
    """Test the GitignorePattern class."""
    
    def test_gitignore_pattern_basic_match(self) -> None:
        """Test basic gitignore pattern matching."""
        pattern = GitignorePattern("*.log")
        
        assert pattern.matches(Path("test.log"))
        assert pattern.matches(Path("error.log"))
        assert not pattern.matches(Path("test.txt"))
    
    def test_gitignore_pattern_case_insensitive(self) -> None:
        """Test case-insensitive gitignore pattern matching."""
        pattern = GitignorePattern("*.log", case_sensitive=False)
        
        assert pattern.matches(Path("test.log"))
        assert pattern.matches(Path("test.LOG"))
        assert not pattern.matches(Path("test.txt"))
    
    def test_gitignore_pattern_question_mark(self) -> None:
        """Test gitignore pattern with question mark."""
        pattern = GitignorePattern("test?")
        
        assert pattern.matches(Path("test1"))
        assert pattern.matches(Path("testa"))
        assert not pattern.matches(Path("test"))
        assert not pattern.matches(Path("test12"))
    
    def test_gitignore_pattern_directory_only(self) -> None:
        """Test gitignore pattern for directories only."""
        pattern = GitignorePattern("cache/")
        
        assert pattern.matches(Path("cache"))
        assert not pattern.matches(Path("cache.txt"))


class TestExclusionFilter:
    """Test the ExclusionFilter class."""
    
    def test_exclusion_filter_empty(self) -> None:
        """Test empty exclusion filter."""
        filter_obj = ExclusionFilter()
        
        assert filter_obj.get_pattern_count() == 0
        assert not filter_obj.should_exclude(Path("test.txt"))
    
    def test_exclusion_filter_add_pattern(self) -> None:
        """Test adding a single pattern."""
        filter_obj = ExclusionFilter()
        filter_obj.add_pattern("*.txt")
        
        assert filter_obj.get_pattern_count() == 1
        assert filter_obj.should_exclude(Path("test.txt"))
        assert not filter_obj.should_exclude(Path("test.py"))
    
    def test_exclusion_filter_add_patterns(self) -> None:
        """Test adding multiple patterns."""
        filter_obj = ExclusionFilter()
        filter_obj.add_patterns(["*.txt", "*.log"])
        
        assert filter_obj.get_pattern_count() == 2
        assert filter_obj.should_exclude(Path("test.txt"))
        assert filter_obj.should_exclude(Path("error.log"))
        assert not filter_obj.should_exclude(Path("test.py"))
    
    def test_exclusion_filter_add_extensions(self) -> None:
        """Test adding extension patterns."""
        filter_obj = ExclusionFilter()
        filter_obj.add_extensions([".txt", "py"])
        
        assert filter_obj.get_pattern_count() == 2
        assert filter_obj.should_exclude(Path("test.txt"))
        assert filter_obj.should_exclude(Path("script.py"))
        assert not filter_obj.should_exclude(Path("data.json"))
    
    def test_exclusion_filter_add_exact_names(self) -> None:
        """Test adding exact name patterns."""
        filter_obj = ExclusionFilter()
        filter_obj.add_exact_names(["config.ini", "settings.json"])
        
        assert filter_obj.get_pattern_count() == 2
        assert filter_obj.should_exclude(Path("config.ini"))
        assert filter_obj.should_exclude(Path("settings.json"))
        assert not filter_obj.should_exclude(Path("myconfig.ini"))
    
    def test_exclusion_filter_add_regex_patterns(self) -> None:
        """Test adding regex patterns."""
        filter_obj = ExclusionFilter()
        filter_obj.add_regex_patterns([r"temp_\d+\.log"])
        
        assert filter_obj.get_pattern_count() == 1
        assert filter_obj.should_exclude(Path("temp_123.log"))
        assert not filter_obj.should_exclude(Path("temp_abc.log"))
    
    def test_exclusion_filter_add_gitignore_patterns(self) -> None:
        """Test adding gitignore patterns."""
        filter_obj = ExclusionFilter()
        filter_obj.add_gitignore_patterns(["*.tmp", "cache"])
        
        assert filter_obj.get_pattern_count() == 2
        assert filter_obj.should_exclude(Path("test.tmp"))
        assert filter_obj.should_exclude(Path("cache"))
        assert not filter_obj.should_exclude(Path("test.txt"))
    
    def test_exclusion_filter_mixed_patterns(self) -> None:
        """Test mixing different pattern types."""
        filter_obj = ExclusionFilter()
        filter_obj.add_pattern("*.txt", PatternType.GLOB)
        filter_obj.add_pattern(r"temp_\d+\.log", PatternType.REGEX)
        filter_obj.add_pattern("config.ini", PatternType.EXACT)
        
        assert filter_obj.get_pattern_count() == 3
        assert filter_obj.should_exclude(Path("test.txt"))
        assert filter_obj.should_exclude(Path("temp_123.log"))
        assert filter_obj.should_exclude(Path("config.ini"))
        assert not filter_obj.should_exclude(Path("test.py"))
    
    def test_exclusion_filter_case_sensitivity(self) -> None:
        """Test case sensitivity setting."""
        # Case sensitive filter
        filter_sensitive = ExclusionFilter(case_sensitive=True)
        filter_sensitive.add_pattern("*.TXT")
        
        assert filter_sensitive.should_exclude(Path("test.TXT"))
        assert not filter_sensitive.should_exclude(Path("test.txt"))
        
        # Case insensitive filter
        filter_insensitive = ExclusionFilter(case_sensitive=False)
        filter_insensitive.add_pattern("*.TXT")
        
        assert filter_insensitive.should_exclude(Path("test.TXT"))
        assert filter_insensitive.should_exclude(Path("test.txt"))
    
    def test_exclusion_filter_clear(self) -> None:
        """Test clearing all patterns."""
        filter_obj = ExclusionFilter()
        filter_obj.add_patterns(["*.txt", "*.log"])
        
        assert filter_obj.get_pattern_count() == 2
        
        filter_obj.clear()
        
        assert filter_obj.get_pattern_count() == 0
        assert not filter_obj.should_exclude(Path("test.txt"))
    
    def test_exclusion_filter_compile_performance(self) -> None:
        """Test that patterns are compiled for performance."""
        filter_obj = ExclusionFilter()
        filter_obj.add_pattern("*.txt")
        
        # Should compile automatically on first check
        assert filter_obj.should_exclude(Path("test.txt"))
        
        # Manual compile should not raise an error
        filter_obj.compile()
        assert filter_obj.should_exclude(Path("test.txt"))


class TestDefaultExclusionFilter:
    """Test the DefaultExclusionFilter class."""
    
    def test_default_exclusion_filter_initialization(self) -> None:
        """Test default exclusion filter initialization."""
        filter_obj = DefaultExclusionFilter()
        
        # Should have some default patterns
        assert filter_obj.get_pattern_count() > 0
    
    def test_default_exclusion_filter_system_dirs(self) -> None:
        """Test that common system directories are excluded."""
        filter_obj = DefaultExclusionFilter()
        
        # Common system directories should be excluded
        assert filter_obj.should_exclude(Path(".snapshots"))
        assert filter_obj.should_exclude(Path(".Recycle.Bin"))
        assert filter_obj.should_exclude(Path("@eaDir"))
        assert filter_obj.should_exclude(Path("System Volume Information"))
        assert filter_obj.should_exclude(Path("$RECYCLE.BIN"))
        assert filter_obj.should_exclude(Path("lost+found"))
    
    def test_default_exclusion_filter_temp_files(self) -> None:
        """Test that temporary files are excluded."""
        filter_obj = DefaultExclusionFilter()
        
        # Temporary files should be excluded
        assert filter_obj.should_exclude(Path("temp.tmp"))
        assert filter_obj.should_exclude(Path("test.temp"))
        assert filter_obj.should_exclude(Path("thumbs.db"))
        assert filter_obj.should_exclude(Path("desktop.ini"))
    
    def test_default_exclusion_filter_dev_dirs(self) -> None:
        """Test that development directories are excluded."""
        filter_obj = DefaultExclusionFilter()
        
        # Development directories should be excluded
        assert filter_obj.should_exclude(Path(".git"))
        assert filter_obj.should_exclude(Path("node_modules"))
        assert filter_obj.should_exclude(Path("__pycache__"))
        assert filter_obj.should_exclude(Path(".pytest_cache"))
        assert filter_obj.should_exclude(Path("venv"))
    
    def test_default_exclusion_filter_normal_files(self) -> None:
        """Test that normal files are not excluded."""
        filter_obj = DefaultExclusionFilter()
        
        # Normal files should not be excluded
        assert not filter_obj.should_exclude(Path("document.txt"))
        assert not filter_obj.should_exclude(Path("script.py"))
        assert not filter_obj.should_exclude(Path("data.json"))
        assert not filter_obj.should_exclude(Path("image.jpg"))
    
    def test_default_exclusion_filter_case_sensitivity(self) -> None:
        """Test case sensitivity in default filter."""
        filter_sensitive = DefaultExclusionFilter(case_sensitive=True)
        filter_insensitive = DefaultExclusionFilter(case_sensitive=False)
        
        # Case sensitive should not match different cases
        assert filter_sensitive.should_exclude(Path(".git"))
        assert not filter_sensitive.should_exclude(Path(".GIT"))
        
        # Case insensitive should match different cases
        assert filter_insensitive.should_exclude(Path(".git"))
        assert filter_insensitive.should_exclude(Path(".GIT"))
    
    def test_default_exclusion_filter_extensibility(self) -> None:
        """Test that default filter can be extended."""
        filter_obj = DefaultExclusionFilter()
        initial_count = filter_obj.get_pattern_count()
        
        # Add additional patterns
        filter_obj.add_pattern("*.custom")
        
        assert filter_obj.get_pattern_count() == initial_count + 1
        assert filter_obj.should_exclude(Path("test.custom"))


class TestExclusionFilterIntegration:
    """Integration tests for the exclusion filter system."""
    
    def test_exclusion_filter_with_real_filesystem(self) -> None:
        """Test exclusion filter with actual filesystem."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files and directories
            _ = (temp_path / "document.txt").write_text("content")
            _ = (temp_path / "script.py").write_text("code")
            _ = (temp_path / "temp.tmp").write_text("temporary")
            (temp_path / ".git").mkdir()
            _ = (temp_path / ".git" / "config").write_text("git config")
            (temp_path / "node_modules").mkdir()
            _ = (temp_path / "node_modules" / "package.json").write_text("{}")
            
            filter_obj = DefaultExclusionFilter()
            
            # Test exclusions
            assert not filter_obj.should_exclude(temp_path / "document.txt")
            assert not filter_obj.should_exclude(temp_path / "script.py")
            assert filter_obj.should_exclude(temp_path / "temp.tmp")
            assert filter_obj.should_exclude(temp_path / ".git")
            assert filter_obj.should_exclude(temp_path / "node_modules")
    
    def test_exclusion_filter_performance_with_many_patterns(self) -> None:
        """Test performance with many patterns."""
        filter_obj = ExclusionFilter()
        
        # Add many patterns
        for i in range(100):
            filter_obj.add_pattern(f"pattern_{i:03d}*")
        
        # Should still work efficiently
        assert filter_obj.get_pattern_count() == 100
        assert filter_obj.should_exclude(Path("pattern_050_test.txt"))
        assert not filter_obj.should_exclude(Path("other_file.txt"))
    
    def test_exclusion_filter_edge_cases(self) -> None:
        """Test edge cases and boundary conditions."""
        filter_obj = ExclusionFilter()
        
        # Empty pattern
        filter_obj.add_pattern("")
        assert not filter_obj.should_exclude(Path("test.txt"))
        
        # Very long pattern
        long_pattern = "a" * 1000 + "*.txt"
        filter_obj.add_pattern(long_pattern)
        
        # Unicode patterns
        filter_obj.add_pattern("测试*.txt")
        assert filter_obj.should_exclude(Path("测试file.txt"))
        
        # Special characters
        filter_obj.add_pattern("file[!].txt")
        assert filter_obj.should_exclude(Path("file[!].txt"))