# Python Mover Status Monitor - Complete Project Specification

## Project Description
A modern, modular Python 3.13 application that monitors the Unraid mover process, calculates progress metrics, and delivers status notifications through a plugin-based provider system. The application emphasizes extensibility, maintainability, and clean architecture principles.

## Core Requirements
- **Python 3.13** with full type annotations
- **uv** for project and dependency management
- **basedpyright** with recommended severity for static type checking
- **pytest** with 100% test coverage requirement
- **YAML-based configuration** with environment variable overrides
- **Plugin-based notification system** with provider isolation
- **TDD approach** with corresponding test files for all modules

## Complete Project Tree

```
.
├── LICENSE
├── README.md
├── mover-status.svg
├── pyproject.toml
├── src/
│   └── mover_status/
│       ├── __init__.py
│       ├── __main__.py
│       ├── config.yaml
│       ├── app/
│       │   ├── __init__.py
│       │   ├── application.py
│       │   ├── cli.py
│       │   └── runner.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── monitor/
│       │   │   ├── __init__.py
│       │   │   ├── orchestrator.py
│       │   │   ├── state_machine.py
│       │   │   └── event_bus.py
│       │   ├── process/
│       │   │   ├── __init__.py
│       │   │   ├── detector.py
│       │   │   ├── unraid_detector.py
│       │   │   └── models.py
│       │   ├── progress/
│       │   │   ├── __init__.py
│       │   │   ├── calculator.py
│       │   │   ├── estimator.py
│       │   │   ├── tracker.py
│       │   │   └── models.py
│       │   └── data/
│       │       ├── __init__.py
│       │       ├── collector.py
│       │       ├── filesystem/
│       │       │   ├── __init__.py
│       │       │   ├── scanner.py
│       │       │   ├── size_calculator.py
│       │       │   └── exclusions.py
│       │       └── models.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── loader/
│       │   │   ├── __init__.py
│       │   │   ├── yaml_loader.py
│       │   │   ├── env_loader.py
│       │   │   └── merger.py
│       │   ├── validator/
│       │   │   ├── __init__.py
│       │   │   ├── schema_validator.py
│       │   │   ├── rules.py
│       │   │   └── errors.py
│       │   ├── manager/
│       │   │   ├── __init__.py
│       │   │   ├── config_manager.py
│       │   │   └── provider_configs.py
│       │   └── models/
│       │       ├── __init__.py
│       │       ├── base.py
│       │       ├── main_config.py
│       │       └── provider_config.py
│       ├── notifications/
│       │   ├── __init__.py
│       │   ├── manager/
│       │   │   ├── __init__.py
│       │   │   ├── notification_manager.py
│       │   │   ├── provider_registry.py
│       │   │   └── dispatcher.py
│       │   ├── base/
│       │   │   ├── __init__.py
│       │   │   ├── provider.py
│       │   │   ├── exceptions.py
│       │   │   └── retry.py
│       │   └── models/
│       │       ├── __init__.py
│       │       ├── status.py
│       │       ├── message.py
│       │       └── event.py
│       ├── plugins/
│       │   ├── __init__.py
│       │   ├── loader/
│       │   │   ├── __init__.py
│       │   │   ├── plugin_loader.py
│       │   │   ├── validator.py
│       │   │   └── exceptions.py
│       │   ├── template/
│       │   │   ├── __init__.py
│       │   │   ├── provider.py
│       │   │   ├── config.py
│       │   │   ├── models.py
│       │   │   └── README.md
│       │   ├── discord/
│       │   │   ├── __init__.py
│       │   │   ├── provider.py
│       │   │   ├── config.py
│       │   │   ├── models.py
│       │   │   ├── webhook/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── client.py
│       │   │   │   └── formatter.py
│       │   │   └── embeds/
│       │   │       ├── __init__.py
│       │   │       ├── builder.py
│       │   │       └── colors.py
│       │   └── telegram/
│       │       ├── __init__.py
│       │       ├── provider.py
│       │       ├── config.py
│       │       ├── models.py
│       │       ├── bot/
│       │       │   ├── __init__.py
│       │       │   ├── client.py
│       │       │   └── api.py
│       │       └── formatting/
│       │           ├── __init__.py
│       │           ├── html_formatter.py
│       │           └── markdown_formatter.py
│       └── utils/
│           ├── __init__.py
│           ├── formatting/
│           │   ├── __init__.py
│           │   ├── size_formatter.py
│           │   ├── time_formatter.py
│           │   └── percentage_formatter.py
│           ├── time/
│           │   ├── __init__.py
│           │   ├── calculator.py
│           │   ├── timezone.py
│           │   └── relative.py
│           ├── logging/
│           │   ├── __init__.py
│           │   ├── logger.py
│           │   ├── formatters.py
│           │   └── handlers.py
│           └── validation/
│               ├── __init__.py
│               ├── validators.py
│               └── sanitizers.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── __init__.py
│   │   ├── filesystem.py
│   │   ├── process.py
│   │   ├── config.py
│   │   └── plugins.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── test_application.py
│   │   │   ├── test_cli.py
│   │   │   └── test_runner.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── monitor/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_orchestrator.py
│   │   │   │   ├── test_state_machine.py
│   │   │   │   └── test_event_bus.py
│   │   │   ├── process/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_detector.py
│   │   │   │   ├── test_unraid_detector.py
│   │   │   │   └── test_models.py
│   │   │   ├── progress/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_calculator.py
│   │   │   │   ├── test_estimator.py
│   │   │   │   ├── test_tracker.py
│   │   │   │   └── test_models.py
│   │   │   └── data/
│   │   │       ├── __init__.py
│   │   │       ├── test_collector.py
│   │   │       ├── filesystem/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── test_scanner.py
│   │   │       │   ├── test_size_calculator.py
│   │   │       │   └── test_exclusions.py
│   │   │       └── test_models.py
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── loader/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_yaml_loader.py
│   │   │   │   ├── test_env_loader.py
│   │   │   │   └── test_merger.py
│   │   │   ├── validator/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_schema_validator.py
│   │   │   │   ├── test_rules.py
│   │   │   │   └── test_errors.py
│   │   │   ├── manager/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_config_manager.py
│   │   │   │   └── test_provider_configs.py
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── test_base.py
│   │   │       ├── test_main_config.py
│   │   │       └── test_provider_config.py
│   │   ├── notifications/
│   │   │   ├── __init__.py
│   │   │   ├── manager/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_notification_manager.py
│   │   │   │   ├── test_provider_registry.py
│   │   │   │   └── test_dispatcher.py
│   │   │   ├── base/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_provider.py
│   │   │   │   ├── test_exceptions.py
│   │   │   │   └── test_retry.py
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── test_status.py
│   │   │       ├── test_message.py
│   │   │       └── test_event.py
│   │   ├── plugins/
│   │   │   ├── __init__.py
│   │   │   ├── loader/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_plugin_loader.py
│   │   │   │   ├── test_validator.py
│   │   │   │   └── test_exceptions.py
│   │   │   ├── template/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_provider.py
│   │   │   │   ├── test_config.py
│   │   │   │   └── test_models.py
│   │   │   ├── discord/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_provider.py
│   │   │   │   ├── test_config.py
│   │   │   │   ├── test_models.py
│   │   │   │   ├── webhook/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── test_client.py
│   │   │   │   │   └── test_formatter.py
│   │   │   │   └── embeds/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── test_builder.py
│   │   │   │       └── test_colors.py
│   │   │   └── telegram/
│   │   │       ├── __init__.py
│   │   │       ├── test_provider.py
│   │   │       ├── test_config.py
│   │   │       ├── test_models.py
│   │   │       ├── bot/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── test_client.py
│   │   │       │   └── test_api.py
│   │   │       └── formatting/
│   │   │           ├── __init__.py
│   │   │           ├── test_html_formatter.py
│   │   │           └── test_markdown_formatter.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── formatting/
│   │       │   ├── __init__.py
│   │       │   ├── test_size_formatter.py
│   │       │   ├── test_time_formatter.py
│   │       │   └── test_percentage_formatter.py
│   │       ├── time/
│   │       │   ├── __init__.py
│   │       │   ├── test_calculator.py
│   │       │   ├── test_timezone.py
│   │       │   └── test_relative.py
│   │       ├── logging/
│   │       │   ├── __init__.py
│   │       │   ├── test_logger.py
│   │       │   ├── test_formatters.py
│   │       │   └── test_handlers.py
│   │       └── validation/
│   │           ├── __init__.py
│   │           ├── test_validators.py
│   │           └── test_sanitizers.py
│   └── integration/
│       ├── __init__.py
│       ├── scenarios/
│       │   ├── __init__.py
│       │   ├── test_full_cycle.py
│       │   ├── test_plugin_lifecycle.py
│       │   ├── test_config_changes.py
│       │   └── test_failure_recovery.py
│       └── e2e/
│           ├── __init__.py
│           ├── test_dry_run.py
│           └── test_notification_flow.py
└── configs/
    ├── examples/
    │   ├── config_discord.yaml.example
    │   └── config_telegram.yaml.example
    └── schemas/
        ├── main_config_schema.json
        └── provider_config_schema.json
```

## Component Descriptions

### Root Level
- **`__main__.py`**: Entry point that bootstraps the application, initializes dependency injection container, handles uncaught exceptions, and delegates to the application runner
- **`config.yaml`**: Main configuration file containing core settings, enabled providers list, monitoring intervals, and global exclusion paths

### `app/` - Application Layer
- **`application.py`**: Main application class implementing dependency injection container, lifecycle management hooks, and coordinating all subsystems initialization
- **`cli.py`**: Command-line interface parser using argparse, handling --dry-run flag, environment variable processing, and configuration file path resolution
- **`runner.py`**: Application execution orchestrator managing startup sequence, graceful shutdown handling, signal interception, and main event loop coordination

### `core/` - Core Business Logic

#### `monitor/` - Monitoring Orchestration
- **`orchestrator.py`**: Central monitoring coordinator implementing the main monitoring loop, coordinating between process detection, data collection, progress calculation, and notification dispatch
- **`state_machine.py`**: Finite state machine managing monitoring states (idle, starting, monitoring, completing), enforcing valid state transitions, and triggering appropriate actions
- **`event_bus.py`**: Publisher-subscriber event system for decoupled communication between components, supporting async event handling and priority-based event processing

#### `process/` - Process Management
- **`detector.py`**: Abstract base class defining process detection interface with methods for checking process existence, getting process info, and monitoring state changes
- **`unraid_detector.py`**: Concrete implementation for Unraid mover process detection using psutil or proc filesystem, handling process matching by executable path
- **`models.py`**: Data classes for process information including PID, command line, start time, and state enumeration

#### `progress/` - Progress Tracking
- **`calculator.py`**: Progress percentage calculation based on initial and current data sizes, handling edge cases like zero-size transfers
- **`estimator.py`**: ETC estimation using moving average algorithms, adaptive estimation based on transfer rate history, and handling variable transfer speeds
- **`tracker.py`**: Historical progress tracking for trend analysis, maintaining sliding window of progress samples, and providing progress velocity calculations
- **`models.py`**: Progress data structures including percentage, bytes remaining, transfer rate, and estimated completion time

#### `data/` - Data Collection
- **`collector.py`**: Abstract interface for data collection defining methods for getting directory sizes and handling exclusions
- **`filesystem/scanner.py`**: Recursive directory traversal implementation with exclusion support, symlink handling, and permission error management
- **`filesystem/size_calculator.py`**: Efficient size calculation using os.stat, batch processing for performance, and caching mechanisms for repeated calculations
- **`filesystem/exclusions.py`**: Path exclusion pattern matching supporting glob patterns, regex patterns, and exact path matching
- **`models.py`**: Data models for collection results including total size, file count, and excluded paths information

### `config/` - Configuration Management

#### `loader/` - Configuration Loading
- **`yaml_loader.py`**: YAML file parsing with error handling, schema-aware loading, and support for includes/references
- **`env_loader.py`**: Environment variable extraction with prefix filtering, type conversion, and nested key support using delimiter notation
- **`merger.py`**: Configuration merging logic implementing precedence rules (env > file), deep merging for nested structures, and conflict resolution

#### `validator/` - Configuration Validation
- **`schema_validator.py`**: JSON Schema-based validation for configuration structure, custom validator registration, and comprehensive error reporting
- **`rules.py`**: Business rule validation beyond schema including cross-field validation, conditional requirements, and value range checking
- **`errors.py`**: Typed exceptions for validation failures with detailed error context, suggested fixes, and configuration path information

#### `manager/` - Configuration Management
- **`config_manager.py`**: Central configuration access point with lazy loading, configuration reloading support, and change notification system
- **`provider_configs.py`**: Provider-specific configuration file management, dynamic config file creation, and provider enable/disable handling

#### `models/` - Configuration Models
- **`base.py`**: Base configuration model with common fields, validation decorators, and serialization methods
- **`main_config.py`**: Main configuration schema as Pydantic model with field validators, default values, and environment variable mapping
- **`provider_config.py`**: Base provider configuration schema defining common provider fields and extensibility points

### `notifications/` - Notification System

#### `manager/` - Notification Management
- **`notification_manager.py`**: High-level notification orchestration, provider lifecycle management, and failure recovery coordination
- **`provider_registry.py`**: Dynamic provider registration system, provider discovery and validation, and capability querying
- **`dispatcher.py`**: Message routing to providers with parallel dispatch support, timeout handling, and delivery confirmation tracking

#### `base/` - Notification Foundation
- **`provider.py`**: Abstract base class for notification providers defining required methods, lifecycle hooks, and configuration interface
- **`exceptions.py`**: Notification-specific exceptions for delivery failures, configuration errors, and provider unavailability
- **`retry.py`**: Retry logic implementation with exponential backoff, circuit breaker pattern, and failure threshold management

#### `models/` - Notification Models
- **`status.py`**: Mover status data model containing all progress information, timestamps, and calculated metrics
- **`message.py`**: Message formatting models with template support, variable substitution, and platform-specific formatting
- **`event.py`**: Notification event types enumeration and event data structures for different notification triggers

### `plugins/` - Plugin System

#### `loader/` - Plugin Infrastructure
- **`plugin_loader.py`**: Dynamic plugin discovery and loading using importlib, dependency resolution, and circular dependency detection
- **`validator.py`**: Plugin validation ensuring interface compliance, dependency availability, and configuration completeness
- **`exceptions.py`**: Plugin-specific exceptions for loading failures, validation errors, and runtime issues

#### `template/` - Template Provider
- **`provider.py`**: Reference implementation demonstrating all provider interface methods, error handling patterns, and best practices
- **`config.py`**: Template-specific configuration model showing configuration structure, validation examples, and documentation
- **`models.py`**: Template-specific data models if needed for extended functionality
- **`README.md`**: Comprehensive plugin development guide with examples and best practices

#### `discord/` - Discord Provider
- **`provider.py`**: Discord notification provider implementing webhook delivery, rate limit handling, and error recovery
- **`config.py`**: Discord configuration model with webhook URL validation, embed customization options, and authentication settings
- **`models.py`**: Discord-specific models for embeds, fields, and attachments
- **`webhook/client.py`**: HTTP client for Discord webhook API with connection pooling, retry logic, and response handling
- **`webhook/formatter.py`**: Message to Discord payload conversion with markdown support and mention formatting
- **`embeds/builder.py`**: Fluent interface for building Discord embeds with field management and validation
- **`embeds/colors.py`**: Color management for progress-based coloring with predefined color schemes

#### `telegram/` - Telegram Provider
- **`provider.py`**: Telegram notification provider using Bot API, supporting multiple chat IDs, and handling API errors
- **`config.py`**: Telegram configuration with bot token validation, parse mode selection, and notification preferences
- **`models.py`**: Telegram-specific models for messages, keyboards, and media
- **`bot/client.py`**: Telegram Bot API client with method wrappers, automatic retry, and error handling
- **`bot/api.py`**: Low-level API communication with request signing and response parsing
- **`formatting/html_formatter.py`**: HTML message formatting for Telegram with entity escaping and tag support
- **`formatting/markdown_formatter.py`**: Markdown V2 formatting with proper escaping rules

### `utils/` - Shared Utilities

#### `formatting/` - Data Formatting
- **`size_formatter.py`**: Bytes to human-readable conversion with configurable units, precision control, and localization support
- **`time_formatter.py`**: Time duration formatting for different contexts, relative time display, and absolute timestamp formatting
- **`percentage_formatter.py`**: Percentage formatting with precision control, progress bar generation, and threshold-based formatting

#### `time/` - Time Utilities
- **`calculator.py`**: Time calculation algorithms for ETC, elapsed time computation, and time arithmetic operations
- **`timezone.py`**: Timezone handling for consistent timestamps, user timezone preferences, and DST management
- **`relative.py`**: Relative time formatting ("in 2 hours"), Discord timestamp generation, and human-friendly duration display

#### `logging/` - Logging Infrastructure
- **`logger.py`**: Logger factory with module-specific loggers, log level management, and structured logging support
- **`formatters.py`**: Custom log formatters for different outputs, JSON formatting for structured logs, and colorized console output
- **`handlers.py`**: Custom handlers for log rotation, remote logging support, and performance-aware buffering

#### `validation/` - Validation Utilities
- **`validators.py`**: Reusable validators for common patterns like URLs, file paths, and numeric ranges
- **`sanitizers.py`**: Input sanitization for security, path traversal prevention, and command injection protection

### `tests/` - Test Suite

#### `fixtures/` - Test Fixtures
- **`filesystem.py`**: Mock filesystem structures, temporary directory management, and file content generators
- **`process.py`**: Mock process objects, process state simulators, and process lifecycle helpers
- **`config.py`**: Configuration fixtures for different scenarios, invalid configuration generators, and edge case configs
- **`plugins.py`**: Mock plugins for testing, plugin discovery helpers, and provider test doubles

#### `unit/` - Unit Tests
Complete mirror of source structure with focused unit tests for each component, extensive mocking of dependencies, and edge case coverage

#### `integration/` - Integration Tests
- **`scenarios/test_full_cycle.py`**: Complete monitoring cycle from start to completion with various progress patterns
- **`scenarios/test_plugin_lifecycle.py`**: Plugin loading, configuration, and notification delivery integration
- **`scenarios/test_config_changes.py`**: Configuration hot-reloading and provider enable/disable scenarios
- **`scenarios/test_failure_recovery.py`**: Error recovery scenarios including network failures and process crashes
- **`e2e/test_dry_run.py`**: Dry-run mode validation ensuring no side effects and proper notification preview
- **`e2e/test_notification_flow.py`**: End-to-end notification delivery through multiple providers

### `configs/` - Configuration Resources
- **`examples/`**: Example configuration files for each provider with documented settings and common use cases
- **`schemas/`**: JSON Schema definitions for configuration validation and IDE autocomplete support

## Python Development Guidelines

- Use `uv` or `uvx` for all Python commands (e.g., `uv run`, `uv run pytest`, `uv pip install`).
- Adhere to Python 3.13 best practices and leverage new typing features.
- Verify type safety using `uvx basedpyright` before commits.
- Install type stubs for dependencies (e.g., `uv pip install types-requests`) only when `basedpyright` reports missing stubs.
- Prefer `# pyright: ignore[specific-error]` over `# type: ignore` comments, always with specific error codes.
- **MANDATORY: Achieve exactly 0 errors and 0 warnings across ALL code including tests.** No exceptions—this prevents technical debt and ensures real issues aren't masked.
- **Fix type issues properly rather than using ignores.** Ignores are a last resort for unavoidable third-party limitations, not a shortcut for difficult typing.
- **NEVER use global configuration ignores.** Always use targeted per-line ignores (`# pyright: ignore[import-untyped]`) to maintain visibility of suppressed issues.
- Add brief inline comments for ignores only when the reason isn't immediately obvious (e.g., `# pyright: ignore[import-untyped] # third-party lib has no stubs`).
- Do not modify basedpyright rules in `pyproject.toml` to suppress issues—fix the root cause instead.
- Treat test files with the same type safety standards as production code.
