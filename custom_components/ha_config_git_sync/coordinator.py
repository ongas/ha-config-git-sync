"""Git operations coordinator for HA Config Git Sync."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import timedelta

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ACTION_DISMISS,
    ACTION_PUSH,
    CONF_BRANCH,
    CONF_COMMIT_AUTHOR_EMAIL,
    CONF_COMMIT_AUTHOR_NAME,
    CONF_NOTIFICATION_COOLDOWN,
    CONF_NOTIFY_SERVICE,
    CONF_REMOTE,
    CONF_REPO_PATH,
    CONF_SCAN_INTERVAL,
    CONF_SSH_KEY_PATH,
    DEFAULT_DEBOUNCE_SECONDS,
    DOMAIN,
    STATUS_CLEAN,
    STATUS_ERROR,
    STATUS_MERGE_CONFLICT,
    STATUS_PENDING,
    STATUS_PULLING,
    STATUS_PUSHING,
    STATUS_RELOADING,
    STATUS_VALIDATING,
)

_LOGGER = logging.getLogger(__name__)


class _GitIgnoreAwareHandler(FileSystemEventHandler):
    """File system event handler that ignores .git/ directory changes."""

    def __init__(self, coordinator, loop):
        self._coordinator = coordinator
        self._loop = loop

    def on_any_event(self, event):
        # Ignore changes inside .git/ directory
        if "/.git/" in event.src_path or event.src_path.endswith("/.git"):
            return
        self._loop.call_soon_threadsafe(self._coordinator._on_filesystem_event)


class GitSyncCoordinator(DataUpdateCoordinator):
    """Coordinator that polls git status and manages push operations."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize the coordinator."""
        # Options flow saves to entry.options; merge over entry.data
        cfg = {**entry.data, **entry.options}
        self._repo_path: str = cfg[CONF_REPO_PATH]
        self._branch: str = cfg[CONF_BRANCH]
        self._remote: str = cfg[CONF_REMOTE]
        self._ssh_key_path: str = cfg[CONF_SSH_KEY_PATH]
        self._author_name: str = cfg[CONF_COMMIT_AUTHOR_NAME]
        self._author_email: str = cfg[CONF_COMMIT_AUTHOR_EMAIL]
        self._notify_service: str = cfg[CONF_NOTIFY_SERVICE]
        self._cooldown_minutes: int = cfg[CONF_NOTIFICATION_COOLDOWN]

        self._last_notification: float | None = None
        self._status: str = STATUS_CLEAN
        self._changed_files: list[str] = []
        self._last_push: str | None = None
        self._last_push_commit: str | None = None
        self._last_error: str | None = None
        self._git_available: bool = False
        self._observer: Observer | None = None
        self._debounce_handle: asyncio.TimerHandle | None = None
        self._debounce_seconds: float = DEFAULT_DEBOUNCE_SECONDS
        self._is_revert_head: bool = False
        self._git_operating: bool = False
        self._last_activity: str | None = None
        self._merge_conflict_files: list[str] = []
        self._has_merge_conflict: bool = False

        scan_interval = entry.data[CONF_SCAN_INTERVAL]

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )

    async def async_setup(self) -> None:
        """One-time setup: verify git and configure safe directory."""
        self._git_available = await self._check_git_available()
        if not self._git_available:
            _LOGGER.error("git binary not found — integration cannot function")
            return

        # Ensure safe.directory is set (Docker ownership mismatch)
        await self._run_git(
            "config", "--global", "--add", "safe.directory", self._repo_path
        )

    def start_watcher(self) -> None:
        """Start the filesystem watcher for instant change detection."""
        if self._observer is not None:
            return

        try:
            handler = _GitIgnoreAwareHandler(self, self.hass.loop)
            self._observer = Observer()
            self._observer.schedule(handler, self._repo_path, recursive=True)
            self._observer.daemon = True
            # Run observer.start() in thread executor to avoid blocking event loop
            # watchdog's Observer.start() uses os.walk() which blocks
            self.hass.loop.run_in_executor(None, self._observer.start)
            _LOGGER.info("File watcher started on %s", self._repo_path)
        except Exception:
            _LOGGER.exception("Failed to start file watcher, falling back to polling")
            self._observer = None

    def stop_watcher(self) -> None:
        """Stop the filesystem watcher."""
        if self._observer is not None:
            # Schedule observer stop/join in thread executor to avoid blocking event loop
            def _stop_observer():
                try:
                    self._observer.stop()
                    self._observer.join(timeout=5)
                except Exception:
                    _LOGGER.exception("Error stopping observer")
            
            self.hass.loop.run_in_executor(None, _stop_observer)
            self._observer = None
            _LOGGER.debug("File watcher stopped")
        if self._debounce_handle is not None:
            self._debounce_handle.cancel()
            self._debounce_handle = None

    def _on_filesystem_event(self) -> None:
        """Handle a filesystem event (called from watcher thread via loop)."""
        if self._git_operating:
            return
        # Cancel any pending debounce timer
        if self._debounce_handle is not None:
            self._debounce_handle.cancel()
        # Schedule a debounced refresh
        self._debounce_handle = self.hass.loop.call_later(
            self._debounce_seconds,
            lambda: self.hass.async_create_task(self.async_request_refresh()),
        )

    async def _async_update_data(self) -> dict:
        """Poll git status."""
        if self._git_operating:
            return self._build_data()
        if not self._git_available:
            self._status = STATUS_ERROR
            self._last_error = "git binary not available"
            return self._build_data()

        try:
            returncode, stdout, stderr = await self._run_git("status", "--porcelain")
            if returncode != 0:
                self._status = STATUS_ERROR
                self._last_error = stderr
                return self._build_data()

            if stdout:
                files = []
                for line in stdout.split("\n"):
                    if not line or len(line) < 4:
                        continue
                    # git status --porcelain format: "XY filename"
                    # X=index status, Y=worktree status, then a space
                    files.append(line[3:])
                self._changed_files = files
                if self._status != STATUS_PUSHING:
                    self._status = STATUS_PENDING
                    await self._maybe_notify()
            else:
                self._changed_files = []
                if self._status != STATUS_PUSHING:
                    self._status = STATUS_CLEAN
                self._last_error = None

            return self._build_data()

        except Exception as err:
            self._status = STATUS_ERROR
            self._last_error = str(err)
            raise UpdateFailed(f"Git status check failed: {err}") from err

    def _build_data(self) -> dict:
        """Build the data dict exposed to entities."""
        return {
            "status": self._status,
            "changed_files": self._changed_files,
            "changed_count": len(self._changed_files),
            "last_push": self._last_push,
            "last_push_commit": self._last_push_commit,
            "last_error": self._last_error,
            "last_check": dt_util.utcnow().isoformat(),
            "is_revert_head": self._is_revert_head,
            "last_activity": self._last_activity,
            "has_merge_conflict": self._has_merge_conflict,
            "merge_conflict_files": self._merge_conflict_files,
        }

    def _update_progress(self, status: str, activity: str) -> None:
        """Update status and activity, then push to entities."""
        self._status = status
        self._last_activity = activity
        self.async_set_updated_data(self._build_data())

    async def _maybe_notify(self) -> None:
        """Send notification if cooldown allows."""
        if not self._notify_service:
            return

        now = dt_util.utcnow().timestamp()
        if self._last_notification:
            elapsed_minutes = (now - self._last_notification) / 60
            if elapsed_minutes < self._cooldown_minutes:
                return

        await self._send_notification()
        self._last_notification = now

    async def _send_notification(self) -> None:
        """Send actionable notification to user's device."""
        files_str = ", ".join(self._changed_files[:5])
        if len(self._changed_files) > 5:
            files_str += f" (+{len(self._changed_files) - 5} more)"

        # Extract service name (strip "notify." prefix if present)
        service = self._notify_service
        if service.startswith("notify."):
            service = service[7:]

        try:
            await self.hass.services.async_call(
                "notify",
                service,
                {
                    "title": "HA Config Changed",
                    "message": (
                        f"{len(self._changed_files)} file(s) modified: {files_str}"
                    ),
                    "data": {
                        "actions": [
                            {"action": ACTION_PUSH, "title": "Push to Git"},
                            {"action": ACTION_DISMISS, "title": "Dismiss"},
                        ],
                    },
                },
            )
        except Exception:
            _LOGGER.exception("Failed to send notification")

    async def async_push(self) -> None:
        """Commit all changes and push to remote."""
        _LOGGER.info("Sync button pressed — checking for changes")
        
        if not self._changed_files:
            _LOGGER.info("No changes detected — repository is clean")
            self._last_activity = "No changes to sync"
            self.async_set_updated_data(self._build_data())
            return

        self._git_operating = True
        num_files = len(self._changed_files)
        self._update_progress(STATUS_PUSHING, f"Staging {num_files} file(s)…")

        try:
            # Stage all changes
            rc, _, stderr = await self._run_git("add", "-A")
            if rc != 0:
                raise RuntimeError(f"git add failed: {stderr}")

            # Build commit message
            files_str = ", ".join(self._changed_files[:5])
            if len(self._changed_files) > 5:
                files_str += f" (+{len(self._changed_files) - 5} more)"
            message = f"UI change: {files_str}"

            # Commit with configured author
            self._update_progress(STATUS_PUSHING, f"Committing {num_files} file(s)…")
            env = {
                "GIT_AUTHOR_NAME": self._author_name,
                "GIT_AUTHOR_EMAIL": self._author_email,
                "GIT_COMMITTER_NAME": self._author_name,
                "GIT_COMMITTER_EMAIL": self._author_email,
            }
            rc, _, stderr = await self._run_git("commit", "-m", message, env=env)
            if rc != 0:
                raise RuntimeError(f"git commit failed: {stderr}")

            # Get commit hash
            _, commit_hash, _ = await self._run_git("rev-parse", "--short", "HEAD")

            # Push with SSH key
            self._update_progress(STATUS_PUSHING, f"Pushing {commit_hash} to remote…")
            ssh_cmd = (
                f"ssh -i {self._ssh_key_path} "
                "-o StrictHostKeyChecking=no "
                "-o UserKnownHostsFile=/dev/null"
            )
            push_env = {"GIT_SSH_COMMAND": ssh_cmd}
            rc, _, stderr = await self._run_git(
                "push", self._remote, self._branch, env=push_env
            )
            if rc != 0:
                raise RuntimeError(f"git push failed: {stderr}")

            # Success
            self._changed_files = []
            self._last_push = dt_util.utcnow().isoformat()
            self._last_push_commit = commit_hash
            self._last_error = None
            self._last_notification = None  # Reset cooldown
            self._is_revert_head = False

            self._update_progress(STATUS_CLEAN, f"Pushed {commit_hash}: {files_str}")
            _LOGGER.info(
                "Successfully pushed %d file(s) in commit %s: %s",
                num_files,
                commit_hash,
                message,
            )

            await self._notify_result(
                "Config Pushed to Git",
                f"Commit {commit_hash}: {message}",
            )

        except Exception as err:
            self._status = STATUS_ERROR
            self._last_error = str(err)
            self._last_activity = f"Push failed: {err}"
            _LOGGER.error("Git push failed: %s", err)

            await self._notify_result("Git Push Failed", str(err))

        finally:
            self._git_operating = False
            self.async_set_updated_data(self._build_data())

    # Targeted YAML reload services — avoids disrupting MQTT / other integrations
    _YAML_RELOAD_TARGETS: list[tuple[str, str]] = [
        ("automation", "reload"),
        ("script", "reload"),
        ("scene", "reload"),
        ("group", "reload"),
        ("input_boolean", "reload"),
        ("input_number", "reload"),
        ("input_select", "reload"),
        ("input_text", "reload"),
        ("input_datetime", "reload"),
        ("input_button", "reload"),
        ("timer", "reload"),
        ("counter", "reload"),
        ("template", "reload"),
        ("person", "reload"),
        ("zone", "reload"),
        ("homeassistant", "reload_core_config"),
        ("frontend", "reload_themes"),
    ]

    async def _reload_yaml_config(self) -> None:
        """Reload YAML-based config without disrupting integration connections.

        Calls individual reload services for each YAML domain instead of
        homeassistant.reload_all, which can disrupt MQTT and other
        long-lived integration connections.
        """

        async def _safe_reload(domain: str, service: str) -> None:
            try:
                await self.hass.services.async_call(
                    domain, service, blocking=True
                )
            except Exception:  # noqa: BLE001
                pass  # Service may not exist if domain isn't loaded

        await asyncio.gather(
            *[_safe_reload(d, s) for d, s in self._YAML_RELOAD_TARGETS]
        )
        _LOGGER.info("YAML configuration reloaded (targeted)")

    async def _check_config_valid(self) -> tuple[bool, str]:
        """Check if HA configuration is valid after pulling new files."""
        try:
            from homeassistant.config import async_check_ha_config_file
            errors = await async_check_ha_config_file(self.hass)
            if errors:
                return False, str(errors)
            return True, ""
        except ImportError:
            _LOGGER.warning("Config check API not available, skipping validation")
            return True, ""
        except Exception as err:  # noqa: BLE001
            return False, str(err)

    async def _get_merge_conflict_files(self) -> list[str]:
        """Get list of files with merge conflicts."""
        rc, stdout, _ = await self._run_git("diff", "--name-only", "--diff-filter=U")
        if rc != 0:
            return []
        return [f for f in stdout.split("\n") if f.strip()]

    async def async_pull(self) -> None:
        """Pull latest changes from remote, validate config, and reload.

        Backs up local state before pulling. If the new config is invalid,
        rolls back to the previous state and notifies the user.
        """
        self._git_operating = True
        self._update_progress(STATUS_PULLING, "Backing up local state…")

        prev_head = None
        has_stash = False

        try:
            # Save current HEAD for rollback
            _, prev_head, _ = await self._run_git("rev-parse", "HEAD")
            prev_head = prev_head.strip()

            # Stash local changes (e.g. UI-made modifications not yet pushed)
            rc_stash, _, _ = await self._run_git(
                "stash", "push", "--include-untracked",
                "-m", "git-sync-pre-pull-backup",
            )
            has_stash = rc_stash == 0

            # Fetch from remote (main config)
            self._update_progress(STATUS_PULLING, "Fetching from remote…")
            ssh_cmd = (
                f"ssh -i {self._ssh_key_path} "
                "-o StrictHostKeyChecking=no "
                "-o UserKnownHostsFile=/dev/null"
            )
            fetch_env = {"GIT_SSH_COMMAND": ssh_cmd}
            rc, _, stderr = await self._run_git(
                "fetch", self._remote, env=fetch_env
            )
            if rc != 0:
                raise RuntimeError(f"git fetch failed: {stderr}")

            # Attempt merge with remote branch to detect conflicts
            self._update_progress(STATUS_PULLING, "Merging remote changes…")
            rc, _, stderr = await self._run_git(
                "merge", f"{self._remote}/{self._branch}", "-m", "git-sync-pull-merge"
            )
            
            # Check for merge conflicts
            conflict_files = await self._get_merge_conflict_files()
            if conflict_files:
                self._status = STATUS_MERGE_CONFLICT
                self._merge_conflict_files = conflict_files
                self._has_merge_conflict = True
                self._last_error = f"Merge conflict in files: {', '.join(conflict_files)}"
                self._last_activity = f"Merge conflict detected in {len(conflict_files)} file(s)"
                self.async_set_updated_data(self._build_data())
                
                # Abort the merge to maintain a clean state
                await self._run_git("merge", "--abort")
                
                await self._notify_result(
                    "Merge Conflict Detected",
                    f"Pull failed due to merge conflicts in:\n" + "\n".join(conflict_files)
                    + "\n\nPlease resolve conflicts manually or reset to remote.",
                )
                return
            
            if rc != 0:
                raise RuntimeError(f"git merge failed: {stderr}")

            # Get new commit hash
            _, commit_hash, _ = await self._run_git("rev-parse", "--short", "HEAD")
            commit_hash = commit_hash.strip()
            
            # Clear any previous merge conflict state
            self._has_merge_conflict = False
            self._merge_conflict_files = []

            # Validate configuration before reloading
            self._update_progress(STATUS_VALIDATING, f"Validating config ({commit_hash})…")
            config_valid, config_errors = await self._check_config_valid()
            if not config_valid:
                _LOGGER.error(
                    "Config check failed after pull of %s: %s",
                    commit_hash, config_errors,
                )
                # Rollback to previous state
                self._update_progress(STATUS_PULLING, "Rolling back (invalid config)…")
                await self._run_git("reset", "--hard", prev_head)
                if has_stash:
                    await self._run_git("stash", "pop")
                    has_stash = False

                self._status = STATUS_ERROR
                self._last_error = f"Config invalid: {config_errors}"
                self._last_activity = "Pull rejected: invalid config"
                await self._notify_result(
                    "Git Pull Rejected — Config Invalid",
                    f"Commit {commit_hash} failed validation. "
                    f"Rolled back to {prev_head[:7]}.\n{config_errors}",
                )
                return

            self._update_progress(STATUS_VALIDATING, f"Config valid ({commit_hash}) ✓")

            # Also pull ha-config-git-sync custom integration if it exists
            integration_path = "/config/custom_components/ha-config-git-sync"
            try:
                if os.path.exists(integration_path):
                    _LOGGER.info("Pulling custom integration from %s", integration_path)
                    rc, _, stderr = await self._run_git(
                        "-C", integration_path, "fetch", self._remote, env=fetch_env
                    )
                    if rc == 0:
                        rc, _, stderr = await self._run_git(
                            "-C", integration_path, "reset", "--hard", f"{self._remote}/{self._branch}", env=fetch_env
                        )
                        if rc == 0:
                            _LOGGER.info("Custom integration pulled successfully")
                        else:
                            _LOGGER.warning("Custom integration reset failed: %s", stderr)
                    else:
                        _LOGGER.warning("Custom integration fetch failed: %s", stderr)
            except Exception as integration_err:  # noqa: BLE001
                _LOGGER.warning("Could not pull custom integration: %s", integration_err)

            # Config is valid — drop the backup stash
            if has_stash:
                await self._run_git("stash", "drop")
                has_stash = False

            self._changed_files = []
            self._last_push = dt_util.utcnow().isoformat()
            self._last_push_commit = commit_hash
            self._last_error = None

            _LOGGER.info("Successfully pulled from %s/%s: %s", self._remote, self._branch, commit_hash)

            # Reload YAML configuration so HA picks up the pulled files
            self._update_progress(STATUS_RELOADING, f"Reloading config ({commit_hash})…")
            try:
                await self._reload_yaml_config()
            except Exception as reload_err:  # noqa: BLE001
                _LOGGER.warning("Config reload after pull failed: %s", reload_err)

            self._update_progress(STATUS_CLEAN, f"Pulled {commit_hash}")

            await self._notify_result(
                "Config Pulled & Reloaded",
                f"Pulled {commit_hash}",
            )

        except Exception as err:
            self._status = STATUS_ERROR
            self._last_error = str(err)
            self._last_activity = f"Pull failed: {err}"
            _LOGGER.error("Git pull failed: %s", err)

            # Attempt rollback on unexpected errors
            if prev_head:
                try:
                    await self._run_git("reset", "--hard", prev_head)
                    if has_stash:
                        await self._run_git("stash", "pop")
                    _LOGGER.info("Rolled back to %s after pull failure", prev_head[:7])
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Rollback after pull failure also failed")

            await self._notify_result("Git Pull Failed", str(err))

        finally:
            self._git_operating = False
            self.async_set_updated_data(self._build_data())

    async def async_undo(self) -> None:
        """Undo/redo: revert the most recent commit with git revert HEAD.

        Acts as a toggle — first press undoes, second press redoes, etc.
        Making a new push after an undo starts a fresh history.
        """
        self._git_operating = True
        action = "Redo" if self._is_revert_head else "Undo"
        self._update_progress(STATUS_PUSHING, f"{action}: reading current commit…")

        try:
            # Get the current HEAD commit subject for the notification
            rc, head_subject, stderr = await self._run_git(
                "log", "-1", "--format=%s"
            )
            if rc != 0:
                raise RuntimeError(f"git log failed: {stderr}")

            # Revert HEAD with our author info
            self._update_progress(STATUS_PUSHING, f"{action}: reverting commit…")
            env = {
                "GIT_AUTHOR_NAME": self._author_name,
                "GIT_AUTHOR_EMAIL": self._author_email,
                "GIT_COMMITTER_NAME": self._author_name,
                "GIT_COMMITTER_EMAIL": self._author_email,
            }
            rc, _, stderr = await self._run_git(
                "revert", "HEAD", "--no-edit", env=env
            )
            if rc != 0:
                raise RuntimeError(f"git revert failed: {stderr}")

            # Get new commit hash
            _, commit_hash, _ = await self._run_git("rev-parse", "--short", "HEAD")

            # Push
            self._update_progress(STATUS_PUSHING, f"{action}: pushing {commit_hash} to remote…")
            ssh_cmd = (
                f"ssh -i {self._ssh_key_path} "
                "-o StrictHostKeyChecking=no "
                "-o UserKnownHostsFile=/dev/null"
            )
            push_env = {"GIT_SSH_COMMAND": ssh_cmd}
            rc, _, stderr = await self._run_git(
                "push", self._remote, self._branch, env=push_env
            )
            if rc != 0:
                raise RuntimeError(f"git push failed: {stderr}")

            self._changed_files = []
            self._last_push = dt_util.utcnow().isoformat()
            self._last_push_commit = commit_hash
            self._last_error = None

            self._is_revert_head = not self._is_revert_head

            # Reload YAML configuration so HA picks up the reverted files
            self._update_progress(STATUS_RELOADING, f"{action}: reloading config…")
            try:
                await self._reload_yaml_config()
            except Exception as reload_err:  # noqa: BLE001
                _LOGGER.warning("Config reload after undo failed: %s", reload_err)

            self._update_progress(STATUS_CLEAN, f"{action} & reloaded: {head_subject}")
            _LOGGER.info("Undo successful: reverted '%s'", head_subject)

            await self._notify_result(
                "Config Reverted & Reloaded",
                f"Undid: {head_subject}",
            )

        except Exception as err:
            self._status = STATUS_ERROR
            self._last_error = str(err)
            self._last_activity = f"Undo failed: {err}"
            _LOGGER.error("Undo failed: %s", err)
            await self._notify_result("Undo Failed", str(err))

        finally:
            self._git_operating = False
            self.async_set_updated_data(self._build_data())

    async def async_handle_action(self, action: str) -> None:
        """Handle a notification action response."""
        if action == ACTION_PUSH:
            await self.async_push()
        elif action == ACTION_DISMISS:
            # Reset cooldown so next poll can notify again after cooldown period
            self._last_notification = dt_util.utcnow().timestamp()
            _LOGGER.debug("User dismissed push notification")

    async def _notify_result(self, title: str, message: str) -> None:
        """Send a simple (non-actionable) notification."""
        if not self._notify_service:
            return

        service = self._notify_service
        if service.startswith("notify."):
            service = service[7:]

        try:
            await self.hass.services.async_call(
                "notify",
                service,
                {"title": title, "message": message},
            )
        except Exception:
            _LOGGER.exception("Failed to send result notification")

    async def _run_git(
        self, *args: str, env: dict[str, str] | None = None
    ) -> tuple[int, str, str]:
        """Run a git command asynchronously."""
        cmd_env = dict(os.environ)
        if env:
            cmd_env.update(env)

        try:
            process = await asyncio.create_subprocess_exec(
                "git",
                *args,
                cwd=self._repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=cmd_env,
            )
            stdout, stderr = await process.communicate()
            return process.returncode, stdout.decode().rstrip(), stderr.decode().strip()
        except (FileNotFoundError, OSError) as err:
            return 1, "", str(err)

    async def _check_git_available(self) -> bool:
        """Check if git binary is available."""
        try:
            process = await asyncio.create_subprocess_exec(
                "git",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except FileNotFoundError:
            return False
