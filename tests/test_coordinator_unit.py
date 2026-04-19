"""Unit tests for GitSyncCoordinator — all git calls mocked."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_config_git_sync.coordinator import GitSyncCoordinator
from custom_components.ha_config_git_sync.const import (
    ACTION_DISMISS,
    ACTION_PUSH,
    STATUS_CLEAN,
    STATUS_ERROR,
    STATUS_PENDING,
    STATUS_PUSHING,
)


# ---------------------------------------------------------------------------
# Helper to build a coordinator with mocked subprocess
# ---------------------------------------------------------------------------

def _make_coordinator(fake_hass, fake_entry, overrides=None):
    """Build a coordinator, optionally overriding entry.data keys."""
    if overrides:
        fake_entry.data = {**fake_entry.data, **overrides}
    return GitSyncCoordinator(fake_hass, fake_entry)


def _mock_process(returncode=0, stdout=b"", stderr=b""):
    """Return an AsyncMock that behaves like asyncio.subprocess.Process."""
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


# ---------------------------------------------------------------------------
# 1. async_setup — git availability check
# ---------------------------------------------------------------------------

class TestSetup:

    @pytest.mark.asyncio
    async def test_setup_git_available(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)
        git_version_proc = _mock_process(returncode=0, stdout=b"git version 2.40")
        safe_dir_proc = _mock_process(returncode=0)

        with patch("asyncio.create_subprocess_exec",
                    side_effect=[git_version_proc, safe_dir_proc]) as mock_exec:
            await coord.async_setup()

        assert coord._git_available is True
        # Called twice: git --version, then git config --global ...
        assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_setup_git_not_available(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)
        proc = _mock_process(returncode=127)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await coord.async_setup()

        assert coord._git_available is False

    @pytest.mark.asyncio
    async def test_setup_git_binary_missing(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            await coord.async_setup()

        assert coord._git_available is False


# ---------------------------------------------------------------------------
# 2. _async_update_data — status polling
# ---------------------------------------------------------------------------

class TestStatusPolling:

    @pytest.mark.asyncio
    async def test_clean_repo(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._git_available = True

        proc = _mock_process(returncode=0, stdout=b"")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            data = await coord._async_update_data()

        assert data["status"] == STATUS_CLEAN
        assert data["changed_files"] == []
        assert data["changed_count"] == 0

    @pytest.mark.asyncio
    async def test_pending_changes(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry, {"notify_service": ""})
        coord._git_available = True

        porcelain = b" M configuration.yaml\n?? new_file.yaml\n"
        proc = _mock_process(returncode=0, stdout=porcelain)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            data = await coord._async_update_data()

        assert data["status"] == STATUS_PENDING
        assert data["changed_count"] == 2
        assert "configuration.yaml" in data["changed_files"]
        assert "new_file.yaml" in data["changed_files"]

    @pytest.mark.asyncio
    async def test_deleted_file_shows_in_changes(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry, {"notify_service": ""})
        coord._git_available = True

        porcelain = b" D automations.yaml\n"
        proc = _mock_process(returncode=0, stdout=porcelain)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            data = await coord._async_update_data()

        assert data["status"] == STATUS_PENDING
        assert "automations.yaml" in data["changed_files"]

    @pytest.mark.asyncio
    async def test_git_status_error(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry, {"notify_service": ""})
        coord._git_available = True

        proc = _mock_process(returncode=128, stderr=b"fatal: not a git repo")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            data = await coord._async_update_data()

        assert data["status"] == STATUS_ERROR
        assert "not a git repo" in data["last_error"]

    @pytest.mark.asyncio
    async def test_git_not_available_returns_error(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._git_available = False

        data = await coord._async_update_data()
        assert data["status"] == STATUS_ERROR
        assert "not available" in data["last_error"]

    @pytest.mark.asyncio
    async def test_status_stays_pushing_during_poll(self, fake_hass, fake_entry):
        """If a push is in progress, status should not revert to pending."""
        coord = _make_coordinator(fake_hass, fake_entry, {"notify_service": ""})
        coord._git_available = True
        coord._status = STATUS_PUSHING

        porcelain = b" M some_file.yaml\n"
        proc = _mock_process(returncode=0, stdout=porcelain)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            data = await coord._async_update_data()

        # Status remains PUSHING, not overwritten to PENDING
        assert data["status"] == STATUS_PUSHING


# ---------------------------------------------------------------------------
# 3. async_push — commit and push
# ---------------------------------------------------------------------------

class TestPush:

    @pytest.mark.asyncio
    async def test_push_no_changes(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._changed_files = []

        # Should return early without calling git
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            await coord.async_push()

        mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_push_success(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._git_available = True
        coord._changed_files = ["configuration.yaml"]
        coord._status = STATUS_PENDING

        add_proc = _mock_process(returncode=0)
        commit_proc = _mock_process(returncode=0)
        rev_parse_proc = _mock_process(returncode=0, stdout=b"abc1234")
        push_proc = _mock_process(returncode=0)

        with patch("asyncio.create_subprocess_exec",
                    side_effect=[add_proc, commit_proc, rev_parse_proc, push_proc]):
            await coord.async_push()

        assert coord._status == STATUS_CLEAN
        assert coord._changed_files == []
        assert coord._last_push_commit == "abc1234"
        assert coord._last_push is not None
        assert coord._last_error is None

    @pytest.mark.asyncio
    async def test_push_add_fails(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._changed_files = ["file.yaml"]

        add_proc = _mock_process(returncode=1, stderr=b"git add failed")

        with patch("asyncio.create_subprocess_exec", return_value=add_proc):
            await coord.async_push()

        assert coord._status == STATUS_ERROR
        assert "git add failed" in coord._last_error

    @pytest.mark.asyncio
    async def test_push_commit_fails(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._changed_files = ["file.yaml"]

        add_proc = _mock_process(returncode=0)
        commit_proc = _mock_process(returncode=1, stderr=b"nothing to commit")

        with patch("asyncio.create_subprocess_exec",
                    side_effect=[add_proc, commit_proc]):
            await coord.async_push()

        assert coord._status == STATUS_ERROR

    @pytest.mark.asyncio
    async def test_push_push_fails(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._changed_files = ["file.yaml"]

        add_proc = _mock_process(returncode=0)
        commit_proc = _mock_process(returncode=0)
        rev_parse_proc = _mock_process(returncode=0, stdout=b"abc1234")
        push_proc = _mock_process(returncode=1, stderr=b"permission denied")

        with patch("asyncio.create_subprocess_exec",
                    side_effect=[add_proc, commit_proc, rev_parse_proc, push_proc]):
            await coord.async_push()

        assert coord._status == STATUS_ERROR
        assert "permission denied" in coord._last_error

    @pytest.mark.asyncio
    async def test_push_commit_message_format(self, fake_hass, fake_entry):
        """Verify the commit message includes changed filenames."""
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._changed_files = ["file1.yaml", "file2.yaml"]

        captured_args = []

        async def capture_exec(*args, **kwargs):
            captured_args.append(args)
            return _mock_process(returncode=0, stdout=b"abc1234")

        with patch("asyncio.create_subprocess_exec", side_effect=capture_exec):
            await coord.async_push()

        # Second call is commit — args: "git", "commit", "-m", <message>
        commit_call = captured_args[1]
        message = commit_call[3]  # "-m" argument value
        assert "file1.yaml" in message
        assert "file2.yaml" in message

    @pytest.mark.asyncio
    async def test_push_truncates_long_file_list(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._changed_files = [f"file{i}.yaml" for i in range(10)]

        captured_args = []

        async def capture_exec(*args, **kwargs):
            captured_args.append(args)
            return _mock_process(returncode=0, stdout=b"abc1234")

        with patch("asyncio.create_subprocess_exec", side_effect=capture_exec):
            await coord.async_push()

        commit_call = captured_args[1]
        message = commit_call[3]
        assert "(+5 more)" in message


# ---------------------------------------------------------------------------
# 4. Notification logic
# ---------------------------------------------------------------------------

class TestNotifications:

    @pytest.mark.asyncio
    async def test_notification_sent_on_pending(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry,
                                   {"notify_service": "notify.mobile_app_phone"})
        coord._git_available = True
        coord._last_notification = None

        porcelain = b" M configuration.yaml\n"
        proc = _mock_process(returncode=0, stdout=porcelain)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await coord._async_update_data()

        fake_hass.services.async_call.assert_called_once()
        call_args = fake_hass.services.async_call.call_args
        assert call_args[0][0] == "notify"
        assert call_args[0][1] == "mobile_app_phone"

    @pytest.mark.asyncio
    async def test_notification_respects_cooldown(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry,
                                   {"notify_service": "notify.test",
                                    "notification_cooldown": 30})
        coord._git_available = True

        import datetime
        # Simulate recent notification (5 seconds ago)
        coord._last_notification = datetime.datetime.utcnow().timestamp() - 5

        porcelain = b" M configuration.yaml\n"
        proc = _mock_process(returncode=0, stdout=porcelain)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await coord._async_update_data()

        # Should NOT send — cooldown not elapsed
        fake_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_notification_when_service_empty(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry, {"notify_service": ""})
        coord._git_available = True

        porcelain = b" M configuration.yaml\n"
        proc = _mock_process(returncode=0, stdout=porcelain)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await coord._async_update_data()

        fake_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_push_success_sends_result_notification(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry,
                                   {"notify_service": "notify.test"})
        coord._changed_files = ["file.yaml"]

        add_proc = _mock_process(returncode=0)
        commit_proc = _mock_process(returncode=0)
        rev_parse_proc = _mock_process(returncode=0, stdout=b"abc1234")
        push_proc = _mock_process(returncode=0)

        with patch("asyncio.create_subprocess_exec",
                    side_effect=[add_proc, commit_proc, rev_parse_proc, push_proc]):
            await coord.async_push()

        # At least one call should be the success notification
        calls = fake_hass.services.async_call.call_args_list
        assert any("Pushed" in str(c) for c in calls)

    @pytest.mark.asyncio
    async def test_push_failure_sends_error_notification(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry,
                                   {"notify_service": "notify.test"})
        coord._changed_files = ["file.yaml"]

        add_proc = _mock_process(returncode=1, stderr=b"add failed")

        with patch("asyncio.create_subprocess_exec", return_value=add_proc):
            await coord.async_push()

        calls = fake_hass.services.async_call.call_args_list
        assert any("Failed" in str(c) for c in calls)


# ---------------------------------------------------------------------------
# 5. Notification action handling
# ---------------------------------------------------------------------------

class TestActionHandling:

    @pytest.mark.asyncio
    async def test_action_push_triggers_push(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._changed_files = ["file.yaml"]

        add_proc = _mock_process(returncode=0)
        commit_proc = _mock_process(returncode=0)
        rev_parse_proc = _mock_process(returncode=0, stdout=b"abc1234")
        push_proc = _mock_process(returncode=0)

        with patch("asyncio.create_subprocess_exec",
                    side_effect=[add_proc, commit_proc, rev_parse_proc, push_proc]):
            await coord.async_handle_action(ACTION_PUSH)

        assert coord._status == STATUS_CLEAN

    @pytest.mark.asyncio
    async def test_action_dismiss_resets_cooldown(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._last_notification = None

        await coord.async_handle_action(ACTION_DISMISS)

        assert coord._last_notification is not None


# ---------------------------------------------------------------------------
# 6. _run_git — environment handling
# ---------------------------------------------------------------------------

class TestRunGit:

    @pytest.mark.asyncio
    async def test_run_git_passes_cwd(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)

        proc = _mock_process(returncode=0, stdout=b"output")
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            rc, out, err = await coord._run_git("status", "--porcelain")

        assert rc == 0
        assert out == "output"
        _, kwargs = mock_exec.call_args
        assert kwargs["cwd"] == fake_entry.data["repo_path"]

    @pytest.mark.asyncio
    async def test_run_git_merges_env(self, fake_hass, fake_entry):
        coord = _make_coordinator(fake_hass, fake_entry)

        proc = _mock_process(returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await coord._run_git("commit", "-m", "test",
                                  env={"GIT_AUTHOR_NAME": "Custom"})

        _, kwargs = mock_exec.call_args
        assert kwargs["env"]["GIT_AUTHOR_NAME"] == "Custom"


# ---------------------------------------------------------------------------
# 7. Undo / redo
# ---------------------------------------------------------------------------

class TestUndo:

    @pytest.mark.asyncio
    async def test_undo_reverts_and_pushes(self, fake_hass, fake_entry):
        """Successful undo should call revert HEAD, rev-parse, and push."""
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._status = STATUS_CLEAN

        calls = [
            # git log -1 --format=%s
            _mock_process(returncode=0, stdout=b"UI change: automations.yaml"),
            # git revert HEAD --no-edit
            _mock_process(returncode=0),
            # git rev-parse --short HEAD
            _mock_process(returncode=0, stdout=b"abc1234"),
            # git push origin main
            _mock_process(returncode=0),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        assert coord._status == STATUS_CLEAN
        assert coord._last_push_commit == "abc1234"
        assert coord._last_error is None

    @pytest.mark.asyncio
    async def test_undo_revert_failure(self, fake_hass, fake_entry):
        """If git revert fails, status should be error."""
        coord = _make_coordinator(fake_hass, fake_entry)

        calls = [
            # git log -1 --format=%s
            _mock_process(returncode=0, stdout=b"some commit"),
            # git revert HEAD --no-edit  (fails)
            _mock_process(returncode=1, stderr=b"conflict"),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        assert coord._status == STATUS_ERROR
        assert "git revert failed" in coord._last_error

    @pytest.mark.asyncio
    async def test_undo_push_failure(self, fake_hass, fake_entry):
        """If push after revert fails, status should be error."""
        coord = _make_coordinator(fake_hass, fake_entry)

        calls = [
            _mock_process(returncode=0, stdout=b"some commit"),
            _mock_process(returncode=0),  # revert ok
            _mock_process(returncode=0, stdout=b"abc1234"),  # rev-parse
            _mock_process(returncode=1, stderr=b"rejected"),  # push fails
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        assert coord._status == STATUS_ERROR
        assert "git push failed" in coord._last_error

    @pytest.mark.asyncio
    async def test_undo_log_failure(self, fake_hass, fake_entry):
        """If git log fails, undo should error before revert."""
        coord = _make_coordinator(fake_hass, fake_entry)

        calls = [
            _mock_process(returncode=1, stderr=b"bad revision"),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        assert coord._status == STATUS_ERROR
        assert "git log failed" in coord._last_error

    @pytest.mark.asyncio
    async def test_undo_sends_notification(self, fake_hass, fake_entry):
        """Successful undo should call _notify_result."""
        coord = _make_coordinator(fake_hass, fake_entry)

        calls = [
            _mock_process(returncode=0, stdout=b"UI change: test.yaml"),
            _mock_process(returncode=0),
            _mock_process(returncode=0, stdout=b"def5678"),
            _mock_process(returncode=0),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls), \
             patch.object(coord, "_notify_result", new_callable=AsyncMock) as mock_notify:
            await coord.async_undo()

        mock_notify.assert_called_once()
        title, body = mock_notify.call_args[0]
        assert "Reverted" in title
        assert "Reloaded" in title
        assert "UI change: test.yaml" in body

    @pytest.mark.asyncio
    async def test_undo_calls_yaml_reload(self, fake_hass, fake_entry):
        """Successful undo should call targeted YAML reload services."""
        coord = _make_coordinator(fake_hass, fake_entry)

        calls = [
            _mock_process(returncode=0, stdout=b"UI change: test.yaml"),
            _mock_process(returncode=0),
            _mock_process(returncode=0, stdout=b"def5678"),
            _mock_process(returncode=0),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        # Should call targeted reloads, NOT reload_all
        call_args = [c.args for c in fake_hass.services.async_call.call_args_list]
        assert ("homeassistant", "reload_all") not in call_args
        assert ("automation", "reload") in call_args
        assert ("script", "reload") in call_args

    @pytest.mark.asyncio
    async def test_undo_succeeds_even_if_reload_fails(self, fake_hass, fake_entry):
        """If YAML reloads fail, undo should still succeed with a warning."""
        coord = _make_coordinator(fake_hass, fake_entry)

        calls = [
            _mock_process(returncode=0, stdout=b"UI change: test.yaml"),
            _mock_process(returncode=0),
            _mock_process(returncode=0, stdout=b"def5678"),
            _mock_process(returncode=0),
        ]

        # Make all reload services raise
        original_async_call = fake_hass.services.async_call

        async def selective_fail(*args, **kwargs):
            if len(args) >= 2 and args[1] == "reload":
                raise RuntimeError("reload unavailable")
            if args == ("homeassistant", "reload_core_config"):
                raise RuntimeError("reload unavailable")
            if args == ("frontend", "reload_themes"):
                raise RuntimeError("reload unavailable")
            return await original_async_call(*args, **kwargs)

        fake_hass.services.async_call = AsyncMock(side_effect=selective_fail)

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        assert coord._status == STATUS_CLEAN
        assert coord._last_error is None

    @pytest.mark.asyncio
    async def test_undo_sets_pushing_status_during_operation(self, fake_hass, fake_entry):
        """Status should be PUSHING during the undo operation."""
        coord = _make_coordinator(fake_hass, fake_entry)
        statuses_during = []

        original_build = coord._build_data

        def capturing_build():
            statuses_during.append(coord._status)
            return original_build()

        coord._build_data = capturing_build

        calls = [
            _mock_process(returncode=0, stdout=b"commit msg"),
            _mock_process(returncode=0),
            _mock_process(returncode=0, stdout=b"aaa1111"),
            _mock_process(returncode=0),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        assert STATUS_PUSHING in statuses_during


# ---------------------------------------------------------------------------
# 8. Undo/redo state tracking
# ---------------------------------------------------------------------------

class TestUndoState:

    @pytest.mark.asyncio
    async def test_undo_sets_is_revert_head(self, fake_hass, fake_entry):
        """After a successful undo, is_revert_head should be True."""
        coord = _make_coordinator(fake_hass, fake_entry)
        assert coord._is_revert_head is False

        calls = [
            _mock_process(returncode=0, stdout=b"UI change: test.yaml"),
            _mock_process(returncode=0),
            _mock_process(returncode=0, stdout=b"abc1234"),
            _mock_process(returncode=0),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        assert coord._is_revert_head is True
        assert coord.data.get("is_revert_head") is True

    @pytest.mark.asyncio
    async def test_undo_twice_toggles_is_revert_head(self, fake_hass, fake_entry):
        """Pressing undo twice should toggle is_revert_head back to False."""
        coord = _make_coordinator(fake_hass, fake_entry)

        def _undo_calls():
            return [
                _mock_process(returncode=0, stdout=b"commit msg"),
                _mock_process(returncode=0),
                _mock_process(returncode=0, stdout=b"abc1234"),
                _mock_process(returncode=0),
            ]

        with patch("asyncio.create_subprocess_exec", side_effect=_undo_calls()):
            await coord.async_undo()
        assert coord._is_revert_head is True

        with patch("asyncio.create_subprocess_exec", side_effect=_undo_calls()):
            await coord.async_undo()
        assert coord._is_revert_head is False

    @pytest.mark.asyncio
    async def test_push_resets_is_revert_head(self, fake_hass, fake_entry):
        """A new push after an undo should reset is_revert_head to False."""
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._is_revert_head = True
        coord._changed_files = ["file.yaml"]

        calls = [
            _mock_process(returncode=0),          # git add
            _mock_process(returncode=0),          # git commit
            _mock_process(returncode=0, stdout=b"abc1234"),  # rev-parse
            _mock_process(returncode=0),          # git push
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_push()

        assert coord._is_revert_head is False
        assert coord.data.get("is_revert_head") is False

    @pytest.mark.asyncio
    async def test_failed_undo_preserves_revert_state(self, fake_hass, fake_entry):
        """If undo fails, is_revert_head should not change."""
        coord = _make_coordinator(fake_hass, fake_entry)
        assert coord._is_revert_head is False

        calls = [
            _mock_process(returncode=0, stdout=b"some commit"),
            _mock_process(returncode=1, stderr=b"conflict"),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        assert coord._is_revert_head is False  # unchanged on failure

    @pytest.mark.asyncio
    async def test_build_data_includes_is_revert_head(self, fake_hass, fake_entry):
        """_build_data should expose is_revert_head."""
        coord = _make_coordinator(fake_hass, fake_entry)

        data = coord._build_data()
        assert "is_revert_head" in data
        assert data["is_revert_head"] is False

    @pytest.mark.asyncio
    async def test_build_data_includes_last_activity(self, fake_hass, fake_entry):
        """_build_data should expose last_activity."""
        coord = _make_coordinator(fake_hass, fake_entry)

        data = coord._build_data()
        assert "last_activity" in data
        assert data["last_activity"] is None

    @pytest.mark.asyncio
    async def test_push_sets_last_activity(self, fake_hass, fake_entry):
        """Successful push should set _last_activity."""
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._changed_files = ["automations.yaml"]
        coord._git_available = True

        calls = [
            _mock_process(returncode=0),          # git add
            _mock_process(returncode=0),          # git commit
            _mock_process(returncode=0, stdout=b"abc1234"),  # rev-parse
            _mock_process(returncode=0),          # git push
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_push()

        assert coord._last_activity is not None
        assert "abc1234" in coord._last_activity

    @pytest.mark.asyncio
    async def test_push_failure_sets_last_activity(self, fake_hass, fake_entry):
        """Failed push should set _last_activity with failure info."""
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._changed_files = ["test.yaml"]
        coord._git_available = True

        calls = [
            _mock_process(returncode=1, stderr=b"add failed"),  # git add fails
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_push()

        assert "Push failed" in coord._last_activity

    @pytest.mark.asyncio
    async def test_undo_sets_last_activity(self, fake_hass, fake_entry):
        """Successful undo should set _last_activity with undo/redo label."""
        coord = _make_coordinator(fake_hass, fake_entry)

        calls = [
            _mock_process(returncode=0, stdout=b"UI change: automations.yaml"),
            _mock_process(returncode=0),
            _mock_process(returncode=0, stdout=b"abc1234"),
            _mock_process(returncode=0),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        assert "Undo" in coord._last_activity
        assert "reloaded" in coord._last_activity
        assert "automations.yaml" in coord._last_activity

    @pytest.mark.asyncio
    async def test_redo_sets_last_activity(self, fake_hass, fake_entry):
        """Redo (second undo press) should label activity as 'Redo'."""
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._is_revert_head = True  # simulate already-reverted state

        calls = [
            _mock_process(returncode=0, stdout=b"Revert: some change"),
            _mock_process(returncode=0),
            _mock_process(returncode=0, stdout=b"def5678"),
            _mock_process(returncode=0),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        assert "Redo" in coord._last_activity

    @pytest.mark.asyncio
    async def test_undo_failure_sets_last_activity(self, fake_hass, fake_entry):
        """Failed undo should set _last_activity with failure info."""
        coord = _make_coordinator(fake_hass, fake_entry)

        calls = [
            _mock_process(returncode=1, stderr=b"bad revision"),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        assert "Undo failed" in coord._last_activity


# ---------------------------------------------------------------------------
# 9. Git operation guard (watcher + poll suppression)
# ---------------------------------------------------------------------------

class TestGitOperationGuard:

    @pytest.mark.asyncio
    async def test_poll_skipped_during_git_operation(self, fake_hass, fake_entry):
        """_async_update_data should return cached data when _git_operating is True."""
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._git_available = True
        coord._git_operating = True
        coord._status = STATUS_PUSHING

        # Should NOT call git at all
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            data = await coord._async_update_data()

        mock_exec.assert_not_called()
        assert data["status"] == STATUS_PUSHING

    def test_filesystem_event_suppressed_during_git_operation(self, fake_hass, fake_entry):
        """_on_filesystem_event should be a no-op when _git_operating is True."""
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._git_operating = True
        fake_hass.loop = MagicMock()

        coord._on_filesystem_event()

        # Should not schedule a debounced refresh
        fake_hass.loop.call_later.assert_not_called()

    @pytest.mark.asyncio
    async def test_git_operating_cleared_after_push(self, fake_hass, fake_entry):
        """_git_operating should be False after push completes (success or failure)."""
        coord = _make_coordinator(fake_hass, fake_entry)
        coord._changed_files = ["file.yaml"]

        add_proc = _mock_process(returncode=1, stderr=b"git add failed")

        with patch("asyncio.create_subprocess_exec", return_value=add_proc):
            await coord.async_push()

        assert coord._git_operating is False

    @pytest.mark.asyncio
    async def test_git_operating_cleared_after_undo(self, fake_hass, fake_entry):
        """_git_operating should be False after undo completes (success or failure)."""
        coord = _make_coordinator(fake_hass, fake_entry)

        calls = [
            _mock_process(returncode=0, stdout=b"some commit"),
            _mock_process(returncode=1, stderr=b"conflict"),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=calls):
            await coord.async_undo()

        assert coord._git_operating is False
