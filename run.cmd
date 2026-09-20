@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo [.env created from .env.example]
        echo Opening Notepad for you to configure API keys...
        notepad .env
        exit /b 0
    ) else (
        echo [ERROR] Neither .env nor .env.example found.
        pause
        exit /b 1
    )
)

if not exist .venv\Scripts\python.exe (
    echo [Creating virtual environment .venv...]
    py -3 -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv with py -3
        pause
        exit /b 1
    )
)

echo [Installing requirements...]
call .venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

set "STREAMLIT_PORT=8592"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%STREAMLIT_PORT% .*LISTENING"') do (
    echo [Stopping existing process on port %STREAMLIT_PORT%: PID %%P]
    taskkill /PID %%P /T /F >nul 2>&1
)

echo [Starting Streamlit app on port %STREAMLIT_PORT%...]
call .venv\Scripts\streamlit run app.py --server.port %STREAMLIT_PORT%
