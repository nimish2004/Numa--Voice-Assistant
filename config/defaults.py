"""
config/defaults.py — Factory default values for Numa.

Rules:
  - This file is NEVER imported directly by feature modules.
  - Only settings.py reads from here (to populate missing keys).
  - Values here are the safe, conservative baseline that works on
    any machine out of the box.
  - Every key here must have a corresponding entry in settings.py's
    schema with the same name.
"""

DEFAULTS: dict = {

    # ── Wake word ─────────────────────────────────────────────────────────────
    "wake_word"             : "alexa",
    "wake_threshold"        : 0.8,      # 0.0–1.0 confidence required
    "wake_required_hits"    : 3,        # consecutive frames above threshold
    "wake_cooldown_sec"     : 3.0,      # seconds between triggers

    # ── Speech (STT) ─────────────────────────────────────────────────────────
    "whisper_model"         : "base.en",  # tiny.en | base.en | small.en
    "stt_language"          : "en",
    "stt_max_silence_sec"   : 0.8,
    "stt_max_record_sec"    : 10,
    "stt_min_audio_sec"     : 0.4,
    "stt_noise_multiplier"  : 3.5,
    "calibration_file"      : "calibration.json",

    # ── TTS ───────────────────────────────────────────────────────────────────
    "tts_voice"             : "en-US-BrianNeural",
    "tts_rate"              : "+5%",
    "tts_pitch"             : "+0Hz",
    "tts_muted"             : False,

    # ── LLM ───────────────────────────────────────────────────────────────────
    "llm_model"             : "gemini-2.0-flash-lite",
    "llm_temperature"       : 0.0,
    "llm_context_messages"  : 6,        # recent messages sent to LLM

    # ── Memory ────────────────────────────────────────────────────────────────
    "memory_file"           : "memory.json",
    "memory_max_history"    : 20,

    # ── System actions ────────────────────────────────────────────────────────
    "screenshot_folder"     : "",       # "" = ~/Pictures/Numa/Screenshots/
    "shutdown_delay_sec"    : 5,
    "battery_warn_pct"      : 15,       # speak warning below this %
    "battery_critical_pct"  : 30,       # "consider charging" below this %

    # ── Network ───────────────────────────────────────────────────────────────
    "request_timeout_sec"   : 6,

    # ── App ───────────────────────────────────────────────────────────────────
    "startup_greeting"      : "Hello! I am Numa, your personal voice assistant. Say Numa to wake me up.",
    "log_level"             : "INFO",   # DEBUG | INFO | WARNING
}