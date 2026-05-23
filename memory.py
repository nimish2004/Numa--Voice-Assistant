"""
memory.py — Conversation memory manager for Numa.

Design decisions:
  - Every message is stored with a UTC timestamp so the LLM has
    temporal context ("earlier today you asked about...").
  - Only SUCCESSFUL exchanges are saved. Garbled speech, unknown
    intents, and one-word fragments are never written to disk.
  - Tasks (open chrome, take screenshot, etc.) are stored as a
    compact summary, not the raw assistant reply, so history stays
    readable and token-efficient.
  - Atomic writes (write to .tmp → rename) prevent a corrupt
    memory.json if the process is killed mid-write.
  - A single load/save lock makes the module safe to call from
    background threads.
"""

import json
import os
import threading
from datetime import datetime, timezone

from config.settings import settings

# ── Config (always read live from settings) ───────────────────────────────────

def _memory_file() -> str : return settings.get("memory_file")
def _max_history() -> int : return settings.get("memory_max_history")

_lock = threading.Lock()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load() -> list:
    """Load history from disk. Returns [] on any failure."""
    mem_file = _memory_file()
    if not os.path.exists(mem_file):
        return []
    try:
        with open(mem_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception as e:
        print(f"⚠️  Memory load error: {e} — starting fresh.")
    return []


def _save(history: list):
    """Atomically persist history to disk."""
    mem_file = _memory_file()
    tmp = mem_file + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        os.replace(tmp, mem_file)
    except Exception as e:
        print(f"❌  Memory save error: {e}")
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _now_iso() -> str:
    """Current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Public API ────────────────────────────────────────────────────────────────

def add_exchange(user_text: str, assistant_response: str, intent_type: str = "chat"):
    """
    Save one full exchange (user turn + assistant turn) to memory.

    Parameters
    ----------
    user_text           : what the user actually said
    assistant_response  : what Numa replied (for chat) or intent name (for task)
    intent_type         : "chat" | "task" — controls how assistant turn is stored

    Only call this after a SUCCESSFUL exchange. Never call it for:
      - Empty / too-short transcriptions
      - "unknown" intents
      - LLM / network errors
    """
    with _lock:
        history = _load()

        timestamp = _now_iso()

        history.append({
            "role"      : "user",
            "content"   : user_text.strip(),
            "timestamp" : timestamp,
        })

        # For tasks, store a compact label so history stays readable
        if intent_type == "task":
            assistant_content = f"[task: {assistant_response}]"
        else:
            assistant_content = assistant_response.strip()

        history.append({
            "role"      : "assistant",
            "content"   : assistant_content,
            "timestamp" : timestamp,
        })

        # Trim to max_history (read live from settings)
        max_h = _max_history()
        if len(history) > max_h:
            history = history[-max_h:]

        _save(history)


def get_memory() -> list:
    """Return the full conversation history as a list of message dicts."""
    with _lock:
        return _load()


def get_recent(n: int = 6) -> list:
    """
    Return only the last n messages.
    Useful for building a short context window for the LLM.
    """
    with _lock:
        return _load()[-n:]


def clear_memory():
    """Wipe all history — called by the 'forget everything' voice command."""
    with _lock:
        _save([])
    print("🧹  Memory cleared.")
