@echo off
title Al-Narjis AI Server
cd /d "%~dp0"

echo ============================================
echo   Al-Narjis AI - Platform Launcher
echo   النرجس للذكاء الاصطناعي
echo ============================================
echo.

echo [1/3] Stopping any existing server on port 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1
timeout /t 1 /nobreak >nul

echo [2/3] Opening browser (4 second delay)...
start "" /min cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8000/home"

echo [3/3] Starting server... (close this window to stop)
echo.
echo   Landing page : http://127.0.0.1:8000/home
echo   Dashboard    : http://127.0.0.1:8000
echo.
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000

if errorlevel 1 (
    echo.
    echo ERROR: Server failed to start. Make sure Python is installed.
    pause
)