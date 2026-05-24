"""
test_actions_system_simple.py — Smoke tests for actions/system.py

Simplified tests that verify Phase 1.13 fix without complex mocking.
"""

from unittest.mock import patch, MagicMock

import pytest


class TestShutdownRestart:
    """Test shutdown and restart don't crash."""

    def test_shutdown_does_not_crash(self):
        """shutdown() should run without exception."""
        from actions import system
        with patch('subprocess.run'):
            with patch('actions.system.speak'):
                system.shutdown({})  # Should not raise

    def test_restart_does_not_crash(self):
        """restart() should run without exception."""
        from actions import system
        with patch('subprocess.run'):
            with patch('actions.system.speak'):
                system.restart({})  # Should not raise

    def test_shutdown_calls_subprocess(self):
        """shutdown() should call subprocess.run."""
        from actions import system
        with patch('subprocess.run') as mock_run:
            with patch('actions.system.speak'):
                system.shutdown({})
                # Verify subprocess was called with shutdown command
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args[0] == "shutdown"

    def test_restart_calls_subprocess(self):
        """restart() should call subprocess.run."""
        from actions import system
        with patch('subprocess.run') as mock_run:
            with patch('actions.system.speak'):
                system.restart({})
                # Verify subprocess was called with shutdown /r
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args[0] == "shutdown"
                assert "/r" in args
