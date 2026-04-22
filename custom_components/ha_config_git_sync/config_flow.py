"""Config flow for HA Config Git Sync."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_AUTO_PUSH_ENABLED,
    CONF_BRANCH,
    CONF_COMMIT_AUTHOR_EMAIL,
    CONF_COMMIT_AUTHOR_NAME,
    CONF_INIT_GIT,
    CONF_NOTIFICATION_COOLDOWN,
    CONF_NOTIFY_SERVICE,
    CONF_REMOTE,
    CONF_REMOTE_CHECK_ENABLED,
    CONF_REPO_PATH,
    CONF_SCAN_INTERVAL,
    CONF_SSH_KEY_PATH,
    DEFAULT_AUTO_PUSH_ENABLED,
    DEFAULT_BRANCH,
    DEFAULT_COMMIT_AUTHOR_EMAIL,
    DEFAULT_COMMIT_AUTHOR_NAME,
    DEFAULT_NOTIFICATION_COOLDOWN,
    DEFAULT_REMOTE,
    DEFAULT_REMOTE_CHECK_ENABLED,
    DEFAULT_REPO_PATH,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSH_KEY_PATH,
    DOMAIN,
)


class HAConfigGitSyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Config Git Sync."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Repository settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate git is available
            if not await self._check_git_available():
                errors["base"] = "git_not_found"
            # Check if repo path is a git repo
            elif not await self._check_is_git_repo(user_input[CONF_REPO_PATH]):
                # Not a git repo - ask if user wants to initialize it
                self._repo_data = user_input
                return await self.async_step_init_git()
            else:
                # Valid git repo, proceed to settings
                self._repo_data = user_input
                return await self.async_step_settings()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REPO_PATH, default=DEFAULT_REPO_PATH): str,
                    vol.Required(CONF_BRANCH, default=DEFAULT_BRANCH): str,
                    vol.Required(CONF_REMOTE, default=DEFAULT_REMOTE): str,
                }
            ),
            errors=errors,
        )

    async def async_step_init_git(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1b: Ask user if they want to initialize git in the directory."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get(CONF_INIT_GIT):
                # User wants to initialize git
                repo_path = self._repo_data[CONF_REPO_PATH]
                success = await self._init_git_repo(repo_path)
                if not success:
                    errors["base"] = "git_init_failed"
                    return self.async_show_form(
                        step_id="init_git",
                        data_schema=vol.Schema(
                            {
                                vol.Required(CONF_INIT_GIT, default=False): bool,
                            }
                        ),
                        errors=errors,
                        description_placeholders={
                            "path": repo_path,
                        },
                    )
            # Either initialized or user chose not to - proceed to settings
            return await self.async_step_settings()

        return self.async_show_form(
            step_id="init_git",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INIT_GIT, default=False): bool,
                }
            ),
            description_placeholders={
                "path": self._repo_data[CONF_REPO_PATH],
            },
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Notification and commit settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check SSH key only if provided and non-empty
            ssh_key = user_input.get(CONF_SSH_KEY_PATH)
            if ssh_key and not os.path.isfile(ssh_key):
                errors[CONF_SSH_KEY_PATH] = "ssh_key_not_found"
            else:
                # Combine data from both steps
                data = {**self._repo_data, **user_input}

                # Prevent duplicate entries
                await self.async_set_unique_id(data[CONF_REPO_PATH])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Git Sync ({data[CONF_REPO_PATH]})",
                    data=data,
                )

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SSH_KEY_PATH, default=DEFAULT_SSH_KEY_PATH
                    ): str,
                    vol.Required(
                        CONF_COMMIT_AUTHOR_NAME, default=DEFAULT_COMMIT_AUTHOR_NAME
                    ): str,
                    vol.Required(
                        CONF_COMMIT_AUTHOR_EMAIL, default=DEFAULT_COMMIT_AUTHOR_EMAIL
                    ): str,
                    vol.Optional(CONF_NOTIFY_SERVICE, default=""): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): vol.All(int, vol.Range(min=1, max=60)),
                    vol.Required(
                        CONF_NOTIFICATION_COOLDOWN,
                        default=DEFAULT_NOTIFICATION_COOLDOWN,
                    ): vol.All(int, vol.Range(min=5, max=1440)),
                    vol.Required(
                        CONF_REMOTE_CHECK_ENABLED,
                        default=DEFAULT_REMOTE_CHECK_ENABLED,
                    ): bool,
                    vol.Required(
                        CONF_AUTO_PUSH_ENABLED,
                        default=DEFAULT_AUTO_PUSH_ENABLED,
                    ): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow handler."""
        return HAConfigGitSyncOptionsFlow()

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

    async def _check_is_git_repo(self, path: str) -> bool:
        """Check if the path is a git repository."""
        try:
            process = await asyncio.create_subprocess_exec(
                "git",
                "rev-parse",
                "--git-dir",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except (FileNotFoundError, OSError):
            return False

    async def _init_git_repo(self, path: str) -> bool:
        """Initialize a new git repository at the specified path."""
        try:
            # Ensure directory exists
            os.makedirs(path, exist_ok=True)
            
            # Initialize git repo
            process = await asyncio.create_subprocess_exec(
                "git",
                "init",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                return False
            
            # Configure git user for this repo
            process = await asyncio.create_subprocess_exec(
                "git",
                "config",
                "user.name",
                "HA Config Sync",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            
            process = await asyncio.create_subprocess_exec(
                "git",
                "config",
                "user.email",
                "ha-config-sync@local",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            
            return True
        except (FileNotFoundError, OSError):
            return False


class HAConfigGitSyncOptionsFlow(OptionsFlow):
    """Handle options for HA Config Git Sync."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate SSH key path if provided
            ssh_key = user_input.get(CONF_SSH_KEY_PATH, "")
            if ssh_key and not os.path.isfile(ssh_key):
                errors[CONF_SSH_KEY_PATH] = "ssh_key_not_found"
            
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SSH_KEY_PATH,
                        default=current.get(CONF_SSH_KEY_PATH, DEFAULT_SSH_KEY_PATH),
                    ): str,
                    vol.Required(
                        CONF_COMMIT_AUTHOR_NAME,
                        default=current.get(
                            CONF_COMMIT_AUTHOR_NAME, DEFAULT_COMMIT_AUTHOR_NAME
                        ),
                    ): str,
                    vol.Required(
                        CONF_COMMIT_AUTHOR_EMAIL,
                        default=current.get(
                            CONF_COMMIT_AUTHOR_EMAIL, DEFAULT_COMMIT_AUTHOR_EMAIL
                        ),
                    ): str,
                    vol.Optional(
                        CONF_NOTIFY_SERVICE,
                        default=current.get(CONF_NOTIFY_SERVICE, ""),
                    ): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(int, vol.Range(min=1, max=60)),
                    vol.Required(
                        CONF_NOTIFICATION_COOLDOWN,
                        default=current.get(
                            CONF_NOTIFICATION_COOLDOWN, DEFAULT_NOTIFICATION_COOLDOWN
                        ),
                    ): vol.All(int, vol.Range(min=5, max=1440)),
                    vol.Required(
                        CONF_REMOTE_CHECK_ENABLED,
                        default=current.get(
                            CONF_REMOTE_CHECK_ENABLED, DEFAULT_REMOTE_CHECK_ENABLED
                        ),
                    ): bool,
                    vol.Required(
                        CONF_AUTO_PUSH_ENABLED,
                        default=current.get(
                            CONF_AUTO_PUSH_ENABLED, DEFAULT_AUTO_PUSH_ENABLED
                        ),
                    ): bool,
                }
            ),
            errors=errors,
        )
