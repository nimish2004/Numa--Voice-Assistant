"""
state.py — Global application state manager for Numa.

Every module that needs to read or change app state imports this module
directly (import state) and uses the functions below. Nobody should ever
import a bare value like `from state import RUNNING` because Python copies
primitives on import — changes made later won't be seen by the importer.
"""

import threading

# ── Internal state ────────────────────────────────────────────────────────────

_state = {
    "running": True,        # Main event loop alive?
    "processing": False,    # Currently handling a wake event?
    "muted": False,         # TTS muted by user?
}
_lock = threading.Lock()

# ── Public API ────────────────────────────────────────────────────────────────

def is_running() -> bool:
    """Return True while the assistant should keep listening."""
    return _state["running"]


def stop():
    """Signal the assistant to shut down cleanly."""
    _state["running"] = False


def is_processing() -> bool:
    """Return True if a wake event is currently being handled."""
    return _state["processing"]


def set_processing(value: bool):
    """Mark whether a wake event is actively being processed."""
    _state["processing"] = value


def try_start_processing() -> bool:
    """
    Atomically check if processing is False and set it to True.
    Returns True if we successfully started, False if already processing.
    Use this to prevent multiple simultaneous wake event handlers.
    """
    with _lock:
        if not _state["processing"]:
            _state["processing"] = True
            return True
        return False


def is_muted() -> bool:
    """Return True if TTS output is muted."""
    return _state["muted"]


def toggle_mute() -> bool:
    """Toggle TTS mute. Returns the new mute state."""
    _state["muted"] = not _state["muted"]
    return _state["muted"]


def get_all() -> dict:
    """Return a snapshot of the full state (for debugging)."""
    return dict(_state)