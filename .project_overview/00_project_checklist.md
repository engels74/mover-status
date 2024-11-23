# MoverStatus - Python Project Guide

## Complete Project Structure
```
mover_status/
├── config/
│   ├── __init__.py
│   ├── constants.py
│   ├── settings.py
│   └── providers/
│       ├── __init__.py
│       ├── base.py
│       ├── discord/
│       │   ├── __init__.py
│       │   ├── settings.py
│       │   ├── schemas.py
│       │   ├── types.py
│       └── telegram/
│           ├── __init__.py
│           ├── settings.py
│           ├── schemas.py
│           ├── types.py
├── shared/
│   └── types/
│       ├── __init__.py
│       ├── discord.py
│       └── telegram.py
├── core/
│   ├── __init__.py
│   ├── calculator.py
│   ├── monitor.py
│   └── process.py
├── notifications/
│   ├── __init__.py
│   ├── base.py
│   ├── factory.py
│   └── providers/
│       ├── __init__.py
│       ├── discord/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── provider.py
│       │   ├── templates.py
│       │   └── types.py
│       └── telegram/
│           ├── __init__.py
│           ├── config.py
│           ├── provider.py
│           ├── templates.py
│           └── types.py
├── utils/
│   ├── __init__.py
│   ├── formatters.py
│   ├── validators.py
│   └── version.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_core/
│   ├── test_notifications/
│   └── test_utils/
├── __init__.py
├── __main__.py
├── pyproject.toml
└── requirements.txt
```

## ✅ Completed Implementations

### Configuration
- [x] **constants.py**
  * Implements `ByteSize`, `Percentage`, `PathLike` type aliases
  * Defines system-wide constants for byte sizes and time intervals
  * Provides template placeholders and error message constants
  * Uses Python enums for notification providers and log levels

- [x] **settings.py** (Core)
  * Implements base settings class using Pydantic
  * Defines core application settings
  * Implements settings validation framework
  * Provides configuration loading utilities

- [x] **providers/base.py**
  * Implements abstract base provider settings
  * Defines common provider configuration patterns
  * Implements shared validation methods
  * Define provider settings interfaces

- [x] **providers/discord/settings.py**
  * Implements Discord-specific settings class
  * Defines webhook configuration models
  * Implements Discord-specific validators
  * Handle Discord rate limiting configuration

- [x] **providers/discord/schemas.py**
  * Defines Discord configuration schemas
  * Implements webhook payload validation
  * Defines Discord-specific constraints
  * Handles Discord API limitations

- [x] **providers/discord/types.py**
  * Defines Discord setting types
  * Implements type aliases for Discord
  * Defines constants for Discord settings
  * Implements Discord-specific enums

- [x] **providers/telegram/settings.py**
  * Implements Telegram-specific settings class
  * Defines bot API configuration models
  * Implements Telegram-specific validators
  * Handles Telegram rate limiting configuration

- [x] **providers/telegram/schemas.py**
  * Defines Telegram configuration schemas
  * Implements bot API payload validation
  * Defines Telegram-specific constraints
  * Handles Telegram API limitations

- [x] **providers/telegram/types.py**
  * Defines Telegram setting types
  * Implements type aliases for Telegram
  * Defines constants for Telegram settings
  * Implements Telegram-specific enums

### Shared Components
- [x] **shared/types/discord.py**
  * Implemented shared Discord type definitions
  * Defined API limits and constants
  * Created reusable embed structures
  * Implemented utility functions

- [x] **shared/types/telegram.py**
  * Defined shared Telegram type definitions
  * Defined API limits and constants
  * Created reusable message structures
  * Implemented utility functions

### Core Functionality
- [x] **calculator.py**
  * Implements `TransferCalculator` class using async Python operations
  * Uses moving average algorithm for transfer rate calculation
  * Implements `@dataclass` for transfer statistics
  * Uses asyncio for non-blocking directory size monitoring

- [x] **monitor.py**
  * Implements async event loop using `asyncio`
  * Uses Python context managers for resource management
  * Implements observer pattern for notification distribution
  * Uses structured logging with `structlog`

- [x] **process.py**
  * Uses `psutil` for process monitoring
  * Implements async process checking with `asyncio`
  * Uses Python enums for process states
  * Implements resource usage tracking using system calls

### Notifications
- [x] **base.py**
  * Implements abstract base class using Python's `ABC`
  * Uses async methods for notification handling
  * Implements rate limiting using Python decorators
  * Uses typed exceptions for error handling

- [x] **factory.py**
  * Implements factory pattern using class decorators
  * Uses Python type hints for provider registration
  * Implements singleton pattern for factory instance
  * Uses async context managers for provider lifecycle

#### Discord Provider
- [x] **config.py**
  * Uses Pydantic for configuration validation
  * Implements custom validators using decorators
  * Uses Python dataclasses for configuration models
  * Implements environment variable mapping

- [x] **provider.py**
  * Uses `aiohttp` for async webhook requests
  * Implements retry logic using exponential backoff
  * Uses context managers for session management
  * Implements rate limiting per Discord API specs

- [x] **templates.py**
  * Uses string templating for message formatting
  * Implements embed creation using Python dictionaries
  * Uses type hints for template validation
  * Implements character limit validation

- [x] **types.py**
  * Uses Python `TypedDict` for API types
  * Implements enums for message types
  * Uses literal types for Discord-specific constants
  * Defines webhook payload structures

#### Telegram Provider
- [x] **config.py**
  * Uses Pydantic models for configuration
  * Implements chat ID validation using regex
  * Uses Python enums for parse modes
  * Implements environment variable loading

- [x] **provider.py**
  * Uses `aiohttp` for Telegram Bot API requests
  * Implements message editing capabilities
  * Uses async context managers
  * Implements error handling with custom exceptions

- [x] **templates.py**
  * Uses HTML/Markdown parsing for messages
  * Implements message entity extraction
  * Uses string formatting for templates
  * Implements character limit validation

- [x] **types.py**
  * Uses Python enums for message types
  * Implements TypedDict for API structures
  * Uses literal types for Telegram constants
  * Defines bot API payload structures

### Utils
- [x] **formatters.py**
  * Implements human-readable size formatting
  * Uses Python string formatting
  * Implements duration formatting with units
  * Uses type hints for format specifications

- [x] **validators.py**
  * Implements path and URL validation
  * Uses Python's `urllib.parse`
  * Implements type checking utilities
  * Uses regular expressions for validation

- [x] **version.py**
  * Implements semantic versioning using `@dataclass`
  * Uses `aiohttp` for GitHub API requests
  * Implements version comparison using `@total_ordering`
  * Uses caching for API responses

### Application
- [x] **__main__.py**
  * Uses argparse for CLI handling
  * Implements async main loop
  * Uses signal handlers for graceful shutdown
  * Implements structured logging setup

## ⏳ Pending Implementations

### Tests
- [ ] test_core/
  - [ ] test_calculator.py
  - [ ] test_monitor.py
  - [ ] test_process.py

- [ ] test_notifications/
  - [ ] test_base.py
  - [ ] test_factory.py
  - [ ] Discord Tests:
    - [ ] test_config.py
    - [ ] test_provider.py
    - [ ] test_templates.py
    - [ ] test_types.py
  - [ ] Telegram Tests:
    - [ ] test_config.py
    - [ ] test_provider.py
    - [ ] test_templates.py
    - [ ] test_types.py

- [ ] test_utils/
  - [ ] test_formatters.py
  - [ ] test_validators.py
  - [ ] test_version.py

## Development Guidelines

### Code Style Requirements
- Follow PEP 8 guidelines
- Use type hints throughout
- Comprehensive docstrings
- Clear error messages
- Proper exception handling

### File Requirements
Each Python file must include:
```python
# folder/subfolder/filename.py

"""
Module docstring explaining purpose and functionality.
Includes usage examples where appropriate.
"""
```

### Implementation Requirements
1. Complete implementation with type hints
2. Comprehensive docstrings
3. Error handling
4. Unit tests
5. PEP 8 compliance
6. Clean whitespace formatting

### Implementation Requirements for Settings
1. Provider settings must inherit from base provider settings
2. Each provider module must implement:
   - Settings class with provider-specific configuration
   - Schema definitions for configuration validation
   - Type definitions and constants
   - Custom validators for provider requirements
3. All settings classes must:
   - Use Pydantic for validation
   - Include comprehensive type hints
   - Provide clear error messages
   - Include usage examples in docstrings
4. Settings must support:
   - Environment variable loading
   - Configuration file loading
   - Runtime validation
   - Default values
5. Provider settings must maintain:
   - Rate limiting configurations
   - API-specific constraints
   - Authentication settings
   - Message format settings

## Notes on Mover Process
- Mover is implemented as a PHP script called via bash wrapper
- Process chain: bash -> php -> ionice/nice -> file operations
- Monitoring focuses on:
  * Process state detection
  * Resource usage tracking
  * File operation progress
  * Nice/IO priority levels
- No process control capabilities needed (monitor only)
