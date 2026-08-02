# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Shape

`moverStatus.sh` is the entire product: one self-contained Bash script that users copy-paste into the Unraid "User Scripts" plugin (see the install steps in `README.md`). There is no build, no package manager, no test suite, and no CI — `.github/` holds only issue templates, and `renovate.json` only governs dependency PRs.

Because the script is distributed by copy-paste, it must not `source` external files, split into modules, or add dependencies beyond those declared at `moverStatus.sh:15` (`bash`, `curl`, `jq`, `du`, `pgrep`, `date`; `stat` is also used). Add new helpers as functions inside `moverStatus.sh`.

## Essential Commands

Run from the repository root:

```bash
shellcheck moverStatus.sh   # the only linter; currently exits 0 with no output
bash -n moverStatus.sh      # syntax-only parse, fast check after an edit
```

Keep `shellcheck` clean. When a warning is genuinely unavoidable, suppress it inline with `# shellcheck disable=SCxxxx` directly above the affected line (existing examples at `moverStatus.sh:67`, `:313`, `:528`) rather than leaving it unfixed.

The script cannot be exercised end-to-end on a dev machine — it polls Unraid mover processes and reads `/usr/local/emhttp/state/mover.ini`.

## Architecture Overview

Three layers inside the single file:

1. **Config and validation** (`moverStatus.sh:27-125`) — user-edited settings, then fail-fast checks that `exit 1` on bad input.
2. **Data acquisition** — `detect_data_source` (`:295-303`) picks one of two modes per monitoring cycle:
   - `mover_ini` — parses `/usr/local/emhttp/state/mover.ini`, written by the Mover Tuning plugin. Supplies byte totals *and* file counts / current file.
   - `du_polling` — `du -sb "$CACHE_PATH"` against an initial snapshot. No file info available.

   `get_progress` (`:349-432`) is the single funnel: both modes populate the same `PROGRESS_*` globals, including the excluded-path subtraction.
3. **Presentation** — `send_notification` (`:729-833`) builds and posts the Discord and Telegram payloads.

Notification, ETA, and completion-summary code (`calculate_etc`, `build_completion_summary`, `send_notification`) reads only `PROGRESS_*`. Keep new consumers on those globals instead of re-reading `mover.ini` or shelling out to `du` again — the exclusion math and the 99%-cap only exist inside `get_progress`.

**Crash recovery:** state is written atomically to `/tmp/mover-status/state` on every poll (`save_state`, `:480-499`). `load_state` (`:503-571`) resumes only when the saved `MOVER_PID` *and* its `/proc/<pid>` start time both still match, which guards against PID reuse. A finished run writes `/tmp/mover-status/last-run` and deletes the state file.

**Main loop** (`:839-971`): the outer loop waits indefinitely for a mover process; the inner loop ticks every 5 s but only recalculates progress once `DU_POLL_INTERVAL` seconds have passed.

## Common Change Workflows

### Add a message placeholder

1. Add the `${msg//\{token\}/$value}` substitution in `send_notification` for **both** `value_message_discord` and `value_message_telegram` (`:751-761`).
2. Mirror it in the dry-run block (`:174-184`), which builds its payloads independently and will otherwise emit a literal `{token}`.
3. Note the two placeholder sets are disjoint: progress tokens (`{percent}`, `{remaining_data}`, `{etc}`, `{file_count}`, `{current_file}`) are substituted in `send_notification`; completion tokens (`{total_moved}`, `{file_count}`, `{duration}`, `{avg_speed}`) only in `build_completion_summary` (`:653-666`).

### Add a configuration setting

1. Add it to the settings block (`:31-42`) with an inline comment.
2. Add a fail-fast check alongside the existing ones (`:91-121`) if a bad value would break the run — follow the `DU_POLL_INTERVAL` (`:112-115`) and `CACHE_PATH` (`:117-121`) pattern.
3. Add it to the `### ⚙️ Script Settings` list in `README.md`. That list is already behind the script — `DU_POLL_INTERVAL`, `CACHE_PATH`, and `ENABLE_FILE_INFO` are undocumented there, as are the `*_COMPLETION_MESSAGE` variables.

### Cut a release

1. Bump `CURRENT_VERSION` (`:76`) in a standalone commit messaged `chore: update script version` (matches `b7db20d`, `64323d8`, `073e421`).
2. Tag that commit with the bare version — `0.0.11`, **not** `v0.0.11`. Every existing tag `0.0.1`–`0.0.10` follows this.
3. Publish a GitHub release for the tag.

`check_latest_version` (`:79-81`) reads `.[0].tag_name` from the GitHub releases API and compares it to `CURRENT_VERSION` with exact string equality (`:169`, `:764`). A `v` prefix, or a tag that does not match `CURRENT_VERSION` character-for-character, makes every notification footer permanently read "(update available)".

## Critical Gotchas

- **Discord payloads are hand-built JSON strings; Telegram payloads use `jq -n --arg`.** The Discord embed (`:805-823`) interpolates message text straight into a JSON literal, so anything reaching it must already be JSON-safe — `DISCORD_*` messages use `\n` for newlines. Telegram posts with `parse_mode: "HTML"`, so `TELEGRAM_*` messages use `&#10;` and HTML tags. Do not swap the conventions; if you need to put arbitrary or user-derived text into the Discord path, build that payload with `jq -n` the way the Telegram path does (`:790-793`).
- **The `#name=` / `#backgroundOnly=true` / `#arrayStarted=true` header (`:3-7`) is parsed by the Unraid User Scripts plugin.** Keep it immediately below the shebang; relocating or reformatting it breaks background execution and array-start scheduling.
- **Mover detection is duplicated.** `is_mover_running` (`:256-261`) and `get_mover_pid` (`:445`) each match the same three patterns (`mover`, `age_mover`, `^/usr/libexec/unraid/move`). Add new patterns to both, or loop-exit and state-resume logic will disagree.
- **Changing which fields `save_state` writes requires bumping `STATE_VERSION`** (`:483`) and updating the restore block in `load_state` (`:556-567`). `load_state` deletes any state file whose version is not `1` (`:516-520`) — that is the intended migration path for old files.
- **`DRY_RUN=true` does not skip startup validation.** Lines `:91-121` run first, so a dry run still requires a valid webhook config and an existing `CACHE_PATH` directory before it reaches the dry-run block (`:131-224`).

## Additional Documentation

- `README.md` — Read before changing the settings block, notification behaviour, or install instructions. It is the only user-facing documentation, and step 7 of its install section tells users to copy `moverStatus.sh` from `main`, so `main` must always hold a runnable script.
