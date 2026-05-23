"""
actions/web.py — Web-dependent actions for Numa.

Covers: Google search, weather lookup.

Design decisions:
  - Requests has a hard 6-second timeout — voice assistants must respond
    fast. Hanging network calls kill UX.
  - Weather uses wttr.in (free, no API key needed) with a clean spoken
    format — the raw response is readable aloud without modification.
  - web_search opens the browser; it does not scrape results. For a
    future premium feature, we can integrate a search API (SerpAPI /
    Brave Search) and read top results aloud.
"""

import logging
import urllib.parse
import webbrowser

import requests
from tts import speak

logger = logging.getLogger(__name__)
from config.settings import settings

def _timeout() -> int:
    return settings.get("request_timeout_sec")


# ── Web search ────────────────────────────────────────────────────────────────

def web_search(data: dict):
    query = (
        data.get("parameters", {}).get("query", "")
        or data.get("query", "")
    ).strip()

    if not query:
        speak("What would you like me to search for?")
        return

    speak(f"Searching for {query}.")
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
    webbrowser.open(url)


# ── Weather ───────────────────────────────────────────────────────────────────

def get_weather(data: dict):
    city = (
        data.get("parameters", {}).get("city", "")
        or data.get("city", "")
    ).strip()

    # wttr.in uses "auto" to detect location from IP when city is blank
    location = urllib.parse.quote(city) if city else ""
    url      = f"https://wttr.in/{location}?format=3"

    speak("Checking the weather.")

    try:
        response = requests.get(url, timeout=_timeout())
        response.raise_for_status()

        weather_text = response.text.strip()

        if not weather_text:
            speak("I got an empty response from the weather service.")
            return

        logger.info(f"Weather: {weather_text}")
        speak(weather_text)

    except requests.Timeout:
        speak("The weather service took too long to respond. Try again in a moment.")

    except requests.ConnectionError:
        speak("I can't reach the weather service. Please check your internet connection.")

    except requests.HTTPError as e:
        logger.warning(f"Weather HTTP error: {e}")
        speak("The weather service returned an error. Try again shortly.")

    except Exception as e:
        logger.error(f"Weather unexpected error: {e}")
        speak("Something went wrong fetching the weather.")
