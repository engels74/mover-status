# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mover Status is a single-file Bash script (`moverStatus.sh`) for Unraid servers that monitors the "Mover" process (which transfers data from SSD cache to HDD array) and sends real-time progress notifications via Discord webhooks and/or Telegram.

Deployed by copy-pasting the script into Unraid's "User Scripts" plugin. There is no build system, no package manager, and no test suite.

## Linting

```bash
shellcheck moverStatus.sh
```

Recent commits address ShellCheck warnings (SC2034, SC2155). All new code should pass ShellCheck cleanly.

## Architecture

The entire application is `moverStatus.sh` (~880 lines). It runs as a long-lived background process with this flow:

1. **Configuration & Validation** (lines 29-121) — User-editable settings at the top (including `CACHE_PATH`, `ENABLE_FILE_INFO`, completion message templates), followed by validation of notification methods, webhook URLs, and paths.
2. **Dry-run mode** (lines 128-224) — When `DRY_RUN=true`, detects data source availability, sends a test notification with simulated data, and exits immediately.
3. **Helper functions** (lines 243-744) — Process detection, data source management, state persistence, progress calculation, and notification delivery.
4. **Main monitoring loop** (lines 749-865) — An outer `while true` loop waits for a mover process to appear, detects data source (`mover.ini` vs `du` polling), attempts crash recovery from saved state, then an inner loop polls progress every `DU_POLL_INTERVAL` seconds, persists state, and sends notifications at each `NOTIFICATION_INCREMENT` threshold. When the mover process exits, it sends a rich completion notification and restarts the outer loop.

### Data Sources

The script supports two data sources, selected automatically:

- **`mover_ini`** — When the Mover Tuning plugin is installed, reads `/usr/local/emhttp/state/mover.ini` for exact byte counts, file counts, and currently-moving file. Enables late-join (accurate progress regardless of when script starts) and richer completion stats.
- **`du_polling`** — Fallback for standard mover without the plugin. Uses `du -sb $CACHE_PATH` to track cache size reduction. This is the original behavior.

### Key Functions

- `is_mover_running()` — Detects mover via three methods: `pgrep -x "mover"`, `pgrep -x "age_mover"` (Mover Tuning plugin), and `pgrep -f "^/usr/libexec/unraid/move"` (Unraid v7+).
- `detect_data_source()` — Checks for `mover.ini`, sets `DATA_SOURCE` global.
- `read_mover_ini()` — Parses `mover.ini` into `INI_*` globals with staleness detection.
- `get_progress()` — Unified progress reader; sets `PROGRESS_*` globals from either data source.
- `get_mover_pid()` / `get_mover_start_time()` — PID and start time detection for state tracking.
- `init_state_dir()` / `save_state()` / `load_state()` / `save_last_run()` — Persistent state management in `/tmp/mover-status/` for crash recovery.
- `human_readable()` — Converts bytes to TB/GB/MB/KB strings.
- `format_duration()` / `format_speed()` — Seconds-to-duration and bytes/sec-to-speed formatting.
- `build_completion_summary()` — Builds rich completion messages with total moved, file count, duration, and average speed.
- `calculate_etc()` — Estimates completion time using `PROGRESS_*` byte-rate calculation; returns Discord timestamp format (`<t:...:R>`) or human-readable time for Telegram.
- `send_notification()` — Builds and sends JSON payloads to Discord (color-coded embeds) and/or Telegram (HTML-formatted messages). Uses `{percent}`, `{remaining_data}`, `{etc}`, `{file_count}`, `{current_file}` template placeholders. Completion messages support `{total_moved}`, `{duration}`, `{avg_speed}`, `{file_count}`.

### Runtime Dependencies

`bash`, `curl`, `jq`, `du`, `pgrep`, `date`, `stat` — all available on Unraid by default.

## Conventions

- All user-editable configuration is at the top of the script (lines 29-70). The rest of the script is marked "Do Not Modify" for end users.
- Exclusion paths use a naming convention `EXCLUDE_PATH_XX` and are collected dynamically via `${!EXCLUDE_PATH_@}`.
- Discord embed colors: Light Red (<=34%), Light Orange (35-65%), Light Green (66-99%), Green (100%).
- Version checking compares `CURRENT_VERSION` against the latest GitHub release tag.
- Commit messages follow conventional commits (`fix:`, `feat:`, `refactor:`, `chore:`, `docs:`).
