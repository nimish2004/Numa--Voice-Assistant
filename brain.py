"""
brain.py - Rule-based intent engine (Layer 2 fallback for Numa).

Called only when Gemini is unavailable (quota, network, no API key).
Works 100% offline with zero external dependencies.

Design rules:
  - _fuzzy_has(text, *words)  : ALL words must fuzzy-match somewhere in text
  - _fuzzy_any(text, *words)  : ANY word must fuzzy-match somewhere in text
  - Natural speech inserts fillers ("the", "can you", "please") between
    keywords - we match keywords not exact phrases.
  - Parameterised intents (set_volume, set_timer) use regex to extract
    the numeric value from the spoken text so they work offline too.
  - More specific rules come first to avoid false matches.
    e.g. "close spotify" must match close_app before "spotify" alone
    would match open_spotify.
  - Fuzzy matching handles Whisper typos: "Spoofy" → Spotify, "volumme" → volume
"""

import re
from rapidfuzz import fuzz

# ── Fuzzy matching thresholds ──────────────────────────────────────────────────
# Raise to reduce false positives; lower to catch more typos.
FUZZY_THRESHOLD = 80  # standard: media, volume, apps, timers, web
DESTRUCTIVE_THRESHOLD = 92  # exit, lock, shutdown, restart, sleep

# ── Helpers ───────────────────────────────────────────────────────────────────

def _fuzzy_word_match(keyword: str, text: str, threshold: int) -> bool:
    """
    Core fuzzy matcher. Strategy depends on keyword type:
      - Single word: compare against each token in text using fuzz.ratio
        (avoids partial_ratio substring false positives on short words)
      - Multi-word phrase: use fuzz.partial_ratio on the full text
        (finds the phrase as a contiguous chunk within the sentence)
    """
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    if " " in keyword_lower:
        # Multi-word: sliding window search in full text
        return fuzz.partial_ratio(keyword_lower, text_lower) >= threshold
    # Single word: token-level comparison
    return any(
        fuzz.ratio(keyword_lower, token) >= threshold
        for token in text_lower.split()
    )


def _fuzzy_has(text: str, *words: str, threshold: int = FUZZY_THRESHOLD) -> bool:
    """All keywords must fuzzy-match somewhere in text (order-independent)."""
    return all(_fuzzy_word_match(w, text, threshold) for w in words)


def _fuzzy_any(text: str, *words: str, threshold: int = FUZZY_THRESHOLD) -> bool:
    """At least one keyword must fuzzy-match somewhere in text."""
    return any(_fuzzy_word_match(w, text, threshold) for w in words)


def _has(text: str, *words: str) -> bool:
    """Exact substring matching - kept for highly distinctive words only."""
    return all(w in text for w in words)


def _any(text: str, *words: str) -> bool:
    """Exact substring matching - kept for highly distinctive words only."""
    return any(w in text for w in words)


def _extract_number(text: str) -> int | None:
    """
    Pull the first integer from text.
    Handles: "set volume to 80", "80%", "eighty" (word form not handled -
    users saying "eighty percent" should use Gemini; rule engine handles digits).
    Returns None if no number found.
    """
    match = re.search(r'\b(\d+)\b', text)
    if match:
        return int(match.group(1))
    return None


def _extract_app_name(text: str) -> str | None:
    """
    Extract app name from "open [app]" pattern.
    Examples: "open docker" → "docker", "open the door" → "door"
    Returns the first word after "open" (ignoring "the", "a").
    """
    words = text.lower().split()
    try:
        open_idx = words.index("open")
        # Look for the next word after "open" that isn't a filler
        for i in range(open_idx + 1, len(words)):
            word = words[i].strip('.,?!')
            if word and word not in ("the", "a", "an", "please", "could", "can", "you"):
                return word
    except (ValueError, IndexError):
        pass
    return None


# ── Intent resolver ───────────────────────────────────────────────────────────

def get_intent(text: str) -> str | dict:
    """
    Map natural language text to an intent string OR a full result dict
    (for parameterised intents like set_volume that need extracted values).

    Returns:
      - str  "intent_name"  for simple intents
      - dict {"type": "task", "intent": ..., "parameters": {...}}
             for intents that carry extracted parameters
      - str  "unknown"  if no rule matched
    """
    text = text.lower().strip()

    # ── EXIT (highest priority) ───────────────────────────────────────────────
    if _fuzzy_any(text, "exit", "quit", "goodbye", "bye bye", threshold=DESTRUCTIVE_THRESHOLD) and not _fuzzy_any(text, "app", "program"):
        return "exit"

    # ── MEDIA ─────────────────────────────────────────────────────────────────
    if _fuzzy_has(text, "play") and _fuzzy_any(text, "music", "song", "track", "spotify"):
        return "play_music"

    if _fuzzy_any(text, "pause", "resume") and _fuzzy_any(text, "music", "song", "track"):
        return "pause_music"

    if _fuzzy_has(text, "stop") and _fuzzy_any(text, "music", "song", "playing"):
        return "pause_music"

    if _fuzzy_any(text, "next") and _fuzzy_any(text, "song", "track", "music"):
        return "next_track"

    if _fuzzy_any(text, "previous", "prev", "last") and _fuzzy_any(text, "song", "track", "music"):
        return "prev_track"

    # ── CLOSE APP (before open rules) ────────────────────────────────────────
    if _fuzzy_any(text, "close", "quit", "kill", "shut") and _fuzzy_has(text, "chrome"):
        return {"type": "task", "intent": "close_app", "parameters": {"app": "chrome"}}

    if _fuzzy_any(text, "close", "quit", "kill", "shut") and _fuzzy_has(text, "spotify"):
        return {"type": "task", "intent": "close_app", "parameters": {"app": "spotify"}}

    if _fuzzy_any(text, "close", "quit", "kill", "shut") and _fuzzy_has(text, "notepad"):
        return {"type": "task", "intent": "close_app", "parameters": {"app": "notepad"}}

    if _fuzzy_any(text, "close", "quit", "kill") and _fuzzy_any(text, "vscode", "vs code", "code"):
        return {"type": "task", "intent": "close_app", "parameters": {"app": "vscode"}}

    if _fuzzy_any(text, "close", "quit", "kill", "shut") and _fuzzy_has(text, "youtube"):
        return {"type": "task", "intent": "close_app", "parameters": {"app": "youtube"}}

    if _fuzzy_any(text, "close", "quit", "kill") and _fuzzy_any(text, "discord", "zoom", "teams", "whatsapp"):
        for app in ["discord", "zoom", "teams", "whatsapp"]:
            if app in text:
                return {"type": "task", "intent": "close_app", "parameters": {"app": app}}

    if _fuzzy_any(text, "close", "quit", "kill") and _fuzzy_any(text, "app", "window", "program"):
        return "close_app"

    # ── OPEN APP ──────────────────────────────────────────────────────────────
    if _fuzzy_has(text, "chrome") or (_fuzzy_has(text, "open") and _fuzzy_has(text, "browser")):
        return "open_chrome"

    if _fuzzy_has(text, "spotify"):
        return "open_spotify"

    if _fuzzy_any(text, "vscode", "vs code") or (_fuzzy_has(text, "open") and _fuzzy_has(text, "code")):
        return "open_vscode"

    if _fuzzy_has(text, "notepad"):
        return "open_notepad"

    if _fuzzy_has(text, "youtube"):
        return "open_youtube"

    if _fuzzy_any(text, "terminal", "command prompt", "cmd") and _fuzzy_has(text, "open"):
        return "open_terminal"

    if _fuzzy_has(text, "open"):
        app_name = _extract_app_name(text)
        if app_name:
            return {"type": "task", "intent": "open_app", "parameters": {"app": app_name}}

    if _fuzzy_any(text, "refresh apps", "update apps", "rescan apps", "scan apps"):
        return "refresh_app_cache"

    # ── VOLUME — parameterised (must come before up/down rules) ───────────────
    # "set volume to 80", "volume at 50%", "set it to 60 percent"
    if _fuzzy_any(text, "set volume", "volume to", "volume at") or (
        _fuzzy_has(text, "set") and _fuzzy_has(text, "volume")
    ):
        n = _extract_number(text)
        if n is not None:
            n = max(0, min(100, n))   # clamp to valid range
            return {
                "type"      : "task",
                "intent"    : "set_volume",
                "parameters": {"value": n},
            }
        # "set volume" said but no number heard - ask for clarification
        return "volume_up"   # safe fallback

    # "increase the volume", "turn up volume", "louder", "volume up"
    if _fuzzy_any(text, "louder", "volume up"):
        return "volume_up"

    if _fuzzy_has(text, "increase") and _fuzzy_has(text, "volume"):
        return "volume_up"

    if _fuzzy_has(text, "turn") and _fuzzy_has(text, "up") and _fuzzy_has(text, "volume"):
        return "volume_up"

    if _fuzzy_has(text, "raise") and _fuzzy_has(text, "volume"):
        return "volume_up"

    # "decrease the volume", "turn down volume", "quieter", "lower"
    if _fuzzy_any(text, "quieter", "volume down"):
        return "volume_down"

    if _fuzzy_has(text, "decrease") and _fuzzy_has(text, "volume"):
        return "volume_down"

    if _fuzzy_has(text, "turn") and _fuzzy_has(text, "down") and _fuzzy_has(text, "volume"):
        return "volume_down"

    if _fuzzy_has(text, "lower") and _fuzzy_has(text, "volume"):
        return "volume_down"

    if _fuzzy_has(text, "reduce") and _fuzzy_has(text, "volume"):
        return "volume_down"

    # "mute", "silence", "be quiet"
    if _fuzzy_any(text, "mute", "silence") and not _fuzzy_any(text, "yourself", "numa"):
        return "mute"

    # ── SYSTEM POWER ──────────────────────────────────────────────────────────
    if _fuzzy_has(text, "cancel") and _fuzzy_has(text, "shutdown", threshold=DESTRUCTIVE_THRESHOLD):
        return "cancel_shutdown"

    if _fuzzy_has(text, "lock") and _fuzzy_any(text, "laptop", "screen", "computer", "pc"):
        return "lock_laptop"

    if _fuzzy_has(text, "lock"):
        return "lock_laptop"

    if (_fuzzy_has(text, "shut") and _fuzzy_has(text, "down")) or _fuzzy_has(text, "shutdown", threshold=DESTRUCTIVE_THRESHOLD):
        return "shutdown"

    if _fuzzy_has(text, "power off") or (_fuzzy_has(text, "turn") and _fuzzy_has(text, "off") and _fuzzy_any(text, "laptop", "computer", "pc")):
        return "shutdown"

    if _fuzzy_has(text, "restart", threshold=DESTRUCTIVE_THRESHOLD) or _fuzzy_has(text, "reboot", threshold=DESTRUCTIVE_THRESHOLD):
        return "restart"

    if _fuzzy_has(text, "sleep", threshold=DESTRUCTIVE_THRESHOLD) and _fuzzy_any(text, "laptop", "computer", "pc", "put"):
        return "sleep"

    # ── SCREENSHOT ────────────────────────────────────────────────────────────
    if _fuzzy_any(text, "screenshot", "screen shot", "capture screen", "snap screen"):
        return "take_screenshot"

    # ── TIMER (parameterised) ─────────────────────────────────────────────────
    if _fuzzy_has(text, "cancel") and _fuzzy_has(text, "timer"):
        return "cancel_timer"

    if _fuzzy_any(text, "timer", "set a timer", "countdown"):
        n = _extract_number(text)
        if n is not None:
            # Detect unit: minutes (default), seconds, hours
            if _fuzzy_any(text, "second", "sec", "secs"):
                seconds = n
            elif _fuzzy_any(text, "hour", "hr", "hrs"):
                seconds = n * 3600
            else:
                seconds = n * 60   # default: minutes
            return {
                "type"      : "task",
                "intent"    : "set_timer",
                "parameters": {"duration_seconds": seconds, "label": "Timer"},
            }
        return "set_timer"   # Gemini will handle the number extraction

    # ── REMINDER ─────────────────────────────────────────────────────────────
    if _fuzzy_any(text, "remind", "reminder"):
        return "set_reminder"

    # ── SYSTEM INFO ───────────────────────────────────────────────────────────
    if _fuzzy_any(text, "battery", "charge", "charging"):
        return "battery_status"

    if _fuzzy_any(text, "cpu", "processor", "ram", "memory usage"):
        return "cpu_status"

    if _fuzzy_has(text, "time") and not _fuzzy_any(text, "timer", "remind", "what time"):
        return "tell_time"

    if "what time" in text or ("tell" in text and "time" in text) or "current time" in text:
        return "tell_time"

    if _fuzzy_any(text, "date", "today", "what day"):
        return "tell_date"

    # ── WEB ───────────────────────────────────────────────────────────────────
    if _fuzzy_any(text, "weather", "temperature", "forecast"):
        return "get_weather"

    if _fuzzy_any(text, "search", "google", "look up", "find online", "browse for"):
        return "web_search"

    # ── CLIPBOARD ─────────────────────────────────────────────────────────────
    if _fuzzy_has(text, "clipboard"):
        return "read_clipboard"

    # ── DEV ───────────────────────────────────────────────────────────────────
    if _fuzzy_has(text, "git") and _fuzzy_has(text, "status"):
        return "git_status"

    if _fuzzy_has(text, "terminal") or _fuzzy_has(text, "command prompt"):
        return "open_terminal"

    # ── MEMORY ────────────────────────────────────────────────────────────────
    if _fuzzy_any(text, "forget", "clear memory", "wipe memory", "reset memory"):
        return "clear_memory"

    # ── ASSISTANT CONTROL ─────────────────────────────────────────────────────
    if _fuzzy_has(text, "mute") and _fuzzy_any(text, "yourself", "numa", "voice"):
        return "toggle_mute_numa"

    if _fuzzy_has(text, "recalibrate") or (_fuzzy_has(text, "calibrate") and _fuzzy_has(text, "mic")):
        return "recalibrate_mic"

    # ── FALLBACK ──────────────────────────────────────────────────────────────
    return "unknown"