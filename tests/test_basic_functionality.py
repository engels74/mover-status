"""Test basic functionality and integration points."""

from __future__ import annotations

from pathlib import Path


class TestBasicFunctionality:
    """Test basic functionality of the project setup."""

    def test_sample_config_fixture(self, sample_config: dict[str, object]) -> None:
        """Test that sample_config fixture works correctly."""
        assert isinstance(sample_config, dict)
        assert "monitoring" in sample_config
        assert "process" in sample_config
        assert "progress" in sample_config
        assert "notifications" in sample_config
        assert "logging" in sample_config
        
        # Test monitoring section
        monitoring = sample_config["monitoring"]
        assert isinstance(monitoring, dict)
        assert "interval" in monitoring
        assert "detection_timeout" in monitoring
        assert "dry_run" in monitoring
        
        # Test process section
        process = sample_config["process"]
        assert isinstance(process, dict)
        assert "name" in process
        assert "paths" in process
        assert process["name"] == "mover"
        
        # Test progress section
        progress = sample_config["progress"]
        assert isinstance(progress, dict)
        assert "min_change_threshold" in progress
        assert "estimation_window" in progress
        assert "exclusions" in progress
        
        # Test notifications section
        notifications = sample_config["notifications"]
        assert isinstance(notifications, dict)
        assert "enabled_providers" in notifications
        assert "events" in notifications
        assert "rate_limits" in notifications
        
        # Test logging section
        logging = sample_config["logging"]
        assert isinstance(logging, dict)
        assert "level" in logging
        assert "format" in logging
        assert "file" in logging

    def test_temp_dir_fixture(self, temp_dir: Path) -> None:
        """Test that temp_dir fixture works correctly."""
        assert isinstance(temp_dir, Path)
        assert temp_dir.exists()
        assert temp_dir.is_dir()
        
        # Create a test file in the temp directory
        test_file = temp_dir / "test.txt"
        _ = test_file.write_text("test content")
        
        assert test_file.exists()
        assert test_file.read_text() == "test content"

    def test_config_file_exists(self) -> None:
        """Test that the config.yaml file exists."""
        config_path = Path(__file__).parent.parent / "src" / "mover_status" / "config.yaml"
        assert config_path.exists()
        assert config_path.is_file()

    def test_example_config_files_exist(self) -> None:
        """Test that example configuration files exist."""
        project_root = Path(__file__).parent.parent
        
        discord_example = project_root / "configs" / "examples" / "config_discord.yaml.example"
        telegram_example = project_root / "configs" / "examples" / "config_telegram.yaml.example"
        
        assert discord_example.exists()
        assert telegram_example.exists()
        
        # Check that they have content
        discord_content = discord_example.read_text()
        telegram_content = telegram_example.read_text()
        assert len(discord_content) > 0
        assert len(telegram_content) > 0


    def test_plugin_template_documentation(self) -> None:
        """Test that plugin template documentation exists."""
        project_root = Path(__file__).parent.parent
        
        template_readme = project_root / "src" / "mover_status" / "plugins" / "template" / "README.md"
        assert template_readme.exists()
        
        # Check that it has content
        content = template_readme.read_text()
        assert len(content) > 0
        assert "Plugin Template" in content or "template" in content.lower()


class TestProjectConfiguration:
    """Test project configuration and setup."""

    def test_project_name_consistency(self) -> None:
        """Test that project name is consistent across files."""
        project_root = Path(__file__).parent.parent
        
        # Check pyproject.toml
        pyproject = project_root / "pyproject.toml"
        pyproject_content = pyproject.read_text()
        
        # Should contain the project name
        assert "mover-status" in pyproject_content
        assert "name = \"mover-status\"" in pyproject_content

    def test_python_version_consistency(self) -> None:
        """Test that Python version is consistent across configuration files."""
        project_root = Path(__file__).parent.parent
        
        # Check pyproject.toml
        pyproject = project_root / "pyproject.toml"
        pyproject_content = pyproject.read_text()
        
        # Should require Python 3.13
        assert "requires-python = \">=3.13\"" in pyproject_content
        assert "pythonVersion = \"3.13\"" in pyproject_content

    def test_test_configuration(self) -> None:
        """Test that test configuration is set up correctly."""
        project_root = Path(__file__).parent.parent
        
        # Check pyproject.toml
        pyproject = project_root / "pyproject.toml"
        pyproject_content = pyproject.read_text()
        
        # Should have pytest configuration
        assert "tool.pytest.ini_options" in pyproject_content
        assert "testpaths = [\"tests\"]" in pyproject_content
        assert "--cov=src/mover_status" in pyproject_content
        assert "--cov-fail-under=100" in pyproject_content

    def test_type_checking_configuration(self) -> None:
        """Test that type checking is configured correctly."""
        project_root = Path(__file__).parent.parent
        
        # Check pyproject.toml
        pyproject = project_root / "pyproject.toml"
        pyproject_content = pyproject.read_text()
        
        # Should have basedpyright configuration
        assert "tool.basedpyright" in pyproject_content
        assert "pythonVersion = \"3.13\"" in pyproject_content
        assert "typeCheckingMode = \"recommended\"" in pyproject_content