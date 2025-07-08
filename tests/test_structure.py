"""Test project structure and directory layout."""

from __future__ import annotations

import sys
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "mover_status"
TESTS_DIR = PROJECT_ROOT / "tests"


class TestProjectStructure:
    """Test that the project structure matches specifications."""

    def test_project_root_exists(self) -> None:
        """Test that project root directory exists."""
        assert PROJECT_ROOT.exists()
        assert PROJECT_ROOT.is_dir()

    def test_src_directory_structure(self) -> None:
        """Test that source directory structure exists as expected."""
        expected_dirs = [
            "src/mover_status",
            "src/mover_status/app",
            "src/mover_status/config",
            "src/mover_status/config/loader",
            "src/mover_status/config/manager",
            "src/mover_status/config/models",
            "src/mover_status/config/validator",
            "src/mover_status/core",
            "src/mover_status/core/data",
            "src/mover_status/core/data/filesystem",
            "src/mover_status/core/monitor",
            "src/mover_status/core/process",
            "src/mover_status/core/progress",
            "src/mover_status/notifications",
            "src/mover_status/notifications/base",
            "src/mover_status/notifications/manager",
            "src/mover_status/notifications/models",
            "src/mover_status/plugins",
            "src/mover_status/plugins/discord",
            "src/mover_status/plugins/discord/embeds",
            "src/mover_status/plugins/discord/webhook",
            "src/mover_status/plugins/loader",
            "src/mover_status/plugins/telegram",
            "src/mover_status/plugins/telegram/bot",
            "src/mover_status/plugins/telegram/formatting",
            "src/mover_status/plugins/template",
            "src/mover_status/utils",
            "src/mover_status/utils/formatting",
            "src/mover_status/utils/logging",
            "src/mover_status/utils/time",
            "src/mover_status/utils/validation",
        ]
        
        for dir_path in expected_dirs:
            full_path = PROJECT_ROOT / dir_path
            assert full_path.exists(), f"Directory {dir_path} should exist"
            assert full_path.is_dir(), f"{dir_path} should be a directory"

    def test_tests_directory_structure(self) -> None:
        """Test that tests directory structure exists as expected."""
        expected_dirs = [
            "tests",
            "tests/fixtures",
            "tests/integration",
            "tests/integration/e2e",
            "tests/integration/scenarios",
            "tests/unit",
            "tests/unit/app",
            "tests/unit/config",
            "tests/unit/config/loader",
            "tests/unit/config/manager",
            "tests/unit/config/models",
            "tests/unit/config/validator",
            "tests/unit/core",
            "tests/unit/core/data",
            "tests/unit/core/data/filesystem",
            "tests/unit/core/monitor",
            "tests/unit/core/process",
            "tests/unit/core/progress",
            "tests/unit/notifications",
            "tests/unit/notifications/base",
            "tests/unit/notifications/manager",
            "tests/unit/notifications/models",
            "tests/unit/plugins",
            "tests/unit/plugins/discord",
            "tests/unit/plugins/discord/embeds",
            "tests/unit/plugins/discord/webhook",
            "tests/unit/plugins/loader",
            "tests/unit/plugins/telegram",
            "tests/unit/plugins/telegram/bot",
            "tests/unit/plugins/telegram/formatting",
            "tests/unit/plugins/template",
            "tests/unit/utils",
            "tests/unit/utils/formatting",
            "tests/unit/utils/logging",
            "tests/unit/utils/time",
            "tests/unit/utils/validation",
        ]
        
        for dir_path in expected_dirs:
            full_path = PROJECT_ROOT / dir_path
            assert full_path.exists(), f"Directory {dir_path} should exist"
            assert full_path.is_dir(), f"{dir_path} should be a directory"

    def test_config_directory_structure(self) -> None:
        """Test that configuration directory structure exists as expected."""
        expected_dirs = [
            "configs",
            "configs/examples",
        ]
        
        for dir_path in expected_dirs:
            full_path = PROJECT_ROOT / dir_path
            assert full_path.exists(), f"Directory {dir_path} should exist"
            assert full_path.is_dir(), f"{dir_path} should be a directory"

    def test_init_files_exist(self) -> None:
        """Test that all required __init__.py files exist."""
        # Get all Python package directories
        package_dirs: list[Path] = []
        
        # Source package directories
        for root, _, _ in (SRC_DIR.parent).walk():
            if root.name == "__pycache__":
                continue
            # Only include directories that should be Python packages
            if "mover_status" in str(root):
                package_dirs.append(root)
        
        # Test package directories
        for root, _, _ in TESTS_DIR.walk():
            if root.name == "__pycache__":
                continue
            package_dirs.append(root)
        
        # Check that each package directory has an __init__.py file
        for pkg_dir in package_dirs:
            init_file = pkg_dir / "__init__.py"
            assert init_file.exists(), f"Package {pkg_dir} should have __init__.py"
            assert init_file.is_file(), f"__init__.py in {pkg_dir} should be a file"

    def test_required_files_exist(self) -> None:
        """Test that required project files exist."""
        required_files = [
            "pyproject.toml",
            "README.md",
            "LICENSE",
            "CLAUDE.md",
            "src/mover_status/__init__.py",
            "src/mover_status/__main__.py",
            "src/mover_status/config.yaml",
            "tests/conftest.py",
            "configs/examples/config_discord.yaml.example",
            "configs/examples/config_telegram.yaml.example",
        ]
        
        for file_path in required_files:
            full_path = PROJECT_ROOT / file_path
            assert full_path.exists(), f"File {file_path} should exist"
            assert full_path.is_file(), f"{file_path} should be a file"


class TestPyprojectToml:
    """Test pyproject.toml configuration."""

    def test_pyproject_toml_exists(self) -> None:
        """Test that pyproject.toml exists and is valid."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        assert pyproject_path.exists()
        assert pyproject_path.is_file()
        
        # Test that it's readable
        content = pyproject_path.read_text()
        assert len(content) > 0

    def test_python_version_requirement(self) -> None:
        """Test that project requires Python 3.13+."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        content = pyproject_path.read_text()
        assert "requires-python" in content
        assert ">=3.13" in content

    def test_required_dependencies(self) -> None:
        """Test that pyproject.toml contains required dependencies."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        content = pyproject_path.read_text()
        
        required_deps = [
            "pydantic",
            "pyyaml",
            "psutil",
            "httpx",
            "rich",
            "click",
            "python-telegram-bot",
        ]
        
        for dep in required_deps:
            assert dep in content, f"Dependency {dep} should be in pyproject.toml"

    def test_dev_dependencies(self) -> None:
        """Test that pyproject.toml contains required dev dependencies."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        content = pyproject_path.read_text()
        
        dev_deps = [
            "pytest",
            "pytest-cov",
            "pytest-asyncio",
            "pytest-mock",
            "basedpyright",
            "ruff",
        ]
        
        for dep in dev_deps:
            assert dep in content, f"Dev dependency {dep} should be in pyproject.toml"

    def test_pytest_configuration(self) -> None:
        """Test that pytest is configured correctly."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        content = pyproject_path.read_text()
        
        assert "tool.pytest.ini_options" in content
        assert "testpaths" in content
        assert "tests" in content
        assert "--cov=src/mover_status" in content
        assert "--cov-fail-under=100" in content

    def test_basedpyright_configuration(self) -> None:
        """Test that basedpyright is configured correctly."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        content = pyproject_path.read_text()
        
        assert "tool.basedpyright" in content
        assert "pythonVersion" in content
        assert "3.13" in content


class TestCurrentPythonVersion:
    """Test that current Python version meets requirements."""

    def test_python_version_meets_requirements(self) -> None:
        """Test that current Python version is 3.13+."""
        assert sys.version_info >= (3, 13), f"Python 3.13+ required, got {sys.version_info}"

    def test_python_version_info(self) -> None:
        """Test Python version information."""
        version_info = sys.version_info
        assert version_info.major == 3
        assert version_info.minor >= 13