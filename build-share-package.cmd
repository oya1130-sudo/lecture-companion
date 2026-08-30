@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-share-package.ps1"
if errorlevel 1 (
  echo.
  echo Share package build failed. Review the error above.
  pause
)
