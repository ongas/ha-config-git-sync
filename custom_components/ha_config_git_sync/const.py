"""Constants for HA Config Git Sync."""

DOMAIN = "ha_config_git_sync"
PLATFORMS = ["sensor", "binary_sensor", "button"]

# Config keys
CONF_REPO_PATH = "repo_path"
CONF_BRANCH = "branch"
CONF_REMOTE = "remote"
CONF_SSH_KEY_PATH = "ssh_key_path"
CONF_COMMIT_AUTHOR_NAME = "commit_author_name"
CONF_COMMIT_AUTHOR_EMAIL = "commit_author_email"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_NOTIFICATION_COOLDOWN = "notification_cooldown"
CONF_INIT_GIT = "init_git"

# Defaults
DEFAULT_REPO_PATH = "/config"
DEFAULT_BRANCH = "main"
DEFAULT_REMOTE = "origin"
DEFAULT_SSH_KEY_PATH = "/config/.ssh/id_ed25519"
DEFAULT_COMMIT_AUTHOR_NAME = "HA Config Sync"
DEFAULT_COMMIT_AUTHOR_EMAIL = "ha-config-sync@local"
DEFAULT_SCAN_INTERVAL = 5  # minutes (fallback poll; primary is inotify)
DEFAULT_NOTIFICATION_COOLDOWN = 30  # minutes
DEFAULT_DEBOUNCE_SECONDS = 5  # debounce rapid filesystem events

# Notification actions
ACTION_PUSH = "HA_GIT_SYNC_PUSH"
ACTION_DISMISS = "HA_GIT_SYNC_DISMISS"

# Statuses
STATUS_CLEAN = "clean"
STATUS_PENDING = "pending_changes"
STATUS_PUSHING = "pushing"
STATUS_PULLING = "pulling"
STATUS_VALIDATING = "validating"
STATUS_RELOADING = "reloading"
STATUS_ERROR = "error"
STATUS_MERGE_CONFLICT = "merge_conflict"
