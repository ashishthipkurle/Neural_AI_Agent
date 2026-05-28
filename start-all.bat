@echo off
title Neural AI Agent - All Servers
echo ============================================
echo   Starting AI Agent Services
echo ============================================
echo.

:: Start Ollama LLM server (required for cloud models)
echo [1/4] Checking Ollama LLM server...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if errorlevel 1 (
    echo Starting Ollama...
    start "" "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
    timeout /t 5 /nobreak > nul
) else (
    echo Ollama already running.
)

:: Kill existing sessions to prevent port conflicts
echo [2/4] Cleaning up old processes...
taskkill /FI "WINDOWTITLE eq Python API Server" /F >NUL 2>&1
taskkill /FI "WINDOWTITLE eq React Frontend" /F >NUL 2>&1
taskkill /FI "WINDOWTITLE eq INDRA Service" /F >NUL 2>&1
timeout /t 2 /nobreak > nul

:: Start Python API server in new window
echo [3/4] Starting Python API server on port 8000...
start "Python API Server" cmd /k "cd /d %~dp0 && python -m agent.api_server"

:: Wait a moment for Python to start
timeout /t 5 /nobreak > nul

:: Start INDRA background service
echo [3/4] Starting INDRA background service on port 8001...
start "INDRA Service" cmd /k "cd /d %~dp0jarvis && python main.py"
timeout /t 3 /nobreak > nul

:: Start React frontend in new window
echo [4/4] Starting React frontend on port 5173...
start "React Frontend" cmd /k "cd /d %~dp0desktop && npm run dev"

echo.
echo ============================================
echo   All servers starting...
echo ============================================
echo.
echo   Ollama LLM:    http://localhost:11434
echo   Python API:    http://localhost:8000
echo   INDRA API:    http://localhost:8001
echo   React UI:      http://localhost:5173
echo.
echo Open http://localhost:5173 in your browser!
echo.
pause
