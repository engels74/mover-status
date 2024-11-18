# MoverStatus Python Project Overview

## Project Description
A Python-based monitoring system that tracks the Unraid Mover process and sends notifications via configurable providers (Discord, Telegram). The system monitors data movement from SSD Cache to HDD Array, calculating progress and estimated completion times with efficient asynchronous operations and caching mechanisms.

## Project Goals
- Provide real-time monitoring of the Unraid Mover process
- Send configurable notifications through modular provider system
- Support easy integration of new notification providers
- Calculate accurate progress and time estimates
- Maintain high code quality and test coverage
- Ensure efficient async operations for file system monitoring

## Project Structure
```
mover_status/
├── config/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── settings.py        # Core settings models
│   │   └── constants.py       # Core constants and type aliases
│   └── providers/
│       ├── __init__.py
│       ├── base.py            # Base provider settings model
│       ├── discord/
│       │   ├── __init__.py
│       │   ├── settings.py    # Discord-specific settings
│       │   └── constants.py   # Discord-specific constants
│       └── telegram/
│           ├── __init__.py
│           ├── settings.py    # Telegram-specific settings
│           └── constants.py   # Telegram-specific constants
├── core/
│   ├── __init__.py
│   ├── monitor.py            # Main monitoring loop with async file operations
│   ├── calculator.py         # Progress and time calculations
│   └── process.py            # Process management and state tracking
├── notifications/
│   ├── __init__.py
│   ├── base.py              # Abstract base notification class
│   ├── factory.py           # Provider instantiation and registry
│   ├── interface.py         # Provider interface definitions
│   ├── discord/
│   │   ├── __init__.py
│   │   ├── provider.py      # Discord webhook implementation
│   │   ├── templates.py     # Message templates and formatting
│   │   └── types.py         # Discord-specific types
│   └── telegram/
│       ├── __init__.py
│       ├── provider.py      # Telegram API implementation
│       ├── templates.py     # Message templates and formatting
│       └── types.py         # Telegram-specific types
├── utils/
│   ├── __init__.py
│   ├── formatters.py        # Data and time formatting utilities
│   ├── validators.py        # Configuration validation functions
│   └── version.py           # Version checking and comparison
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Test configuration and fixtures 
│   ├── test_core/
│   │   ├── __init__.py
│   │   ├── test_calculator.py
│   │   ├── test_monitor.py
│   │   └── test_process.py
│   ├── test_notifications/
│   │   ├── __init__.py
│   │   ├── test_base.py
│   │   ├── test_factory.py
│   │   ├── test_interface.py
│   │   ├── test_discord/
│   │   │   ├── __init__.py
│   │   │   ├── test_provider.py
│   │   │   ├── test_templates.py
│   │   │   └── test_types.py
│   │   └── test_telegram/
│   │       ├── __init__.py
│   │       ├── test_provider.py
│   │       ├── test_templates.py
│   │       └── test_types.py
│   └── test_utils/
│       ├── __init__.py
│       ├── test_formatters.py
│       ├── test_validators.py
│       └── test_version.py
├── __init__.py
├── __main__.py             # Application entry point
├── pyproject.toml          # Project metadata and dependencies
└── README.md
```

## Component Details

### 1. Configuration Management (`config/`)
The configuration system is designed for modularity and easy provider integration:

- Core Settings (`core/`)
  * Base application configuration
  * Monitoring parameters
  * System-wide defaults
  * Common settings shared across components

- Provider Settings (`providers/`)
  * Isolated provider configurations
  * Provider-specific validation rules
  * Independent version tracking
  * Separate environment handling

### 2. Core Functionality (`core/`)
- `monitor.py`
  * Main monitoring loop
  * Event handling and state tracking
  * Progress tracking and updates
  * Provider coordination
  * State management

- `calculator.py`
  * Progress calculation algorithms
  * Time estimation (ETC) logic
  * Data size computations
  * Historical trend analysis

- `process.py`
  * Process detection utilities
  * Process state monitoring
  * Async process checking
  * Resource usage tracking

### 3. Notification System (`notifications/`)
- `base.py`
  * Abstract notification provider interface
  * Common notification handling logic
  * Rate limiting base implementation
  * Error handling patterns

- `factory.py`
  * Provider registration and instantiation
  * Configuration mapping
  * Instance management
  * Error handling

- `interface.py`
  * Provider interface definitions
  * Required method specifications
  * Type hints and documentation
  * Contract enforcement

- Provider Implementations
  * Independent provider modules
  * Provider-specific logic
  * Custom message formatting
  * API integration

### 4. Utilities (`utils/`)
- `formatters.py`
  * Data size formatting
  * Time duration formatting
  * Progress percentage formatting
  * Message template processing

- `validators.py`
  * Settings validation functions
  * Path and URL validation
  * Type checking helpers
  * Environment validation

- `version.py`
  * GitHub API integration
  * Version comparison logic
  * Update checking functionality
  * Async HTTP client implementation

### 5. Testing Structure (`tests/`)
- Comprehensive test coverage
- Provider-specific test suites
- Integration testing
- Mock configurations
- Performance testing

## Development Guidelines

### Code Style
- Follow PEP 8 guidelines
- Use type hints throughout
- Comprehensive docstrings
- Clear error messages
- Proper exception handling

### Testing Requirements
- Minimum 80% code coverage
- Unit tests for all components
- Integration tests for providers
- Performance tests for core logic

## Provider Architecture

### Base Provider Requirements
- Must implement notification interface
- Must provide settings model
- Must handle rate limiting
- Must implement error handling
- Must provide message templates

### Adding New Providers
1. Create provider settings in `config/providers/`
2. Implement provider logic in `notifications/`
3. Add provider tests
4. Register with provider factory
