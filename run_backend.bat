@echo off
title TrueCheck AI - Backend Engine (Port 8000)
set "PATH=C:\Users\Admin\AppData\Local\Python\pythoncore-3.15-64;C:\Users\Admin\AppData\Local\Python\pythoncore-3.15-64\Scripts;%PATH%"
cd /d "%~dp0backend"

echo ===================================================
echo   TRUECHECK AI - KHOI DONG BACKEND ENGINE (:8000)
echo ===================================================

python start-server.py
pause
