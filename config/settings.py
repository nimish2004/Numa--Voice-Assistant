"""
config/settings.py — Runtime settings manager for Numa.

Design decisions:
  - Single source of truth: every tunable value lives here.
    Feature modules never hardcode config values — they call get().
  - Persistent: settings are saved to numa_settings.json in the
    user's app data folder so they survive restarts.
  - Hot-reloadable: reload() re-reads the file without restarting
    Numa — settings window can apply changes instantly.
  - Validated: set() type-checks and range-checks before saving.
    Bad values are rejected with a clear error, never silently accepted.
  - Thread-safe: a RLock protects all reads and writes.

Usage (in any module):
    from config.settings import settings

    model  = settings.get("whisper_model")
    settings.set("tts_voice", "en-GB-SoniaNeural")
    settings.reload()
"""

import json
import logging
import os
import threading
from typing import Any

from config.defaults import DEFAULTS

logger = logging.getLogger(__name__)


# ── Storage location ──────────────────────────────────────────────────────────
# AppData/Roaming/Numa/ on Windows — survives app reinstalls and
# working directory changes. Falls back to project root if AppData
# is unavailable (e.g. running in a restricted environment).

def _settings_path() -> str:
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        folder = os.path.join(appdata, "Numa")
    else:
        folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "numa_settings.json")


SETTINGS_FILE = _settings_path()


# ── Validation schema ─────────────────────────────────────────────────────────
# (type, min, max) — min/max only apply to numeric types.
# None means no range restriction.

_SCHEMA: dict[str, tuple] = {
    "wake_word"             : (str,   None, None),
    "wake_threshold"        : (float, 0.1,  1.0),
    "wake_required_hits"    : (int,   1,    10),
    "wake_cooldown_sec"     : (float, 1.0,  10.0),

    "whisper_model"         : (str,   None, None),
    "stt_language"          : (str,   None, None),
    "stt_max_silence_sec"   : (float, 0.3,  3.0),
    "stt_max_record_sec"    : (int,   5,    30),
    "stt_min_audio_sec"     : (float, 0.1,  2.0),
    "stt_noise_multiplier"  : (float, 1.5,  8.0),
    "calibration_file"      : (str,   None, None),

    "tts_voice"             : (str,   None, None),
    "tts_rate"              : (str,   None, None),
    "tts_pitch"             : (str,   None, None),
    "tts_muted"             : (bool,  None, None),

    "llm_model"             : (str,   None, None),
    "llm_temperature"       : (float, 0.0,  1.0),
    "llm_context_messages"  : (int,   2,    20),

    "memory_file"           : (str,   None, None),
    "memory_max_history"    : (int,   4,    100),

    "screenshot_folder"     : (str,   None, None),
    "shutdown_delay_sec"    : (int,   1,    60),
    "battery_warn_pct"      : (int,   5,    50),
    "battery_critical_pct"  : (int,   10,   80),

    "request_timeout_sec"   : (int,   2,    30),

    "startup_greeting"      : (str,   None, None),
    "log_level"             : (str,   None, None),
}

_VALID_LOG_LEVELS     = {"DEBUG", "INFO", "WARNING"}
_VALID_WHISPER_MODELS = {"tiny.en", "base.en", "small.en", "medium.en", "large"}
_VALID_LLM_MODELS     = {"gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash", "gemini-1.5-flash-8b"}


# ── Settings manager ──────────────────────────────────────────────────────────

class _Settings:
    """
    Internal singleton class. Use the module-level `settings` instance,
    never instantiate this directly.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self):
        """
        Load settings from disk, filling missing keys from DEFAULTS.
        Corrupt or missing file → start from DEFAULTS silently.
        """
        with self._lock:
            loaded = {}
            if os.path.exists(SETTINGS_FILE):
                try:
                    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                except Exception as e:
                    logger.warning(f"Settings file unreadable ({e}) — using defaults.")

            # Merge: loaded values override defaults, missing keys get defaults
            self._data = {**DEFAULTS, **loaded}

            # Remove any keys that no longer exist in schema (stale settings)
            stale = [k for k in self._data if k not in DEFAULTS]
            for k in stale:
                logger.warning(f"Removing stale setting: '{k}'")
                del self._data[k]

    def _save(self):
        """Atomically persist current settings to disk."""
        tmp = SETTINGS_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, SETTINGS_FILE)
        except Exception as e:
            logger.error(f"Could not save settings: {e}")
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate(self, key: str, value: Any) -> tuple[bool, str]:
        """
        Returns (True, "") if valid, (False, reason) if not.
        Coerces int/float where safe (e.g. user passes "3" for an int field).
        """
        if key not in _SCHEMA:
            return False, f"Unknown setting key: '{key}'"

        expected_type, vmin, vmax = _SCHEMA[key]

        # Type coercion for numeric types
        try:
            if expected_type == int and not isinstance(value, bool):
                value = int(value)
            elif expected_type == float and not isinstance(value, bool):
                value = float(value)
            elif expected_type == bool:
                if not isinstance(value, bool):
                    return False, f"'{key}' must be True or False."
        except (ValueError, TypeError):
            return False, f"'{key}' must be of type {expected_type.__name__}."

        if not isinstance(value, expected_type):
            return False, f"'{key}' expects {expected_type.__name__}, got {type(value).__name__}."

        if vmin is not None and value < vmin:
            return False, f"'{key}' minimum is {vmin}, got {value}."
        if vmax is not None and value > vmax:
            return False, f"'{key}' maximum is {vmax}, got {value}."

        # Domain-specific validation
        if key == "log_level" and value not in _VALID_LOG_LEVELS:
            return False, f"log_level must be one of {_VALID_LOG_LEVELS}."
        if key == "whisper_model" and value not in _VALID_WHISPER_MODELS:
            return False, f"whisper_model must be one of {_VALID_WHISPER_MODELS}."
        if key == "battery_critical_pct":
            warn = self._data.get("battery_warn_pct", 15)
            if value <= warn:
                return False, f"battery_critical_pct ({value}) must be > battery_warn_pct ({warn})."

        return True, ""

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, key: str, fallback: Any = None) -> Any:
        """
        Read a setting value.
        Returns fallback if key doesn't exist (should never happen
        in practice since all keys are seeded from DEFAULTS).
        """
        with self._lock:
            return self._data.get(key, fallback)

    def set(self, key: str, value: Any) -> tuple[bool, str]:
        """
        Update a setting value, validate it, and persist to disk.
        Returns (True, "") on success, (False, error_message) on failure.

        Example:
            ok, err = settings.set("tts_voice", "en-GB-SoniaNeural")
            if not ok:
                print(err)
        """
        valid, reason = self._validate(key, value)
        if not valid:
            logger.error(f"Invalid setting — {reason}")
            return False, reason

        with self._lock:
            self._data[key] = value
            self._save()

        logger.info(f"Setting updated: {key} = {value!r}")
        return True, ""

    def reload(self):
        """
        Re-read settings from disk. Called after external edits
        or from the settings UI to apply changes without restart.
        """
        with self._lock:
            self._load()
        logger.info("Settings reloaded.")

    def reset_to_defaults(self):
        """Wipe user settings and restore factory defaults."""
        with self._lock:
            self._data = dict(DEFAULTS)
            self._save()
        logger.info("Settings reset to defaults.")

    def all(self) -> dict:
        """Return a copy of all current settings (for UI display / debug)."""
        with self._lock:
            return dict(self._data)

    def get_settings_file_path(self) -> str:
        """Return the path to the settings JSON file."""
        return SETTINGS_FILE


# ── Module-level singleton ────────────────────────────────────────────────────
# Import this everywhere: from config.settings import settings

settings = _Settings()