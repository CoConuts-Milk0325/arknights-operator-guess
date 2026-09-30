@echo off
chcp 65001 >nul
title Arknights Voice Guess - Dev

echo ========================================
echo   Arknights Voice Guess - Dev Mode
echo ========================================
echo.

:: Kill any leftover process on port 5173
echo [Cleanup] Freeing port 5173...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5173" ^| find "LISTENING"') do taskkill /f /pid %%a >nul 2>nul
timeout /t 1 /nobreak >nul

:: Check Node.js
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Node.js not found, installing...
    where winget >nul 2>nul
    if %errorlevel% equ 0 (
        winget install OpenJS.NodeJS.LTS
    ) else (
        echo Please install Node.js from https://nodejs.org
        pause
        exit /b 1
    )
    set "PATH=%PATH%;C:\Program Files\nodejs"
)

echo Node.js version:
node -v
echo.

:: Install deps if needed
if not exist "node_modules\" (
    echo Installing dependencies...
    call npm install
)

:: Start Vite dev server
echo Starting dev server...
echo Open http://localhost:5173 in browser
echo.
npx vite --host 0.0.0.0 --port 5173
pause
