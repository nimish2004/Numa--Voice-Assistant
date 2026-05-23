"""
actions/apps.py — Application launching and closing.

Security note:
  All subprocess calls use a fixed argument list — never shell=True with
  user-supplied strings. The allowlist (APP_REGISTRY) is the single source
  of truth for what Numa is permitted to launch. Anything not in the
  allowlist goes through open_app() which uses subprocess with a controlled
  argument list, not os.system().

Design:
  - Known apps have dedicated shortcuts for reliability and speed.
  - open_app() handles any app name the LLM extracts, but sanitises
    input and validates against the allowlist before executing.
  - close_app() kills by process name — more reliable than sending
    window close events which apps can swallow.
"""

import logging
import subprocess
import psutil

logger = logging.getLogger(__name__)
from tts import speak


# ── Known app registry ────────────────────────────────────────────────────────
# Maps common spoken names → (launch_command, process_name_for_close)
# process_name is used by close_app() to find and kill the process.

APP_REGISTRY: dict[str, tuple[list[str], str]] = {
    "chrome"    : (["cmd", "/c", "start", "chrome"],          "chrome.exe"),
    "spotify"   : (["cmd", "/c", "start", "spotify"],         "Spotify.exe"),
    "vscode"    : (["cmd", "/c", "code"],                      "Code.exe"),
    "notepad"   : (["cmd", "/c", "notepad"],                   "notepad.exe"),
    "youtube"   : (["cmd", "/c", "start", "https://www.youtube.com"], ""),
    "calculator": (["cmd", "/c", "start", "calc"],             "CalculatorApp.exe"),
    "explorer"  : (["cmd", "/c", "start", "explorer"],         "explorer.exe"),
    "terminal"  : (["cmd", "/c", "start", "cmd"],              "cmd.exe"),
    "word"      : (["cmd", "/c", "start", "winword"],          "WINWORD.EXE"),
    "excel"     : (["cmd", "/c", "start", "excel"],            "EXCEL.EXE"),
    "powerpoint": (["cmd", "/c", "start", "powerpnt"],         "POWERPNT.EXE"),
    "teams"     : (["cmd", "/c", "start", "ms-teams:"],        "Teams.exe"),
    "discord"   : (["cmd", "/c", "start", "discord:"],         "Discord.exe"),
    "zoom"      : (["cmd", "/c", "start", "zoommtg:"],         "Zoom.exe"),
    "whatsapp"  : (["cmd", "/c", "start", "whatsapp:"],        "WhatsApp.exe"),
    "vlc"       : (["cmd", "/c", "start", "vlc"],              "vlc.exe"),
    "paint"     : (["cmd", "/c", "start", "mspaint"],          "mspaint.exe"),
    "task manager": (["cmd", "/c", "start", "taskmgr"],        "Taskmgr.exe"),
}

# Aliases — maps alternate spoken names to registry keys
_ALIASES: dict[str, str] = {
    "google chrome" : "chrome",
    "vs code"       : "vscode",
    "visual studio code": "vscode",
    "ms teams"      : "teams",
    "microsoft teams": "teams",
    "cmd"           : "terminal",
    "command prompt": "terminal",
    "file explorer" : "explorer",
}


def _resolve_app_name(raw: str) -> str:
    """Normalise spoken app name to a registry key."""
    raw = raw.lower().strip()
    return _ALIASES.get(raw, raw)


def _launch(cmd: list[str], app_display_name: str):
    """Run a launch command safely without shell=True."""
    try:
        subprocess.Popen(cmd, shell=False)
    except FileNotFoundError:
        speak(f"I couldn't find {app_display_name} on this system.")
    except Exception as e:
        logger.error(f"Launch error for {app_display_name}: {e}")
        speak(f"Something went wrong opening {app_display_name}.")


# ── Known app shortcuts ───────────────────────────────────────────────────────

def open_chrome(data: dict):
    speak("Opening Chrome.")
    _launch(APP_REGISTRY["chrome"][0], "Chrome")

def open_spotify(data: dict):
    speak("Opening Spotify.")
    _launch(APP_REGISTRY["spotify"][0], "Spotify")

def open_vscode(data: dict):
    speak("Opening VS Code.")
    _launch(APP_REGISTRY["vscode"][0], "VS Code")

def open_notepad(data: dict):
    speak("Opening Notepad.")
    _launch(APP_REGISTRY["notepad"][0], "Notepad")

def open_youtube(data: dict):
    speak("Opening YouTube.")
    _launch(APP_REGISTRY["youtube"][0], "YouTube")

def open_terminal(data: dict):
    speak("Opening terminal.")
    _launch(APP_REGISTRY["terminal"][0], "terminal")


# ── Generic open (LLM-supplied app name) ─────────────────────────────────────

def open_app(data: dict):
    """
    Open any app by name extracted by the LLM.
    Resolves aliases, checks the allowlist, then launches safely.
    """
    raw = (
        data.get("parameters", {}).get("app", "")
        or data.get("app", "")
    ).strip()

    if not raw:
        speak("Which app would you like me to open?")
        return

    key = _resolve_app_name(raw)

    if key in APP_REGISTRY:
        cmd, _ = APP_REGISTRY[key]
        speak(f"Opening {raw}.")
        _launch(cmd, raw)
    else:
        # App not in allowlist — refuse with explanation
        speak(f"I don't have {raw} in my app list. You can ask me to add it.")
        logger.warning(f"App not in registry: '{raw}'")


# ── Close app ─────────────────────────────────────────────────────────────────

def close_app(data: dict):
    """
    Close a running app by killing its process.
    Uses psutil for cross-process visibility — more reliable than
    sending WM_CLOSE which apps can ignore.
    """
    raw = (
        data.get("parameters", {}).get("app", "")
        or data.get("app", "")
    ).strip()

    if not raw:
        speak("Which app should I close?")
        return

    key          = _resolve_app_name(raw)
    _, proc_name = APP_REGISTRY.get(key, (None, ""))

    if not proc_name:
        speak(f"I don't know how to close {raw}.")
        return

    killed = False
    for proc in psutil.process_iter(["name", "pid"]):
        if proc.info["name"] and proc.info["name"].lower() == proc_name.lower():
            try:
                proc.terminate()
                killed = True
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                speak(f"I don't have permission to close {raw}.")
                return

    if killed:
        speak(f"Closed {raw}.")
    else:
        speak(f"{raw} doesn't appear to be running.")
