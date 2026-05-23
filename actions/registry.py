"""
actions/registry.py — Intent registry and dispatcher for Numa.

This is the ONLY file that imports from all action modules.
Every other part of the system calls handle_intent(data) and
never needs to know which module implements it.

Adding a new intent = two steps:
  1. Write the function in the appropriate actions/ module.
  2. Add one line to INTENT_MAP below.
  That's it. No other file needs to change.
"""

import logging
import state
from tts import speak
from memory import clear_memory

logger = logging.getLogger(__name__)

from actions.media        import play_music, pause_music, next_track, prev_track
from actions.apps         import (
    open_chrome, open_spotify, open_vscode, open_notepad,
    open_youtube, open_terminal, open_app, close_app,
)
from actions.system       import (
    mute, volume_up, volume_down, set_volume,
    take_screenshot, lock_laptop, shutdown, restart, sleep,
    cancel_shutdown, tell_time, tell_date, battery_status, cpu_status,
)
from actions.web          import web_search, get_weather
from actions.productivity import (
    set_timer, cancel_timer,
    set_reminder,
    read_clipboard, clear_clipboard,
    git_status,
)


# ── Special actions (defined inline — too small to deserve their own file) ────

def _forget_everything(data: dict):
    clear_memory()
    speak("Done. I've cleared my memory.")


def _exit_app(data: dict):
    speak("Goodbye.")
    state.stop()
    # Tell Qt to shut down — without this the tray and UI keep running
    # even after the wake engine stops. quit_requested is connected to
    # app.quit() in main.py which cleanly exits the Qt event loop.
    from app.signals import numa_signals
    numa_signals.quit_requested.emit()


def _toggle_mute(data: dict):
    muted = state.toggle_mute()
    if muted:
        logger.info("Numa muted.")     # can't speak when muted — log only
    else:
        speak("I'm back.")


def _recalibrate_mic(data: dict):
    speak("Recalibrating microphone. Please stay silent for a moment.")
    from speech import recalibrate
    recalibrate()
    speak("Microphone calibrated.")


# ── Intent map ────────────────────────────────────────────────────────────────
#
# Key   = exact intent string the LLM returns (must match system prompt)
# Value = callable(data: dict) → None

INTENT_MAP: dict[str, callable] = {
    # ── Media ─────────────────────────────────────────────────────────────
    "play_music"        : play_music,
    "pause_music"       : pause_music,
    "next_track"        : next_track,
    "prev_track"        : prev_track,

    # ── Apps ──────────────────────────────────────────────────────────────
    "open_chrome"       : open_chrome,
    "open_spotify"      : open_spotify,
    "open_vscode"       : open_vscode,
    "open_notepad"      : open_notepad,
    "open_youtube"      : open_youtube,
    "open_terminal"     : open_terminal,
    "open_app"          : open_app,
    "close_app"         : close_app,

    # ── System ────────────────────────────────────────────────────────────
    "lock_laptop"       : lock_laptop,
    "shutdown"          : shutdown,
    "restart"           : restart,
    "sleep"             : sleep,
    "cancel_shutdown"   : cancel_shutdown,
    "mute"              : mute,
    "volume_up"         : volume_up,
    "volume_down"       : volume_down,
    "set_volume"        : set_volume,
    "take_screenshot"   : take_screenshot,
    "cpu_status"        : cpu_status,

    # ── Info ──────────────────────────────────────────────────────────────
    "tell_time"         : tell_time,
    "tell_date"         : tell_date,
    "battery_status"    : battery_status,

    # ── Web ───────────────────────────────────────────────────────────────
    "web_search"        : web_search,
    "get_weather"       : get_weather,

    # ── Productivity ──────────────────────────────────────────────────────
    "set_timer"         : set_timer,
    "cancel_timer"      : cancel_timer,
    "set_reminder"      : set_reminder,
    "read_clipboard"    : read_clipboard,
    "clear_clipboard"   : clear_clipboard,
    "git_status"        : git_status,

    # ── Assistant control ─────────────────────────────────────────────────
    "toggle_mute_numa"  : _toggle_mute,
    "recalibrate_mic"   : _recalibrate_mic,
    "clear_memory"      : _forget_everything,
    "exit"              : _exit_app,
}


# ── Dispatcher ────────────────────────────────────────────────────────────────

def handle_intent(data: dict):
    """
    Route an intent dict to the correct action function.

    data must contain at minimum: {"intent": "intent_name"}
    Additional keys (parameters, etc.) are passed through to the action.

    Unknown intents are logged and spoken — never silently swallowed.
    """
    intent = data.get("intent", "").strip()

    if not intent:
        print("⚠️  handle_intent called with no intent key.")
        speak("I didn't get a clear instruction. Please try again.")
        return

    action = INTENT_MAP.get(intent)

    if action:
        try:
            action(data)
        except Exception as e:
            print(f"❌  Action '{intent}' raised an error: {e}")
            speak("Something went wrong while doing that. Please try again.")
    else:
        print(f"⚠️  Unknown intent: '{intent}'")
        speak("I don't know how to do that yet.")