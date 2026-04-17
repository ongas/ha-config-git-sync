# Changelog

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
