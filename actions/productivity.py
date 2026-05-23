"""
actions/productivity.py — Productivity features for Numa.

New capabilities in this module:
  - set_timer     : "set a timer for 5 minutes" — threading.Timer based,
                    multiple concurrent timers supported, each named.
  - set_reminder  : "remind me to call John at 3pm" — polls every 30s,
                    fires speak() when the target time is reached.
  - read_clipboard: "what's on my clipboard" — reads aloud.
  - write_clipboard: "copy that" — writes LLM response to clipboard.
  - git_status    : moved here from actions.py — now speaks a summary
                    instead of just printing raw output.

All timers and reminders survive for the session only (in-memory).
A future premium feature can persist them across reboots via Supabase.
"""

import logging
import subprocess
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

import pyperclip
from tts import speak

logger = logging.getLogger(__name__)


# ── Timer ─────────────────────────────────────────────────────────────────────

# Active timers: name → threading.Timer
_active_timers: dict[str, threading.Timer] = {}
_timers_lock = threading.Lock()


def _timer_fired(label: str):
    """Callback when a timer expires."""
    with _timers_lock:
        _active_timers.pop(label, None)
    speak(f"Timer done! {label}")
    logger.info(f"Timer fired: {label}")


def set_timer(data: dict):
    """
    Set a countdown timer.
    LLM should extract: {"duration_seconds": 300, "label": "pasta"}
    Spoken form: "set a timer for 5 minutes" / "5 minute pasta timer"
    """
    params   = data.get("parameters", {})
    seconds  = int(params.get("duration_seconds", 0))
    label    = params.get("label", "Timer").strip().title()

    if seconds <= 0:
        speak("Please tell me how long the timer should be.")
        return

    # Cancel existing timer with same label
    with _timers_lock:
        if label in _active_timers:
            _active_timers[label].cancel()

        t = threading.Timer(seconds, _timer_fired, args=[label])
        t.daemon = True
        t.name   = f"Timer-{label}"
        _active_timers[label] = t
        t.start()

    # Human-readable duration
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        duration_str = f"{h} hour{'s' if h > 1 else ''}"
        if m:
            duration_str += f" {m} minute{'s' if m > 1 else ''}"
    elif seconds >= 60:
        m = seconds // 60
        s = seconds % 60
        duration_str = f"{m} minute{'s' if m > 1 else ''}"
        if s:
            duration_str += f" {s} second{'s' if s > 1 else ''}"
    else:
        duration_str = f"{seconds} second{'s' if seconds > 1 else ''}"

    speak(f"{label} timer set for {duration_str}.")
    logger.info(f"Timer set: '{label}' → {seconds}s")


def cancel_timer(data: dict):
    """Cancel a named timer. If no label given, cancel all."""
    params = data.get("parameters", {})
    label  = params.get("label", "").strip().title()

    with _timers_lock:
        if label and label in _active_timers:
            _active_timers[label].cancel()
            del _active_timers[label]
            speak(f"{label} timer cancelled.")
        elif not label:
            for t in _active_timers.values():
                t.cancel()
            _active_timers.clear()
            speak("All timers cancelled.")
        else:
            speak(f"I don't have a timer called {label}.")


# ── Reminder ──────────────────────────────────────────────────────────────────

# Active reminders: list of {"time": datetime, "message": str}
_reminders: list[dict] = []
_reminders_lock = threading.Lock()
_reminder_thread_started = False
_reminder_start_lock = threading.Lock()


def _reminder_loop():
    """Background thread — checks reminders every 30 seconds."""
    while True:
        now = datetime.now()
        fired = []

        with _reminders_lock:
            for r in _reminders:
                if now >= r["time"]:
                    fired.append(r)
            for r in fired:
                _reminders.remove(r)

        for r in fired:
            speak(f"Reminder: {r['message']}")
            logger.info(f"Reminder fired: {r['message']}")

        time.sleep(30)


def _ensure_reminder_thread():
    global _reminder_thread_started
    with _reminder_start_lock:
        if not _reminder_thread_started:
            t = threading.Thread(target=_reminder_loop, name="ReminderLoop", daemon=True)
            t.start()
            _reminder_thread_started = True


def set_reminder(data: dict):
    """
    Set a one-shot reminder.
    LLM should extract:
      {"message": "call John", "time_iso": "2024-01-15T15:00:00"}
    or
      {"message": "call John", "minutes_from_now": 30}
    """
    _ensure_reminder_thread()
    params  = data.get("parameters", {})
    message = params.get("message", "").strip()

    if not message:
        speak("What should I remind you about?")
        return

    # Resolve target time
    target: Optional[datetime] = None

    if "time_iso" in params:
        try:
            target = datetime.fromisoformat(params["time_iso"])
        except ValueError:
            pass

    if target is None and "minutes_from_now" in params:
        try:
            mins   = int(params["minutes_from_now"])
            target = datetime.now() + timedelta(minutes=mins)
        except (ValueError, TypeError):
            pass

    if target is None:
        speak("I couldn't figure out when to remind you. Please try again.")
        return

    if target <= datetime.now():
        speak("That time has already passed.")
        return

    with _reminders_lock:
        _reminders.append({"time": target, "message": message})

    time_str = target.strftime("%I:%M %p")
    speak(f"I'll remind you to {message} at {time_str}.")
    logger.info(f"Reminder set: '{message}' at {target}")


# ── Clipboard ─────────────────────────────────────────────────────────────────

def read_clipboard(data: dict):
    """Read the current clipboard contents aloud."""
    try:
        content = pyperclip.paste()
        if not content or not content.strip():
            speak("Your clipboard is empty.")
            return

        # Truncate very long clipboard content
        if len(content) > 300:
            speak(f"Your clipboard has a lot of text. Here's the start: {content[:200]}...")
        else:
            speak(f"Your clipboard contains: {content.strip()}")

    except Exception as e:
        logger.error(f"Clipboard read error: {e}")
        speak("I couldn't read your clipboard.")


def clear_clipboard(data: dict):
    """Clear the clipboard."""
    try:
        pyperclip.copy("")
        speak("Clipboard cleared.")
    except Exception as e:
        logger.error(f"Clipboard clear error: {e}")
        speak("I couldn't clear the clipboard.")


# ── Git ───────────────────────────────────────────────────────────────────────

def git_status(data: dict):
    """
    Run git status in the current directory and speak a human summary.
    Old version just printed raw output — useless for a voice assistant.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            shell=False,
            timeout=5,
        )

        if result.returncode != 0:
            speak("This doesn't appear to be a git repository.")
            return

        output = result.stdout.strip()

        if not output:
            speak("Your working directory is clean. Nothing to commit.")
            return

        lines    = output.splitlines()
        modified = sum(1 for l in lines if l.startswith(" M") or l.startswith("M"))
        untracked= sum(1 for l in lines if l.startswith("??"))
        staged   = sum(1 for l in lines if l.startswith("A") or l.startswith("M "))

        parts = []
        if staged:
            parts.append(f"{staged} file{'s' if staged > 1 else ''} staged")
        if modified:
            parts.append(f"{modified} file{'s' if modified > 1 else ''} modified")
        if untracked:
            parts.append(f"{untracked} untracked file{'s' if untracked > 1 else ''}")

        summary = ", ".join(parts) if parts else f"{len(lines)} changes"
        speak(f"Git status: {summary}.")
        logger.debug(result.stdout)

    except subprocess.TimeoutExpired:
        speak("Git took too long to respond.")
    except FileNotFoundError:
        speak("Git is not installed or not in your system path.")
    except Exception as e:
        logger.error(f"Git error: {e}")
        speak("I couldn't run git status.")
