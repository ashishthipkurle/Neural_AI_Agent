@echo off
setlocal EnableDelayedExpansion
title AI Agent One-Click Setup

echo ===============================================================================
echo                        AI AGENT ONE-CLICK SETUP
echo ===============================================================================
echo This script will install ALL necessary components:
echo 1. Python 3.11 (if missing)
echo 2. Node.js (for Desktop App)
echo 3. FFmpeg (for Audio Processing)
echo 4. Ollama (for Local LLM)
echo 5. Python Libraries (including Chatterbox & InsightFace)
echo ===============================================================================
echo.

:: Check for Winget
winget --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Winget is not installed. Please update Windows or install App Installer from Store.
    pause
    exit /b 1
)

:: -----------------------------------------------------------------------------
:: 1. SYSTEM DEPENDENCIES (using Winget)
:: ----------------------------------------------------------------------------- 
echo [Step 1/7] Checking System Dependencies...

:: Python 3.11 Check
python --version 2>nul | findstr /C:"3.11" >nul
if %errorlevel% neq 0 (
    echo [INSTALL] Python 3.11 not found or not default. Installing...
    winget install Python.Python.3.11 -e --silent
    echo [INFO] Please restart the script after Python installation so PATH updates!
) else (
    echo [OK] Python 3.11 detected.
)

:: Node.js Check
node -v >nul 2>&1
if %errorlevel% neq 0 (
    echo [INSTALL] Node.js not found. Installing...
    winget install OpenJS.NodeJS -e --silent
) else (
    echo [OK] Node.js detected.
)

:: FFmpeg Check
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INSTALL] FFmpeg not found. Installing...
    winget install Gyan.FFmpeg -e --silent
) else (
    echo [OK] FFmpeg detected.
)

:: Ollama Check
tool -v >nul 2>&1
:: 'ollama' command might block if server runs, checking binary existence or generic check
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo [INSTALL] Ollama not found. Installing...
    winget install Ollama.Ollama -e --silent
) else (
    echo [OK] Ollama detected.
)

:: -----------------------------------------------------------------------------
:: 2. PYTHON VIRTUAL ENVIRONMENT
:: -----------------------------------------------------------------------------
echo.
echo [Step 2/7] Setting up Python Environment...

if not exist ".venv" (
    echo [INFO] Creating .venv...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

:: Upgrade pip
python -m pip install --upgrade pip setuptools wheel

:: -----------------------------------------------------------------------------
:: 3. CORE PYTHON DEPENDENCIES
:: -----------------------------------------------------------------------------
echo.
echo [Step 3/7] Installing Core Python Libraries...

:: Install PyTorch (Universal - compatible with 3.11+)
:: Using generic pip install, but forcing index-url if needed usually.
:: For compatibility, we try standard install first.
pip install -r requirements.txt

:: -----------------------------------------------------------------------------
:: 4. CHATTERBOX SPECIFIC SETUP
:: -----------------------------------------------------------------------------
echo.
echo [Step 4/7] Installing Chatterbox (Voice Engine)...

python -c "import chatterbox" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Chatterbox not detected. Performing specialized install...
    
    :: Chatterbox needs specific versions often conflicting with latest defaults
    :: 1. Force compatible numpy
    pip install "numpy<2.0.0"
    
    :: 2. Install dependencies manually
    pip install "diffusers>=0.24.0" "transformers>=4.36.0" "scipy" "librosa" "pyloudnorm" "pykakasi" "s3tokenizer" "resemble-perth"
    
    :: 3. Install Chatterbox without deps to avoid downgrading torch if not needed
    pip install --no-deps chatterbox-tts
    
    :: 4. Install Conformers/Sentencepiece
    pip install conformer sentencepiece
    
    echo [OK] Chatterbox installed.
) else (
    echo [OK] Chatterbox already installed.
)

:: -----------------------------------------------------------------------------
:: 5. MODEL ASSETS SETUP
:: -----------------------------------------------------------------------------
echo.
echo [Step 5/6] Downloading AI Models (Vosk, YOLO, Embeddings)...
python setup_models.py

:: -----------------------------------------------------------------------------
:: 6. OLLAMA SETUP
:: -----------------------------------------------------------------------------
echo.
echo [Step 6/6] Setting up Ollama Model...
where ollama >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Pulling phi3:mini model (approx 2.3GB)...
    ollama pull phi3:mini
) else (
    echo [WARNING] Ollama binary not found in PATH, skipping model pull.
)

:: -----------------------------------------------------------------------------
:: 7. DESKTOP APP SETUP
:: -----------------------------------------------------------------------------
echo.
echo [Step 7/7] Building Desktop Application...

if exist "desktop\package.json" (
    cd desktop
    echo [INFO] Installing NPM packages...
    call npm install --silent
    cd ..
    echo [OK] Desktop App ready.
)

:: -----------------------------------------------------------------------------
:: FINAL CHECK
:: -----------------------------------------------------------------------------
echo.
echo ===============================================================================
echo                        SETUP COMPLETE
echo ===============================================================================
echo 1. To start the agent:  run 'start-all.bat'
echo 2. To use Voice:        Ensure microphone is connected.
echo 3. To use Vision:       Ensure webcam is connected.
echo.
pause
