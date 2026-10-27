@echo off
title TrueCheck AI - Web Studio
set "PATH=%PATH%;C:\Program Files\nodejs;%APPDATA%\npm"
cd /d "%~dp0web"

echo ===================================================
echo   TRUECHECK AI - KHOI DONG WEB STUDIO (PORT 3000)
echo ===================================================

echo [1/2] Kiem tra va cai dat dependencies (npm install)...
call npm install
if errorlevel 1 (
    echo [LOI] Khong the chay npm. Hay chac chan ban da cai Node.js LTS!
    pause
    exit /b 1
)

echo [2/2] Khoi dong Next.js tai http://localhost:3000 ...
call npm run dev

pause

