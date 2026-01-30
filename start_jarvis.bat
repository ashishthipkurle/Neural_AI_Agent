@echo off
title Neural AI Agent - Launcher
echo ============================================
echo   Starting Neural AI Agent Services
echo ============================================
echo.

:: 1. Start Python API Server (Headless)
echo [1/2] Starting Python API Server...
start "Neural AI Agent API" /min cmd /c "python agent/main.py --mode api"

:: 2. Wait a moment for API to start
timeout /t 5 /nobreak > nul

:: 3. Launch Electron Executable
echo [2/2] Launching Electron Desktop App...
start "" "desktop\dist\win-unpacked\Neural AI Agent.exe"

echo.
echo ============================================
echo   System is running!
echo ============================================
echo.
pause
