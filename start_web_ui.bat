@echo off
echo ============================================================
echo   ANTIGRAVITY AI AGENT - Starting All Services
echo ============================================================
echo.

:: Start Python API Server
echo Starting Python API Server on port 8000...
start "Python API" cmd /k "cd /d D:\All Projects\My AI Agent && python -m agent.api_server"

:: Wait a moment for Python to start
timeout /t 3 /nobreak > nul

:: Start Node.js Proxy
echo Starting Node.js Proxy on port 5000...
start "Node.js Proxy" cmd /k "cd /d D:\All Projects\My AI Agent\web\server && npm run dev"

:: Wait a moment
timeout /t 2 /nobreak > nul

:: Start React Frontend
echo Starting React Frontend on port 5173...
start "React Frontend" cmd /k "cd /d D:\All Projects\My AI Agent\web\client && npm run dev"

echo.
echo ============================================================
echo   All services started!
echo   - Python API:    http://localhost:8000
echo   - Node.js Proxy: http://localhost:5000  
echo   - React UI:      http://localhost:5173
echo ============================================================
echo.
echo Opening Web UI in browser...
timeout /t 5 /nobreak > nul
start http://localhost:5173
