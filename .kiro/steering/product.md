---
inclusion: always
---

# Product Overview

## What is Mover Status?

Mover Status is a Python monitoring application for Unraid systems that tracks the Mover process and sends real-time progress notifications to Discord and/or Telegram. It monitors data transfer from SSD cache to HDD array, providing percentage completion, estimated time remaining, and transfer rates.

## Core Functionality

- Monitors Unraid Mover process lifecycle (waiting → started → progressing → completed)
- Calculates progress percentage based on disk usage changes
- Estimates time of completion (ETC) from data movement rates
- Sends notifications at configurable progress thresholds (e.g., 25%, 50%, 75%, 100%)
- Supports multiple notification providers concurrently (Discord, Telegram)
- Excludes specified directories from progress calculations (e.g., qBittorrent, SABnzbd folders)

## Target Environment

- **Platform**: Unraid OS (Linux-based NAS operating system)
- **Integration**: Runs via Unraid's "User Scripts" plugin
- **Execution**: Long-running background process that loops continuously
- **Python Version**: Requires Python 3.14+ for modern type system and performance features

## Key Design Goals

- **Extensibility**: Plugin architecture allows adding new notification providers without modifying core code
- **Type Safety**: Comprehensive type hints using Python 3.14+ features (PEP 695, TypeIs, Protocols)
- **Reliability**: Provider failure isolation ensures one provider's failure doesn't affect others
- **Performance**: Structured concurrency with TaskGroup for concurrent webhook delivery
- **Maintainability**: Modular architecture with clear separation of concerns

## Migration Context

This is a Python rewrite of an existing bash script (`.old_script/moverStatus.sh`). The rewrite addresses limitations in the bash implementation:
- Hardcoded provider logic → Plugin-based provider system
- Weak typing → Strict type safety with basedpyright
- Monolithic structure → Modular, testable components
- Limited extensibility → Zero-code provider additions
