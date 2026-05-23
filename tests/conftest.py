"""
conftest.py — Shared pytest fixtures for Numa tests.

Fixtures provide temporary test resources and cleanup.
"""

import os
import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_settings_file():
    """
    Temporary settings file for testing.
    Returns path, cleans up after test.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        tmp_path = f.name
    yield tmp_path
    # Cleanup
    if os.path.exists(tmp_path):
        os.remove(tmp_path)


@pytest.fixture
def tmp_memory_file():
    """
    Temporary memory file for testing.
    Returns path, cleans up after test.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        tmp_path = f.name
    yield tmp_path
    # Cleanup
    if os.path.exists(tmp_path):
        os.remove(tmp_path)


@pytest.fixture
def tmp_appdata_dir():
    """
    Temporary directory simulating AppData for testing.
    Returns path, cleans up after test.
    """
    tmp_dir = tempfile.mkdtemp()
    yield tmp_dir
    # Cleanup
    if os.path.exists(tmp_dir):
        import shutil
        shutil.rmtree(tmp_dir)


@pytest.fixture
def sample_settings_data():
    """Sample valid settings data for testing."""
    return {
        "wake_word": "alexa",
        "wake_threshold": 0.8,
        "wake_required_hits": 3,
        "wake_cooldown_sec": 3.0,
        "whisper_model": "base.en",
        "stt_language": "en",
        "stt_max_silence_sec": 0.8,
        "stt_max_record_sec": 10,
        "stt_min_audio_sec": 0.4,
        "stt_noise_multiplier": 3.5,
        "calibration_file": "calibration.json",
        "tts_voice": "en-US-BrianNeural",
        "tts_rate": "+5%",
        "tts_pitch": "+0Hz",
        "tts_muted": False,
        "llm_model": "gemini-2.0-flash-lite",
        "llm_temperature": 0.7,
        "llm_context_messages": 6,
        "memory_file": "memory.json",
        "memory_max_history": 20,
        "screenshot_folder": "",
        "shutdown_delay_sec": 5,
        "battery_warn_pct": 15,
        "battery_critical_pct": 30,
        "request_timeout_sec": 6,
        "startup_greeting": "Hello! I am Numa.",
        "log_level": "INFO",
    }


@pytest.fixture
def sample_memory_data():
    """Sample valid memory data for testing."""
    return [
        {
            "role": "user",
            "content": "what's the time",
            "timestamp": "2026-05-23T10:00:00+00:00"
        },
        {
            "role": "assistant",
            "content": "It's 10 o'clock AM",
            "timestamp": "2026-05-23T10:00:00+00:00"
        },
        {
            "role": "user",
            "content": "play music",
            "timestamp": "2026-05-23T10:01:00+00:00"
        },
        {
            "role": "assistant",
            "content": "[task: play_music]",
            "timestamp": "2026-05-23T10:01:00+00:00"
        },
    ]
