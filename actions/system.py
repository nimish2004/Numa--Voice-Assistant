"""
actions/system.py — System-level controls for Numa.

Covers: volume, screen, power management, system info.

Notes:
  - pycaw is used for precise volume control (0-100 mapped to scalar).
    pyautogui volume keys are kept as a fallback since pycaw requires
    the Windows audio COM stack which can fail on some configurations.
  - Destructive actions (shutdown, restart) speak a warning and use a
    5-second delay — enough time for the user to cancel via Task Manager
    if triggered by accident.
  - Screenshots are saved to ~/Pictures/Numa/Screenshots/ rather than
    a relative path — survives working directory changes and is findable
    by non-technical users.
"""

import datetime
import os
import subprocess

import psutil
import pyautogui
from tts import speak
from config.settings import settings

def _cfg(key: str):
    return settings.get(key)


# ── Volume helpers ────────────────────────────────────────────────────────────

def _set_volume_pycaw(percent: int):
    """Set system master volume using Windows audio COM stack."""
    try:
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetSpeakers()
        volume  = devices.EndpointVolume
        scalar  = max(0.0, min(1.0, percent / 100.0))
        volume.SetMasterVolumeLevelScalar(scalar, None)
        return True
    except Exception as e:
        print(f"⚠️  pycaw volume error: {e}")
        return False


# ── Volume actions ────────────────────────────────────────────────────────────

def mute(data: dict):
    speak("Muted.")
    pyautogui.press("volumemute")


def volume_up(data: dict):
    speak("Volume up.")
    pyautogui.press("volumeup")


def volume_down(data: dict):
    speak("Volume down.")
    pyautogui.press("volumedown")


def set_volume(data: dict):
    """Set volume to an exact percentage (0–100)."""
    raw = (
        data.get("parameters", {}).get("value")
        or data.get("value")
        or 50
    )
    try:
        percent = max(0, min(100, int(raw)))
    except (ValueError, TypeError):
        speak("Please give me a number between 0 and 100.")
        return

    success = _set_volume_pycaw(percent)
    if success:
        speak(f"Volume set to {percent} percent.")
    else:
        # Fallback: use media keys to approximate (imprecise but functional)
        speak(f"Adjusting volume to approximately {percent} percent.")
        pyautogui.press("volumemute")   # mute first to normalise
        pyautogui.press("volumemute")   # unmute
        steps = percent // 2
        for _ in range(steps):
            pyautogui.press("volumeup")


# ── Screenshot ────────────────────────────────────────────────────────────────

def take_screenshot(data: dict):
    """
    Save a timestamped screenshot.
    Folder: settings screenshot_folder, or ~/Pictures/Numa/Screenshots/ if blank.
    """
    folder = _cfg("screenshot_folder") or os.path.join(
        os.path.expanduser("~"), "Pictures", "Numa", "Screenshots"
    )
    os.makedirs(folder, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename  = os.path.join(folder, f"screenshot_{timestamp}.png")

    try:
        img = pyautogui.screenshot()
        img.save(filename)
        speak("Screenshot saved to your Pictures folder.")
        print(f"📸  Saved: {filename}")
    except Exception as e:
        print(f"❌  Screenshot error: {e}")
        speak("I couldn't take a screenshot.")


# ── Power management ──────────────────────────────────────────────────────────

def lock_laptop(data: dict):
    speak("Locking.")
    subprocess.run(
        ["rundll32.exe", "user32.dll,LockWorkStation"],
        shell=False, check=False
    )


def shutdown(data: dict):
    delay = str(_cfg("shutdown_delay_sec") or 5)
    speak(f"Shutting down in {delay} seconds. Save your work.")
    subprocess.run(["shutdown", "/s", "/t", delay], shell=False, check=False)


def restart(data: dict):
    delay = str(_cfg("shutdown_delay_sec") or 5)
    speak(f"Restarting in {delay} seconds.")
    subprocess.run(["shutdown", "/r", "/t", delay], shell=False, check=False)


def sleep(data: dict):
    speak("Going to sleep.")
    subprocess.run(
        ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        shell=False, check=False
    )


def cancel_shutdown(data: dict):
    """Cancel a pending shutdown — useful if user triggered it by accident."""
    result = subprocess.run(
        ["shutdown", "/a"],
        shell=False, capture_output=True, text=True
    )
    if result.returncode == 0:
        speak("Shutdown cancelled.")
    else:
        speak("There's no pending shutdown to cancel.")


# ── System info ───────────────────────────────────────────────────────────────

def tell_time(data: dict):
    now = datetime.datetime.now()
    hour   = now.strftime("%I").lstrip("0") or "12"
    minute = now.strftime("%M")
    period = now.strftime("%p")
    speak(f"It's {hour}:{minute} {period}.")


def tell_date(data: dict):
    today = datetime.datetime.now().strftime("%A, %d %B %Y")
    speak(f"Today is {today}.")


def battery_status(data: dict):
    battery = psutil.sensors_battery()
    if battery is None:
        speak("I can't read battery info on this system.")
        return

    percent    = int(battery.percent)
    plugged_in = battery.power_plugged
    warn_pct   = _cfg("battery_warn_pct")
    crit_pct   = _cfg("battery_critical_pct")

    if plugged_in:
        if percent >= 100:
            speak("Battery is fully charged and plugged in.")
        else:
            speak(f"Battery is at {percent} percent and charging.")
    else:
        if percent <= warn_pct:
            speak(f"Battery is critically low at {percent} percent. Please plug in.")
        elif percent <= crit_pct:
            speak(f"Battery is at {percent} percent. Consider charging soon.")
        else:
            speak(f"Battery is at {percent} percent, running on battery.")


def cpu_status(data: dict):
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    speak(
        f"CPU is at {cpu} percent. "
        f"RAM usage is {ram.percent} percent, "
        f"with {round(ram.available / (1024**3), 1)} gigabytes free."
    )
