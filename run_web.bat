@echo off
title TrueCheck AI - Web Studio (Port 3000)
set "PATH=C:\Program Files\nodejs;%APPDATA%\npm;%PATH%"
cd /d "%~dp0web"

echo ===================================================
echo   TRUECHECK AI - KHOI DONG WEB STUDIO (:3000)
echo ===================================================

if not exist "node_modules\next" (
    echo [1/2] Dang cai dat thu vien lan dau ^(npm install^)...
    call npm install
)

echo Khoi dong giao dien tai http://localhost:3000 ...
node start-dev.js dev -p 3000
pause
