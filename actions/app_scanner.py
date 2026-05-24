"""
actions/app_scanner.py — Dynamic Windows app discovery and fuzzy lookup.

Scans Start Menu shortcuts and Windows registry App Paths on first use,
caches to disk, and exposes find_app() for fuzzy name matching.
"""

import difflib
import json
import logging
import os
import pathlib
import threading
import winreg
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_FILE = pathlib.Path(os.environ.get("APPDATA", "")) / "Numa" / "app_cache.json"

_cache: dict[str, str] = {}  # lowercase_name -> launch_path
_cache_lock = threading.Lock()
_scan_done = threading.Event()


def _scan_registry() -> dict[str, str]:
    apps = {}
    reg_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(hive, reg_path)
            count = winreg.QueryInfoKey(key)[0]
            for i in range(count):
                try:
                    sub_name = winreg.EnumKey(key, i)          # e.g. "Chrome.exe"
                    sub = winreg.OpenKey(key, sub_name)
                    exe_path, _ = winreg.QueryValueEx(sub, "")  # default value
                    winreg.CloseKey(sub)
                    canonical = sub_name.lower().replace(".exe", "").strip()
                    if exe_path and pathlib.Path(exe_path).exists():
                        apps[canonical] = exe_path
                except OSError:
                    pass
            winreg.CloseKey(key)
        except OSError:
            pass
    return apps


def _scan_start_menu() -> dict[str, str]:
    apps = {}
    dirs = [
        pathlib.Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        pathlib.Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for base in dirs:
        if not base.exists():
            continue
        for lnk in base.rglob("*.lnk"):
            name = lnk.stem.lower().strip()
            apps[name] = str(lnk)
    return apps


def _do_scan() -> dict[str, str]:
    apps = _scan_start_menu()
    apps.update(_scan_registry())  # registry exe paths override shortcut paths
    return apps


def _load_cache() -> dict[str, str]:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(apps: dict[str, str]):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(apps, indent=2, ensure_ascii=False), encoding="utf-8")


def _populate(refresh: bool = False):
    global _cache
    with _cache_lock:
        if not refresh:
            on_disk = _load_cache()
            if on_disk:
                _cache = on_disk
                _scan_done.set()
                return
        apps = _do_scan()
        _cache = apps
        _save_cache(apps)
        _scan_done.set()
        logger.info(f"App scan complete: {len(apps)} apps discovered.")


def start_background_scan():
    """Kick off a background scan at startup so the cache is warm when needed."""
    threading.Thread(target=_populate, daemon=True).start()


def refresh_cache():
    """Force a fresh scan, overwriting any cached data."""
    threading.Thread(target=lambda: _populate(refresh=True), daemon=True).start()


def find_app(query: str) -> Optional[tuple[str, str]]:
    """
    Find an installed app by name. Returns (matched_name, launch_path) or None.
    Waits up to 5 s for the background scan to finish on first call.
    """
    _scan_done.wait(timeout=5.0)
    with _cache_lock:
        apps = dict(_cache)

    q = query.lower().strip()

    # 1. Exact match
    if q in apps:
        return q, apps[q]

    # 2. Query is a substring of an app name (e.g. "chrome" in "google chrome")
    for name, path in apps.items():
        if q in name:
            return name, path

    # 3. App name is a substring of query (e.g. "discord" in "open discord now")
    for name, path in apps.items():
        if name in q:
            return name, path

    # 4. Fuzzy match
    matches = difflib.get_close_matches(q, apps.keys(), n=1, cutoff=0.6)
    if matches:
        return matches[0], apps[matches[0]]

    return None
