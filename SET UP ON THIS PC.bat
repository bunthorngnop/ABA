@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ABA Payment Speaker - Set Up This PC

echo ABA PAYMENT SPEAKER - ONE-CLICK PC SETUP
echo.

echo(%CD%| find /i "\Dropbox\" >nul
if not errorlevel 1 (
  echo ERROR: This project is inside Dropbox.
  echo Clone it into a normal local folder such as C:\ABA Payment Speaker,
  echo then run this setup file from that local folder.
  goto :failed
)

if not exist "requirements.txt" (
  echo ERROR: requirements.txt is missing.
  goto :failed
)

if not exist ".env.example" (
  echo ERROR: .env.example is missing.
  goto :failed
)

where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: The Python launcher is not installed.
  echo Install 64-bit Python 3.12, then run this file again.
  goto :failed
)

py -3.12 -c "import struct,sys; sys.exit(0 if struct.calcsize('P') * 8 == 64 else 1)" >nul 2>nul
if errorlevel 1 (
  echo ERROR: 64-bit Python 3.12 is required but was not found.
  echo Install it from python.org, then run this file again.
  goto :failed
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
  if errorlevel 1 (
    echo Existing virtual environment belongs to another Python or PC.
    echo Recreating the project-local .venv...
    rmdir /s /q ".venv"
    if exist ".venv" (
      echo ERROR: Could not replace .venv. Close programs using it and retry.
      goto :failed
    )
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python 3.12 virtual environment...
  py -3.12 -m venv ".venv"
  if errorlevel 1 goto :failed
)

echo Installing pinned dependencies...
".venv\Scripts\python.exe" -m pip install -r "requirements.txt"
if errorlevel 1 goto :failed

if exist "requirements-dev.txt" (
  ".venv\Scripts\python.exe" -m pip install -r "requirements-dev.txt"
  if errorlevel 1 goto :failed
)

if not exist ".env" (
  copy /y ".env.example" ".env" >nul
  if errorlevel 1 goto :failed
  echo Created this PC's private .env file.
  set "ABA_NEW_ENV=1"
) else (
  echo Existing .env preserved unchanged.
)

if exist "requirements-dev.txt" (
  echo.
  echo Running the complete regression suite...
  ".venv\Scripts\python.exe" -m pytest -q -p no:cacheprovider --basetemp "%TEMP%\aba-payment-speaker-tests-%RANDOM%-%RANDOM%"
  if errorlevel 1 (
    echo ERROR: Tests failed. Do not start production operation.
    goto :failed
  )
)

echo.
echo SUCCESS: This PC's Python environment is ready.
if defined ABA_NEW_ENV (
  echo NEXT: Open .env and enter this PC's private Telegram settings.
) else (
  echo This PC's existing .env was not changed.
)
echo.
echo IMPORTANT: Do not start this application while another PC is running it.
echo After confirming every other copy is closed, use Start ABA Payment Speaker.bat.
pause
exit /b 0

:failed
echo.
echo SETUP DID NOT COMPLETE. Review the error above; production was not started.
pause
exit /b 1
