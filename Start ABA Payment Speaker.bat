@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Setup is incomplete. Follow README.md first.
  pause
  exit /b 1
)
start "ABA Payment Speaker" ".venv\Scripts\pythonw.exe" main.py

