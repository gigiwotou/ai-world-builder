@echo off
chcp 65001 >nul
title AI World Builder
echo ========================================
echo   AI World Builder - Launcher
echo ========================================
echo.

cd /d "%~dp0"

echo [1/5] Checking Python...
python --version
if errorlevel 1 (
    echo Error: Python not found, please install Python 3.10+
    pause
    exit /b 1
)
echo Python OK

echo [2/5] Installing dependencies...
pip install -r requirements.txt
echo Dependencies installed

echo [3/5] Checking Ollama service...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama service...
    start cmd /c "ollama serve"
    timeout /t 8 /nobreak >nul
    echo Ollama service started
) else (
    echo Ollama is running
)

echo [4/5] Checking AI model...
set MODEL_NAME=qwen3.5:4b
ollama list | findstr /i "%MODEL_NAME%" >nul 2>&1
if errorlevel 1 (
    echo Pulling model: %MODEL_NAME%
    ollama pull %MODEL_NAME%
) else (
    echo Model already exists
)

echo.
echo [5/5] Starting server...
echo.
echo ========================================
echo Open http://localhost:8000 in browser
echo ========================================
echo.

python -m backend.main

pause
