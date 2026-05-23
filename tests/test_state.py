"""
test_state.py — Tests for state.py

Tests:
- is_running / stop
- is_processing / set_processing
- try_start_processing (Phase 1.4 atomic fix)
- toggle_mute / is_muted
- Race condition: concurrent try_start_processing
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
import state


class TestRunningState:
    """Test running state management."""

    def test_is_running_initially_true(self):
        """App should be running initially."""
        # Reset state
        import importlib
        importlib.reload(state)
        assert state.is_running() is True

    def test_stop_sets_running_false(self):
        """stop() should set running to False."""
        import importlib
        importlib.reload(state)
        state.stop()
        assert state.is_running() is False

    def test_stop_is_persistent(self):
        """Once stopped, app stays stopped."""
        import importlib
        importlib.reload(state)
        state.stop()
        assert state.is_running() is False
        assert state.is_running() is False  # still false


class TestProcessingState:
    """Test processing state management."""

    def test_is_processing_initially_false(self):
        """Should not be processing initially."""
        import importlib
        importlib.reload(state)
        assert state.is_processing() is False

    def test_set_processing_true(self):
        """set_processing(True) should set processing flag."""
        import importlib
        importlib.reload(state)
        state.set_processing(True)
        assert state.is_processing() is True

    def test_set_processing_false(self):
        """set_processing(False) should clear processing flag."""
        import importlib
        importlib.reload(state)
        state.set_processing(True)
        state.set_processing(False)
        assert state.is_processing() is False


class TestAtomicTryStartProcessing:
    """Test Phase 1.4 fix: atomic try_start_processing()."""

    def test_try_start_processing_success(self):
        """try_start_processing should return True if not already processing."""
        import importlib
        importlib.reload(state)
        result = state.try_start_processing()
        assert result is True
        assert state.is_processing() is True

    def test_try_start_processing_fails_when_busy(self):
        """try_start_processing should return False if already processing."""
        import importlib
        importlib.reload(state)
        # First call succeeds
        result1 = state.try_start_processing()
        assert result1 is True

        # Second call should fail
        result2 = state.try_start_processing()
        assert result2 is False

    def test_try_start_after_clear(self):
        """After clearing processing, try_start should succeed again."""
        import importlib
        importlib.reload(state)
        state.try_start_processing()
        state.set_processing(False)
        result = state.try_start_processing()
        assert result is True

    @pytest.mark.concurrency
    def test_concurrent_try_start_only_one_wins(self):
        """
        When 10 threads call try_start_processing() simultaneously,
        only 1 should succeed (Phase 1.4 race condition fix).
        """
        import importlib
        importlib.reload(state)

        results = []
        results_lock = threading.Lock()

        def try_start():
            result = state.try_start_processing()
            with results_lock:
                results.append(result)

        # 10 threads, all try to start simultaneously
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(try_start) for _ in range(10)]
            for f in futures:
                f.result()

        # Exactly 1 should have succeeded
        assert sum(results) == 1, "Only 1 thread should win the race"
        assert results.count(True) == 1, "Should have exactly 1 True"
        assert results.count(False) == 9, "Should have exactly 9 False"

    @pytest.mark.concurrency
    def test_stress_concurrent_try_start(self):
        """Heavy concurrent load on try_start_processing."""
        import importlib
        importlib.reload(state)

        results = []
        results_lock = threading.Lock()

        def rapid_try_start(iteration):
            local_results = []
            for i in range(5):
                state.set_processing(False)  # reset for next attempt
                result = state.try_start_processing()
                local_results.append(result)
            with results_lock:
                results.extend(local_results)

        # 10 threads, each tries 5 times
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(rapid_try_start, i) for i in range(10)]
            for f in futures:
                f.result()

        # Each reset allows exactly 1 winner
        assert len(results) == 50  # 10 threads * 5 tries
        # Each attempt (after reset) should have exactly 1 winner
        # This is a stress test - just verify no crashes and results collected
        assert results.count(True) > 0


class TestMuteState:
    """Test mute state management."""

    def test_is_muted_initially_false(self):
        """Should not be muted initially."""
        import importlib
        importlib.reload(state)
        assert state.is_muted() is False

    def test_toggle_mute_true(self):
        """toggle_mute should toggle to True and return True."""
        import importlib
        importlib.reload(state)
        result = state.toggle_mute()
        assert result is True
        assert state.is_muted() is True

    def test_toggle_mute_back_to_false(self):
        """toggle_mute should toggle back to False."""
        import importlib
        importlib.reload(state)
        state.toggle_mute()
        result = state.toggle_mute()
        assert result is False
        assert state.is_muted() is False

    def test_toggle_mute_returns_new_state(self):
        """toggle_mute should return the NEW state after toggling."""
        import importlib
        importlib.reload(state)
        # Initially False
        assert state.is_muted() is False
        # Toggle to True
        result = state.toggle_mute()
        assert result is True  # returns new state (True)
        # Toggle back to False
        result = state.toggle_mute()
        assert result is False  # returns new state (False)


class TestStateSnapshot:
    """Test get_all() snapshot."""

    def test_get_all_returns_dict(self):
        """get_all should return a snapshot dict."""
        import importlib
        importlib.reload(state)
        snapshot = state.get_all()
        assert isinstance(snapshot, dict)

    def test_get_all_includes_all_keys(self):
        """Snapshot should include running, processing, muted."""
        import importlib
        importlib.reload(state)
        snapshot = state.get_all()
        assert "running" in snapshot
        assert "processing" in snapshot
        assert "muted" in snapshot

    def test_get_all_is_snapshot(self):
        """Snapshot should not change when state changes."""
        import importlib
        importlib.reload(state)
        snapshot1 = state.get_all()
        state.toggle_mute()
        snapshot2 = state.get_all()
        # snapshot1 should still have old value (False for muted)
        # snapshot2 should have new value (True for muted)
        assert snapshot1["muted"] is False
        assert snapshot2["muted"] is True
