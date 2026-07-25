# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Scope

- `moverStatus.sh` is both the implementation and the distributed artifact: users copy the
  whole file into Unraid's User Scripts plugin. Keep runtime changes in that file.
- The script intentionally uses Unraid/GNU interfaces (`/mnt/cache`, `/proc`, GNU `date`,
  `du -sb`, and `stat -c`). Do not replace them with macOS/BSD-compatible variants unless the
  Unraid behavior remains the authority.
- There is currently no repository-defined build, lint, typecheck, or test command. Do not
  resurrect commands from deleted Python-era files or present a locally invented check as the
  project test suite.

## Coupled behavior

- Mover identity is duplicated in `is_mover_running()` and `get_mover_pid()`. Add or change a
  supported process in both places; process detection controls completion while PID detection
  controls crash recovery.
- `get_progress()` has two production paths: Mover Tuning's
  `/usr/local/emhttp/state/mover.ini` and the `du` fallback. Preserve both paths when changing
  progress, exclusions, ETA inputs, or completion statistics.
- A running mover is capped at 99%; process exit is what produces the 100% notification. Do not
  report 100 from progress calculation; use the existing finalization path.
- Excluded-directory size is snapshotted once per mover run and subtracted in both data-source
  paths. Change exclusion accounting in both branches rather than recalculating only one.
- `save_state()` and `load_state()` share the sourced `/tmp/mover-status/state` format. Keep
  field names, restoration, validation, and `STATE_VERSION` handling synchronized.
- Moving-message placeholders are expanded separately in dry-run and live notifications, for
  Discord and Telegram. Completion placeholders are expanded in `build_completion_summary()`.
  Wire a new placeholder through every applicable expansion site instead of only its template.
- `DRY_RUN=true` still validates `CACHE_PATH`, calls the GitHub releases API, and sends enabled
  webhook messages. Use test credentials on an Unraid-like host; it is not an offline local
  simulation.

## Runtime constraints

- Do not add a script-level lock or recommend cron. Run it in the User Scripts plugin's
  background mode, or schedule it for **At Startup of Array**; the plugin owns instance locking.
- The User Scripts metadata comments at the top (`backgroundOnly` and `arrayStarted`) are part
  of deployment behavior; preserve them when editing the header.

## References

- `README.md` — installation, user-editable settings, notification setup, and startup
  scheduling. Read before changing deployment or configuration documentation.
