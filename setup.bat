@echo off
setlocal EnableDelayedExpansion
title Numa Setup
color 0F

echo.
echo  =============================================
echo   Numa - Personal Voice Assistant - Setup
echo   Version 2.0
echo  =============================================
echo.

REM ── STEP 1: Check Python 3.10 ─────────────────────────────────────────────
echo  [1/7] Checking Python version...

py -3.10 --version >nul 2>&1
if errorlevel 1 (
    python --version 2>nul | findstr /C:"3.10" >nul
    if errorlevel 1 (
        echo.
        echo  [ERROR] Python 3.10 not found.
        echo.
        echo  Download from:
        echo  https://www.python.org/downloads/release/python-31011/
        echo.
        echo  IMPORTANT: Check "Add Python to PATH" during install.
        pause
        exit /b 1
    )
    set PYTHON=python
) else (
    set PYTHON=py -3.10
)
echo  [OK] Python 3.10 found.
echo.

REM ── STEP 2: Check FFmpeg ──────────────────────────────────────────────────
echo  [2/7] Checking FFmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo  [WARNING] FFmpeg not found. Install via: winget install ffmpeg
    echo  Whisper may not work without it. Continuing anyway...
) else (
    echo  [OK] FFmpeg found.
)
echo.

REM ── STEP 3: Create virtual environment ───────────────────────────────────
echo  [3/7] Setting up virtual environment...
if not exist ".venv" (
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo  [OK] Virtual environment created.
) else (
    echo  [OK] Already exists.
)
echo.

REM ── Use venv pip and python directly - NEVER bare pip ─────────────────────
set VENV_PIP=.venv\Scripts\pip.exe
set VENV_PYTHON=.venv\Scripts\python.exe

REM ── STEP 4: Upgrade pip ──────────────────────────────────────────────────
echo  [4/7] Upgrading pip...
%VENV_PYTHON% -m pip install --upgrade pip --quiet
echo  [OK] Done.
echo.

REM ── STEP 5: Install dependencies ─────────────────────────────────────────
echo  [5/7] Installing dependencies (5-15 min first time)...
echo.
%VENV_PIP% install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  [ERROR] Install failed. Check errors above.
    pause
    exit /b 1
)
echo.
echo  [OK] Dependencies installed.
echo.

REM ── STEP 6: Download wake word models ────────────────────────────────────
echo  [6/7] Installing wake word models...
set MODEL_DEST=.venv\Lib\site-packages\openwakeword\resources\models
set BUNDLED=assests\models\alexa_v0.1.onnx

if not exist "%MODEL_DEST%" mkdir "%MODEL_DEST%"

if exist "%BUNDLED%" (
    echo  Copying bundled alexa model...
    copy /Y "%BUNDLED%" "%MODEL_DEST%\alexa_v0.1.onnx" >nul
    echo  [OK] Alexa model installed from bundle.
) else (
    echo  Downloading alexa model...
    %VENV_PYTHON% -c "import urllib.request; urllib.request.urlretrieve('https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/alexa_v0.1.onnx', r'%MODEL_DEST%\alexa_v0.1.onnx')" >nul 2>&1
    if errorlevel 1 (
        echo  [WARNING] Failed to download alexa model
    ) else (
        echo  [OK] Alexa model downloaded.
    )
)

REM Download required preprocessing models
echo  Downloading melspectrogram preprocessing model...
%VENV_PYTHON% -c "import urllib.request; urllib.request.urlretrieve('https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/melspectrogram.onnx', r'%MODEL_DEST%\melspectrogram.onnx')" >nul 2>&1
if errorlevel 1 (
    echo  [WARNING] Failed to download melspectrogram model
) else (
    echo  [OK] Melspectrogram model downloaded.
)

echo  Downloading embedding model...
%VENV_PYTHON% -c "import urllib.request; urllib.request.urlretrieve('https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/embedding_model.onnx', r'%MODEL_DEST%\embedding_model.onnx')" >nul 2>&1
if errorlevel 1 (
    echo  [WARNING] Failed to download embedding model
) else (
    echo  [OK] Embedding model downloaded.
)
echo.

REM ── STEP 7: Verify critical imports ──────────────────────────────────────
echo  [7/7] Verifying installation...
echo.
%VENV_PYTHON% -c "from google import genai; print('  [OK] google-genai')"
if errorlevel 1 (
    echo  [FIXING] Reinstalling google-genai into venv...
    %VENV_PIP% install --force-reinstall google-genai --quiet
    %VENV_PYTHON% -c "from google import genai; print('  [OK] google-genai fixed')"
)
%VENV_PYTHON% -c "import whisper; print('  [OK] whisper')"
%VENV_PYTHON% -c "import PyQt6; print('  [OK] PyQt6')"
%VENV_PYTHON% -c "import sounddevice; print('  [OK] sounddevice')"
%VENV_PYTHON% -c "import openwakeword; print('  [OK] openwakeword')"
echo.

REM ── Setup .env ────────────────────────────────────────────────────────────
if not exist ".env" (
    echo GEMINI_API_KEY=your_key_here> .env
    echo  [ACTION REQUIRED] Open .env and add your Gemini API key.
    echo  Get one free at: https://aistudio.google.com/apikey
    echo.
) else (
    findstr /C:"your_key_here" .env >nul
    if not errorlevel 1 (
        echo  [REMINDER] Replace 'your_key_here' in .env with your real API key!
        echo.
    ) else (
        echo  [OK] .env configured.
        echo.
    )
)

REM ── Create launcher ───────────────────────────────────────────────────────
(
    echo @echo off
    echo cd /d "%%~dp0"
    echo if not exist ".venv\Scripts\activate.bat" (
    echo     echo [ERROR] Run setup.bat first!
    echo     pause
    echo     exit /b 1
    echo )
    echo call .venv\Scripts\activate.bat
    echo python main.py
    echo if errorlevel 1 (
    echo     echo.
    echo     echo Numa exited with an error. See above.
    echo     pause
    echo )
) > start_numa.bat

echo  =============================================
echo   Setup Complete! 
echo  =============================================
echo.
echo  Next: Double-click start_numa.bat to launch.
echo.
pause