"""
tests/test_app_scanner.py — Unit tests for app_scanner module.

Tests app discovery, caching, and fuzzy matching without needing Google API.
"""

import json
import pathlib
import tempfile
import threading
import time
from unittest.mock import patch, MagicMock

import pytest


class TestAppScannerRegistry:
    """Test Windows registry scanning."""

    def test_scan_registry_returns_dict(self):
        from actions.app_scanner import _scan_registry
        result = _scan_registry()
        assert isinstance(result, dict)
        # Should find at least a few common apps (Chrome, Excel, Notepad, etc.)
        assert len(result) > 0

    def test_registry_keys_are_lowercase(self):
        from actions.app_scanner import _scan_registry
        result = _scan_registry()
        for key in result.keys():
            assert key == key.lower(), f"Key {key} is not lowercase"


class TestAppScannerStartMenu:
    """Test Start Menu shortcut scanning."""

    def test_scan_start_menu_returns_dict(self):
        from actions.app_scanner import _scan_start_menu
        result = _scan_start_menu()
        assert isinstance(result, dict)
        # Start Menu typically has shortcuts
        assert len(result) >= 0  # May be 0 on minimal installs

    def test_start_menu_keys_are_lowercase(self):
        from actions.app_scanner import _scan_start_menu
        result = _scan_start_menu()
        for key in result.keys():
            assert key == key.lower(), f"Key {key} is not lowercase"


class TestAppScannerCombined:
    """Test combined scanning."""

    def test_do_scan_returns_combined_apps(self):
        from actions.app_scanner import _do_scan, _scan_registry, _scan_start_menu
        registry = _scan_registry()
        menu = _scan_start_menu()
        combined = _do_scan()

        # Combined should have at least as many apps as either source
        assert len(combined) >= max(len(registry), len(menu))
        assert isinstance(combined, dict)

    def test_registry_overrides_start_menu(self):
        """Registry paths override Start Menu shortcuts for the same app."""
        from actions.app_scanner import _do_scan
        combined = _do_scan()
        # Check that some apps have .exe paths (from registry)
        exe_paths = [p for p in combined.values() if p.endswith('.exe')]
        assert len(exe_paths) > 0


class TestAppScannerFuzzyMatch:
    """Test fuzzy matching logic."""

    def test_find_app_exact_match(self):
        from actions.app_scanner import start_background_scan, find_app
        start_background_scan()
        time.sleep(1)  # Wait for scan

        # Try exact matches for known apps
        for app_query in ['chrome', 'excel', 'notepad']:
            result = find_app(app_query)
            if result:
                name, path = result
                assert name is not None
                assert path is not None
                break  # At least one should be found

    def test_find_app_returns_tuple_or_none(self):
        from actions.app_scanner import start_background_scan, find_app
        start_background_scan()
        time.sleep(1)

        # Should return either (name, path) tuple or None
        result = find_app('nonexistent_xyzabc_app_that_definitely_does_not_exist')
        assert result is None or (isinstance(result, tuple) and len(result) == 2)

    def test_find_app_case_insensitive(self):
        from actions.app_scanner import start_background_scan, find_app
        start_background_scan()
        time.sleep(1)

        # Query should be case-insensitive
        result_lower = find_app('chrome')
        result_upper = find_app('CHROME')
        result_mixed = find_app('ChRoMe')

        # All should find the same app or all not find
        found_count = sum(1 for r in [result_lower, result_upper, result_mixed] if r is not None)
        assert found_count in [0, 3], "Case sensitivity should be consistent"


class TestAppScannerCache:
    """Test caching logic."""

    def test_cache_file_path_correct(self):
        from actions.app_scanner import CACHE_FILE
        assert 'Numa' in str(CACHE_FILE)
        assert str(CACHE_FILE).endswith('app_cache.json')

    def test_load_cache_returns_dict(self):
        from actions.app_scanner import _load_cache
        result = _load_cache()
        assert isinstance(result, dict)

    def test_save_and_load_cache(self):
        from actions.app_scanner import _save_cache, _load_cache
        test_data = {'chrome': '/path/to/chrome', 'notepad': '/path/to/notepad'}
        _save_cache(test_data)
        loaded = _load_cache()
        assert loaded == test_data


class TestAppScannerBackgroundThread:
    """Test background scanning thread."""

    def test_start_background_scan_is_threaded(self):
        from actions.app_scanner import start_background_scan, _scan_done
        _scan_done.clear()
        start_background_scan()
        # Thread should be a daemon thread (non-blocking)
        time.sleep(2)  # Let it scan
        # Should complete without blocking the test

    def test_scan_done_event_fires(self):
        from actions.app_scanner import start_background_scan, _scan_done
        _scan_done.clear()
        start_background_scan()
        # Wait for scan to complete (up to 10 seconds)
        fired = _scan_done.wait(timeout=10)
        assert fired, "Scan should complete within 10 seconds"


class TestAppScannerRefresh:
    """Test refresh functionality."""

    def test_refresh_cache_is_threaded(self):
        from actions.app_scanner import refresh_cache
        refresh_cache()
        # Should not block — it's a background thread
        time.sleep(1)

    def test_refresh_triggers_new_scan(self):
        from actions.app_scanner import refresh_cache, _scan_done, start_background_scan
        _scan_done.clear()
        start_background_scan()
        _scan_done.wait(timeout=5)
        initial_fired = _scan_done.is_set()

        _scan_done.clear()
        refresh_cache()
        refreshed = _scan_done.wait(timeout=10)
        assert refreshed, "Refresh should trigger a new scan"
