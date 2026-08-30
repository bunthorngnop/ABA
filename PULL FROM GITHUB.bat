@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ABA Payment Speaker - Pull from GitHub
set "ABA_PYTEST_TEMP=%TEMP%\aba-payment-speaker-tests-%RANDOM%-%RANDOM%"

echo ABA PAYMENT SPEAKER - SAFE PULL AND TEST
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo ERROR: Git is not installed or is not available in PATH.
  goto :failed
)

if not exist ".git" (
  echo ERROR: This folder is not a Git clone.
  echo Clone the private repository into C:\ABA Payment Speaker first.
  goto :failed
)

powershell -NoProfile -Command "$running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue ^| Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -match 'main\.py' }; if ($running) { exit 1 } else { exit 0 }"
if errorlevel 1 (
  echo ERROR: ABA Payment Speaker appears to be running.
  echo Close its dashboard completely, then run this file again.
  goto :failed
)

git status --porcelain > "%TEMP%\aba-payment-speaker-status.txt"
for %%A in ("%TEMP%\aba-payment-speaker-status.txt") do if not %%~zA==0 (
  echo ERROR: This project has local source changes or untracked files.
  echo Push, commit, or review them before pulling. Nothing was overwritten.
  del /q "%TEMP%\aba-payment-speaker-status.txt" >nul 2>nul
  goto :failed
)
del /q "%TEMP%\aba-payment-speaker-status.txt" >nul 2>nul

echo Pulling the main branch with fast-forward-only protection...
git pull --ff-only
if errorlevel 1 goto :failed

if not exist ".venv\Scripts\python.exe" (
  echo No local virtual environment was found.
  echo Starting the one-click setup...
  call "SET UP ON THIS PC.bat"
  exit /b %errorlevel%
)

".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
if errorlevel 1 (
  echo Existing .venv is not Python 3.12.
  echo Starting the one-click setup to repair it...
  call "SET UP ON THIS PC.bat"
  exit /b %errorlevel%
)

echo Refreshing pinned dependencies...
".venv\Scripts\python.exe" -m pip install -r "requirements.txt"
if errorlevel 1 goto :failed
if exist "requirements-dev.txt" (
  ".venv\Scripts\python.exe" -m pip install -r "requirements-dev.txt"
  if errorlevel 1 goto :failed
)

echo.
echo Running the complete regression suite...
".venv\Scripts\python.exe" -m pytest -q -p no:cacheprovider --basetemp "%ABA_PYTEST_TEMP%"
if errorlevel 1 goto :failed

echo.
echo SUCCESS: Source, dependencies, and tests are up to date.
echo Confirm every other PC is closed before starting ABA Payment Speaker.
pause
exit /b 0

:failed
echo.
echo PULL DID NOT COMPLETE SAFELY. Review the message above.
echo No forced reset or automatic conflict resolution was used.
pause
exit /b 1
