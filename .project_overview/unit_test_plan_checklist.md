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

- [x] `ProcessState` enumeration
- [x] `ProcessStats` data class
- [x] `ProcessManager` class
  - [x] Process discovery
  - [x] Resource usage statistics
  - [x] Error handling
  - [x] Async operations

## Configuration Tests

### Settings Tests (`tests/config/test_settings.py`)

- [x] Test `Settings` class:
  - [x] Environment variables
  - [x] YAML loading
  - [x] Validation rules
  - [x] Default values
  - [x] Active providers

### Provider Settings Tests

- [x] Test Discord Settings (`tests/config/providers/discord/test_settings.py`)

  - [x] Test webhook URL validation
  - [x] Test username validation
  - [x] Test rate limiting configuration
  - [x] Test message customization

- [x] Test Telegram Settings (`tests/config/providers/telegram/test_settings.py`)
  - [x] Test bot token validation
  - [x] Test chat ID validation
  - [x] Test API configuration
  - [x] Test rate limiting settings

## Notification Tests

### Base Tests

- [x] Test base notification provider (`tests/notifications/test_notification_base.py`)
  - [x] Test NotificationError
  - [x] Test NotificationState 
  - [x] Test NotificationProvider base class
  - [x] Test notification tracking
  - [x] Test error handling
  - [x] Test retry logic
  - [x] Test rate limiting

- [x] Test notification factory (`tests/notifications/test_notification_factory.py`)
  - [x] Test provider registration
  - [x] Test provider creation
  - [x] Test provider retrieval
  - [x] Test config validation
  - [x] Test factory cleanup
  - [x] Test error handling

### Provider Tests

- [x] Test Discord Provider (`tests/notifications/providers/discord/test_provider.py`)

  - [x] Test initialization and config
  - [x] Test message formatting and template rendering
  - [x] Test webhook sending
  - [x] Test rate limiting
  - [x] Test error handling and retry logic

- [ ] Test Telegram Provider (`tests/notifications/providers/telegram/test_provider.py`)
  - [ ] Test initialization and config validation
  - [ ] Test message formatting and template rendering
  - [ ] Test API communication with mocked responses
  - [ ] Test rate limiting implementation
  - [ ] Test error handling and retry mechanism

## Utility Tests

### Formatter Tests (`tests/utils/test_formatters.py`)

- [ ] Test size formatting (KB, MB, GB)
- [ ] Test duration formatting (seconds to human-readable)
- [ ] Test timestamp formatting
- [ ] Test progress bar formatting
- [ ] Test edge cases (zero, negative, extreme values)

### Validator Tests (`tests/utils/test_validators.py`)

- [ ] Test path validation
  - [ ] Test existence checks
  - [ ] Test permission checks
  - [ ] Test symbolic link handling
- [ ] Test URL validation
  - [ ] Test valid format
  - [ ] Test supported protocols
  - [ ] Test domain validation
- [ ] Test configuration validation
  - [ ] Test type checking
  - [ ] Test required fields
  - [ ] Test field constraints

### Version Tests (`tests/utils/test_version.py`)

- [ ] Test version parsing
- [ ] Test version comparison
- [ ] Test update checking
- [ ] Test version string formatting

## Test Infrastructure

### Fixtures (`tests/conftest.py`)

- [x] Create mock settings fixture
- [x] Create mock process fixture
- [x] Create mock transfer stats fixture
- [x] Create mock notification provider fixtures
- [x] Create temporary directory fixtures
- [x] Create async test utilities and helpers

### Test Utilities

- [x] Create mock classes for external dependencies
- [x] Create test data generators
- [x] Create assertion helpers
- [x] Create async test wrappers

## Priority for Remaining Tests

1. **Telegram Provider Tests** - Important for feature parity with Discord provider
2. **Formatter Tests** - Critical for UX and display functionality
3. **Validator Tests** - Important for application robustness
4. **Version Tests** - Important for update functionality

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
│   ├── test_notification_base.py
│   └── test_notification_factory.py
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
