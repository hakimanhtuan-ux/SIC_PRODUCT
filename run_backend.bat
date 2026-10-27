@echo off
title TrueCheck AI - Backend Engine (Port 8000)
set "PATH=%PATH%;C:\Users\Admin\AppData\Local\Python\pythoncore-3.15-64;C:\Users\Admin\AppData\Local\Python\pythoncore-3.15-64\Scripts"
cd /d "%~dp0backend"

echo ===================================================
echo   TRUECHECK AI - KHOI DONG BACKEND ENGINE (PORT 8000)
echo ===================================================

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
