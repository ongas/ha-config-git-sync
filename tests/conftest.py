"""Shared fixtures for HA Config Git Sync tests."""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Lightweight HA stubs — avoids pulling in the full homeassistant package
# ---------------------------------------------------------------------------

class _FakeUpdateCoordinator:
    """Minimal stand-in for DataUpdateCoordinator."""

    def __init__(self, hass, logger, *, name, update_interval):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = {}

    async def async_config_entry_first_refresh(self):
        self.data = await self._async_update_data()

    def async_set_updated_data(self, data):
        self.data = data


class _FakeUpdateFailed(Exception):
    pass


class _FakeConfigFlow:
    """Minimal stand-in for homeassistant.config_entries.ConfigFlow."""

    _unique_id = None

    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.domain = domain

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    async def async_set_unique_id(self, unique_id):
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        pass


class _FakeOptionsFlow:
    """Minimal stand-in for homeassistant.config_entries.OptionsFlow."""

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}


def _callback_passthrough(fn):
    """Passthrough for the @callback decorator."""
    return fn


# Patch HA imports before anything in custom_components is imported
_ha_mocks = {
    "homeassistant": MagicMock(),
    "homeassistant.core": MagicMock(callback=_callback_passthrough),
    "homeassistant.config_entries": MagicMock(
        ConfigFlow=_FakeConfigFlow,
        OptionsFlow=_FakeOptionsFlow,
    ),
    "homeassistant.helpers": MagicMock(),
    "homeassistant.helpers.entity_platform": MagicMock(),
    "homeassistant.helpers.update_coordinator": MagicMock(
        DataUpdateCoordinator=_FakeUpdateCoordinator,
        UpdateFailed=_FakeUpdateFailed,
        CoordinatorEntity=MagicMock,
    ),
    "homeassistant.util": MagicMock(),
    "homeassistant.util.dt": MagicMock(),
    "homeassistant.components": MagicMock(),
    "homeassistant.components.sensor": MagicMock(),
    "homeassistant.components.binary_sensor": MagicMock(),
    "homeassistant.components.button": MagicMock(),
    "homeassistant.data_entry_flow": MagicMock(FlowResult=dict),
}

import sys

for mod_name, mock_obj in _ha_mocks.items():
    sys.modules.setdefault(mod_name, mock_obj)

# Now make dt_util.utcnow work realistically
import datetime

_real_utcnow = datetime.datetime.utcnow

sys.modules["homeassistant.util.dt"].utcnow = lambda: _real_utcnow()
sys.modules["homeassistant.util"].dt = sys.modules["homeassistant.util.dt"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_hass():
    """Return a minimal fake HomeAssistant object."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.bus = MagicMock()
    hass.bus.async_listen = MagicMock(return_value=lambda: None)
    return hass


@pytest.fixture
def fake_entry():
    """Return a minimal fake ConfigEntry with default data."""
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.data = {
        "repo_path": "/tmp/fake-repo",
        "branch": "main",
        "remote": "origin",
        "ssh_key_path": "/tmp/fake-key",
        "commit_author_name": "Test Author",
        "commit_author_email": "test@example.com",
        "notify_service": "notify.test",
        "scan_interval": 5,
        "notification_cooldown": 30,
    }
    return entry


@pytest.fixture
def git_repo(tmp_path):
    """Create a real temporary git repo with a bare remote for push testing.

    Returns a dict with:
      - repo_path: working repo directory
      - remote_path: bare remote directory
    """
    repo_path = tmp_path / "repo"
    remote_path = tmp_path / "remote.git"

    # Create bare remote
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True,
                    capture_output=True)

    # Create working repo
    subprocess.run(["git", "init", str(repo_path)], check=True,
                    capture_output=True)

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@test.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@test.com",
    }

    # Initial commit so the branch exists
    init_file = repo_path / "configuration.yaml"
    init_file.write_text("homeassistant:\n")
    subprocess.run(["git", "add", "-A"], cwd=str(repo_path), check=True,
                    capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"],
                    cwd=str(repo_path), check=True, capture_output=True,
                    env=env)

    # Ensure we're on main branch
    subprocess.run(["git", "branch", "-M", "main"], cwd=str(repo_path),
                    check=True, capture_output=True)

    # Add local bare remote as "origin"
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote_path)],
        cwd=str(repo_path), check=True, capture_output=True,
    )

    # Push initial commit to remote
    subprocess.run(["git", "push", "-u", "origin", "main"],
                    cwd=str(repo_path), check=True, capture_output=True,
                    env=env)

    return {"repo_path": str(repo_path), "remote_path": str(remote_path)}
