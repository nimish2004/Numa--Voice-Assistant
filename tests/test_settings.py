"""
test_settings.py — Tests for config/settings.py

Tests:
- get/set operations
- type coercion (int, float, bool)
- validation (min/max ranges)
- llm_temperature float fix (from Phase 1.10)
- corrupt file fallback
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

from config.settings import _Settings
from config.defaults import DEFAULTS


class TestSettingsBasics:
    """Basic get/set operations."""

    def test_get_default_value(self, tmp_settings_file):
        """Test getting a value that exists in defaults."""
        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            value = settings.get("wake_word")
            assert value == DEFAULTS["wake_word"]

    def test_get_with_fallback(self, tmp_settings_file):
        """Test get() with fallback parameter."""
        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            value = settings.get("nonexistent_key", fallback="default_value")
            assert value == "default_value"

    def test_set_valid_string(self, tmp_settings_file):
        """Test setting a valid string value."""
        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            ok, err = settings.set("wake_word", "alexa")
            assert ok is True
            assert settings.get("wake_word") == "alexa"

    def test_set_valid_int(self, tmp_settings_file):
        """Test setting a valid int value within range."""
        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            ok, err = settings.set("wake_required_hits", 5)
            assert ok is True
            assert settings.get("wake_required_hits") == 5

    def test_set_invalid_range(self, tmp_settings_file):
        """Test setting value outside valid range fails."""
        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            ok, err = settings.set("wake_required_hits", 999)  # max is 10
            assert ok is False
            assert "maximum is 10" in err.lower()


class TestTypeCoercion:
    """Test automatic type coercion."""

    def test_string_to_int(self, tmp_settings_file):
        """Test coercing string '5' to int."""
        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            ok, err = settings.set("wake_required_hits", "5")
            assert ok is True
            assert settings.get("wake_required_hits") == 5
            assert isinstance(settings.get("wake_required_hits"), int)

    def test_string_to_float(self, tmp_settings_file):
        """Test coercing string '0.7' to float."""
        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            ok, err = settings.set("llm_temperature", "0.7")
            assert ok is True
            assert settings.get("llm_temperature") == 0.7
            assert isinstance(settings.get("llm_temperature"), float)

    def test_int_to_float_temperature(self, tmp_settings_file):
        """Test that integer 1 is coerced to float 1.0 for temperature."""
        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            ok, err = settings.set("llm_temperature", 1)  # int
            assert ok is True
            value = settings.get("llm_temperature")
            assert value == 1.0
            # Phase 1.10 fix: temperature should be float, not int
            assert isinstance(value, float), "temperature must be float"

    def test_invalid_coercion(self, tmp_settings_file):
        """Test that invalid coercion fails."""
        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            ok, err = settings.set("wake_required_hits", "not_a_number")
            assert ok is False
            assert "must be of type int" in err.lower()


class TestTemperatureFix:
    """Test Phase 1.10 fix: llm_temperature as float."""

    def test_temperature_accepts_floats(self, tmp_settings_file):
        """Temperature should accept 0.0-1.0 floats."""
        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            for val in [0.0, 0.5, 0.7, 1.0]:
                ok, err = settings.set("llm_temperature", val)
                assert ok is True, f"temperature {val} should be valid"

    def test_temperature_schema_is_float(self, tmp_settings_file):
        """Temperature schema should specify float, not int."""
        from config.settings import _SCHEMA
        schema_type, min_val, max_val = _SCHEMA["llm_temperature"]
        assert schema_type == float, "temperature type must be float"
        assert min_val == 0.0, "temperature min must be 0.0 (float)"
        assert max_val == 1.0, "temperature max must be 1.0 (float)"

    def test_temperature_default_is_float(self):
        """Default temperature should be float."""
        temp = DEFAULTS["llm_temperature"]
        assert isinstance(temp, float), "default temperature must be float"


class TestCorruptFileFallback:
    """Test handling of corrupt settings file."""

    def test_corrupt_json_uses_defaults(self, tmp_settings_file):
        """If settings file is corrupt JSON, use defaults."""
        # Write corrupt JSON
        with open(tmp_settings_file, 'w') as f:
            f.write('{"invalid": json here}')

        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            # Should fall back to defaults
            assert settings.get("wake_word") == DEFAULTS["wake_word"]

    def test_missing_file_uses_defaults(self, tmp_settings_file):
        """If settings file doesn't exist, use defaults."""
        # Don't create the file
        os.remove(tmp_settings_file)

        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            # Should use defaults
            assert settings.get("wake_word") == DEFAULTS["wake_word"]
            assert settings.get("llm_temperature") == 0.0

    def test_all_defaults_on_corrupt(self, tmp_settings_file, sample_settings_data):
        """Corrupt file → all values fall back to defaults."""
        with open(tmp_settings_file, 'w') as f:
            f.write('bad json {')

        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            # Check several defaults are in place
            assert settings.get("wake_word") == "alexa"
            assert settings.get("whisper_model") == "base.en"
            assert settings.get("llm_temperature") == 0.0


class TestReload:
    """Test settings reload functionality."""

    def test_reload_from_disk(self, tmp_settings_file, sample_settings_data):
        """Test reloading settings from disk."""
        # Write initial settings
        with open(tmp_settings_file, 'w') as f:
            json.dump(sample_settings_data, f)

        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            assert settings.get("wake_word") == "alexa"

            # Modify settings on disk (simulate external change)
            sample_settings_data["wake_word"] = "custom_word"
            with open(tmp_settings_file, 'w') as f:
                json.dump(sample_settings_data, f)

            # Reload
            settings.reload()
            assert settings.get("wake_word") == "custom_word"

    def test_reset_to_defaults(self, tmp_settings_file, sample_settings_data):
        """Test resetting to factory defaults."""
        with open(tmp_settings_file, 'w') as f:
            json.dump(sample_settings_data, f)

        with patch('config.settings.SETTINGS_FILE', tmp_settings_file):
            settings = _Settings()
            settings.set("wake_word", "custom")
            assert settings.get("wake_word") == "custom"

            # Reset
            settings.reset_to_defaults()
            assert settings.get("wake_word") == DEFAULTS["wake_word"]
