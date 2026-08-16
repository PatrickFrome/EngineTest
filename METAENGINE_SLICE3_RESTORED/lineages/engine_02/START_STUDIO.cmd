@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js 20+ is required. Install Node.js, then run SETUP.cmd.
  pause
  exit /b 1
)
node studio\studio.mjs
if errorlevel 1 pause
