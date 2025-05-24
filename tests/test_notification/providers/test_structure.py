"""
Tests for provider package structure standardization.

This module contains tests to verify that all notification providers
follow the standardized package structure and can be imported correctly.
"""

from pathlib import Path

import pytest

from mover_status.notification.base import NotificationProvider


class TestProviderPackageStructure:
    """Tests for standardized provider package structure."""

    def test_provider_package_structure(self) -> None:
        """Test case: Provider package structure."""
        # Define the expected provider structure
        expected_files = [
            "__init__.py",      # Provider registration
            "provider.py",      # Provider implementation
            "formatter.py",     # Provider-specific formatting
            "config.py",        # Provider configuration schema
            "defaults.py"       # Default configuration values
        ]

        # Get the providers directory
        providers_dir = Path(__file__).parent.parent.parent.parent / "mover_status" / "notification" / "providers"

        # Find all provider packages (directories that are not __pycache__)
        provider_packages = [
            d for d in providers_dir.iterdir()
            if d.is_dir() and not d.name.startswith("__pycache__") and not d.name.startswith(".")
        ]

        # Ensure we have at least some providers to test
        assert len(provider_packages) > 0, "No provider packages found"

        # Test each provider package
        for provider_dir in provider_packages:
            provider_name = provider_dir.name

            # Skip base provider files (not packages)
            if provider_name.endswith("_provider.py"):
                continue

            print(f"Testing provider package structure: {provider_name}")

            # Check that all expected files exist
            for expected_file in expected_files:
                file_path = provider_dir / expected_file
                assert file_path.exists(), f"Provider '{provider_name}' is missing required file: {expected_file}"
                assert file_path.is_file(), f"Provider '{provider_name}' has '{expected_file}' but it's not a file"

    def test_provider_module_imports(self) -> None:
        """Test case: Provider module imports."""
        # Test that we can import modules from each provider package
        providers_to_test = ["telegram", "discord", "template"]

        for provider_name in providers_to_test:
            print(f"Testing module imports for provider: {provider_name}")

            # Test importing the provider package
            try:
                provider_module = __import__(f"mover_status.notification.providers.{provider_name}", fromlist=[""])
                assert provider_module is not None
            except ImportError as e:
                pytest.fail(f"Failed to import provider package '{provider_name}': {e}")

            # Test importing the provider class
            try:
                provider_class_module = __import__(
                    f"mover_status.notification.providers.{provider_name}.provider",
                    fromlist=[""]
                )
                assert provider_class_module is not None
            except ImportError as e:
                pytest.fail(f"Failed to import provider class module for '{provider_name}': {e}")

            # Test importing the formatter
            try:
                formatter_module = __import__(
                    f"mover_status.notification.providers.{provider_name}.formatter",
                    fromlist=[""]
                )
                assert formatter_module is not None
            except ImportError as e:
                pytest.fail(f"Failed to import formatter module for '{provider_name}': {e}")

            # Test importing the config
            try:
                config_module = __import__(
                    f"mover_status.notification.providers.{provider_name}.config",
                    fromlist=[""]
                )
                assert config_module is not None
            except ImportError as e:
                pytest.fail(f"Failed to import config module for '{provider_name}': {e}")

            # Test importing the defaults
            try:
                defaults_module = __import__(
                    f"mover_status.notification.providers.{provider_name}.defaults",
                    fromlist=[""]
                )
                assert defaults_module is not None
            except ImportError as e:
                pytest.fail(f"Failed to import defaults module for '{provider_name}': {e}")

    def test_provider_class_availability(self) -> None:
        """Test that each provider package exposes a provider class."""
        providers_to_test = ["telegram", "discord", "template"]

        for provider_name in providers_to_test:
            print(f"Testing provider class availability for: {provider_name}")

            # Import the provider package
            provider_package = __import__(f"mover_status.notification.providers.{provider_name}", fromlist=[""])

            # Check if the package exports the provider class directly
            expected_class_name = f"{provider_name.capitalize()}Provider"
            assert hasattr(provider_package, expected_class_name), \
                f"Provider package '{provider_name}' must export '{expected_class_name}' class"

            # Get the provider class
            provider_class = getattr(provider_package, expected_class_name)

            # Verify it's a class and subclass of NotificationProvider
            assert isinstance(provider_class, type), \
                f"'{expected_class_name}' for '{provider_name}' must be a class"
            assert issubclass(provider_class, NotificationProvider), \
                f"Provider class for '{provider_name}' must be a subclass of NotificationProvider"

    def test_provider_configuration_schema_availability(self) -> None:
        """Test that each provider package exposes configuration schema functions."""
        providers_to_test = ["telegram", "discord", "template"]

        for provider_name in providers_to_test:
            print(f"Testing configuration schema availability for: {provider_name}")

            # Import the config module
            config_module = __import__(
                f"mover_status.notification.providers.{provider_name}.config",
                fromlist=[""]
            )

            # Check for schema function (naming convention: get_{provider}_schema)
            schema_function_name = f"get_{provider_name}_schema"
            assert hasattr(config_module, schema_function_name), \
                f"Config module for '{provider_name}' must have a '{schema_function_name}' function"

            # Check for validation function (naming convention: validate_{provider}_config)
            validation_function_name = f"validate_{provider_name}_config"
            assert hasattr(config_module, validation_function_name), \
                f"Config module for '{provider_name}' must have a '{validation_function_name}' function"

    def test_provider_formatter_availability(self) -> None:
        """Test that each provider package exposes formatter functions."""
        providers_to_test = ["telegram", "discord", "template"]

        for provider_name in providers_to_test:
            print(f"Testing formatter availability for: {provider_name}")

            # Import the formatter module
            formatter_module = __import__(
                f"mover_status.notification.providers.{provider_name}.formatter",
                fromlist=[""]
            )

            # Check for main formatting function (naming convention: format_{provider}_message)
            main_formatter_name = f"format_{provider_name}_message"
            assert hasattr(formatter_module, main_formatter_name), \
                f"Formatter module for '{provider_name}' must have a '{main_formatter_name}' function"

            # Check for ETA formatting function (naming convention: format_{provider}_eta)
            eta_formatter_name = f"format_{provider_name}_eta"
            assert hasattr(formatter_module, eta_formatter_name), \
                f"Formatter module for '{provider_name}' must have a '{eta_formatter_name}' function"

    def test_provider_defaults_availability(self) -> None:
        """Test that each provider package exposes default configuration."""
        providers_to_test = ["telegram", "discord", "template"]

        for provider_name in providers_to_test:
            print(f"Testing defaults availability for: {provider_name}")

            # Import the defaults module
            defaults_module = __import__(
                f"mover_status.notification.providers.{provider_name}.defaults",
                fromlist=[""]
            )

            # Check for default configuration (naming convention: {PROVIDER}_DEFAULTS)
            default_config_name = f"{provider_name.upper()}_DEFAULTS"
            assert hasattr(defaults_module, default_config_name), \
                f"Defaults module for '{provider_name}' must have a '{default_config_name}' constant"

            # Verify it's a dictionary
            default_config = getattr(defaults_module, default_config_name)
            assert isinstance(default_config, dict), \
                f"Default config for '{provider_name}' must be a dictionary"


class TestProviderStructureConsistency:
    """Tests for consistency across all provider packages."""

    def test_all_providers_follow_same_structure(self) -> None:
        """Test that all providers follow the exact same structure."""
        # Get the providers directory
        providers_dir = Path(__file__).parent.parent.parent.parent / "mover_status" / "notification" / "providers"

        # Find all provider packages
        provider_packages = [
            d for d in providers_dir.iterdir()
            if d.is_dir() and not d.name.startswith("__pycache__") and not d.name.startswith(".")
        ]

        # Define the expected structure
        expected_structure = {
            "__init__.py": "file",
            "provider.py": "file",
            "formatter.py": "file",
            "config.py": "file",
            "defaults.py": "file"
        }

        # Test each provider package has the same structure
        for provider_dir in provider_packages:
            provider_name = provider_dir.name

            # Skip base provider files
            if provider_name.endswith("_provider.py"):
                continue

            print(f"Testing structure consistency for: {provider_name}")

            # Get actual structure
            actual_files: set[str] = set()
            for item in provider_dir.iterdir():
                if not item.name.startswith("__pycache__") and not item.name.startswith("."):
                    actual_files.add(item.name)

            # Check that we have exactly the expected files
            expected_files = set(expected_structure.keys())

            missing_files = expected_files - actual_files
            extra_files = actual_files - expected_files

            assert not missing_files, \
                f"Provider '{provider_name}' is missing files: {missing_files}"

            # Allow extra files but warn about them
            if extra_files:
                print(f"Warning: Provider '{provider_name}' has extra files: {extra_files}")

    def test_provider_naming_conventions(self) -> None:
        """Test that providers follow naming conventions."""
        providers_to_test = ["telegram", "discord", "template"]

        for provider_name in providers_to_test:
            print(f"Testing naming conventions for: {provider_name}")

            # Test provider class naming
            provider_module = __import__(
                f"mover_status.notification.providers.{provider_name}.provider",
                fromlist=[""]
            )

            expected_class_name = f"{provider_name.capitalize()}Provider"
            assert hasattr(provider_module, expected_class_name), \
                f"Provider module for '{provider_name}' should have class '{expected_class_name}'"

            # Test formatter function naming
            formatter_module = __import__(
                f"mover_status.notification.providers.{provider_name}.formatter",
                fromlist=[""]
            )

            # Check for main formatting function
            expected_main_formatter = f"format_{provider_name}_message"
            assert hasattr(formatter_module, expected_main_formatter), \
                f"Formatter module for '{provider_name}' should have function '{expected_main_formatter}'"

            # Check for ETA formatting function
            expected_eta_formatter = f"format_{provider_name}_eta"
            assert hasattr(formatter_module, expected_eta_formatter), \
                f"Formatter module for '{provider_name}' should have function '{expected_eta_formatter}'"
