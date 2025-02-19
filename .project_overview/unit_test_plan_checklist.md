# MoverStatus Unit Test Plan

This document outlines the comprehensive unit test plan for the MoverStatus application. Tests are organized by module and functionality.

## Core Module Tests

### Calculator Tests (`tests/core/test_calculator.py`)

- [x] TransferStats data class

  - [x] Default & custom initialization
  - [x] Property calculations

- [x] TransferCalculator class
  - [x] Initialization & settings
  - [x] initialize_transfer: valid size, errors (0, negative, max)
  - [x] update_progress: updates, edge cases, rate & time calc
  - [x] reset method
  - [x] monitor_transfer: valid/invalid callbacks, cancel, errors

### Monitor Tests (`tests/core/test_monitor.py`)

- [x] DirectoryScanner class

  - [x] Initialization, path exclusion, cache, and async scanning

- [x] MonitorStats class

  - [x] Initialization and state updates

- [x] MoverMonitor class
  - [x] Core functionality (init, events, notifications)
  - [x] Process monitoring and version checking
  - [x] Async operations (context manager, shutdown)

### Process Tests (`tests/core/test_process.py`)

- [ ] Test `ProcessState` enumeration
- [ ] Test `ProcessStats` data class
- [ ] Test `ProcessManager` class
  - [ ] Test process discovery
  - [ ] Test resource usage statistics
  - [ ] Test error handling
  - [ ] Test async operations

## Configuration Tests

### Settings Tests (`tests/config/test_settings.py`)

- [ ] Test `Settings` class
  - [ ] Test loading from environment variables
  - [ ] Test loading from YAML
  - [ ] Test validation rules
  - [ ] Test default values
  - [ ] Test active providers property

### Provider Settings Tests

- [ ] Test Discord Settings (`tests/config/providers/discord/test_settings.py`)

  - [ ] Test webhook URL validation
  - [ ] Test username validation
  - [ ] Test rate limiting configuration
  - [ ] Test message customization

- [ ] Test Telegram Settings (`tests/config/providers/telegram/test_settings.py`)
  - [ ] Test bot token validation
  - [ ] Test chat ID validation
  - [ ] Test API configuration
  - [ ] Test rate limiting settings

## Notification Tests

### Base Tests (`tests/notifications/test_base.py`)

- [ ] Test base notification provider
- [ ] Test notification factory
- [ ] Test error handling

### Provider Tests

- [ ] Test Discord Provider (`tests/notifications/providers/discord/test_provider.py`)

  - [ ] Test message formatting
  - [ ] Test webhook sending
  - [ ] Test rate limiting
  - [ ] Test error handling
  - [ ] Test template rendering

- [ ] Test Telegram Provider (`tests/notifications/providers/telegram/test_provider.py`)
  - [ ] Test message formatting
  - [ ] Test API communication
  - [ ] Test rate limiting
  - [ ] Test error handling
  - [ ] Test template rendering

## Utility Tests

### Formatter Tests (`tests/utils/test_formatters.py`)

- [ ] Test size formatting
- [ ] Test duration formatting
- [ ] Test ETA formatting
- [ ] Test edge cases

### Validator Tests (`tests/utils/test_validators.py`)

- [ ] Test path validation
- [ ] Test URL validation
- [ ] Test configuration validation
- [ ] Test edge cases

### Version Tests (`tests/utils/test_version.py`)

- [ ] Test version parsing
- [ ] Test version comparison
- [ ] Test update checking
- [ ] Test version string formatting

## Test Infrastructure

### Fixtures (`tests/conftest.py`)

- [ ] Create mock settings fixture
- [ ] Create mock process fixture
- [ ] Create mock filesystem fixture
- [ ] Create mock notification provider fixtures
- [ ] Create temporary directory fixtures
- [ ] Create async test utilities

### Test Utilities

- [ ] Create mock classes for external dependencies
- [ ] Create test data generators
- [ ] Create assertion helpers
- [ ] Create async test wrappers

## Test Organization Guidelines

1. Follow this directory structure for tests:

```
tests/
├── conftest.py
├── core/
│   ├── test_calculator.py
│   ├── test_monitor.py
│   └── test_process.py
├── config/
│   ├── providers/
│   │   ├── discord/
│   │   │   └── test_settings.py
│   │   └── telegram/
│   │       └── test_settings.py
│   └── test_settings.py
├── notifications/
│   ├── providers/
│   │   ├── discord/
│   │   │   └── test_provider.py
│   │   └── telegram/
│   │       └── test_provider.py
│   └── test_base.py
└── utils/
    ├── test_formatters.py
    ├── test_validators.py
    └── test_version.py
```

2. Test File Naming:

   - All test files should be prefixed with `test_`
   - Test file names should match the module they test
   - Use descriptive suffixes for specialized test files

3. Test Function Naming:

   - Use `test_` prefix for all test functions
   - Include the name of the function/method being tested
   - Include the scenario or condition being tested
   - Example: `test_update_progress_with_valid_size`

4. Test Organization:

   - Group related tests in classes
   - Use descriptive test class names
   - Include setup and teardown methods where needed
   - Use appropriate pytest markers

5. Documentation:
   - Include docstrings for test classes and complex test functions
   - Document test data and fixtures
   - Explain complex test scenarios
   - Include examples in docstrings where helpful
