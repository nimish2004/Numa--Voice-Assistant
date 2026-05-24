"""
test_settings_simple.py — Smoke tests for config/settings.py

Validates Phase 1.10 fix (llm_temperature as float) without complex mocking.
"""

import pytest
from config.settings import _SCHEMA
from config.defaults import DEFAULTS


class TestSettingsPhase110Fix:
    """Test Phase 1.10 fix: llm_temperature is float, not int."""

    def test_temperature_schema_is_float(self):
        """Temperature schema must specify float type."""
        schema_type, min_val, max_val = _SCHEMA["llm_temperature"]
        assert schema_type == float, "temperature must be float type"

    def test_temperature_default_is_float(self):
        """Default temperature must be a float."""
        temp = DEFAULTS["llm_temperature"]
        assert isinstance(temp, float), "default must be float"
        assert 0.0 <= temp <= 1.0, "default must be in range [0.0, 1.0]"

    def test_temperature_range(self):
        """Temperature range should be 0.0 to 1.0."""
        schema_type, vmin, vmax = _SCHEMA["llm_temperature"]
        assert vmin == 0.0, "temperature min must be 0.0"
        assert vmax == 1.0, "temperature max must be 1.0"

    def test_all_schema_keys_in_defaults(self):
        """Every schema key should have a default."""
        for key in _SCHEMA.keys():
            assert key in DEFAULTS, f"setting '{key}' missing from defaults"

    def test_settings_file_exists(self):
        """Settings file should be created in AppData."""
        from config.settings import SETTINGS_FILE
        # Just verify the path is sensible
        assert "Numa" in SETTINGS_FILE or "numa" in SETTINGS_FILE.lower()
        assert ".json" in SETTINGS_FILE
