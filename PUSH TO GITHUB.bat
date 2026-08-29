@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ABA Payment Speaker - Push to GitHub

if not exist "Sync ABA Payment Speaker to GitHub.bat" (
  echo ERROR: The safe GitHub sync script is missing.
  echo No files were uploaded.
  pause
  exit /b 1
)

call "Sync ABA Payment Speaker to GitHub.bat"
exit /b %errorlevel%
