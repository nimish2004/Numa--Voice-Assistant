"""
wakeword.py - Wake word detection engine for Numa.

Key behaviours:
  - POST_SPEECH_SILENCE_SEC: ignores detections for 2s after Numa speaks.
    Prevents Numa's TTS from self-triggering. Was 1.5s, increased to 2.0s
    based on real-world testing showing false triggers still occurring.

  - REQUIRED_HITS: requires 3 consecutive confident frames before firing.
    Reduces single-frame noise false positives.

  - Processing lock: never fires while a command is being processed.
    Prevents overlapping wake events.

  - tts.interrupt(): stops Numa mid-speech when user triggers wake word.
    User doesn't need to wait for Numa to finish talking.
"""

import threading
import time
import os

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

import state
import tts as _tts
from config.settings import settings


# ── Config ────────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16000
BLOCK_SIZE  = 1280

# Seconds after Numa finishes speaking to ignore wake detections.
# 2.0s works better than 1.5s for faster speakers and louder speakers.
POST_SPEECH_SILENCE_SEC = 2.0


def _cfg(key: str):
    return settings.get(key)


# ── Model ─────────────────────────────────────────────────────────────────────

def _resolve_model_path():
    """Get full path to wake word model file."""
    wake_word = settings.get("wake_word")

    # Always use full path to the downloaded ONNX model in openwakeword resources
    import openwakeword
    model_dir = os.path.join(os.path.dirname(openwakeword.__file__), "resources", "models")
    model_path = os.path.join(model_dir, f"{wake_word}_v0.1.onnx")

    if os.path.exists(model_path):
        return model_path

    # Fallback to local assets if available
    local_model = os.path.join(
        os.path.dirname(__file__),
        "assets",
        "models",
        f"{wake_word}_v0.1.onnx"
    )
    if os.path.exists(local_model):
        return local_model

    # Last resort: return model name and let openwakeword handle it
    return wake_word

print("[Numa] Loading wake word model...")
_wake_model = Model(
    wakeword_models     = [_resolve_model_path()],
    inference_framework = "onnx",
)
print("[Numa] Wake word model ready.")


# ── Internal state ────────────────────────────────────────────────────────────

_last_trigger_time = 0.0
_hit_count         = 0


# ── Core engine ───────────────────────────────────────────────────────────────

def start_wake_engine(on_wake_callback):
    """
    Block the calling thread, streaming mic audio.
    Fires on_wake_callback in a daemon thread on confident wake detection.
    """
    global _last_trigger_time, _hit_count
    _frame_count = [0]

    def _audio_callback(indata, frames, time_info, status):
        global _last_trigger_time, _hit_count
        _frame_count[0] += 1

        audio      = np.frombuffer(indata, dtype=np.int16)
        prediction = _wake_model.predict(audio)
        now        = time.time()

        # Get score - openwakeword returns predictions with model name as key (e.g., 'alexa_v0.1')
        # First try exact wake word name, then try with _v0.1 suffix
        wake_word = _cfg("wake_word")
        score = prediction.get(wake_word, None)
        if score is None:
            # Try with _v0.1 suffix (standard openwakeword naming)
            score = prediction.get(f"{wake_word}_v0.1", 0)
        if score is None:
            # Fallback: get first available prediction
            score = next(iter(prediction.values())) if prediction else 0

        # Debug: Show all scores to see model behavior
        if _frame_count[0] % 50 == 0:
            print(f"[Frame {_frame_count[0]:4d}] score={score:.4f} (max={max(prediction.values()) if prediction else 0:.4f}, all={prediction})")

        # Accumulate or reset confidence counter
        if score > _cfg("wake_threshold"):
            _hit_count += 1
            if _hit_count == 1:
                print(f"[Wake] Score {score:.3f} > {_cfg('wake_threshold')} - threshold crossed!")
        else:
            if _hit_count > 0:
                print(f"[Wake] Score {score:.3f} - streak broken, resetting")
            _hit_count = 0

        # How long since Numa last finished speaking
        time_since_speech   = now - _tts.speech_just_ended()
        in_post_speech_win  = time_since_speech < POST_SPEECH_SILENCE_SEC

        # Fire when ALL conditions met:
        # 1. Enough consecutive confident frames
        # 2. Cooldown since last trigger elapsed
        # 3. Not already processing a command
        # 4. Not in post-speech silence window (prevents self-trigger)
        if (
            _hit_count          >= _cfg("wake_required_hits")
            and (now - _last_trigger_time) > _cfg("wake_cooldown_sec")
            and not in_post_speech_win
        ):
            _last_trigger_time = now
            _hit_count         = 0

            _tts.interrupt()
            if not state.try_start_processing():
                return
            print("\n[Numa] Wake word detected!")

            threading.Thread(
                target = on_wake_callback,
                name   = "WakeHandler",
                daemon = True,
            ).start()

    print("[Numa] Listening for wake word...")

    try:
        with sd.RawInputStream(
            samplerate = SAMPLE_RATE,
            blocksize  = BLOCK_SIZE,
            dtype      = "int16",
            channels   = 1,
            callback   = _audio_callback,
        ):
            while state.is_running():
                time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[Numa] Wake engine error: {e}")