@echo off
echo ============================================================
echo   ANTIGRAVITY AI AGENT - Starting Web UI (Unified)
echo ============================================================
echo.

:: Start Python API Server
echo Starting Python API Server on port 8000...
start "Python API" cmd /k "cd /d D:\All Projects\My AI Agent && python -m agent.api_server"

:: Wait a moment for Python to start
timeout /t 3 /nobreak > nul

:: Start React Frontend (Using Desktop Codebase)
echo Starting React Frontend (Desktop/Web Unified) on port 5173...
start "React Frontend" cmd /k "cd /d D:\All Projects\My AI Agent\desktop && npm run dev"

echo.
echo ============================================================
echo   All services started!
echo   - Python API:    http://localhost:8000
echo   - React UI:      http://localhost:5173 (Unified Desktop/Web)
echo ============================================================
echo.
echo Opening Web UI in browser...
timeout /t 5 /nobreak > nul
start http://localhost:5173
