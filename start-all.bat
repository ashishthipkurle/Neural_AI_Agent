@echo off
title Neural AI Agent - All Servers
echo ============================================
echo   Starting AI Agent Services
echo ============================================
echo.

:: Start Ollama LLM server (required for Code Agent)
echo [1/4] Checking Ollama LLM server...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if errorlevel 1 (
    echo Starting Ollama...
    start "" ollama serve
    timeout /t 3 /nobreak > nul
) else (
    echo Ollama already running.
)

:: Start Python API server in new window
echo [2/4] Starting Python API server on port 8000...
start "Python API Server" cmd /k "cd /d %~dp0 && python agent/api_server.py"

:: Wait a moment for Python to start
timeout /t 5 /nobreak > nul

:: Start Node.js proxy server in new window  
echo [3/4] Starting Node.js proxy server on port 5000...
start "Node.js Proxy" cmd /k "cd /d %~dp0web\server && node index.js"

:: Wait a moment
timeout /t 2 /nobreak > nul

:: Start React frontend in new window
echo [4/4] Starting React frontend on port 5173...
start "React Frontend" cmd /k "cd /d %~dp0web\client && npm run dev"

echo.
echo ============================================
echo   All servers starting...
echo ============================================
echo.
echo   Ollama LLM:    http://localhost:11434
echo   Python API:    http://localhost:8000
echo   Node.js Proxy: http://localhost:5000  
echo   React UI:      http://localhost:5173
echo.
echo Open http://localhost:5173 in your browser!
echo.
pause
