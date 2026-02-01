# 🎙️ Personal Voice Assistant 

A fully offline, modular voice assistant built in Python.  
Wake it up using a custom wake word (“Alexa”), speak commands, and control your laptop using voice.

No cloud.  
No paid APIs.  
Runs completely on your local machine.

---

## 🚀 Features

- Custom Wake Word Detection (using OpenWakeWord)
- Offline Speech Recognition (using OpenAI Whisper)
- Modular Architecture (easy to extend)
- Control Laptop with Voice:
  - Open apps (Chrome, Spotify, VS Code, etc.)
  - Media controls (play, pause, next, previous)
  - System controls (lock, shutdown, volume)
  - Take screenshots
  - Developer commands (terminal, git status)
- Works 100% offline
- Windows supported

---

## 🧠 Architecture

The system is built using a clean modular pipeline:

wakeword.py → speech.py → brain.py → actions.py
↑ ↓
main.py (orchestrator)

### Modules

| File        | Purpose |
|------------|---------|
| wakeword.py | Detects the wake word ("Alexa") |
| speech.py   | Records audio & converts speech to text |
| brain.py    | Converts text into intent |
| actions.py  | Executes real system actions |
| main.py     | Connects everything |

---

## 📦 Requirements

- Python 3.10+
- Windows OS
- Microphone

Python libraries:

```bash
pip install openwakeword whisper sounddevice scipy pyautogui psutil
```
Also install FFmpeg (required for Whisper).

▶️ How to Run

From project folder:
```bash
py -3.10 main.py
```

Say:

- Alexa open chrome
- Alexa play music
- Alexa take screenshot
- Alexa what is the time

🪟 Auto Start with Windows

Create a file:
```bash
start_assistant.bat
```

Content:
```bash
@echo off
cd /d D:\projects\voice
py -3.10 main.py
pause
```

## 🧩 Future Improvements

Planned upgrades:
- LLM brain (ChatGPT / LLaMA / Ollama)
- Text-to-Speech responses
- Memory system
- GUI / System tray
- Plugin system

## 📌 Why This Project is Different

Most assistants:

- Use cloud APIs
- Require internet
- Are black boxes
  
This project:
- Is fully local
-Transparent code
- Real AI pipeline
- Great for learning AI systems engineering

## 🎯 Use Cases

- Final year project
- Portfolio project
- AI experimentation
- Personal automation tool
- Foundation for building Jarvis-like systems

## 🧑‍💻 Author

Built by Nimish

This project is meant to help others learn how real voice assistants are built from scratch.
