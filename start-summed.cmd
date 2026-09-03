@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-summed.ps1"
if errorlevel 1 (
  echo.
  echo summed startup failed. Review the error message above.
  pause
)
