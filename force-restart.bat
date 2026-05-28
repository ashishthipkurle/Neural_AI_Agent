@echo off
title Force Restart - Neural AI Agent
echo.
echo ==================================================
echo   FORCE KILLING ALL SERVICES
echo ==================================================
echo.

echo [1/4] Killing Ollama...
taskkill /F /IM ollama.exe >NUL 2>&1
taskkill /F /IM "Ollama Helper.exe" >NUL 2>&1

echo [2/4] Killing Python Processes (API & INDRA)...
taskkill /F /IM python.exe >NUL 2>&1
taskkill /FI "WINDOWTITLE eq INDRA Service" /F >NUL 2>&1

echo [3/4] Killing Node/React...
taskkill /F /IM node.exe >NUL 2>&1

echo.
echo Clean up complete. Waiting 3 seconds...
timeout /t 3 /nobreak > nul

echo.
echo [4/4] Restarting everything...
call start-all.bat
