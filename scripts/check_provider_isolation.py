#!/usr/bin/env python3
"""Provider isolation validation script.

Enforces the architectural rule that core/, types/, and utils/ directories
must remain completely provider-agnostic. No references to specific providers
(Discord, Telegram, or any future providers) are allowed outside the plugins/
directory.

This script scans for:
- Direct imports from mover_status.plugins.{discord,telegram,...}
- Hardcoded provider name strings in code, comments, or docstrings
- Provider-specific configuration field names (e.g., discord_enabled)

Exit codes:
    0: No violations found (clean)
    1: Violations detected (architectural rule broken)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

# ANSI color codes for terminal output
RED: Final[str] = "\033[91m"
GREEN: Final[str] = "\033[92m"
YELLOW: Final[str] = "\033[93m"
RESET: Final[str] = "\033[0m"

# Directories that must remain provider-agnostic
PROTECTED_DIRS: Final[tuple[str, ...]] = ("core", "types", "utils")

# Known provider names to check for (case-insensitive)
PROVIDER_NAMES: Final[tuple[str, ...]] = ("discord", "telegram")

# Regex patterns for violation detection
IMPORT_PATTERN: Final[re.Pattern[str]] = re.compile(r"from\s+mover_status\.plugins\.(?:discord|telegram)\b")

# Pattern to match provider names in code (case-insensitive)
# Excludes:
# - Comments explaining what we're checking for (like this file)
# - Variable names that are compound words (e.g., "concord", "elegram")
PROVIDER_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(?:discord|telegram)\b", re.IGNORECASE)

# Pattern to match provider-specific config field names
CONFIG_FIELD_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:discord|telegram)_(?:enabled|config|settings)\b", re.IGNORECASE
)


def check_file(file_path: Path) -> list[tuple[int, str]]:
    """Check a single Python file for provider isolation violations.

    Args:
        file_path: Path to the Python file to check.

    Returns:
        List of (line_number, violation_description) tuples.
        Empty list if no violations found.
    """
    violations: list[tuple[int, str]] = []

    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
    except Exception as e:
        print(f"{YELLOW}Warning: Could not read {file_path}: {e}{RESET}", file=sys.stderr)
        return violations

    for line_num, line in enumerate(lines, start=1):
        # Check for direct imports from plugin modules
        if IMPORT_PATTERN.search(line):
            violations.append(
                (
                    line_num,
                    f"Direct import from provider plugin: {line.strip()}",
                )
            )

        # Check for provider-specific config field names
        if CONFIG_FIELD_PATTERN.search(line):
            violations.append(
                (
                    line_num,
                    f"Provider-specific config field: {line.strip()}",
                )
            )

        # Check for hardcoded provider names
        # Skip this check if the line is a comment explaining the check itself
        # (to avoid false positives in this very script)
        if PROVIDER_NAME_PATTERN.search(line):
            # Allow mentions in comments that explain what we're checking
            if not (
                line.strip().startswith("#")
                and any(
                    keyword in line.lower() for keyword in ["check", "validate", "exclude", "example", "e.g.", "like"]
                )
            ):
                violations.append(
                    (
                        line_num,
                        f"Hardcoded provider name reference: {line.strip()}",
                    )
                )

    return violations


def scan_directory(base_path: Path, protected_dir: str) -> dict[Path, list[tuple[int, str]]]:
    """Scan a protected directory for violations.

    Args:
        base_path: Root path of the mover_status package.
        protected_dir: Name of protected directory (core, types, or utils).

    Returns:
        Dictionary mapping file paths to their violations.
        Empty dict if no violations found.
    """
    dir_path = base_path / protected_dir
    if not dir_path.exists():
        print(
            f"{YELLOW}Warning: Protected directory {dir_path} does not exist{RESET}",
            file=sys.stderr,
        )
        return {}

    violations_by_file: dict[Path, list[tuple[int, str]]] = {}

    # Recursively find all Python files
    for py_file in dir_path.rglob("*.py"):
        # Skip __pycache__ and other cache directories
        if "__pycache__" in py_file.parts:
            continue

        file_violations = check_file(py_file)
        if file_violations:
            violations_by_file[py_file] = file_violations

    return violations_by_file


def main() -> int:
    """Main entry point for provider isolation check.

    Returns:
        Exit code: 0 if no violations, 1 if violations found.
    """
    # Find the src/mover_status directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    src_path = project_root / "src" / "mover_status"

    if not src_path.exists():
        print(f"{RED}Error: Could not find src/mover_status directory{RESET}", file=sys.stderr)
        return 1

    print("Checking provider isolation in core, types, and utils modules...")
    print(f"Scanning: {src_path}\n")

    all_violations: dict[Path, list[tuple[int, str]]] = {}

    # Scan each protected directory
    for protected_dir in PROTECTED_DIRS:
        violations = scan_directory(src_path, protected_dir)
        all_violations.update(violations)

    # Report results
    if not all_violations:
        print(f"{GREEN}✓ No provider isolation violations found!{RESET}")
        print(f"{GREEN}✓ Core, types, and utils modules are completely provider-agnostic{RESET}")
        return 0

    # Print violations
    total_violations = sum(len(v) for v in all_violations.values())
    print(f"{RED}✗ Found {total_violations} provider isolation violations:{RESET}\n")

    for file_path, violations in sorted(all_violations.items()):
        # Make path relative to project root for cleaner output
        try:
            rel_path = file_path.relative_to(project_root)
        except ValueError:
            rel_path = file_path

        print(f"{RED}{rel_path}{RESET}")
        for line_num, description in violations:
            print(f"  {line_num}: {description}")
        print()

    print(f"{RED}Provider isolation check failed!{RESET}")
    print(
        "\nCore, types, and utils modules must remain provider-agnostic."
        "\nMove provider-specific code to plugins/<provider>/ directory."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
