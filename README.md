# HA Config Git Sync

A Home Assistant custom integration that detects configuration changes made via the HA UI and prompts you to push them to git.

## Features

- **Polls git status** on a configurable interval (default: every 5 minutes)
- **Instant change detection** — uses filesystem monitoring (inotify) to detect changes immediately, without waiting for the next poll
- **Actionable phone notifications** — tap "Push to Git" or "Dismiss" directly from the notification
- **Manual push button** — push from the HA dashboard or automations
- **Undo / redo button** — reverts the last commit with `git revert HEAD`; press again to redo (toggle)
- **Dashboard entities:**
  - `sensor.ha_config_git_sync_status` — clean / pending_changes / pushing / error
  - `binary_sensor.ha_config_git_sync_pending_changes` — on when uncommitted changes exist
  - `button.ha_config_git_sync_push_to_git` — manual push trigger
  - `button.ha_config_git_sync_undo_last_change` — undo / redo toggle
- **Configurable via UI** — Settings → Integrations → HA Config Git Sync → Configure

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

```
You edit an automation in the HA UI
    ↓
HA writes to automations.yaml on disk
    ↓
Integration detects uncommitted changes (git status + filesystem watcher)
    ↓
Sends actionable notification to your phone
    ↓
You tap "Push to Git"
    ↓
Integration runs: git add -A → git commit → git push
    ↓
Changes are now in GitHub
    ↓
Run "git pull" locally to sync your dev machine
```

## Entities

| Entity | Type | Description |
|---|---|---|
| `sensor.ha_config_git_sync_status` | Sensor | Status: `clean`, `pending_changes`, `pushing`, `error` |
| `binary_sensor.ha_config_git_sync_pending_changes` | Binary Sensor | ON when uncommitted changes exist |
| `button.ha_config_git_sync_push_to_git` | Button | Manually trigger a git push |
| `button.ha_config_git_sync_undo_last_change` | Button | Undo (or redo) the last commit |

### Status Sensor Attributes

- `changed_files` — list of modified files
- `changed_count` — number of changed files
- `last_push` — timestamp of last successful push
- `last_push_commit` — short hash of last push commit
- `last_check` — timestamp of last git status check
- `last_error` — last error message (if any)

## Undo / Redo

The **Undo Last Change** button runs `git revert HEAD --no-edit`, which creates a new commit that reverses the previous one. It then pushes the result automatically.

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

### "git binary not found"
The HA Core container may not have git installed. Check with:
```bash
docker exec homeassistant git --version
```

### Push fails with "Permission denied (publickey)"
The deploy key needs write access. See [Setup step 1](#1-enable-write-access-on-your-deploy-key).

### Notifications not arriving
Ensure the `notify_service` matches your device exactly (e.g. `mobile_app_mobile_pixel_6`). Test with Developer Tools → Services.

### Changes detected after Git Pull
The integration ignores changes for the duration of the notification cooldown. Increase the cooldown if Git Pull triggers unwanted notifications.

## License

MIT
