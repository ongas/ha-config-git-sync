# Graph Report - /mnt/e/source/personal_repos/homeassistant/custom_components/ha-config-git-sync  (2026-04-28)

## Corpus Check
- Corpus is ~18,053 words - fits in a single context window. You may not need a graph.

## Summary
- 459 nodes · 1029 edges · 20 communities detected
- Extraction: 59% EXTRACTED · 41% INFERRED · 0% AMBIGUOUS · INFERRED: 420 edges (avg confidence: 0.66)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]

## God Nodes (most connected - your core abstractions)
1. `GitSyncCoordinator` - 211 edges
2. `_make_coordinator()` - 67 edges
3. `_mock_process()` - 55 edges
4. `HAConfigGitSyncConfigFlow` - 45 edges
5. `HAConfigGitSyncOptionsFlow` - 33 edges
6. `_make_entry()` - 31 edges
7. `_git()` - 12 edges
8. `GitSyncAutoPushSwitch` - 11 edges
9. `TestFileWatcher` - 9 edges
10. `GitSyncPushButton` - 8 edges

## Surprising Connections (you probably didn't know these)
- `TestRealGitStatus` --uses--> `GitSyncCoordinator`  [INFERRED]
  tests/test_coordinator_integration.py → custom_components/ha_config_git_sync/coordinator.py
- `TestRealGitPush` --uses--> `GitSyncCoordinator`  [INFERRED]
  tests/test_coordinator_integration.py → custom_components/ha_config_git_sync/coordinator.py
- `TestEdgeCases` --uses--> `GitSyncCoordinator`  [INFERRED]
  tests/test_coordinator_integration.py → custom_components/ha_config_git_sync/coordinator.py
- `TestRealGitUndo` --uses--> `GitSyncCoordinator`  [INFERRED]
  tests/test_coordinator_integration.py → custom_components/ha_config_git_sync/coordinator.py
- `TestAutoSyncAheadCommits` --uses--> `GitSyncCoordinator`  [INFERRED]
  tests/test_coordinator_integration.py → custom_components/ha_config_git_sync/coordinator.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.0
Nodes (93): DataUpdateCoordinator, Return remote change details., Return True if there are pending changes., Return icon based on state., Return changed file count., Return True if remote has commits we don't have., Return icon based on state., Return dynamic icon based on undo/redo state. (+85 more)

### Community 1 - "Community 1"
Cohesion: 0.0
Nodes (69): Undo/redo: revert the most recent commit with git revert HEAD.          Acts as, Handle a notification action response., Reload YAML-based config without disrupting integration connections.          Ca, Pull latest changes from remote, validate config, and reload.          Fetches f, _make_coordinator(), _mock_process(), test_action_dismiss_resets_cooldown(), test_action_push_triggers_push() (+61 more)

### Community 2 - "Community 2"
Cohesion: 0.0
Nodes (59): ConfigFlow, async_get_options_flow(), HAConfigGitSyncConfigFlow, HAConfigGitSyncOptionsFlow, Config flow for HA Config Git Sync., Step 2: Notification and commit settings., Check if git binary is available., Check if the path is a git repository. (+51 more)

### Community 3 - "Community 3"
Cohesion: 0.0
Nodes (37): One-time setup: verify git and configure safe directory., Poll git status and check for remote changes., Return the number of local commits not yet pushed to the remote.          Return, Push committed-but-unpushed changes when auto-sync is enabled.          Called f, Commit all changes and push to remote., _git(), _make_entry(), Integration tests — real git operations against a local disposable repo. (+29 more)

### Community 4 - "Community 4"
Cohesion: 0.0
Nodes (26): BinarySensorEntity, ButtonEntity, CoordinatorEntity, async_setup_entry(), GitSyncPendingChangesSensor, GitSyncRemoteUpdateSensor, Binary sensor platform for HA Config Git Sync., Set up binary sensors. (+18 more)

### Community 5 - "Community 5"
Cohesion: 0.0
Nodes (18): FileSystemEventHandler, Constants for HA Config Git Sync., _GitIgnoreAwareHandler, Git operations coordinator for HA Config Git Sync., Start the filesystem watcher for instant change detection., File system event handler that ignores .git/ directory changes., async_setup_entry(), async_unload_entry() (+10 more)

### Community 6 - "Community 6"
Cohesion: 0.0
Nodes (12): Exception, Send an actionable notification to the configured mobile device.          Skips, Check if all pending changes are YAML formatting-only (no semantic diff)., Send a persistent notification to HA panel only., Run a git command asynchronously., Fetch from remote and check for new commits (best-effort).          Detects whet, Send notification about available remote changes to HA panel and mobile., Send notification if cooldown allows. (+4 more)

### Community 7 - "Community 7"
Cohesion: 0.0
Nodes (9): Build the data dict exposed to entities., Update status and activity, then push to entities., Push existing local commits to the remote (no staging/committing)., GitSyncAutoPushSwitch, Switch to enable/disable automatic push of local changes., Initialize the switch., Restore previous state on startup., RestoreEntity (+1 more)

### Community 8 - "Community 8"
Cohesion: 0.0
Nodes (11): _callback_passthrough(), fake_entry(), fake_hass(), _FakeConfigFlow, git_repo(), Shared fixtures for HA Config Git Sync tests., Return a minimal fake HomeAssistant object., Return a minimal fake ConfigEntry with default data. (+3 more)

### Community 9 - "Community 9"
Cohesion: 0.0
Nodes (9): async_setup_entry(), GitSyncLastActivitySensor, GitSyncStatusSensor, Sensor platform for HA Config Git Sync., Initialize the sensor., Sensor showing git sync status and changed files., Initialize the sensor., Sensor showing the last activity performed by the integration. (+1 more)

### Community 10 - "Community 10"
Cohesion: 0.0
Nodes (8): Stop the filesystem watcher., Watcher should start an observer and stop cleanly., stop_watcher must offload observer.stop()/join() to a thread executor., Calling start_watcher twice should not create a second observer., Stopping a watcher that was never started should not error., Watcher should fire the handler callback when a file changes., Changes inside .git/ should not trigger events., TestFileWatcher

### Community 11 - "Community 11"
Cohesion: 0.0
Nodes (3): Handle a filesystem event (called from watcher thread via loop)., _on_filesystem_event should be a no-op when _git_operating is True., TestGitOperationGuard

### Community 12 - "Community 12"
Cohesion: 0.0
Nodes (1): Check if git binary is available.

### Community 13 - "Community 13"
Cohesion: 0.0
Nodes (1): Check if HA configuration is valid after pulling new files.

### Community 14 - "Community 14"
Cohesion: 0.0
Nodes (1): Delete old backup files, keeping only the specified one.                  Called

### Community 15 - "Community 15"
Cohesion: 0.0
Nodes (2): Tests for merge conflict detection during pull operations., TestMergeConflictDetection

### Community 16 - "Community 16"
Cohesion: 0.0
Nodes (1): Initialize the coordinator.

### Community 17 - "Community 17"
Cohesion: 0.0
Nodes (1): Restore git-tracked files from a disk-based backup.                  Returns Tru

### Community 18 - "Community 18"
Cohesion: 0.0
Nodes (1): Test package for HA Config Git Sync.

### Community 19 - "Community 19"
Cohesion: 0.0
Nodes (1): Get the options flow handler.

## Knowledge Gaps
- **131 isolated node(s):** `Return True if there are pending changes.`, `Return icon based on state.`, `Return changed file count.`, `Return True if remote has commits we don't have.`, `Return icon based on state.` (+126 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 12`** (2 nodes): `._check_git_available()`, `Check if git binary is available.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 13`** (2 nodes): `._check_config_valid()`, `Check if HA configuration is valid after pulling new files.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (2 nodes): `._cleanup_old_backups()`, `Delete old backup files, keeping only the specified one.                  Called`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (2 nodes): `Tests for merge conflict detection during pull operations.`, `TestMergeConflictDetection`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (2 nodes): `.__init__()`, `Initialize the coordinator.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (2 nodes): `._restore_config_backup()`, `Restore git-tracked files from a disk-based backup.                  Returns Tru`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (2 nodes): `__init__.py`, `Test package for HA Config Git Sync.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Get the options flow handler.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.