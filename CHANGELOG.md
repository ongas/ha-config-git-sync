# Changelog

## [1.4.0] — 2026-04-10

### Added

- **Auto-reload configuration after undo** — pressing the Undo button now calls `homeassistant.reload_all` after a successful `git revert` + `git push`, so reverted YAML changes take effect immediately without a manual reload.
- Notification title updated to "Config Reverted & Reloaded" to reflect the new behaviour.
- Reload failure is non-fatal: if the reload service errors, the undo still succeeds and a warning is logged.

## [1.3.2] and earlier

See [GitHub Releases](https://github.com/ongas/ha-config-git-sync/releases).
