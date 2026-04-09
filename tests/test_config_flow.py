"""Tests for config flow and options flow."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_config_git_sync.config_flow import (
    HAConfigGitSyncConfigFlow,
    HAConfigGitSyncOptionsFlow,
)
from custom_components.ha_config_git_sync.const import (
    CONF_BRANCH,
    CONF_COMMIT_AUTHOR_EMAIL,
    CONF_COMMIT_AUTHOR_NAME,
    CONF_NOTIFICATION_COOLDOWN,
    CONF_NOTIFY_SERVICE,
    CONF_REMOTE,
    CONF_REPO_PATH,
    CONF_SCAN_INTERVAL,
    CONF_SSH_KEY_PATH,
    DEFAULT_BRANCH,
    DEFAULT_COMMIT_AUTHOR_EMAIL,
    DEFAULT_COMMIT_AUTHOR_NAME,
    DEFAULT_NOTIFICATION_COOLDOWN,
    DEFAULT_REMOTE,
    DEFAULT_REPO_PATH,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSH_KEY_PATH,
    DOMAIN,
)


def _mock_process(returncode=0, stdout=b"", stderr=b""):
    """Return an AsyncMock that behaves like asyncio.subprocess.Process."""
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


VALID_REPO_INPUT = {
    CONF_REPO_PATH: "/config",
    CONF_BRANCH: "main",
    CONF_REMOTE: "origin",
    CONF_SSH_KEY_PATH: "/config/.ssh/id_ed25519",
}

VALID_SETTINGS_INPUT = {
    CONF_COMMIT_AUTHOR_NAME: "HA Config Sync",
    CONF_COMMIT_AUTHOR_EMAIL: "ha@local",
    CONF_NOTIFY_SERVICE: "notify.mobile_app",
    CONF_SCAN_INTERVAL: 5,
    CONF_NOTIFICATION_COOLDOWN: 30,
}


# ---------------------------------------------------------------------------
# 1. Config flow — step_user
# ---------------------------------------------------------------------------

class TestConfigFlowStepUser:

    @pytest.mark.asyncio
    async def test_shows_form_on_first_load(self):
        """No input → show the repo settings form."""
        flow = HAConfigGitSyncConfigFlow()
        result = await flow.async_step_user(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    @pytest.mark.asyncio
    async def test_error_git_not_found(self):
        """If git is not installed, show 'git_not_found' error."""
        flow = HAConfigGitSyncConfigFlow()
        proc = _mock_process(returncode=127)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await flow.async_step_user(user_input=VALID_REPO_INPUT)

        assert result["type"] == "form"
        assert result["errors"]["base"] == "git_not_found"

    @pytest.mark.asyncio
    async def test_error_git_binary_missing(self):
        """If git binary doesn't exist at all, show 'git_not_found' error."""
        flow = HAConfigGitSyncConfigFlow()

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await flow.async_step_user(user_input=VALID_REPO_INPUT)

        assert result["type"] == "form"
        assert result["errors"]["base"] == "git_not_found"

    @pytest.mark.asyncio
    async def test_error_not_git_repo(self):
        """If the path is not a git repo, show 'not_git_repo' error."""
        flow = HAConfigGitSyncConfigFlow()
        git_ok = _mock_process(returncode=0, stdout=b"git version 2.40")
        not_repo = _mock_process(returncode=128, stderr=b"fatal: not a git repo")

        with patch("asyncio.create_subprocess_exec",
                    side_effect=[git_ok, not_repo]):
            result = await flow.async_step_user(user_input=VALID_REPO_INPUT)

        assert result["type"] == "form"
        assert result["errors"][CONF_REPO_PATH] == "not_git_repo"

    @pytest.mark.asyncio
    async def test_valid_input_proceeds_to_settings(self):
        """Valid repo input should advance to the settings step."""
        flow = HAConfigGitSyncConfigFlow()
        git_ok = _mock_process(returncode=0, stdout=b"git version 2.40")
        repo_ok = _mock_process(returncode=0, stdout=b".git")

        with patch("asyncio.create_subprocess_exec",
                    side_effect=[git_ok, repo_ok]):
            result = await flow.async_step_user(user_input=VALID_REPO_INPUT)

        # Should show the settings form (step 2)
        assert result["type"] == "form"
        assert result["step_id"] == "settings"
        assert flow._repo_data == VALID_REPO_INPUT


# ---------------------------------------------------------------------------
# 2. Config flow — step_settings
# ---------------------------------------------------------------------------

class TestConfigFlowStepSettings:

    @pytest.mark.asyncio
    async def test_shows_form_on_first_load(self):
        """No input → show the settings form."""
        flow = HAConfigGitSyncConfigFlow()
        flow._repo_data = VALID_REPO_INPUT

        result = await flow.async_step_settings(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "settings"

    @pytest.mark.asyncio
    async def test_error_ssh_key_not_found(self):
        """If SSH key file doesn't exist, show error."""
        flow = HAConfigGitSyncConfigFlow()
        flow._repo_data = {**VALID_REPO_INPUT, CONF_SSH_KEY_PATH: "/nonexistent/key"}

        with patch("os.path.isfile", return_value=False):
            result = await flow.async_step_settings(user_input=VALID_SETTINGS_INPUT)

        assert result["type"] == "form"
        assert result["errors"]["base"] == "ssh_key_not_found"

    @pytest.mark.asyncio
    async def test_valid_input_creates_entry(self):
        """Valid settings should create a config entry."""
        flow = HAConfigGitSyncConfigFlow()
        flow._repo_data = {**VALID_REPO_INPUT, CONF_SSH_KEY_PATH: ""}

        result = await flow.async_step_settings(user_input=VALID_SETTINGS_INPUT)

        assert result["type"] == "create_entry"
        assert "Git Sync" in result["title"]
        # Combined data from both steps
        assert result["data"][CONF_REPO_PATH] == "/config"
        assert result["data"][CONF_COMMIT_AUTHOR_NAME] == "HA Config Sync"
        assert result["data"][CONF_SCAN_INTERVAL] == 5

    @pytest.mark.asyncio
    async def test_valid_input_with_existing_ssh_key(self):
        """SSH key exists on disk → entry created without error."""
        flow = HAConfigGitSyncConfigFlow()
        flow._repo_data = VALID_REPO_INPUT

        with patch("os.path.isfile", return_value=True):
            result = await flow.async_step_settings(user_input=VALID_SETTINGS_INPUT)

        assert result["type"] == "create_entry"

    @pytest.mark.asyncio
    async def test_entry_gets_unique_id(self):
        """Config entry should use repo_path as unique_id."""
        flow = HAConfigGitSyncConfigFlow()
        flow._repo_data = {**VALID_REPO_INPUT, CONF_SSH_KEY_PATH: ""}

        await flow.async_step_settings(user_input=VALID_SETTINGS_INPUT)

        assert flow._unique_id == "/config"


# ---------------------------------------------------------------------------
# 3. Options flow
# ---------------------------------------------------------------------------

class TestOptionsFlow:

    def _make_config_entry(self, overrides=None):
        """Build a fake config entry with current data."""
        entry = MagicMock()
        entry.data = {
            CONF_REPO_PATH: "/config",
            CONF_BRANCH: "main",
            CONF_REMOTE: "origin",
            CONF_SSH_KEY_PATH: "/config/.ssh/id_ed25519",
            CONF_COMMIT_AUTHOR_NAME: "HA Config Sync",
            CONF_COMMIT_AUTHOR_EMAIL: "ha@local",
            CONF_NOTIFY_SERVICE: "notify.mobile_app",
            CONF_SCAN_INTERVAL: 5,
            CONF_NOTIFICATION_COOLDOWN: 30,
        }
        if overrides:
            entry.data.update(overrides)
        return entry

    @pytest.mark.asyncio
    async def test_shows_form_on_initial_load(self):
        """Opening options should show form pre-filled with current values."""
        entry = self._make_config_entry()
        flow = HAConfigGitSyncOptionsFlow(entry)

        result = await flow.async_step_init(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "init"
        # Verify schema contains expected fields by checking the schema keys
        schema = result["data_schema"]
        schema_keys = [str(k) for k in schema.schema]
        assert CONF_SSH_KEY_PATH in schema_keys
        assert CONF_NOTIFY_SERVICE in schema_keys
        assert CONF_SCAN_INTERVAL in schema_keys

    @pytest.mark.asyncio
    async def test_saves_updated_options(self):
        """Submitting valid input should create an entry."""
        entry = self._make_config_entry()
        flow = HAConfigGitSyncOptionsFlow(entry)

        new_settings = {
            CONF_SSH_KEY_PATH: "/config/.ssh/new_key",
            CONF_COMMIT_AUTHOR_NAME: "New Author",
            CONF_COMMIT_AUTHOR_EMAIL: "new@local",
            CONF_NOTIFY_SERVICE: "notify.mobile_app_new",
            CONF_SCAN_INTERVAL: 10,
            CONF_NOTIFICATION_COOLDOWN: 60,
        }

        with patch("os.path.isfile", return_value=True):
            result = await flow.async_step_init(user_input=new_settings)

        assert result["type"] == "create_entry"
        assert result["data"] == new_settings

    @pytest.mark.asyncio
    async def test_error_ssh_key_not_found(self):
        """If new SSH key path doesn't exist, show error."""
        entry = self._make_config_entry()
        flow = HAConfigGitSyncOptionsFlow(entry)

        new_settings = {
            CONF_SSH_KEY_PATH: "/nonexistent/key",
            CONF_COMMIT_AUTHOR_NAME: "Author",
            CONF_COMMIT_AUTHOR_EMAIL: "a@b",
            CONF_NOTIFY_SERVICE: "",
            CONF_SCAN_INTERVAL: 5,
            CONF_NOTIFICATION_COOLDOWN: 30,
        }

        with patch("os.path.isfile", return_value=False):
            result = await flow.async_step_init(user_input=new_settings)

        assert result["type"] == "form"
        assert result["errors"][CONF_SSH_KEY_PATH] == "ssh_key_not_found"

    @pytest.mark.asyncio
    async def test_empty_ssh_key_skips_validation(self):
        """Empty SSH key path should not trigger validation error."""
        entry = self._make_config_entry()
        flow = HAConfigGitSyncOptionsFlow(entry)

        new_settings = {
            CONF_SSH_KEY_PATH: "",
            CONF_COMMIT_AUTHOR_NAME: "Author",
            CONF_COMMIT_AUTHOR_EMAIL: "a@b",
            CONF_NOTIFY_SERVICE: "",
            CONF_SCAN_INTERVAL: 5,
            CONF_NOTIFICATION_COOLDOWN: 30,
        }

        result = await flow.async_step_init(user_input=new_settings)
        assert result["type"] == "create_entry"

    @pytest.mark.asyncio
    async def test_form_defaults_from_current_config(self):
        """Form defaults should reflect the current config entry data."""
        entry = self._make_config_entry({
            CONF_SCAN_INTERVAL: 15,
            CONF_NOTIFICATION_COOLDOWN: 120,
        })
        flow = HAConfigGitSyncOptionsFlow(entry)

        result = await flow.async_step_init(user_input=None)

        schema = result["data_schema"]
        # Extract defaults from the voluptuous schema
        defaults = {}
        for key in schema.schema:
            if hasattr(key, "default") and key.default is not None:
                defaults[str(key)] = key.default()
        assert defaults[CONF_SCAN_INTERVAL] == 15
        assert defaults[CONF_NOTIFICATION_COOLDOWN] == 120

    @pytest.mark.asyncio
    async def test_options_flow_accessible_from_config_flow(self):
        """async_get_options_flow should return a valid options flow instance."""
        entry = self._make_config_entry()
        options_flow = HAConfigGitSyncConfigFlow.async_get_options_flow(entry)

        assert isinstance(options_flow, HAConfigGitSyncOptionsFlow)
        assert options_flow.config_entry is entry


# ---------------------------------------------------------------------------
# 4. Full flow end-to-end
# ---------------------------------------------------------------------------

class TestConfigFlowEndToEnd:

    @pytest.mark.asyncio
    async def test_full_flow_user_to_entry(self):
        """Complete flow: step_user → step_settings → create_entry."""
        flow = HAConfigGitSyncConfigFlow()

        # Step 1: show form
        result = await flow.async_step_user(user_input=None)
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        # Step 1: submit valid repo input
        git_ok = _mock_process(returncode=0, stdout=b"git version 2.40")
        repo_ok = _mock_process(returncode=0, stdout=b".git")
        with patch("asyncio.create_subprocess_exec",
                    side_effect=[git_ok, repo_ok]):
            result = await flow.async_step_user(user_input={
                **VALID_REPO_INPUT,
                CONF_SSH_KEY_PATH: "",  # no SSH key
            })
        assert result["type"] == "form"
        assert result["step_id"] == "settings"

        # Step 2: submit valid settings
        result = await flow.async_step_settings(user_input=VALID_SETTINGS_INPUT)
        assert result["type"] == "create_entry"
        assert result["data"][CONF_REPO_PATH] == "/config"
        assert result["data"][CONF_COMMIT_AUTHOR_NAME] == "HA Config Sync"
