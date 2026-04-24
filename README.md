# HA Config Git Sync

A Home Assistant custom integration that detects configuration changes made via the HA UI and prompts you to push them to git.

## Features

### Automatic Detection & Sync
- **Detects uncommitted changes** — uses filesystem monitoring (inotify) for instant detection (no delay)
- **Detects uncommitted changes** — falls back to periodic polling (default: every 5 minutes)
- **Detects committed-but-unpushed commits** — catches local commits that haven't been pushed yet (e.g., "branch ahead of origin by N commits")
- **Auto-sync to GitHub** — automatically pushes both uncommitted changes and unpushed commits when the "Auto-sync local changes" switch is enabled
- **Manual push button** — push from the HA dashboard or automations (auto-detects uncommitted changes and unpushed commits)

### User Interface & Notifications
- **Persistent notifications** — alerts you when changes are detected, with options to push, dismiss, or view details
- **Dashboard entities:**
  - `sensor.ha_config_git_sync_status` — status: `clean`, `pending_changes`, `pushing`, or `error`
  - `sensor.ha_config_git_sync_last_activity` — description of the last action (push, undo, redo, pull, or error)
  - `binary_sensor.ha_config_git_sync_pending_changes` — ON when uncommitted changes or unpushed commits exist
  - `switch.ha_config_git_sync_auto_sync_local_changes` — toggle auto-sync on/off
  - `button.ha_config_git_sync_push_to_git` — manual push trigger
  - `button.ha_config_git_sync_undo_last_change` — undo / redo toggle

### Advanced Features
- **Undo / redo** — reverts the last commit with `git revert HEAD`; press again to redo (toggle). Changes are automatically reloaded.
- **Status attributes** — sensor shows changed file list, commit hashes, timestamps, and error details
- **Configurable via UI** — Settings → Integrations → HA Config Git Sync → Configure
- **Smart pull filtering** — skips unnecessary operations if remote has no new commits
- **Configuration backup & restore** — automatically backs up git-tracked files before pull operations, restores on failure

## Prerequisites

- HA Green (or any HAOS installation) with a git-initialised config directory
- SSH deploy key on GitHub **with write access** enabled
- [Git Pull](https://github.com/home-assistant/addons/tree/master/git_pull) add-on (for the reverse pull direction)

## Installation

### Via HACS (recommended)

1. Open HACS → Integrations → ⋮ (three dots) → Custom Repositories
2. Add `ongas/ha-config-git-sync` as type **Integration**
3. Search for "HA Config Git Sync" → Download
4. Restart HA

### Manual

1. Copy `custom_components/ha_config_git_sync/` to your HA `custom_components/` directory
2. Restart HA

## Setup

### 1. Enable write access on your deploy key

The Git Pull add-on has an SSH key for pulling from GitHub. To push, it needs **write access**:

1. Get the public key:
   ```bash
   ssh ha "sudo cat /data/git_pull/.ssh/id_ed25519.pub 2>/dev/null || sudo find / -path '*git_pull*' -name '*.pub' 2>/dev/null"
   ```
2. Go to **GitHub → your config repo → Settings → Deploy Keys**
3. Delete the existing key
4. Re-add the same public key with **"Allow write access"** checked

### 2. Make the SSH key accessible

The integration needs to know where the SSH private key is. Common locations:
- `/data/git_pull/.ssh/id_ed25519`
- `/config/.ssh/id_ed25519`
- `/root/.ssh/id_ed25519`

You can symlink if needed:
```bash
sudo ln -s /data/git_pull/.ssh/id_ed25519 /config/.ssh/id_ed25519
```

### 3. Add the integration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **HA Config Git Sync**
3. Configure:

| Setting | Default | Description |
|---|---|---|
| Repository path | `/config` | Path to git repo on HA |
| Branch | `main` | Git branch to push to |
| Remote | `origin` | Git remote name |
| SSH key path | `/config/.ssh/id_ed25519` | Private key for git push |
| Commit author name | `HA Config Sync` | Name shown in git commits |
| Commit author email | `ha-config-sync@local` | Email shown in git commits |
| Notify service | *(empty)* | e.g. `mobile_app_mobile_pixel_6` |
| Scan interval | `5` | Minutes between git status checks |
| Notification cooldown | `30` | Minutes between repeated notifications |

## How It Works

### Automatic Sync (Auto-Sync Enabled)

```
You edit an automation in the HA UI
    ↓
HA writes to automations.yaml on disk
    ↓
Integration detects changes (filesystem watcher or polling)
    ↓
Integration checks git status:
  - Uncommitted changes? → git add -A → git commit
  - Unpushed commits? → (detected from step above)
    ↓
Auto-sync trigger: git push to GitHub
    ↓
Changes are now in GitHub (bidirectional sync working!)
    ↓
Your local dev machine can git pull to stay in sync
```

### Manual Sync (or With Notification)

```
You edit an automation in the HA UI
    ↓
HA writes to automations.yaml on disk
    ↓
Integration detects changes (filesystem watcher or polling)
    ↓
Sends persistent notification to HA panel
    ↓
You tap "Push to Git" (or auto-sync is enabled)
    ↓
Integration runs: git add -A → git commit → git push
    ↓
Changes are now in GitHub
    ↓
Run "git pull" locally to sync your dev machine
```

## Auto-Sync Local Changes

**Enable this to automatically keep HA and GitHub in sync without manual intervention.**

The "Auto-sync local changes" switch (on the integration device page) enables automatic pushing of changes to GitHub as soon as they are detected.

### What It Syncs

When auto-sync is enabled, the integration automatically detects and pushes:

1. **Uncommitted changes** — new/modified files on disk that HA has written but not yet committed
2. **Unpushed commits** — commits that exist locally but haven't been pushed to GitHub yet (e.g., after a pull or if the last push failed)

### When Auto-Sync Runs

- **Immediately** — within 1-2 seconds of file changes (via filesystem watcher)
- **Periodically** — every 5 minutes (configurable poll interval) to catch any missed changes

### Use Case: Prevent HA from Drifting Out of Sync

**Problem:** You edit an automation in the HA UI, then try to edit the same file locally, only to discover they've diverged and there are merge conflicts.

**Solution:** Enable auto-sync. Now whenever you make changes in the HA UI:
1. HA writes to YAML files
2. Integration commits and pushes automatically
3. Your local machine can pull immediately — no more surprises!

## Entities

| Entity | Type | Description |
|---|---|---|
| `sensor.ha_config_git_sync_status` | Sensor | Status: `clean`, `pending_changes`, `pushing`, or `error` |
| `sensor.ha_config_git_sync_last_activity` | Sensor | Description of last action: push, undo, redo, pull, or error with timestamp |
| `binary_sensor.ha_config_git_sync_pending_changes` | Binary Sensor | ON when uncommitted changes or unpushed commits exist |
| `switch.ha_config_git_sync_auto_sync_local_changes` | Switch | Enable/disable automatic syncing |
| `button.ha_config_git_sync_push_to_git` | Button | Manually trigger a git push (detects both uncommitted and unpushed changes) |
| `button.ha_config_git_sync_undo_last_change` | Button | Undo the last commit (creates a revert commit, reloads config, pushes automatically) |

### Status Sensor Attributes

- `changed_files` — list of modified/new files detected
- `changed_count` — number of changed files
- `unpushed_commits` — number of commits waiting to be pushed
- `last_push` — timestamp of last successful push
- `last_push_commit` — short hash of last push commit
- `last_check` — timestamp of last git status check
- `last_error` — last error message (if any)
- `last_activity` — human-readable description of last operation

## Undo / Redo

The **Undo Last Change** button runs `git revert HEAD --no-edit`, which creates a new commit that reverses the previous one. It then automatically reloads the configuration and pushes the result to GitHub.

- **First press** — undoes your last change
- **Second press** — redoes it (reverts the revert)
- Making a new push after an undo starts fresh history

This is the standard git approach: every action is recorded and nothing is ever lost.

## Workflow with Git Pull

This integration handles **HA → GitHub** (push). The [Git Pull](https://github.com/home-assistant/addons/tree/master/git_pull) add-on handles **GitHub → HA** (pull). Together they provide bidirectional sync:

| Direction | Tool | Trigger |
|---|---|---|
| Local dev → GitHub → HA | Git Pull add-on | Manual start from HA UI |
| HA UI → GitHub → Local dev | This integration | Notification + approval |

## Troubleshooting

### Auto-sync not working

**Symptom:** You edited something in the HA UI but auto-sync didn't push to GitHub.

**Check list:**
1. **Is the switch enabled?** — Go to Settings → Devices & Services → HA Config Git Sync → find the device → turn ON the "Auto-sync local changes" switch
2. **Are there actually changes?** — Check `sensor.ha_config_git_sync_status` — should show `pending_changes` if changes exist
3. **Check the activity log** — Click the integration device → scroll to Activity → look for error messages
4. **Check the logs** — Settings → System → Logs → search for `ha_config_git_sync`

### Status shows "pending_changes" but nothing pushes

**Symptom:** `binary_sensor.ha_config_git_sync_pending_changes` is ON, but auto-sync never pushes.

**Check list:**
1. **Is auto-sync enabled?** — See above
2. **Are these uncommitted changes or unpushed commits?** — Check `sensor.ha_config_git_sync_status` attributes for `changed_files` and `unpushed_commits`
3. **Is there a git error?** — Check `last_error` attribute in the status sensor
4. **Try manual push** — Click `button.ha_config_git_sync_push_to_git` to test if manual push works
5. **Check SSH key permissions** — Your deploy key must have write access enabled on GitHub

### "Changes detected after Git Pull"

**Symptom:** After running Git Pull, the integration immediately reports pending changes again.

**Explanation:** This usually happens when:
- Git Pull pulled your config from GitHub
- Your local HA instance has slightly different state (database, secrets, etc.)
- Integration detects these as "changes" and tries to push them back

**Solution:** Increase the **Notification Cooldown** setting (Settings → Integrations → HA Config Git Sync → Configure) to give Git Pull time to settle. Default is 30 minutes. Try 60 minutes.

### Push fails with "Permission denied (publickey)"

The deploy key needs **write access**. See [Setup step 1](#1-enable-write-access-on-your-deploy-key).

### "git binary not found"

The HA Core container may not have git installed. Check with:
```bash
docker exec homeassistant git --version
```

### Notifications not arriving

The integration now uses **HA panel persistent notifications**. Check:
- **Settings → Notifications** — look for notification history
- **Integrations page** — scroll to Activity log on the integration device
- **Status sensor** — `sensor.ha_config_git_sync_status` should show current state

If you don't see notifications, check the integration logs:
- Settings → System → Logs → search for `ha_config_git_sync`

## License

MIT
