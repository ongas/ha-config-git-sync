"""Git operations coordinator for HA Config Git Sync."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import timedelta

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
    DOMAIN,
    STATUS_CLEAN,
    STATUS_ERROR,
    STATUS_PENDING,
    STATUS_PUSHING,
)

_LOGGER = logging.getLogger(__name__)


class GitSyncCoordinator(DataUpdateCoordinator):
    """Coordinator that polls git status and manages push operations."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize the coordinator."""
        self._repo_path: str = entry.data[CONF_REPO_PATH]
        self._branch: str = entry.data[CONF_BRANCH]
        self._remote: str = entry.data[CONF_REMOTE]
        self._ssh_key_path: str = entry.data[CONF_SSH_KEY_PATH]
        self._author_name: str = entry.data[CONF_COMMIT_AUTHOR_NAME]
        self._author_email: str = entry.data[CONF_COMMIT_AUTHOR_EMAIL]
        self._notify_service: str = entry.data[CONF_NOTIFY_SERVICE]
        self._cooldown_minutes: int = entry.data[CONF_NOTIFICATION_COOLDOWN]

        self._last_notification: float | None = None
        self._status: str = STATUS_CLEAN
        self._changed_files: list[str] = []
        self._last_push: str | None = None
        self._last_push_commit: str | None = None
        self._last_error: str | None = None
        self._git_available: bool = False

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

    async def _async_update_data(self) -> dict:
        """Poll git status."""
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
                    line = line.strip()
                    if line:
                        # git status --porcelain format: "XY filename"
                        files.append(line[3:] if len(line) > 3 else line)
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
        }

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
        if not self._changed_files:
            _LOGGER.info("No changes to push")
            return

        self._status = STATUS_PUSHING
        self.async_set_updated_data(self._build_data())

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
            self._status = STATUS_CLEAN
            self._changed_files = []
            self._last_push = dt_util.utcnow().isoformat()
            self._last_push_commit = commit_hash
            self._last_error = None
            self._last_notification = None  # Reset cooldown

            _LOGGER.info("Successfully pushed commit %s: %s", commit_hash, message)

            await self._notify_result(
                "Config Pushed to Git",
                f"Commit {commit_hash}: {message}",
            )

        except Exception as err:
            self._status = STATUS_ERROR
            self._last_error = str(err)
            _LOGGER.error("Git push failed: %s", err)

            await self._notify_result("Git Push Failed", str(err))

        finally:
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

        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=self._repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=cmd_env,
        )
        stdout, stderr = await process.communicate()
        return process.returncode, stdout.decode().strip(), stderr.decode().strip()

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
