@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js 20+ is required before setup.
  pause
  exit /b 1
)
node studio\studio.mjs setup
pause
