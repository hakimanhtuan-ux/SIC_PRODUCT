@echo off
title TrueCheck AI - Khoi dong Toan bo He thong
echo ===================================================
echo   TRUECHECK AI - KHOI DONG BACKEND (:8000) + WEB (:3000)
echo ===================================================

start "TrueCheck Backend (:8000)" cmd /k ""%~dp0run_backend.bat""
start "TrueCheck Web Studio (:3000)" cmd /k ""%~dp0run_web.bat""

echo Dang doi may chu khoi dong (4 giay)...
timeout /t 4 /nobreak >nul
start "" "http://localhost:3000"
echo Da mo trinh duyet tai http://localhost:3000 !

