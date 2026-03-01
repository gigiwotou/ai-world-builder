@echo off
title AI World Builder
echo ========================================
echo   AI World Builder - Launcher
echo ========================================
echo.

cd /d "%~dp0ai-world-builder"

echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found, please install Python 3.10+
    pause
    exit /b 1
)

echo [2/3] Installing dependencies...
pip install -r requirements.txt >nul 2>&1

echo.
echo [3/3] Starting server...
echo.
echo Make sure Ollama is running: ollama serve
echo.
echo ========================================
echo Open http://localhost:8000 in browser
echo ========================================
echo.

python -m backend.main

pause
