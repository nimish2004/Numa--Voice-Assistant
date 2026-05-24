"""
brain.py - Rule-based intent engine (Layer 2 fallback for Numa).

Called only when Gemini is unavailable (quota, network, no API key).
Works 100% offline with zero external dependencies.

Design rules:
  - _has(text, *words)  : ALL words must appear anywhere in text
  - _any(text, *words)  : ANY word must appear in text
  - Natural speech inserts fillers ("the", "can you", "please") between
    keywords - we match keywords not exact phrases.
  - Parameterised intents (set_volume, set_timer) use regex to extract
    the numeric value from the spoken text so they work offline too.
  - More specific rules come first to avoid false matches.
    e.g. "close spotify" must match close_app before "spotify" alone
    would match open_spotify.
"""

import re


# ── Helpers ───────────────────────────────────────────────────────────────────

def _has(text: str, *words: str) -> bool:
    """All words must appear in text (order-independent, filler-tolerant)."""
    return all(w in text for w in words)


def _any(text: str, *words: str) -> bool:
    """At least one word must appear in text."""
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
    if _any(text, "exit", "quit", "goodbye", "bye bye") and not _any(text, "app", "program"):
        return "exit"

    # ── MEDIA ─────────────────────────────────────────────────────────────────
    if _has(text, "play") and _any(text, "music", "song", "track", "spotify"):
        return "play_music"

    if _any(text, "pause", "resume") and _any(text, "music", "song", "track"):
        return "pause_music"

    if _has(text, "stop") and _any(text, "music", "song", "playing"):
        return "pause_music"

    if _any(text, "next") and _any(text, "song", "track", "music"):
        return "next_track"

    if _any(text, "previous", "prev", "last") and _any(text, "song", "track", "music"):
        return "prev_track"

    # ── CLOSE APP (before open rules) ────────────────────────────────────────
    if _any(text, "close", "quit", "kill", "shut") and _has(text, "chrome"):
        return {"type": "task", "intent": "close_app", "parameters": {"app": "chrome"}}

    if _any(text, "close", "quit", "kill", "shut") and _has(text, "spotify"):
        return {"type": "task", "intent": "close_app", "parameters": {"app": "spotify"}}

    if _any(text, "close", "quit", "kill", "shut") and _has(text, "notepad"):
        return {"type": "task", "intent": "close_app", "parameters": {"app": "notepad"}}

    if _any(text, "close", "quit", "kill") and _any(text, "vscode", "vs code", "code"):
        return {"type": "task", "intent": "close_app", "parameters": {"app": "vscode"}}

    if _any(text, "close", "quit", "kill", "shut") and _has(text, "youtube"):
        return {"type": "task", "intent": "close_app", "parameters": {"app": "youtube"}}

    if _any(text, "close", "quit", "kill") and _any(text, "discord", "zoom", "teams", "whatsapp"):
        for app in ["discord", "zoom", "teams", "whatsapp"]:
            if app in text:
                return {"type": "task", "intent": "close_app", "parameters": {"app": app}}

    if _any(text, "close", "quit", "kill") and _any(text, "app", "window", "program"):
        return "close_app"

    # ── OPEN APP ──────────────────────────────────────────────────────────────
    if _has(text, "chrome") or (_has(text, "open") and _has(text, "browser")):
        return "open_chrome"

    if _has(text, "spotify"):
        return "open_spotify"

    if _any(text, "vscode", "vs code") or (_has(text, "open") and _has(text, "code")):
        return "open_vscode"

    if _has(text, "notepad"):
        return "open_notepad"

    if _has(text, "youtube"):
        return "open_youtube"

    if _any(text, "terminal", "command prompt", "cmd") and _has(text, "open"):
        return "open_terminal"

    if _has(text, "open"):
        app_name = _extract_app_name(text)
        if app_name:
            return {"type": "task", "intent": "open_app", "parameters": {"app": app_name}}

    if _any(text, "refresh apps", "update apps", "rescan apps", "scan apps"):
        return "refresh_app_cache"

    # ── VOLUME — parameterised (must come before up/down rules) ───────────────
    # "set volume to 80", "volume at 50%", "set it to 60 percent"
    if _any(text, "set volume", "volume to", "volume at") or (
        _has(text, "set") and _has(text, "volume")
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
    if _any(text, "louder", "volume up"):
        return "volume_up"

    if _has(text, "increase") and _has(text, "volume"):
        return "volume_up"

    if _has(text, "turn") and _has(text, "up") and _has(text, "volume"):
        return "volume_up"

    if _has(text, "raise") and _has(text, "volume"):
        return "volume_up"

    # "decrease the volume", "turn down volume", "quieter", "lower"
    if _any(text, "quieter", "volume down"):
        return "volume_down"

    if _has(text, "decrease") and _has(text, "volume"):
        return "volume_down"

    if _has(text, "turn") and _has(text, "down") and _has(text, "volume"):
        return "volume_down"

    if _has(text, "lower") and _has(text, "volume"):
        return "volume_down"

    if _has(text, "reduce") and _has(text, "volume"):
        return "volume_down"

    # "mute", "silence", "be quiet"
    if _any(text, "mute", "silence") and not _any(text, "yourself", "numa"):
        return "mute"

    # ── SYSTEM POWER ──────────────────────────────────────────────────────────
    if _has(text, "cancel") and _has(text, "shutdown"):
        return "cancel_shutdown"

    if _has(text, "lock") and _any(text, "laptop", "screen", "computer", "pc"):
        return "lock_laptop"

    if _has(text, "lock"):
        return "lock_laptop"

    if (_has(text, "shut") and _has(text, "down")) or _has(text, "shutdown"):
        return "shutdown"

    if _has(text, "power off") or (_has(text, "turn") and _has(text, "off") and _any(text, "laptop", "computer", "pc")):
        return "shutdown"

    if _has(text, "restart") or _has(text, "reboot"):
        return "restart"

    if _has(text, "sleep") and _any(text, "laptop", "computer", "pc", "put"):
        return "sleep"

    # ── SCREENSHOT ────────────────────────────────────────────────────────────
    if _any(text, "screenshot", "screen shot", "capture screen", "snap screen"):
        return "take_screenshot"

    # ── TIMER (parameterised) ─────────────────────────────────────────────────
    if _has(text, "cancel") and _has(text, "timer"):
        return "cancel_timer"

    if _any(text, "timer", "set a timer", "countdown"):
        n = _extract_number(text)
        if n is not None:
            # Detect unit: minutes (default), seconds, hours
            if _any(text, "second", "sec", "secs"):
                seconds = n
            elif _any(text, "hour", "hr", "hrs"):
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
    if _any(text, "remind", "reminder"):
        return "set_reminder"

    # ── SYSTEM INFO ───────────────────────────────────────────────────────────
    if _any(text, "battery", "charge", "charging"):
        return "battery_status"

    if _any(text, "cpu", "processor", "ram", "memory usage"):
        return "cpu_status"

    if _has(text, "time") and not _any(text, "timer", "remind", "what time"):
        return "tell_time"

    if "what time" in text or ("tell" in text and "time" in text) or "current time" in text:
        return "tell_time"

    if _any(text, "date", "today", "what day"):
        return "tell_date"

    # ── WEB ───────────────────────────────────────────────────────────────────
    if _any(text, "weather", "temperature", "forecast"):
        return "get_weather"

    if _any(text, "search", "google", "look up", "find online", "browse for"):
        return "web_search"

    # ── CLIPBOARD ─────────────────────────────────────────────────────────────
    if _has(text, "clipboard"):
        return "read_clipboard"

    # ── DEV ───────────────────────────────────────────────────────────────────
    if _has(text, "git") and _has(text, "status"):
        return "git_status"

    if _has(text, "terminal") or _has(text, "command prompt"):
        return "open_terminal"

    # ── MEMORY ────────────────────────────────────────────────────────────────
    if _any(text, "forget", "clear memory", "wipe memory", "reset memory"):
        return "clear_memory"

    # ── ASSISTANT CONTROL ─────────────────────────────────────────────────────
    if _has(text, "mute") and _any(text, "yourself", "numa", "voice"):
        return "toggle_mute_numa"

    if _has(text, "recalibrate") or (_has(text, "calibrate") and _has(text, "mic")):
        return "recalibrate_mic"

    # ── FALLBACK ──────────────────────────────────────────────────────────────
    return "unknown"