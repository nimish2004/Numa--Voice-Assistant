"""
main.py - Entry point for Numa Personal Voice Assistant.

Threading architecture:
  Main thread   -> PyQt6 QApplication (required by Qt)
                -> NumaTray, ChatWindow, SettingsWindow

  Engine thread -> start_wake_engine() (mic streaming, blocks forever)

  Wake thread   -> on_wake() (one per detected command, daemon)
                -> listen, transcribe, resolve intent, execute action
                -> all system actions (pyautogui, subprocess, pycaw)
                   run here - they are NOT Qt and don't need main thread

Communication:
  Wake thread -> main thread via _emit() / numa_signals (Qt signals)
  This is the ONLY way background threads touch the UI.
"""

import sys
import threading

import pyautogui
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore    import Qt

import state
from config.settings import settings
from app.tray        import NumaTray
from app.signals     import numa_signals
from wakeword        import start_wake_engine
from speech          import listen_and_transcribe
from llm_brain       import get_intent_llm
from actions         import handle_intent
from tts             import speak

# Disable pyautogui failsafe — moving mouse to corner would crash actions
pyautogui.FAILSAFE = False
pyautogui.PAUSE    = 0.05   # small pause between actions, prevents misfire


# ── Signal emit helper ────────────────────────────────────────────────────────

def _emit(signal, *args):
    """
    Emit a Qt signal only while the app is still running.
    Guards against post-shutdown emit crashes when wake thread
    is mid-command as Qt tears down.
    """
    if state.is_running():
        try:
            if args:
                signal.emit(*args)
            else:
                signal.emit()
        except RuntimeError:
            pass   # Qt object already deleted — safe to ignore


# ── Wake event handler ────────────────────────────────────────────────────────

def on_wake():
    """
    Runs in a daemon thread per wake event.
    Handles the full pipeline: listen -> think -> act.

    System actions (pyautogui, subprocess, pycaw) all run here safely.
    They don't require the main thread — only Qt widgets do.
    UI updates happen via _emit() which routes through Qt's signal queue.
    """
    try:
        _emit(numa_signals.status_changed, "listening")
        _emit(numa_signals.listening_started)

        # ── Step 1: Listen ────────────────────────────────────────────────
        text = listen_and_transcribe()

        if not text or len(text.split()) < 2:
            print("[Numa] Too short — ignoring.")
            return

        print(f"[Numa] Heard: {text}")
        _emit(numa_signals.transcription_done, text)
        _emit(numa_signals.status_changed, "processing")

        # ── Step 2: Resolve intent ────────────────────────────────────────
        result = get_intent_llm(text)
        intent = result.get("intent", result.get("type", "chat"))
        _emit(numa_signals.command_received, text, intent)

        # ── Step 3: Execute ───────────────────────────────────────────────
        rtype = result.get("type")

        if rtype == "task":
            # System actions run directly in this thread — correct
            handle_intent(result)

        elif rtype == "chat":
            reply = result.get("response", "")
            if reply:
                _emit(numa_signals.status_changed, "speaking")
                _emit(numa_signals.response_spoken, reply)
                speak(reply)

    except Exception as e:
        print(f"[Numa] Error in on_wake: {e}")
        import traceback
        traceback.print_exc()
        _emit(numa_signals.status_changed, "error")

    finally:
        state.set_processing(False)
        _emit(numa_signals.status_changed, "idle")


# ── Engine thread ─────────────────────────────────────────────────────────────

def _start_engine():
    t = threading.Thread(
        target = start_wake_engine,
        args   = (on_wake,),
        name   = "WakeEngine",
        daemon = True,
    )
    t.start()
    return t


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Numa")
    app.setApplicationDisplayName("Numa — Personal Voice Assistant")
    app.setApplicationVersion("2.0.0")

    # Check if first run — show onboarding window
    from app.onboarding import should_show_onboarding, OnboardingWindow
    if should_show_onboarding():
        onboarding = OnboardingWindow(app)
        onboarding.show()
        # Onboarding relaunches main.py itself on finish — just exit here
        sys.exit(app.exec())

    # Normal launch — start engine + tray
    _start_engine()
    print("[Numa] Engine started.")

    tray = NumaTray(app)
    numa_signals.quit_requested.connect(app.quit)

    print("[Numa] Ready. Say the wake word to begin.")
    exit_code = app.exec()

    state.stop()
    print("[Numa] Shutdown complete.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()