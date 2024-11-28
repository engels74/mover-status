# MoverStatus Project Overview

## Project Structure
```
mover_status/
├── config/
│   ├── constants.py
│   ├── settings.py
│   └── providers/
│       ├── base.py
│       ├── discord/
│       │   ├── schemas.py
│       │   ├── settings.py
│       │   └── types.py
│       └── telegram/
│           ├── schemas.py
│           ├── settings.py
│           └── types.py
├── core/
│   ├── calculator.py
│   ├── monitor.py
│   └── process.py
├── notifications/
│   ├── base.py
│   ├── factory.py
│   └── providers/
│       ├── discord/
│       │   ├── __init__.py
│       │   ├── provider.py
│       │   └── templates.py
│       └── telegram/
│           ├── __init__.py
│           ├── provider.py
│           └── templates.py
├── shared/
│   └── providers/
│       ├── discord/
│       │   ├── __init__.py
│       │   └── types.py
│       └── telegram/
│           ├── __init__.py
│           └── types.py
├── utils/
│   ├── formatters.py
│   ├── validators.py
│   └── version.py
├── tests/
│   └── conftest.py
├── __main__.py
└── pyproject.toml
```

## Development Guidelines

### Code Style Requirements
- Follow PEP 8 guidelines
  - 4 spaces for indentation
  - Maximum line length of 88 characters (as configured in pyproject.toml)
  - Proper naming conventions (snake_case for functions/variables, PascalCase for classes)
  - Proper import ordering and grouping

- Use type hints throughout
  - All function parameters and return values
  - Complex data structures using TypedDict, Protocol, etc.
  - Generic type variables where appropriate
  - Optional[] for nullable values

- Comprehensive docstrings
  - Module-level docstrings explaining purpose and usage
  - Class and function docstrings following Google style
  - Include Args, Returns, Raises sections
  - Provide usage examples for complex functionality

- Clear error messages
  - Custom exception classes with descriptive names
  - Detailed error messages including context
  - Proper exception chaining using raise ... from ...

- Proper exception handling
  - Specific exception types over bare except
  - Context managers for resource management
  - Proper cleanup in error cases
  - Logging of errors with context

### Discord Integration Structure

#### Centralized Types and Validation
The Discord integration uses a centralized type system in `shared.providers.discord`:
- **Type Definitions**
  - `WebhookConfig`: Discord webhook configuration
  - `ForumConfig`: Forum channel settings
  - `EmbedConfig`: Message embed structure
  - Other TypedDict definitions for Discord types

- **Constants and Limits**
  - API rate limits and constraints
  - URL validation patterns
  - Allowed domains and schemes
  - Message length limits
  - Color constants

- **Validation Rules**
  - URL format and domain validation
  - Content length and format checks
  - Username and thread name patterns
  - Common validation messages

#### Provider Implementation
- **Configuration (`config.providers.discord/`)**
  - `schemas.py`: Pydantic models using shared types
  - `settings.py`: Settings management with validation

- **Runtime (`notifications.providers.discord/`)**
  - `provider.py`: Webhook handling and message delivery
  - `templates.py`: Message formatting and structure

### Telegram Integration Structure

#### Centralized Types and Validation
The Telegram integration uses a centralized type system in `shared.providers.telegram`:
- **Type Definitions**
  - `ParseMode`: Message parsing modes (HTML, Markdown)
  - `MessageEntity`: Text formatting entities
  - `InlineKeyboardMarkup`: Interactive keyboard layouts
  - Other TypedDict definitions for Telegram types

- **Constants and Limits**
  - `MessageLimit`: Message content limits
  - `ApiLimit`: API constraints and rate limits
  - `ChatType`: Available chat types
  - Message entity type constants

- **Validation Rules**
  - Message length validation
  - UTF-16 encoding handling
  - Entity validation and extraction
  - Common validation messages

#### Provider Implementation
- **Configuration (`config.providers.telegram/`)**
  - `schemas.py`: Pydantic models using shared types
  - `settings.py`: Settings management with validation

- **Runtime (`notifications.providers.telegram/`)**
  - `provider.py`: Bot API handling and message delivery
  - `templates.py`: Message formatting and templates

### File Requirements
Every Python file must include:

```python
# folder/subfolder/filename.py

"""
Module purpose and functionality description.

Includes usage examples where appropriate.

Example:
    >>> from module import MyClass
    >>> obj = MyClass()
    >>> obj.my_method()
    'Expected output'
"""

# Imports grouped by:
# 1. Standard library
# 2. Third-party packages
# 3. Local modules

# Code implementation
```

### Implementation Requirements

1. Complete implementation with type hints
   - All public interfaces fully typed
   - Use of Generic types for reusable components
   - Proper use of TypeVar, Protocol, Union types
   - Type aliases for complex types

2. Comprehensive docstrings
   - Module overview
   - Class and method documentation
   - Usage examples
   - Parameter descriptions
   - Return value descriptions
   - Exception documentation

3. Error handling
   - Custom exception hierarchy
   - Proper exception chaining
   - Resource cleanup
   - Graceful degradation
   - Comprehensive error messages

4. Unit tests
   - Test coverage targets (configured in pyproject.toml)
   - Async test support
   - Mock external services
   - Error case testing
   - Edge case handling

5. PEP 8 compliance
   - Line length limits
   - Import ordering
   - Naming conventions
   - Comment formatting
   - Proper whitespace

6. Clean whitespace formatting
   - Consistent indentation
   - Blank lines between logical sections
   - Proper line breaks
   - No trailing whitespace
   - No mixed tabs/spaces

## Notes on Unraid's Mover Process
- Mover is implemented as a PHP script called via bash wrapper
- Process chain: bash -> php -> ionice/nice -> file operations
- Monitoring focuses on:
  * Process state detection
  * Resource usage tracking
  * File operation progress
  * Nice/IO priority levels
- No process control capabilities needed (monitor only)
