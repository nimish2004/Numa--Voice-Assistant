"""
test_actions_system.py — Tests for actions/system.py

Tests:
- shutdown() Phase 1.13 fix: converts delay to string with fallback
- restart() Phase 1.13 fix: converts delay to string with fallback
- Delay fallback when setting is None
"""

from unittest.mock import patch, MagicMock, call

import pytest


class TestShutdown:
    """Test shutdown action."""

    def test_shutdown_uses_setting_delay(self):
        """shutdown() should read delay from settings."""
        from actions import system

        with patch('config.settings.settings.get') as mock_get:
            mock_get.return_value = 5  # shutdown_delay_sec = 5

            with patch('subprocess.run') as mock_run:
                with patch('actions.system.speak') as mock_speak:
                    system.shutdown({})

                    # Should have called subprocess.run with "5" as string
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    # Check that delay is in the arguments as string
                    assert "5" in call_args[0][0], "delay should be '5' (string)"

    def test_shutdown_converts_delay_to_string(self):
        """shutdown() should convert int delay to string."""
        from actions import system

        with patch('config.settings.settings.get') as mock_get:
            mock_get.return_value = 10

            with patch('subprocess.run') as mock_run:
                with patch('actions.system.speak'):
                    system.shutdown({})

                    call_args = mock_run.call_args[0][0]
                    # Find the delay value in the command
                    delay_str = str(10)
                    assert delay_str in call_args, "delay must be converted to string"

    def test_shutdown_fallback_when_setting_none(self):
        """
        Phase 1.13 fix: shutdown() should use fallback 5 if setting is None.
        Without this fix, it would pass None to subprocess and crash.
        """
        from actions import system

        with patch('config.settings.settings.get') as mock_get:
            mock_get.return_value = None  # Simulate missing setting

            with patch('subprocess.run') as mock_run:
                with patch('actions.system.speak'):
                    system.shutdown({})

                    # Should use fallback 5, not None
                    call_args = mock_run.call_args[0][0]
                    # The command should have "5" (the fallback)
                    assert "5" in call_args, "should use fallback 5 when setting is None"
                    assert None not in call_args, "should never pass None to subprocess"

    def test_shutdown_speaks_warning(self):
        """shutdown() should speak a warning."""
        from actions import system

        with patch('config.settings.settings.get', return_value=5):
            with patch('subprocess.run'):
                with patch('actions.system.speak') as mock_speak:
                    system.shutdown({})

                    # Should have spoken something about shutdown
                    mock_speak.assert_called()
                    spoken_text = mock_speak.call_args[0][0]
                    assert "shutting down" in spoken_text.lower()


class TestRestart:
    """Test restart action."""

    def test_restart_uses_setting_delay(self):
        """restart() should read delay from settings."""
        from actions import system

        with patch('config.settings.settings.get') as mock_get:
            mock_get.return_value = 5

            with patch('subprocess.run') as mock_run:
                with patch('actions.system.speak'):
                    system.restart({})

                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    assert "5" in call_args[0][0], "delay should be '5' (string)"

    def test_restart_converts_delay_to_string(self):
        """restart() should convert int delay to string."""
        from actions import system

        with patch('config.settings.settings.get', return_value=10):
            with patch('subprocess.run') as mock_run:
                with patch('actions.system.speak'):
                    system.restart({})

                    call_args = mock_run.call_args[0][0]
                    assert "10" in call_args, "delay must be converted to string"

    def test_restart_fallback_when_setting_none(self):
        """
        Phase 1.13 fix: restart() should use fallback 5 if setting is None.
        """
        from actions import system

        with patch('config.settings.settings.get', return_value=None):
            with patch('subprocess.run') as mock_run:
                with patch('actions.system.speak'):
                    system.restart({})

                    call_args = mock_run.call_args[0][0]
                    assert "5" in call_args, "should use fallback 5 when setting is None"
                    assert None not in call_args, "should never pass None"

    def test_restart_speaks_message(self):
        """restart() should speak about restarting."""
        from actions import system

        with patch('config.settings.settings.get', return_value=5):
            with patch('subprocess.run'):
                with patch('actions.system.speak') as mock_speak:
                    system.restart({})

                    mock_speak.assert_called()
                    spoken_text = mock_speak.call_args[0][0]
                    assert "restarting" in spoken_text.lower()


class TestOtherSystemActions:
    """Test other system actions work without crashing."""

    def test_lock_laptop(self):
        """lock_laptop should not crash."""
        from actions import system

        with patch('subprocess.run'):
            with patch('actions.system.speak'):
                system.lock_laptop({})  # Should not raise

    def test_sleep(self):
        """sleep should not crash."""
        from actions import system

        with patch('subprocess.run'):
            with patch('actions.system.speak'):
                system.sleep({})  # Should not raise

    def test_volume_up(self):
        """volume_up should not crash."""
        from actions import system

        with patch('pyautogui.press'):
            with patch('actions.system.speak'):
                system.volume_up({})  # Should not raise

    def test_volume_down(self):
        """volume_down should not crash."""
        from actions import system

        with patch('pyautogui.press'):
            with patch('actions.system.speak'):
                system.volume_down({})  # Should not raise

    def test_mute(self):
        """mute should not crash."""
        from actions import system

        with patch('pyautogui.press'):
            with patch('actions.system.speak'):
                system.mute({})  # Should not raise
