"""Integration tests — real git operations against a local disposable repo."""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_config_git_sync.coordinator import GitSyncCoordinator
from custom_components.ha_config_git_sync.const import (
    STATUS_CLEAN,
    STATUS_ERROR,
    STATUS_PENDING,
)


def _make_entry(repo_path: str) -> MagicMock:
    """Build a fake ConfigEntry pointing at the given repo."""
    entry = MagicMock()
    entry.entry_id = "integ_test_entry"
    entry.data = {
        "repo_path": repo_path,
        "branch": "main",
        "remote": "origin",
        "ssh_key_path": "",  # not needed for local push
        "commit_author_name": "Integration Test",
        "commit_author_email": "test@integration.local",
        "notify_service": "",  # disable notifications for integration tests
        "scan_interval": 5,
        "notification_cooldown": 30,
    }
    return entry


def _git(repo_path: str, *args: str) -> str:
    """Run a real git command in the repo and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
        },
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# 1. Status detection on a real repo
# ---------------------------------------------------------------------------

class TestRealGitStatus:

    @pytest.mark.asyncio
    async def test_clean_repo_detected(self, fake_hass, git_repo):
        """A freshly committed repo should report clean."""
        entry = _make_entry(git_repo["repo_path"])
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()

        data = await coord._async_update_data()

        assert data["status"] == STATUS_CLEAN
        assert data["changed_files"] == []
        assert data["changed_count"] == 0

    @pytest.mark.asyncio
    async def test_modified_file_detected(self, fake_hass, git_repo):
        """Modifying a tracked file should show as pending."""
        repo = git_repo["repo_path"]
        Path(repo, "configuration.yaml").write_text("homeassistant:\n  name: test\n")

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()

        data = await coord._async_update_data()

        assert data["status"] == STATUS_PENDING
        assert "configuration.yaml" in data["changed_files"]

    @pytest.mark.asyncio
    async def test_new_file_detected(self, fake_hass, git_repo):
        """An untracked file should show as pending."""
        repo = git_repo["repo_path"]
        Path(repo, "automations.yaml").write_text("- id: test\n")

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()

        data = await coord._async_update_data()

        assert data["status"] == STATUS_PENDING
        assert "automations.yaml" in data["changed_files"]

    @pytest.mark.asyncio
    async def test_deleted_file_detected(self, fake_hass, git_repo):
        """Deleting a tracked file should show as pending."""
        repo = git_repo["repo_path"]
        os.remove(os.path.join(repo, "configuration.yaml"))

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()

        data = await coord._async_update_data()

        assert data["status"] == STATUS_PENDING
        assert "configuration.yaml" in data["changed_files"]

    @pytest.mark.asyncio
    async def test_multiple_changes_detected(self, fake_hass, git_repo):
        """Multiple changes should all appear."""
        repo = git_repo["repo_path"]
        Path(repo, "configuration.yaml").write_text("modified\n")
        Path(repo, "new_file.yaml").write_text("new\n")
        Path(repo, "another.yaml").write_text("another\n")

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()

        data = await coord._async_update_data()

        assert data["status"] == STATUS_PENDING
        assert data["changed_count"] == 3


# ---------------------------------------------------------------------------
# 2. Full push cycle against local bare remote
# ---------------------------------------------------------------------------

class TestRealGitPush:

    @pytest.mark.asyncio
    async def test_push_commits_and_pushes(self, fake_hass, git_repo):
        """Full cycle: modify → push → verify commit reached remote."""
        repo = git_repo["repo_path"]
        remote = git_repo["remote_path"]

        # Make a change
        Path(repo, "configuration.yaml").write_text("homeassistant:\n  name: pushed\n")

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()

        # Detect changes
        await coord._async_update_data()
        assert coord._status == STATUS_PENDING

        # Push — SSH command not needed for local remote, but _run_git will
        # set GIT_SSH_COMMAND anyway. Local push ignores it.
        await coord.async_push()

        assert coord._status == STATUS_CLEAN
        assert coord._changed_files == []
        assert coord._last_push_commit is not None

        # Verify the commit actually reached the bare remote
        remote_log = subprocess.run(
            ["git", "log", "--oneline", "-1", "main"],
            cwd=remote,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert "UI change:" in remote_log

    @pytest.mark.asyncio
    async def test_push_with_deletion(self, fake_hass, git_repo):
        """Verify that git add -A stages file deletions."""
        repo = git_repo["repo_path"]
        remote = git_repo["remote_path"]

        # Add a file, commit, and push it first
        Path(repo, "to_delete.yaml").write_text("will be deleted\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "add file to delete")
        _git(repo, "push", "origin", "main")

        # Now delete it
        os.remove(os.path.join(repo, "to_delete.yaml"))

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()

        await coord._async_update_data()
        assert "to_delete.yaml" in coord._changed_files

        await coord.async_push()
        assert coord._status == STATUS_CLEAN

        # Verify the file no longer exists in the remote
        remote_files = subprocess.run(
            ["git", "ls-tree", "--name-only", "main"],
            cwd=remote,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert "to_delete.yaml" not in remote_files

    @pytest.mark.asyncio
    async def test_push_with_new_untracked_file(self, fake_hass, git_repo):
        """Untracked files should be committed and pushed."""
        repo = git_repo["repo_path"]
        remote = git_repo["remote_path"]

        Path(repo, "secrets.yaml").write_text("api_key: test123\n")

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()
        await coord._async_update_data()

        await coord.async_push()
        assert coord._status == STATUS_CLEAN

        # Verify file reached remote
        remote_files = subprocess.run(
            ["git", "ls-tree", "--name-only", "main"],
            cwd=remote,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert "secrets.yaml" in remote_files

    @pytest.mark.asyncio
    async def test_push_no_changes_is_noop(self, fake_hass, git_repo):
        """Push with no changes should not create a commit."""
        repo = git_repo["repo_path"]

        before_hash = _git(repo, "rev-parse", "HEAD")

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()

        await coord._async_update_data()
        assert coord._status == STATUS_CLEAN

        await coord.async_push()

        after_hash = _git(repo, "rev-parse", "HEAD")
        assert before_hash == after_hash  # No new commit

    @pytest.mark.asyncio
    async def test_push_author_info_in_commit(self, fake_hass, git_repo):
        """Verify the configured author appears in the commit."""
        repo = git_repo["repo_path"]
        Path(repo, "configuration.yaml").write_text("modified for author test\n")

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()
        await coord._async_update_data()
        await coord.async_push()

        log = _git(repo, "log", "-1", "--format=%an <%ae>")
        assert "Integration Test" in log
        assert "test@integration.local" in log

    @pytest.mark.asyncio
    async def test_status_clean_after_push(self, fake_hass, git_repo):
        """After push, subsequent status check should be clean."""
        repo = git_repo["repo_path"]
        Path(repo, "configuration.yaml").write_text("modified\n")

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()

        await coord._async_update_data()
        assert coord._status == STATUS_PENDING

        await coord.async_push()
        assert coord._status == STATUS_CLEAN

        # Poll again — should still be clean
        data = await coord._async_update_data()
        assert data["status"] == STATUS_CLEAN
        assert data["changed_count"] == 0


# ---------------------------------------------------------------------------
# 3. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_invalid_repo_path(self, fake_hass):
        """Pointing at a non-repo directory should produce an error."""
        entry = _make_entry("/tmp/definitely-not-a-repo")
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()

        data = await coord._async_update_data()
        assert data["status"] == STATUS_ERROR

    @pytest.mark.asyncio
    async def test_rapid_consecutive_pushes(self, fake_hass, git_repo):
        """Second push with no new changes should be a no-op."""
        repo = git_repo["repo_path"]
        Path(repo, "configuration.yaml").write_text("change\n")

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()

        await coord._async_update_data()
        await coord.async_push()
        hash_after_first = _git(repo, "rev-parse", "HEAD")

        # Second push — no new changes
        await coord._async_update_data()
        await coord.async_push()
        hash_after_second = _git(repo, "rev-parse", "HEAD")

        assert hash_after_first == hash_after_second

    @pytest.mark.asyncio
    async def test_files_with_spaces_in_name(self, fake_hass, git_repo):
        """Files with spaces should be handled correctly."""
        repo = git_repo["repo_path"]
        Path(repo, "my config file.yaml").write_text("test\n")

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)
        await coord.async_setup()
        await coord._async_update_data()

        assert coord._status == STATUS_PENDING

        await coord.async_push()
        assert coord._status == STATUS_CLEAN


# ---------------------------------------------------------------------------
# 4. Filesystem watcher
# ---------------------------------------------------------------------------

class TestFileWatcher:

    def test_watcher_starts_and_stops(self, fake_hass, git_repo):
        """Watcher should start an observer and stop cleanly."""
        entry = _make_entry(git_repo["repo_path"])
        coord = GitSyncCoordinator(fake_hass, entry)

        coord.start_watcher()
        assert coord._observer is not None
        assert coord._observer.is_alive()

        coord.stop_watcher()
        assert coord._observer is None

    def test_watcher_double_start_is_noop(self, fake_hass, git_repo):
        """Calling start_watcher twice should not create a second observer."""
        entry = _make_entry(git_repo["repo_path"])
        coord = GitSyncCoordinator(fake_hass, entry)

        coord.start_watcher()
        first_observer = coord._observer
        coord.start_watcher()
        assert coord._observer is first_observer

        coord.stop_watcher()

    def test_watcher_stop_without_start(self, fake_hass, git_repo):
        """Stopping a watcher that was never started should not error."""
        entry = _make_entry(git_repo["repo_path"])
        coord = GitSyncCoordinator(fake_hass, entry)
        coord.stop_watcher()  # Should not raise

    def test_watcher_detects_file_change(self, fake_hass, git_repo):
        """Watcher should fire the handler callback when a file changes."""
        from watchdog.observers import Observer
        from custom_components.ha_config_git_sync.coordinator import _GitIgnoreAwareHandler
        import threading

        repo = git_repo["repo_path"]
        event_fired = threading.Event()

        class _TrackingHandler(_GitIgnoreAwareHandler):
            def on_any_event(self, event):
                if "/.git/" not in event.src_path:
                    event_fired.set()

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)

        observer = Observer()
        handler = _TrackingHandler(coord, MagicMock())
        observer.schedule(handler, repo, recursive=True)
        observer.daemon = True
        observer.start()
        try:
            time.sleep(0.3)
            Path(repo, "configuration.yaml").write_text("changed!\n")
            assert event_fired.wait(timeout=5), "Watcher did not detect file change"
        finally:
            observer.stop()
            observer.join(timeout=5)

    def test_watcher_ignores_git_directory(self, fake_hass, git_repo):
        """Changes inside .git/ should not trigger events."""
        from watchdog.observers import Observer
        from custom_components.ha_config_git_sync.coordinator import _GitIgnoreAwareHandler
        import threading

        repo = git_repo["repo_path"]
        event_fired = threading.Event()

        class _TrackingHandler(_GitIgnoreAwareHandler):
            def on_any_event(self, event):
                # Call parent which filters .git/
                if "/.git/" not in event.src_path and not event.src_path.endswith("/.git"):
                    event_fired.set()

        entry = _make_entry(repo)
        coord = GitSyncCoordinator(fake_hass, entry)

        observer = Observer()
        handler = _TrackingHandler(coord, MagicMock())
        observer.schedule(handler, repo, recursive=True)
        observer.daemon = True
        observer.start()
        try:
            time.sleep(0.3)
            # Write inside .git/ directory
            Path(repo, ".git", "test_file").write_text("should be ignored\n")
            # Wait briefly — should NOT fire
            assert not event_fired.wait(timeout=1), "Watcher should ignore .git/ changes"
        finally:
            observer.stop()
            observer.join(timeout=5)
