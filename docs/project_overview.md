# Mover Status Monitor - Python 3.13 Project Overview (Updated)

## Project Structure

```
mover_status/
│
├── pyproject.toml           # Project metadata and dependencies
├── README.md                # Project documentation
├── .gitignore               # Git ignore file
│
├── mover_status/            # Main package
│   ├── __init__.py          # Package initialization with clean public API
│   ├── __main__.py          # Entry point for running as module
│   ├── application.py       # Main application class
│   ├── cli.py               # Command line interface handling
│   │
│   ├── config/              # Configuration management
│   │   ├── __init__.py
│   │   ├── loader.py        # Configuration loading/saving
│   │   ├── validator.py     # Configuration validation
│   │   ├── registry.py      # Configuration schema registry
│   │   ├── schema.py        # Configuration schema system
│   │   └── default_config.py # Core default configuration values
│   │
│   ├── core/                # Core functionality
│   │   ├── __init__.py
│   │   ├── monitor.py       # Main monitoring logic
│   │   ├── version.py       # Version checking
│   │   │
│   │   └── calculation/     # Separate calculation module
│   │       ├── __init__.py
│   │       ├── progress.py  # Calculate progress percentages
│   │       ├── time.py      # ETA and time-related calculations
│   │       └── size.py      # Data size formatting and calculations
│   │
│   ├── notification/        # Notification system
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract base class for notifications
│   │   ├── manager.py       # Manages notification providers
│   │   ├── formatter.py     # Common message formatting
│   │   ├── registry.py      # Provider registry for discovery
│   │   │
│   │   └── providers/       # Individual notification providers
│   │       ├── __init__.py  # Provider discovery mechanism
│   │       ├── base_provider.py    # Base provider with common functionality
│   │       ├── webhook_provider.py # Base class for webhook-based providers
│   │       ├── api_provider.py     # Base class for API-based providers
│   │       │
│   │       ├── template/    # Template for creating new providers
│   │       │   ├── __init__.py     # Provider registration
│   │       │   ├── provider.py     # Provider implementation
│   │       │   ├── formatter.py    # Provider-specific formatting
│   │       │   ├── config.py       # Provider configuration schema
│   │       │   ├── defaults.py     # Default configuration values
│   │       │   └── manifest.py     # Provider plugin manifest
│   │       │
│   │       ├── telegram/
│   │       │   ├── __init__.py     # Provider registration
│   │       │   ├── provider.py     # Telegram implementation
│   │       │   ├── formatter.py    # Telegram-specific formatting
│   │       │   ├── config.py       # Telegram configuration schema
│   │       │   ├── defaults.py     # Default configuration values
│   │       │   └── manifest.py     # Telegram plugin manifest
│   │       │
│   │       └── discord/
│   │           ├── __init__.py     # Provider registration
│   │           ├── provider.py     # Discord implementation
│   │           ├── formatter.py    # Discord-specific formatting
│   │           ├── config.py       # Discord configuration schema
│   │           ├── defaults.py     # Default configuration values
│   │           └── manifest.py     # Discord plugin manifest
│   │
│   ├── plugin/              # Plugin system
│   │   ├── __init__.py
│   │   ├── base.py          # Plugin base class
│   │   ├── registry.py      # Plugin registry
│   │   ├── manager.py       # Plugin lifecycle management
│   │   └── config.py        # Plugin configuration
│   │
│   └── utils/               # Utility functions
│       ├── __init__.py
│       ├── logger.py        # Logging utilities
│       ├── data.py          # Data size conversion utilities
│       └── process.py       # Process monitoring utilities
│
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── conftest.py          # Test fixtures and configuration
│   ├── test_application.py  # Tests for application class
│   ├── test_cli.py          # Tests for CLI
│   ├── test_init.py         # Tests for package initialization
│   │
│   ├── test_config/         # Tests for configuration
│   │   ├── test_loader.py
│   │   ├── test_validator.py
│   │   ├── test_registry.py
│   │   ├── test_schema.py
│   │   └── test_default_config.py
│   │
│   ├── test_core/           # Tests for core functionality
│   │   ├── test_monitor.py
│   │   ├── test_version.py
│   │   └── test_calculation/
│   │       ├── test_progress.py
│   │       ├── test_time.py
│   │       └── test_size.py
│   │
│   ├── test_notification/   # Tests for notification system
│   │   ├── test_base.py
│   │   ├── test_manager.py
│   │   ├── test_formatter.py
│   │   ├── test_registry.py
│   │   │
│   │   └── providers/
│   │       ├── test_base_provider.py
│   │       ├── test_webhook_provider.py
│   │       ├── test_api_provider.py
│   │       ├── test_structure.py
│   │       ├── test_template.py
│   │       ├── test_telegram.py
│   │       ├── test_discord.py
│   │       └── test_*_manifest.py
│   │
│   ├── test_plugin/         # Tests for plugin system
│   │   ├── test_base.py
│   │   ├── test_registry.py
│   │   ├── test_manager.py
│   │   └── test_config.py
│   │
│   └── test_utils/          # Tests for utilities
│       ├── test_logger.py
│       ├── test_data.py
│       └── test_process.py
│
└── docs/                    # Documentation
    ├── development_plan.md
    ├── project_overview.md
    ├── refactoring_plan.md
    └── provider_development_guide.md
```

## File Descriptions

### Project Configuration

- **pyproject.toml**: Defines project metadata, dependencies, and build configuration using modern Python packaging standards.
- **README.md**: Project documentation with installation, usage, and configuration instructions.
- **.gitignore**: Specifies intentionally untracked files to ignore in Git.

### Core Package

#### Root Files

- **mover_status/\_\_init\_\_.py**: Package initialization with a clean public API that doesn't contain hardcoded provider references.
- **mover_status/\_\_main\_\_.py**: Entry point that allows running the package as a module with `python -m mover_status`.
- **mover_status/application.py**: Main application class that handles initialization, provider loading, and application lifecycle.
- **mover_status/cli.py**: Command line interface handling with support for provider-specific options.

#### Configuration System

- **config/\_\_init\_\_.py**: Exports configuration functionality.
- **config/loader.py**: Handles loading and saving configuration from YAML files.
- **config/validator.py**: Validates configuration against schemas.
- **config/registry.py**: Manages provider-specific configuration schemas.
- **config/schema.py**: Configuration schema system for validation.
- **config/default_config.py**: Defines core default configuration values without provider-specific types.

#### Core Functionality

- **core/\_\_init\_\_.py**: Exports core monitoring functionality.
- **core/monitor.py**: Implements the main monitoring loop that watches the mover process and tracks progress.
- **core/version.py**: Handles version checking and update notifications.
- **core/calculation/\_\_init\_\_.py**: Exports calculation functions.
- **core/calculation/progress.py**: Calculates progress percentages based on current/initial data sizes.
- **core/calculation/time.py**: Calculates estimated completion times based on progress rate.
- **core/calculation/size.py**: Handles data size calculations and conversions to human-readable formats.

#### Notification System

- **notification/\_\_init\_\_.py**: Exports notification functionality.
- **notification/base.py**: Abstract base class defining the interface all notification providers must implement.
- **notification/manager.py**: Manages the lifecycle of notification providers and routes messages.
- **notification/formatter.py**: Common message formatting logic shared across providers.
- **notification/registry.py**: Provider registry for discovery and registration.

- **notification/providers/\_\_init\_\_.py**: Provider discovery mechanism.
- **notification/providers/base_provider.py**: Base provider with common functionality.
- **notification/providers/webhook_provider.py**: Base class for webhook-based providers.
- **notification/providers/api_provider.py**: Base class for API-based providers.

- **notification/providers/{provider}/\_\_init\_\_.py**: Provider registration with the registry.
- **notification/providers/{provider}/provider.py**: Provider-specific implementation.
- **notification/providers/{provider}/formatter.py**: Provider-specific message formatting.
- **notification/providers/{provider}/config.py**: Provider configuration schema.
- **notification/providers/{provider}/defaults.py**: Default configuration values.
- **notification/providers/{provider}/manifest.py**: Provider plugin manifest.

#### Plugin System

- **plugin/\_\_init\_\_.py**: Exports plugin functionality.
- **plugin/base.py**: Plugin base class defining the interface all plugins must implement.
- **plugin/registry.py**: Plugin registry for discovery and registration.
- **plugin/manager.py**: Plugin lifecycle management (load, initialize, validate, run).
- **plugin/config.py**: Plugin configuration system.

#### Utilities

- **utils/\_\_init\_\_.py**: Exports utility functions.
- **utils/logger.py**: Configurable logging setup with console and file outputs.
- **utils/data.py**: Data conversion utilities.
- **utils/process.py**: Utilities for monitoring system processes.

### Tests

- **tests/\_\_init\_\_.py**: Package initialization for test suite.
- **tests/conftest.py**: PyTest fixtures and test configuration.
- **tests/test_\*/**: Test modules that mirror the package structure.

### Documentation

- **docs/development_plan.md**: Original development plan.
- **docs/project_overview.md**: Project structure and design overview.
- **docs/refactoring_plan.md**: Refactoring plan with TDD approach.
- **docs/provider_development_guide.md**: Guide for developing new notification providers.
