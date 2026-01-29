import speech_recognition as sr
import pyautogui
import pyttsx3
import os
import time
import random
import winsound


# ---------- SETUP ----------
engine = pyttsx3.init('sapi5')
engine.setProperty('rate', 170)
engine.setProperty('volume', 1.0)

voices = engine.getProperty('voices')
engine.setProperty('voice', voices[1].id)

r = sr.Recognizer()
r.energy_threshold = 300
r.dynamic_energy_threshold = True

acknowledge = ["Okay", "Sure", "Alright", "Got it"]

WAKE_WORDS = ["alexa"]

FILLER_WORDS = [
    "can you", "please", "could you", "would you",
    "hey", "assistant", "bro", "just"
]

# ---------- SPEAK ----------
def speak(text):
    print("Assistant:", text)
    engine.say(text)
    engine.runAndWait()

# ---------- LISTEN ----------
def listen():
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=0.3)
        audio = r.listen(source, phrase_time_limit=4)

    try:
        return r.recognize_google(audio).lower()
    except:
        return ""
    
def listening_beep():
    winsound.Beep(800, 150)

def done_beep():
    winsound.Beep(1200, 150)


# ---------- START ----------
print("Assistant running in background...")
speak("Assistant is running")

while True:
    heard = listen()
    print("Heard:", heard)

    if heard == "":
        continue

    # ---- CHECK WAKE WORD ----
    if not any(wake in heard for wake in WAKE_WORDS):
        continue
    listening_beep()

    # ---- REMOVE WAKE WORD ----
    for wake in WAKE_WORDS:
        heard = heard.replace(wake, "")

    command = heard.strip()

    # ---- REMOVE FILLER WORDS ----
    for word in FILLER_WORDS:
        command = command.replace(word, "")

    command = command.strip()
    print("Cleaned Command:", command)

    if command == "":
        continue

    # ---- INTENT BASED COMMANDS ----

    RESPONSES = [
    "Yes, playing music",
    "Sure, starting your music",
    "Alright, here is your music"
    ]

    if "play" in command and "music" in command:
        speak(random.choice(RESPONSES))
        time.sleep(1.2)
        pyautogui.press("playpause")

    elif "pause" in command or "stop" in command:
        speak("Pausing music")
        pyautogui.press("playpause")

    elif "volume" in command and "up" in command:
        speak("Increasing volume")
        pyautogui.press("volumeup")

    elif "volume" in command and "down" in command:
        speak("Decreasing volume")
        pyautogui.press("volumedown")

    elif "lock" in command:
        speak("Locking laptop")
        os.system("rundll32.exe user32.dll,LockWorkStation")

    elif "open" in command and "chrome" in command:
        speak("Opening Google Chrome")
        os.system("start chrome")

    elif "open" in command and ("vscode" in command or "visual studio" in command):
        speak("Opening Visual Studio Code")
        os.system("code")

    elif "open" in command and "notepad" in command:
        speak("Opening Notepad")
        os.system("notepad")

    elif "open" in command and "calculator" in command:
        speak("Opening Calculator") 
        os.system("calc")

    elif "study" in command:
        speak("Activating study mode")
        pyautogui.press("volumemute")
        os.system("start code")
        os.system("start chrome")

    elif "movie" in command:
        speak("Activating movie mode")
        for _ in range(10):
            pyautogui.press("volumeup")

    elif any(x in command for x in ["exit", "quit", "stop assistant"]):
        speak("Assistant stopped")
        break

    else:
        speak("Sorry, I don't know that command")
