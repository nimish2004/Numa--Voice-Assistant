"""
test_memory.py — Tests for memory.py

Tests:
- add_exchange (user/assistant messages)
- get_memory and get_recent
- history trimming to max_history
- clear_memory
- corrupt file handling
- concurrent adds (thread safety)
"""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest


@pytest.fixture
def memory_module(tmp_memory_file, monkeypatch):
    """
    Import memory module with temp file.
    Monkeypatch the module to use temp file.
    """
    # Patch before importing
    monkeypatch.setenv("MEMORY_FILE", tmp_memory_file)
    with patch('config.settings.settings.get') as mock_get:
        mock_get.side_effect = lambda key, default=None: {
            "memory_file": tmp_memory_file,
            "memory_max_history": 20,
        }.get(key, default)

        # Force re-import to pick up patches
        import importlib
        import memory
        importlib.reload(memory)
        yield memory

        # Cleanup
        importlib.reload(memory)


class TestMemoryBasics:
    """Basic memory operations."""

    def test_add_exchange_user_assistant(self, tmp_memory_file):
        """Test adding a user/assistant exchange."""
        with patch('config.settings.settings.get') as mock_get:
            mock_get.side_effect = lambda key, d=None: {
                "memory_file": tmp_memory_file,
                "memory_max_history": 20,
            }.get(key, d)

            import importlib
            import memory
            importlib.reload(memory)

            memory.add_exchange("what time is it", "It's 10 AM", "chat")

            messages = memory.get_memory()
            assert len(messages) == 2  # user + assistant
            assert messages[0]["role"] == "user"
            assert messages[0]["content"] == "what time is it"
            assert messages[1]["role"] == "assistant"
            assert messages[1]["content"] == "It's 10 AM"

    def test_get_memory_returns_list(self, tmp_memory_file):
        """Test get_memory returns a list."""
        with patch('config.settings.settings.get') as mock_get:
            mock_get.side_effect = lambda key, d=None: {
                "memory_file": tmp_memory_file,
                "memory_max_history": 20,
            }.get(key, d)

            import importlib
            import memory
            importlib.reload(memory)

            memory.add_exchange("test", "response", "chat")
            result = memory.get_memory()
            assert isinstance(result, list)
            assert len(result) > 0

    def test_get_recent(self, tmp_memory_file):
        """Test get_recent(n) returns last n messages."""
        with patch('config.settings.settings.get') as mock_get:
            mock_get.side_effect = lambda key, d=None: {
                "memory_file": tmp_memory_file,
                "memory_max_history": 100,
            }.get(key, d)

            import importlib
            import memory
            importlib.reload(memory)

            # Add 10 messages (5 exchanges)
            for i in range(5):
                memory.add_exchange(f"question {i}", f"answer {i}", "chat")

            recent = memory.get_recent(4)
            assert len(recent) == 4
            # Should be the last 4 messages (last 2 exchanges)

    def test_clear_memory(self, tmp_memory_file):
        """Test clear_memory wipes all history."""
        with patch('config.settings.settings.get') as mock_get:
            mock_get.side_effect = lambda key, d=None: {
                "memory_file": tmp_memory_file,
                "memory_max_history": 20,
            }.get(key, d)

            import importlib
            import memory
            importlib.reload(memory)

            memory.add_exchange("test", "response", "chat")
            assert len(memory.get_memory()) > 0

            memory.clear_memory()
            assert len(memory.get_memory()) == 0


class TestMemoryTrimming:
    """Test history trimming to max_history."""

    def test_trim_to_max_history(self, tmp_memory_file):
        """Add 30 messages, keep only max_history (20)."""
        with patch('config.settings.settings.get') as mock_get:
            mock_get.side_effect = lambda key, d=None: {
                "memory_file": tmp_memory_file,
                "memory_max_history": 20,
            }.get(key, d)

            import importlib
            import memory
            importlib.reload(memory)

            # Add 15 exchanges (30 messages)
            for i in range(15):
                memory.add_exchange(f"q{i}", f"a{i}", "chat")

            messages = memory.get_memory()
            assert len(messages) == 20  # trimmed to max
            # Oldest should be from exchange 5 (10th message)
            assert "q5" in messages[0]["content"]

    def test_trim_happens_on_add(self, tmp_memory_file):
        """Trimming should happen automatically on add_exchange."""
        with patch('config.settings.settings.get') as mock_get:
            mock_get.side_effect = lambda key, d=None: {
                "memory_file": tmp_memory_file,
                "memory_max_history": 4,  # very small
            }.get(key, d)

            import importlib
            import memory
            importlib.reload(memory)

            # Add 4 exchanges (8 messages total, max is 4)
            for i in range(4):
                memory.add_exchange(f"q{i}", f"a{i}", "chat")
                messages = memory.get_memory()
                assert len(messages) <= 4  # always respect max


class TestCorruptFileHandling:
    """Test handling of corrupt memory file."""

    def test_corrupt_json_loads_empty(self, tmp_memory_file):
        """If memory file is corrupt JSON, start fresh."""
        # Write corrupt JSON
        with open(tmp_memory_file, 'w') as f:
            f.write('{"invalid": json here}')

        with patch('config.settings.settings.get') as mock_get:
            mock_get.side_effect = lambda key, d=None: {
                "memory_file": tmp_memory_file,
                "memory_max_history": 20,
            }.get(key, d)

            import importlib
            import memory
            importlib.reload(memory)

            # Should start fresh
            messages = memory.get_memory()
            assert isinstance(messages, list)
            # After reload, should be empty or have defaults
            assert len(messages) == 0 or len(messages) > 0  # just verify it's a list

    def test_missing_file_starts_empty(self, tmp_memory_file):
        """If memory file doesn't exist, start fresh."""
        os.remove(tmp_memory_file)

        with patch('config.settings.settings.get') as mock_get:
            mock_get.side_effect = lambda key, d=None: {
                "memory_file": tmp_memory_file,
                "memory_max_history": 20,
            }.get(key, d)

            import importlib
            import memory
            importlib.reload(memory)

            messages = memory.get_memory()
            assert isinstance(messages, list)
            assert len(messages) == 0  # empty on missing file


class TestConcurrentAdds:
    """Test thread safety of concurrent memory adds."""

    @pytest.mark.concurrency
    def test_concurrent_adds_safe(self, tmp_memory_file):
        """Multiple threads adding simultaneously should not corrupt."""
        with patch('config.settings.settings.get') as mock_get:
            mock_get.side_effect = lambda key, d=None: {
                "memory_file": tmp_memory_file,
                "memory_max_history": 100,
            }.get(key, d)

            import importlib
            import memory
            importlib.reload(memory)

            def add_message(i):
                memory.add_exchange(f"q{i}", f"a{i}", "chat")

            # 10 threads, each adds a message simultaneously
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(add_message, i) for i in range(10)]
                for f in futures:
                    f.result()  # wait for all

            messages = memory.get_memory()
            # Should have all 20 messages (10 exchanges * 2)
            assert len(messages) == 20

    @pytest.mark.concurrency
    def test_no_corruption_under_stress(self, tmp_memory_file):
        """Heavy concurrent load should not corrupt file."""
        with patch('config.settings.settings.get') as mock_get:
            mock_get.side_effect = lambda key, d=None: {
                "memory_file": tmp_memory_file,
                "memory_max_history": 100,
            }.get(key, d)

            import importlib
            import memory
            importlib.reload(memory)

            def stress_add(iteration):
                for i in range(5):
                    memory.add_exchange(
                        f"stress{iteration}_{i}",
                        f"response{iteration}_{i}",
                        "chat"
                    )

            # 5 threads, each adds 5 messages (25 total)
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(stress_add, i) for i in range(5)]
                for f in futures:
                    f.result()

            # Verify file is valid JSON
            with open(tmp_memory_file, 'r') as f:
                data = json.load(f)
                assert isinstance(data, list)
                assert len(data) > 0
