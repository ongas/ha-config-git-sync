# Changelog

## [1.14.0] — 2026-04-24

### Added

- **Mobile push notifications** — Sends actionable notifications to a configured mobile device (via HA Companion App) with "Sync Now" / "Dismiss" buttons for local changes and "Pull Now" / "Dismiss" for remote changes. Configurable in integration options (`notify_service` field). Uses notification tags to prevent stacking and respects the existing cooldown to avoid spam.
- **YAML formatting-only commit suppression** — Detects when pending changes are purely cosmetic YAML reformatting (line wrapping, quote style differences) by comparing parsed YAML structures. Automatically discards these changes instead of creating meaningless commits. Applies to both manual sync and auto-push.

### Changed

- Notifications now send both persistent notifications (HA UI) and mobile notifications (when configured).
- Pull notifications only show the "Pull Now" action when safe (no local ahead commits or uncommitted changes).

## [1.13.1] — 2026-04-24

### Changed

- **README documentation** — Comprehensive update with all current features, including auto-sync capabilities, entity descriptions, workflows, and troubleshooting guides.

## [1.12.0] — 2026-04-24

### Added

- **Auto-sync unpushed commits** — Detects committed-but-unpushed local commits (e.g., "branch ahead of origin by N commits") and automatically pushes them when auto-sync is enabled. Previously only uncommitted file changes triggered a push.
- **Manual push handles ahead commits** — The "Push to git" button now detects and pushes unpushed commits even when the working tree is clean.
- New coordinator methods: `_count_unpushed_commits()` (local `rev-list` check, no network needed), `_auto_push_ahead_commits()`, `_push_to_remote()`.

### Fixed

- **Auto-sync setting now actually works** — Removed the non-functional `auto_push_enabled` toggle from config/options flow. The switch entity on the device page is now the sole control, as intended.
- **SSH command conditional** — `_push_to_remote()` only sets `GIT_SSH_COMMAND` when an SSH key is configured, supporting local remotes without SSH.

### Changed

- Renamed switch entity from "Auto-push local to Git" to "Auto-sync local changes" for clarity.
- Removed `auto_push_enabled` from `strings.json` and `translations/en.json`.

## [1.9.8] — 2026-04-21

### Fixed

- **Push race condition** — "Push to git" now runs a fresh `git status` check before deciding there are no changes. Previously, pressing push immediately after a file change could show "No changes to sync" because the poll cycle hadn't updated yet.

## [1.9.7] — 2026-04-21

### Fixed

- Show "Config reloaded" confirmation in sensor activity after successful pull — previously only showed "Pulled {hash}" with no indication that reload succeeded.

## [1.9.6] — 2026-04-21

### Added

- **Skip pull when no remote changes** — After fetching, compares local HEAD with remote using `merge-base`. If remote has no new commits, returns "Already up to date" without stashing, merging, validating, or reloading. Reduces unnecessary operations and avoids disrupting HA.
- **Disk-based backup persistence** — Backups are now stored as JSON files in `.git/ha-config-git-sync-backup/` instead of in-memory dicts. Backups survive the pull operation lifecycle and persist on disk.
- **Backup cleanup after successful reload** — Old backup files are only deleted after a confirmed successful config reload. The latest backup always remains on disk as a safety net.
- **Non-blocking file I/O in backups** — Backup creation and restoration now use `async_add_executor_job` to avoid blocking the HA event loop during file reads/writes.

### Changed

- Pull flow reordered: fetch → compare → [backup → stash → merge] for efficiency. Backup only created when remote actually has new commits.

## [1.9.5] — 2026-04-21

### Fixed

- **Fix backup creation crash: `_run_git` tuple not unpacked** — `_run_git()` returns `(returncode, stdout, stderr)` but the backup code assigned the whole tuple to a single variable, then called `.strip()` on it, causing an `AttributeError`. This was the root cause of "Pull failed: Failed to create config backup before pull". Now properly unpacks the tuple and checks the return code.

## [1.9.4] — 2026-04-21

### Fixed

- **Fix backup creation failure blocking pull operations** — The backup creation was failing if any exception occurred during `git ls-files`, which blocked the entire pull operation. Now backup creation gracefully handles failures and returns an empty dict, allowing the pull to proceed. This fixes the error "Pull failed: Failed to create config backup before pull".

## [1.9.3] — 2026-04-21

### Fixed

- **CRITICAL: Fix Home Assistant event loop blocking** — The backup system was using synchronous blocking I/O (tarfile, shutil) in async methods, freezing the event loop and causing HA to crash on "Pull from Git". Completely rewrote backup system to use in-memory dictionary with zero blocking operations.
- **Backup captures ONLY git-tracked files** — Previous implementation was backing up the entire `/config` directory (multi-gigabyte tar.gz). Now captures only files managed by git, making backups lightweight and fast.
- **Added multi-layered recovery** — Backup now restored as fallback for merge conflicts, config validation failures, and config reload failures. If new config fails to reload, system automatically restores and retries with old config.

## [1.5.2] — 2026-04-18

### Added

- Enhanced logging when sync button is pressed to show detailed information about the operation.
- Logs now show: sync button activation, detection of no changes, and file count on successful push.
- `last_activity` sensor now updates to "No changes to sync" when repository is clean, making the state visible in the UI.

## [1.5.1] — 2026-04-11

### Fixed

- Removed `by Custom` manufacturer suffix from device display in the Home Assistant UI.

## [1.5.0] — 2026-04-10

### Added

- **Last Activity sensor** — new `sensor.ha_config_git_sync_last_activity` shows a description of the last action (push, undo, redo, or failure) in the device's Activity log on the integration page.

## [1.4.0] — 2026-04-10

### Added

- **Auto-reload configuration after undo** — pressing the Undo button now calls `homeassistant.reload_all` after a successful `git revert` + `git push`, so reverted YAML changes take effect immediately without a manual reload.
- Notification title updated to "Config Reverted & Reloaded" to reflect the new behaviour.
- Reload failure is non-fatal: if the reload service errors, the undo still succeeds and a warning is logged.

## [1.3.2] and earlier

See [GitHub Releases](https://github.com/ongas/ha-config-git-sync/releases).
