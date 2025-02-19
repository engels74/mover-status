# MoverStatus Project Overview

## Project Structure

```
mover_status/
├── LICENSE
├── README.md
├── __main__.py
├── config/
│   ├── constants.py
│   ├── providers/
│   │   ├── base.py
│   │   ├── discord/
│   │   │   ├── schemas.py
│   │   │   ├── settings.py
│   │   │   └── types.py
│   │   └── telegram/
│   │       ├── schemas.py
│   │       ├── settings.py
│   │       └── types.py
│   └── settings.py
├── core/
│   ├── calculator.py
│   ├── monitor.py
│   └── process.py
├── examples/
│   └── config.yml
├── notifications/
│   ├── base.py
│   ├── factory.py
│   └── providers/
│       ├── discord/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── provider.py
│       │   ├── templates.py
│       │   ├── types.py
│       │   └── validators.py
│       └── telegram/
│           ├── __init__.py
│           ├── config.py
│           ├── provider.py
│           ├── templates.py
│           ├── types.py
│           └── validators.py
├── pyproject.toml
├── requirements.txt
├── shared/
│   └── providers/
│       ├── discord/
│       │   ├── __init__.py
│       │   └── types.py
│       └── telegram/
│           ├── __init__.py
│           ├── constants.py
│           ├── errors.py
│           ├── types.py
│           └── utils.py
├── tests/
│   └── conftest.py
└── utils/
    ├── formatters.py
    ├── validators.py
    └── version.py
```

## Key Features

- Real-time monitoring of Unraid's Mover process
- Discord and Telegram notifications
- Progress tracking and ETA calculations
- Resource usage monitoring
- Configurable notification intervals
- Comprehensive error handling

## Development Guidelines

### Core Principles

1. **Code Quality**

   - Follow PEP 8 standards
   - Use type hints and docstrings
   - Implement comprehensive error handling

2. **Modular Design**

   - Separate concerns between modules
   - Use dependency injection
   - Maintain clear interfaces

3. **Testing**
   - Maintain high test coverage
   - Test edge cases and error scenarios
   - Use mocks for external services

## Notes on Unraid's Mover Process

- Mover is implemented as a PHP script called via bash wrapper
- Process chain: bash -> php -> ionice/nice -> file operations
- Monitoring focuses on:
  - Process state detection
  - Resource usage tracking
  - File operation progress
  - Nice/IO priority levels
- No process control capabilities needed (monitor only)
