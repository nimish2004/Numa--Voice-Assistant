"""
hotkeys.py - Global hotkey listener for Numa.

Listens for Ctrl+C globally (even when app is not in focus) and
gracefully exits the application.
"""

import threading

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False


def start_hotkey_listener():
    """
    Start a background thread listening for Ctrl+C globally.
    Runs at startup and monitors for the exit hotkey.
    """
    if not KEYBOARD_AVAILABLE:
        print("[Numa] Keyboard module not available - hotkey listener disabled")
        return

    def _listen():
        try:
            # Listen for Ctrl+C globally
            keyboard.add_hotkey('ctrl+c', _on_exit_hotkey)
            keyboard.wait()  # Keep listener alive
        except Exception as e:
            print(f"[Numa] Hotkey listener error: {e}")

    thread = threading.Thread(
        target=_listen,
        name="HotkeyListener",
        daemon=True
    )
    thread.start()


def _on_exit_hotkey():
    """Called when Ctrl+C is pressed globally."""
    # Import here to avoid circular imports
    import state
    from tts import speak
    from app.signals import numa_signals

    print("\n[Numa] Ctrl+C detected. Exiting...")
    speak("Goodbye.")
    state.stop()
    numa_signals.quit_requested.emit()
