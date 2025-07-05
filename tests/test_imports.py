"""Test module imports and package functionality."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

# Add src to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))


class TestCoreImports:
    """Test that core modules can be imported successfully."""

    def test_import_main_package(self) -> None:
        """Test that main package can be imported."""
        import mover_status
        assert mover_status is not None
        assert isinstance(mover_status, ModuleType)

    def test_import_app_module(self) -> None:
        """Test that app module can be imported."""
        import mover_status.app
        assert mover_status.app is not None
        assert isinstance(mover_status.app, ModuleType)

    def test_import_config_modules(self) -> None:
        """Test that config modules can be imported."""
        import mover_status.config
        import mover_status.config.loader
        import mover_status.config.manager
        import mover_status.config.models
        import mover_status.config.validator
        
        assert mover_status.config is not None
        assert mover_status.config.loader is not None
        assert mover_status.config.manager is not None
        assert mover_status.config.models is not None
        assert mover_status.config.validator is not None

    def test_import_core_modules(self) -> None:
        """Test that core modules can be imported."""
        import mover_status.core
        import mover_status.core.data
        import mover_status.core.data.filesystem
        import mover_status.core.monitor
        import mover_status.core.process
        import mover_status.core.progress
        
        assert mover_status.core is not None
        assert mover_status.core.data is not None
        assert mover_status.core.data.filesystem is not None
        assert mover_status.core.monitor is not None
        assert mover_status.core.process is not None
        assert mover_status.core.progress is not None

    def test_import_notifications_modules(self) -> None:
        """Test that notifications modules can be imported."""
        import mover_status.notifications
        import mover_status.notifications.base
        import mover_status.notifications.manager
        import mover_status.notifications.models
        
        assert mover_status.notifications is not None
        assert mover_status.notifications.base is not None
        assert mover_status.notifications.manager is not None
        assert mover_status.notifications.models is not None

    def test_import_plugins_modules(self) -> None:
        """Test that plugins modules can be imported."""
        import mover_status.plugins
        import mover_status.plugins.discord
        import mover_status.plugins.discord.embeds
        import mover_status.plugins.discord.webhook
        import mover_status.plugins.loader
        import mover_status.plugins.telegram
        import mover_status.plugins.telegram.bot
        import mover_status.plugins.telegram.formatting
        import mover_status.plugins.template
        
        assert mover_status.plugins is not None
        assert mover_status.plugins.discord is not None
        assert mover_status.plugins.discord.embeds is not None
        assert mover_status.plugins.discord.webhook is not None
        assert mover_status.plugins.loader is not None
        assert mover_status.plugins.telegram is not None
        assert mover_status.plugins.telegram.bot is not None
        assert mover_status.plugins.telegram.formatting is not None
        assert mover_status.plugins.template is not None

    def test_import_utils_modules(self) -> None:
        """Test that utils modules can be imported."""
        import mover_status.utils
        import mover_status.utils.formatting
        import mover_status.utils.logging
        import mover_status.utils.time
        import mover_status.utils.validation
        
        assert mover_status.utils is not None
        assert mover_status.utils.formatting is not None
        assert mover_status.utils.logging is not None
        assert mover_status.utils.time is not None
        assert mover_status.utils.validation is not None


class TestPackageAttributes:
    """Test that packages have expected attributes."""

    def test_main_package_attributes(self) -> None:
        """Test that main package has expected attributes."""
        import mover_status
        
        # Check for version info
        assert hasattr(mover_status, "__version__")
        assert hasattr(mover_status, "__author__")
        assert hasattr(mover_status, "__description__")
        
        # Check for main function
        assert hasattr(mover_status, "main")
        assert callable(mover_status.main)

    def test_package_docstrings(self) -> None:
        """Test that packages have docstrings."""
        import mover_status
        import mover_status.app
        import mover_status.config
        import mover_status.core
        import mover_status.notifications
        import mover_status.plugins
        import mover_status.utils
        
        modules_with_docstrings = [
            mover_status,
            mover_status.app,
            mover_status.config,
            mover_status.core,
            mover_status.notifications,
            mover_status.plugins,
            mover_status.utils,
        ]
        
        for module in modules_with_docstrings:
            assert module.__doc__ is not None, f"Module {module.__name__} should have a docstring"
            assert len(module.__doc__.strip()) > 0, f"Module {module.__name__} docstring should not be empty"

    def test_package_all_exports(self) -> None:
        """Test that packages have __all__ exports defined."""
        import mover_status
        import mover_status.app
        import mover_status.config
        import mover_status.core
        import mover_status.notifications
        import mover_status.plugins
        import mover_status.utils
        
        modules_with_all = [
            mover_status,
            mover_status.app,
            mover_status.config,
            mover_status.core,
            mover_status.notifications,
            mover_status.plugins,
            mover_status.utils,
        ]
        
        for module in modules_with_all:
            assert hasattr(module, "__all__"), f"Module {module.__name__} should have __all__ defined"
            all_exports = getattr(module, "__all__", None)
            assert isinstance(all_exports, list), f"Module {module.__name__} __all__ should be a list"


class TestModuleStructure:
    """Test module structure and organization."""

    def test_no_circular_imports(self) -> None:
        """Test that there are no circular imports."""
        # This test passes if all imports above succeed without errors
        # Circular imports would cause ImportError or AttributeError
        import mover_status
        import mover_status.app
        import mover_status.config
        import mover_status.core
        import mover_status.notifications
        import mover_status.plugins
        import mover_status.utils
        
        # If we get here, no circular imports were detected
        modules = [
            mover_status,
            mover_status.app,
            mover_status.config,
            mover_status.core,
            mover_status.notifications,
            mover_status.plugins,
            mover_status.utils,
        ]
        assert len(modules) == 7  # Verify all modules were imported successfully

    def test_module_paths_match_structure(self) -> None:
        """Test that module paths match expected directory structure."""
        import mover_status
        import mover_status.app
        import mover_status.config.loader
        import mover_status.core.data.filesystem
        import mover_status.plugins.discord.embeds
        import mover_status.utils.formatting
        
        # Test that module names match expected structure
        assert mover_status.__name__ == "mover_status"
        assert mover_status.app.__name__ == "mover_status.app"
        assert mover_status.config.loader.__name__ == "mover_status.config.loader"
        assert mover_status.core.data.filesystem.__name__ == "mover_status.core.data.filesystem"
        assert mover_status.plugins.discord.embeds.__name__ == "mover_status.plugins.discord.embeds"
        assert mover_status.utils.formatting.__name__ == "mover_status.utils.formatting"

    def test_import_from_main_package(self) -> None:
        """Test that main functions can be imported from the main package."""
        from mover_status import main
        
        assert main is not None
        assert callable(main)


class TestTestsImports:
    """Test that test modules can be imported."""

    def test_import_tests_package(self) -> None:
        """Test that tests package can be imported."""
        import tests
        assert tests is not None
        assert isinstance(tests, ModuleType)

    def test_import_conftest(self) -> None:
        """Test that conftest can be imported."""
        import tests.conftest
        assert tests.conftest is not None
        assert isinstance(tests.conftest, ModuleType)

    def test_conftest_has_fixtures(self) -> None:
        """Test that conftest has expected fixtures."""
        import tests.conftest
        
        # Check for expected fixture functions
        assert hasattr(tests.conftest, "temp_dir")
        assert hasattr(tests.conftest, "sample_config")
        assert callable(tests.conftest.temp_dir)
        assert callable(tests.conftest.sample_config)