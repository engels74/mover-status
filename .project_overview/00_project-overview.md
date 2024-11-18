# MoverStatus Python Project Overview

## Project Description
A Python-based monitoring system that tracks the Unraid Mover process and sends notifications via configurable providers (Discord, Telegram). The system monitors data movement from SSD Cache to HDD Array, calculating progress and estimated completion times.

## Project Structure
```
mover_status/
├── config/
│   ├── __init__.py
│   ├── settings.py           # Configuration management using Pydantic
│   └── constants.py          # Project-wide constants and type aliases
├── core/
│   ├── __init__.py
│   ├── monitor.py            # Main monitoring logic
│   ├── calculator.py         # Data size and ETC calculations
│   └── process.py           # Process management utilities
├── notifications/
│   ├── __init__.py
│   ├── base.py              # Abstract base notification class
│   ├── discord/             # Discord-specific implementation
│   │   ├── __init__.py
│   │   ├── provider.py      # Discord notification implementation
│   │   ├── templates.py     # Discord message templates
│   │   └── types.py        # Discord-specific types
│   ├── telegram/            # Telegram-specific implementation
│   │   ├── __init__.py
│   │   ├── provider.py      # Telegram notification implementation
│   │   ├── templates.py     # Telegram message templates
│   │   └── types.py        # Telegram-specific types
│   └── factory.py           # Notification provider factory
├── utils/
│   ├── __init__.py
│   ├── formatters.py        # Data formatting utilities
│   ├── path.py             # Path handling and exclusion logic
│   └── version.py          # Version checking functionality
├── tests/
│   ├── __init__.py
│   ├── test_monitor.py
│   ├── test_calculator.py
│   └── test_notifications.py
├── logs/                    # Log file directory
├── __init__.py
├── __main__.py             # Entry point
├── requirements.txt
└── pyproject.toml          # Project metadata and dependencies
```

## Component Details

### 1. Configuration Management (`config/`)
- `settings.py`
  * Uses Pydantic for configuration validation
  * Implements environment variable support
  * Handles webhook URLs, tokens, and notification settings
  * Manages excluded paths configuration

- `constants.py`
  * System-wide configuration defaults
  * Path constants
  * Version information
  * Type aliases and enums

### 2. Core Functionality (`core/`)
- `monitor.py`
  * Implements main monitoring loop using asyncio
  * Handles process detection and monitoring
  * Manages notification triggers based on progress
  * Uses async file system operations for better performance

- `calculator.py`
  * Implements data size calculations
  * Handles progress percentage computation
  * Manages estimated time calculations
  * Provides human-readable format conversions

- `process.py`
  * Manages mover process detection
  * Handles process state monitoring
  * Implements process existence checks

### 3. Notification System (`notifications/`)
- `base.py`
  * Defines AbstractNotificationProvider base class
  * Implements common notification logic
  * Defines interface for notification providers
  * Handles common error patterns

- Provider-specific packages (e.g., `discord/`, `telegram/`)
  * `provider.py`: Provider-specific implementation
  * `templates.py`: Provider-specific message templates
  * `types.py`: Provider-specific type definitions
  * Self-contained provider logic and formatting

- `factory.py`
  * Implements notification provider factory pattern
  * Manages provider instantiation and registration
  * Handles provider configuration
  * Supports dynamic provider loading

### 4. Utilities (`utils/`)
- `formatters.py`
  * Implements data size formatting
  * Handles time formatting
  * Common text processing utilities

- `path.py`
  * Handles path exclusion logic
  * Manages directory size calculations
  * Implements path validation

- `version.py`
  * Manages version checking
  * Handles GitHub API interactions
  * Implements version comparison logic

### 5. Entry Point (`__main__.py`)
- Handles argument parsing
- Initializes logging
- Sets up configuration
- Starts monitoring process
- Manages application lifecycle

## Key Technical Implementations

### Error Handling
- Custom exception classes for different error types
- Comprehensive error catching and logging
- Graceful degradation for non-critical failures
- Retry mechanisms for transient failures

### Logging
- Structured logging using Python's logging module
- Rotating file handler for log management
- Different log levels (DEBUG, INFO, WARNING, ERROR)
- Contextual logging with correlation IDs

### Testing
- Unit tests for core functionality
- Integration tests for notification providers
- Mock objects for external services
- Test fixtures for common scenarios

### Dependencies
Key Python packages to be used:
- `pydantic`: Configuration management and validation
- `aiohttp`: Async HTTP client for notifications
- `asyncio`: Asynchronous I/O operations
- `python-dotenv`: Environment variable management
- `structlog`: Structured logging
- `pytest`: Testing framework
- `tenacity`: Retry handling
- `typing-extensions`: Enhanced type hints

## Future Extensibility
Adding a new notification provider is straightforward:
1. Create a new provider package (e.g., `notifications/slack/`)
2. Implement the required interface from `base.py`
3. Define provider-specific templates and types
4. Register with the factory

The modular structure ensures each provider is self-contained and can be:
- Tested independently
- Configured separately
- Enabled/disabled without affecting other providers
- Updated without modifying core system code

Additional future features:
- Plugin system for new monitoring metrics
- Configurable monitoring strategies
- Health check endpoint capabilities
- Metrics collection and reporting
