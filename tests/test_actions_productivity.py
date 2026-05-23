"""
test_actions_productivity.py — Tests for actions/productivity.py

Tests:
- set_timer: creates timer, cancels properly
- set_reminder: sets reminders
- read_clipboard: reads clipboard
- clear_clipboard: clears clipboard
- git_status: runs git command
- _ensure_reminder_thread: Phase 1.12 atomic fix
- Concurrent reminder starts (race condition fix)
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock, call

import pytest


class TestSetTimer:
    """Test timer creation."""

    def test_set_timer_creates_timer(self):
        """set_timer should create a threading.Timer."""
        from actions import productivity

        with patch('actions.productivity.speak') as mock_speak:
            data = {
                "parameters": {
                    "duration_seconds": 60,
                    "label": "test"
                }
            }
            productivity.set_timer(data)
            # Should have spoken something
            mock_speak.assert_called()

    def test_set_timer_with_zero_duration(self):
        """set_timer with 0 duration should ask for duration."""
        from actions import productivity

        with patch('actions.productivity.speak') as mock_speak:
            data = {"parameters": {"duration_seconds": 0}}
            productivity.set_timer(data)
            # Should have spoken an error
            spoken = mock_speak.call_args[0][0]
            assert "how long" in spoken.lower()

    def test_cancel_timer_by_name(self):
        """cancel_timer should cancel a named timer."""
        from actions import productivity

        with patch('actions.productivity.speak'):
            # Create a timer
            data = {
                "parameters": {
                    "duration_seconds": 60,
                    "label": "test"
                }
            }
            productivity.set_timer(data)

            # Cancel it
            with patch('actions.productivity.speak') as mock_speak:
                cancel_data = {"parameters": {"label": "test"}}
                productivity.cancel_timer(cancel_data)
                spoken = mock_speak.call_args[0][0]
                assert "cancelled" in spoken.lower()

    def test_cancel_all_timers(self):
        """cancel_timer with no label should cancel all."""
        from actions import productivity

        with patch('actions.productivity.speak'):
            # Create two timers
            for i in range(2):
                data = {
                    "parameters": {
                        "duration_seconds": 60,
                        "label": f"timer{i}"
                    }
                }
                productivity.set_timer(data)

            # Cancel all
            with patch('actions.productivity.speak') as mock_speak:
                productivity.cancel_timer({"parameters": {}})
                spoken = mock_speak.call_args[0][0]
                assert "all" in spoken.lower()


class TestSetReminder:
    """Test reminder creation."""

    def test_set_reminder_from_now(self):
        """set_reminder should create reminder from now."""
        from actions import productivity

        with patch('actions.productivity.speak') as mock_speak:
            data = {
                "parameters": {
                    "message": "call john",
                    "minutes_from_now": 30
                }
            }
            productivity.set_reminder(data)
            mock_speak.assert_called()

    def test_set_reminder_starts_thread(self):
        """set_reminder should start reminder loop thread."""
        from actions import productivity
        import importlib
        importlib.reload(productivity)

        with patch('actions.productivity.speak'):
            data = {
                "parameters": {
                    "message": "test",
                    "minutes_from_now": 1
                }
            }
            productivity.set_reminder(data)

            # Check that reminder thread exists
            threads = [t for t in threading.enumerate() if "ReminderLoop" in t.name]
            assert len(threads) > 0, "reminder loop thread should exist"

    def test_set_reminder_no_message(self):
        """set_reminder without message should ask."""
        from actions import productivity

        with patch('actions.productivity.speak') as mock_speak:
            data = {"parameters": {}}
            productivity.set_reminder(data)
            spoken = mock_speak.call_args[0][0]
            assert "remind" in spoken.lower()


class TestEnsureReminderThread:
    """Test Phase 1.12 fix: _ensure_reminder_thread is atomic."""

    @pytest.mark.concurrency
    def test_reminder_thread_starts_once(self):
        """
        When 10 threads call set_reminder() simultaneously,
        only 1 ReminderLoop thread should start.
        Phase 1.12 race condition fix.
        """
        from actions import productivity
        import importlib
        importlib.reload(productivity)

        def start_reminders():
            with patch('actions.productivity.speak'):
                data = {
                    "parameters": {
                        "message": "test",
                        "minutes_from_now": 30
                    }
                }
                productivity.set_reminder(data)

        # 10 threads, all start reminders simultaneously
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(start_reminders) for _ in range(10)]
            for f in futures:
                f.result()

        # Check how many ReminderLoop threads exist
        threads = [t for t in threading.enumerate() if "ReminderLoop" in t.name]
        assert len(threads) == 1, f"Expected 1 ReminderLoop thread, got {len(threads)}"

    @pytest.mark.concurrency
    def test_concurrent_set_reminder_no_duplicate_threads(self):
        """Heavy concurrent load should not create duplicate reminder threads."""
        from actions import productivity
        import importlib
        importlib.reload(productivity)

        def add_reminders(iteration):
            with patch('actions.productivity.speak'):
                for i in range(5):
                    data = {
                        "parameters": {
                            "message": f"reminder {iteration}_{i}",
                            "minutes_from_now": 10
                        }
                    }
                    productivity.set_reminder(data)

        # 5 threads, each adds 5 reminders
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(add_reminders, i) for i in range(5)]
            for f in futures:
                f.result()

        # Should still only have 1 ReminderLoop thread
        threads = [t for t in threading.enumerate() if "ReminderLoop" in t.name]
        assert len(threads) == 1, "Should have exactly 1 ReminderLoop thread"


class TestClipboard:
    """Test clipboard operations."""

    def test_read_clipboard(self):
        """read_clipboard should read and speak."""
        from actions import productivity

        with patch('pyperclip.paste', return_value="test content"):
            with patch('actions.productivity.speak') as mock_speak:
                productivity.read_clipboard({})
                mock_speak.assert_called()

    def test_read_clipboard_empty(self):
        """read_clipboard with empty clipboard should speak that."""
        from actions import productivity

        with patch('pyperclip.paste', return_value=""):
            with patch('actions.productivity.speak') as mock_speak:
                productivity.read_clipboard({})
                spoken = mock_speak.call_args[0][0]
                assert "empty" in spoken.lower()

    def test_clear_clipboard(self):
        """clear_clipboard should clear and confirm."""
        from actions import productivity

        with patch('pyperclip.copy') as mock_copy:
            with patch('actions.productivity.speak') as mock_speak:
                productivity.clear_clipboard({})
                mock_copy.assert_called_with("")
                mock_speak.assert_called()


class TestGitStatus:
    """Test git status command."""

    def test_git_status_success(self):
        """git_status should parse git output."""
        from actions import productivity

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = " M file1.py\n?? file2.py\n"

        with patch('subprocess.run', return_value=mock_result):
            with patch('actions.productivity.speak') as mock_speak:
                productivity.git_status({})
                mock_speak.assert_called()
                spoken = mock_speak.call_args[0][0]
                # Should mention the status
                assert "git" in spoken.lower() or "modified" in spoken.lower() or "untracked" in spoken.lower()

    def test_git_status_not_repo(self):
        """git_status when not in a repo should handle gracefully."""
        from actions import productivity

        mock_result = MagicMock()
        mock_result.returncode = 128  # not a git repo

        with patch('subprocess.run', return_value=mock_result):
            with patch('actions.productivity.speak') as mock_speak:
                productivity.git_status({})
                spoken = mock_speak.call_args[0][0]
                assert "not" in spoken.lower() or "repo" in spoken.lower()

    def test_git_status_git_not_found(self):
        """git_status when git is not installed should handle."""
        from actions import productivity

        with patch('subprocess.run', side_effect=FileNotFoundError()):
            with patch('actions.productivity.speak') as mock_speak:
                productivity.git_status({})
                spoken = mock_speak.call_args[0][0]
                assert "not" in spoken.lower() or "path" in spoken.lower()
