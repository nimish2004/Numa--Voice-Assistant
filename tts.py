"""
tts.py - Text-to-speech output for Numa.

Architecture:
  Primary   : edge-tts (Microsoft neural voices, requires internet)
              Runs on a dedicated persistent asyncio event loop in a
              background thread - no "event loop closed" crashes.
  Fallback  : pyttsx3 (fully offline, Windows SAPI voices)
              Single engine instance created once and reused.

Key behaviours:
  - speak() blocks until audio finishes - correct for a voice assistant.
  - interrupt() stops playback immediately when wake word fires mid-speech.
  - speech_just_ended() lets wakeword.py enforce a post-speech silence
    window to prevent Numa's own voice triggering the wake word detector.
  - Mute state is read from state.py.
  - Temp MP3 files are always cleaned up via try/finally.
  - All public functions are thread-safe.
"""

import asyncio
import logging
import os
import tempfile
import threading
import time

import pygame
import state
from config.settings import settings

logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────────

def _voice()  : return settings.get("tts_voice")
def _rate()   : return settings.get("tts_rate")
def _pitch()  : return settings.get("tts_pitch")


# ── Post-speech timestamp ─────────────────────────────────────────────────────
# Set to time.time() whenever speak() finishes.
# wakeword.py reads this to enforce a silence window after Numa speaks,
# preventing Numa's own voice from triggering the wake word detector.

_speech_ended_at: float = 0.0


def speech_just_ended() -> float:
    """Return the unix timestamp when the last speak() call finished."""
    return _speech_ended_at


# ── pygame mixer ──────────────────────────────────────────────────────────────

_mixer_ready = False
_playback_lock = threading.Lock()


def _ensure_mixer():
    """Deferred initialization of pygame.mixer to handle systems without audio."""
    global _mixer_ready
    if _mixer_ready:
        return
    try:
        pygame.mixer.init()
        _mixer_ready = True
    except Exception as e:
        logger.error(f"pygame.mixer init failed: {e}")


# ── Persistent asyncio event loop (edge-tts) ──────────────────────────────────

_loop   = asyncio.new_event_loop()
_thread = threading.Thread(
    target  = _loop.run_forever,
    name    = "TTS-AsyncLoop",
    daemon  = True,
)
_thread.start()


# ── pyttsx3 singleton (offline fallback) ──────────────────────────────────────

_pyttsx3_engine = None
_pyttsx3_lock   = threading.Lock()


def _get_pyttsx3():
    global _pyttsx3_engine
    with _pyttsx3_lock:
        if _pyttsx3_engine is None:
            try:
                import pyttsx3
                _pyttsx3_engine = pyttsx3.init()
                _pyttsx3_engine.setProperty("rate", 175)
                _pyttsx3_engine.setProperty("volume", 1.0)
            except Exception as e:
                logger.error(f"pyttsx3 init failed: {e}")
        return _pyttsx3_engine


# ── edge-tts implementation ───────────────────────────────────────────────────

async def _synthesise(text: str, path: str):
    """Generate MP3 from edge-tts and save to path."""
    import edge_tts
    communicate = edge_tts.Communicate(text, _voice(), rate=_rate(), pitch=_pitch())
    await communicate.save(path)


def _play_mp3(path: str):
    """Play an MP3 file via pygame, blocking until done or interrupted."""
    _ensure_mixer()
    with _playback_lock:
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(50)
            pygame.mixer.music.unload()
        except Exception as e:
            logger.error(f"pygame playback error: {e}")


def _speak_edge(text: str) -> bool:
    """Speak via edge-tts. Returns True on success, False on failure."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name

        future = asyncio.run_coroutine_threadsafe(_synthesise(text, tmp_path), _loop)
        timeout = settings.get("request_timeout_sec", 10)
        future.result(timeout=timeout)

        _play_mp3(tmp_path)
        return True

    except Exception as e:
        logger.error(f"edge-tts error: {e}")
        return False

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _speak_pyttsx3(text: str):
    """Speak via pyttsx3 (fully offline fallback)."""
    engine = _get_pyttsx3()
    if engine is None:
        logger.error("No TTS engine available.")
        return
    try:
        with _playback_lock:
            engine.say(text)
            engine.runAndWait()
    except Exception as e:
        logger.error(f"pyttsx3 error: {e}")


# ── Public interface ───────────────────────────────────────────────────────────

def speak(text: str):
    """
    Speak text aloud. Blocks until playback is complete.
    Updates _speech_ended_at so wakeword.py can enforce a
    post-speech silence window to prevent self-triggering.
    """
    global _speech_ended_at

    if not text or not text.strip():
        return

    logger.info(f"Speaking: {text}")

    if state.is_muted():
        logger.debug("(muted)")
        return

    success = _speak_edge(text)
    if not success:
        logger.info("Falling back to offline TTS...")
        _speak_pyttsx3(text)

    # Record when speech finished - wakeword.py uses this
    _speech_ended_at = time.time()


def interrupt():
    """
    Stop any currently playing audio immediately.
    Called by wakeword.py when wake word fires mid-speech.
    """
    global _speech_ended_at
    _ensure_mixer()
    with _playback_lock:
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except Exception:
            pass
    # Mark speech as ended so the silence window starts from now
    _speech_ended_at = time.time()


def set_voice(short_name: str):
    """Change the edge-tts voice and persist to settings."""
    ok, err = settings.set("tts_voice", short_name)
    if ok:
        logger.info(f"Voice changed to: {short_name}")
    else:
        logger.warning(f"Could not change voice: {err}")