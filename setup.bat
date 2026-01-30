@echo off
setlocal
title AI Agent Setup

echo ===================================================
echo      Initialize AI Agent Environment
echo ===================================================

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ and try again.
    pause
    exit /b 1
)
echo [OK] Python found.

:: 2. Install Python Dependencies
echo.
echo [1/4] Installing Python Dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install python requirements.
    pause
    exit /b 1
)

:: 3. Install Playwright Browsers
echo.
echo [2/4] Installing Playwright Browsers...
playwright install
if %errorlevel% neq 0 (
    echo [WARNING] Playwright install had issues. You may need to run 'playwright install' manually.
)

:: 4. Setup Desktop App (Node.js)
echo.
echo [3/4] Setting up Desktop App...
if exist "desktop\package.json" (
    cd desktop
    call npm install
    if %errorlevel% neq 0 (
        echo [WARNING] 'npm install' failed. Do you have Node.js installed?
        echo Skipping desktop setup...
    ) else (
        echo [OK] Desktop dependencies installed.
    )
    cd ..
) else (
    echo [INFO] No desktop app found, skipping.
)

:: 5. Check for Large Models (Piper)
echo.
echo [4/4] Checking Media Assets...
if not exist "piper\piper.exe" (
    echo.
    echo [ATTENTION] Piper TTS is missing!
    echo To enable high-quality local voice, download the windows-release of Piper.
    echo extract it to proper directory so that 'piper\piper.exe' exists.
    echo.
) else (
    echo [OK] Piper TTS found.
)

if not exist "yolov8n.pt" (
    echo [INFO] YOLO model missing. It will be downloaded automatically on first run.
)

echo.
echo ===================================================
echo        Setup Complete! Ready to Run.
echo ===================================================
echo.
pause
