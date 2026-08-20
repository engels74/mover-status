# AGENTS.md

This file provides guidance to AI coding agents when working with code in this
repository.

## Repository shape

`moverStatus.sh` (990 lines) is the entire product: one self-contained Bash script that users
copy-paste into the Unraid "User Scripts" plugin. There is no build, no package manager, no test
suite, and no CI — `.github/` holds only issue templates, and `renovate.json` only governs
dependency PRs.

Because it is distributed by copy-paste, the script must not `source` external files, split into
modules, or add dependencies beyond those declared at `moverStatus.sh:15` (`bash`, `curl`, `jq`,
`du`, `pgrep`, `date`; `stat` is also used). Add helpers as functions inside `moverStatus.sh`, and
keep `main` always holding a runnable script — install step 7 in `README.md` points users at the
raw file on `main`.

## Commands

```bash
shellcheck moverStatus.sh   # the only linter; currently exits 0 with no output
bash -n moverStatus.sh      # syntax-only parse, fast check after an edit
```

Keep `shellcheck` clean. Suppress a genuinely unavoidable warning inline with
`# shellcheck disable=SCxxxx` directly above the affected line (existing examples at `:67`,
`:313`, `:528`) rather than leaving it unfixed.

The script cannot be exercised end-to-end off an Unraid box — it polls mover processes and reads
`/usr/local/emhttp/state/mover.ini`. `DRY_RUN=true` sends one fabricated notification and exits.

## Architecture

One file, three concerns:

- **Config and fail-fast validation** — settings block (`:31-42`), then checks that `exit 1` on
  bad input (`:90-121`).
- **Data acquisition** — `detect_data_source` (`:295-303`) picks one of two modes:
  `mover_ini` parses `/usr/local/emhttp/state/mover.ini` (written by the Mover Tuning plugin) and
  supplies byte totals *and* file counts; `du_polling` runs `du -sb "$CACHE_PATH"` against an
  initial snapshot and has no file info. `get_progress` (`:349-432`) is the single funnel — both
  modes populate the same `PROGRESS_*` globals.
- **Presentation** — `send_notification` (`:729-833`), `calculate_etc` (`:693-727`), and
  `build_completion_summary` (`:631-667`) read only `PROGRESS_*`.

Keep new progress consumers on `PROGRESS_*` instead of re-reading `mover.ini` or shelling out to
`du` again: the excluded-path subtraction and the 99% cap exist only inside `get_progress`.

**Crash recovery:** `save_state` (`:480-499`) writes `/tmp/mover-status/state` atomically on every
poll. `load_state` (`:503-571`) resumes only when the saved `MOVER_PID` *and* its `/proc/<pid>`
start time both still match, which guards against PID reuse. A finished run writes
`/tmp/mover-status/last-run` and deletes the state file.

**Main loop** (`:839-971`): the outer loop waits indefinitely for a mover process; the inner loop
ticks every 5 s but recalculates progress only once `DU_POLL_INTERVAL` seconds have passed.

## Gotchas

- **Adding a message placeholder takes two edits.** Substitute it in `send_notification` for both
  `value_message_discord` and `value_message_telegram` (`:750-761`), *and* in the dry-run block
  (`:173-185`), which builds its payloads independently and will otherwise emit a literal
  `{token}`. The two placeholder sets are disjoint: progress tokens (`{percent}`,
  `{remaining_data}`, `{etc}`, `{file_count}`, `{current_file}`) are substituted in
  `send_notification`; completion tokens (`{total_moved}`, `{file_count}`, `{duration}`,
  `{avg_speed}`) only in `build_completion_summary` (`:653-666`).
- **Discord payloads are hand-built JSON strings; Telegram payloads use `jq -n --arg`.** The
  Discord embed (`:805-823`) interpolates message text straight into a JSON literal, so anything
  reaching it must already be JSON-safe — `DISCORD_*` messages use `\n` for newlines. Telegram
  posts with `parse_mode: "HTML"`, so `TELEGRAM_*` messages use `&#10;` and HTML tags. Do not swap
  the conventions; to put arbitrary or user-derived text on the Discord path, build that payload
  with `jq -n` the way the Telegram path does (`:789-793`).
- **The `#name=` / `#backgroundOnly=true` / `#arrayStarted=true` header (`:4-7`) is parsed by the
  Unraid User Scripts plugin.** Keep it immediately below the shebang; relocating or reformatting
  it breaks background execution and array-start scheduling.
- **Mover detection is duplicated.** `is_mover_running` (`:256-261`) and `get_mover_pid`
  (`:435-451`) each match the same three patterns (`mover`, `age_mover`,
  `^/usr/libexec/unraid/move`). Add new patterns to both, or loop-exit and state-resume logic will
  disagree.
- **Changing which fields `save_state` writes requires bumping `STATE_VERSION`** (`:483`) and
  updating the restore block in `load_state` (`:556-567`). `load_state` deletes any state file
  whose version is not `1` (`:516-520`) — that is the intended migration path for old files.
- **`DRY_RUN=true` does not skip startup validation.** The checks at `:90-121` run before the
  dry-run block (`:131-224`), so a dry run still requires a valid webhook config and an existing
  `CACHE_PATH` directory.
- **ETA rate is measured from when this script started watching**, via `monitoring_start_bytes`
  (`calculate_etc:700-703`), not from mover start — that is what keeps late-join ETAs sane. Don't
  derive a rate from `PROGRESS_MOVED_BYTES` alone.

## Adding a configuration setting

1. Add it to the settings block (`:31-42`) with an inline comment.
2. Add a fail-fast check alongside the existing ones if a bad value would break the run — follow
   the `DU_POLL_INTERVAL` (`:112-115`) and `CACHE_PATH` (`:117-121`) pattern.
3. Add it to the `### ⚙️ Script Settings` list in `README.md`. That list is already behind the
   script: `DU_POLL_INTERVAL`, `CACHE_PATH`, `ENABLE_FILE_INFO`, `DISCORD_COMPLETION_MESSAGE`, and
   `TELEGRAM_COMPLETION_MESSAGE` are all undocumented there.

## Cutting a release

1. Bump `CURRENT_VERSION` (`:76`) in a standalone commit messaged `chore: update script version`.
2. Tag that commit with the bare version — `0.0.12`, **not** `v0.0.12`. Every existing tag
   `0.0.1`–`0.0.11` follows this.
3. Publish a GitHub release for the tag.

`check_latest_version` (`:79-81`) reads `.[0].tag_name` from the GitHub releases API and compares
it to `CURRENT_VERSION` with exact string equality (`:169`, `:764`). A `v` prefix, or a tag that
does not match `CURRENT_VERSION` character-for-character, makes every notification footer
permanently read "(update available)".

## Reference

- `README.md` — the only user-facing documentation: install steps, settings list, Telegram and
  Discord setup. Read before changing the settings block, notification behaviour, or install
  instructions.
- `.github/ISSUE_TEMPLATE/01_bug_report.yml` — what reporters are required to supply (debug log
  from `ENABLE_DEBUG=true`, Unraid version, script version). Read when triaging an issue.
