@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ABA Payment Speaker - Push to GitHub
set "ABA_PYTEST_TEMP=%TEMP%\aba-payment-speaker-tests-%RANDOM%-%RANDOM%"

echo ABA PAYMENT SPEAKER - TEST AND PUSH
echo.

if not exist "Sync ABA Payment Speaker to GitHub.bat" (
  echo ERROR: The safe GitHub sync script is missing.
  echo No files were uploaded.
  pause
  exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
  if not errorlevel 1 goto :test_project_venv
)

py -3.12 -c "import pytest" >nul 2>nul
if not errorlevel 1 goto :test_python_launcher

if exist "C:\ABA Payment Speaker\.venv\Scripts\python.exe" (
  "C:\ABA Payment Speaker\.venv\Scripts\python.exe" -c "import pytest" >nul 2>nul
  if not errorlevel 1 goto :test_pc3_runtime
)

echo ERROR: No tested Python 3.12 environment with pytest is available.
echo Run SET UP ON THIS PC.bat from a normal local clone first.
echo Nothing was committed or uploaded.
pause
exit /b 1

:test_project_venv
echo Running the complete regression suite before upload...
".venv\Scripts\python.exe" -m pytest -q -p no:cacheprovider --basetemp "%ABA_PYTEST_TEMP%"
goto :check_tests

:test_python_launcher
echo Running the complete regression suite before upload...
py -3.12 -m pytest -q -p no:cacheprovider --basetemp "%ABA_PYTEST_TEMP%"
goto :check_tests

:test_pc3_runtime
echo Running the complete regression suite before upload...
"C:\ABA Payment Speaker\.venv\Scripts\python.exe" -m pytest -q -p no:cacheprovider --basetemp "%ABA_PYTEST_TEMP%"

:check_tests
if errorlevel 1 goto :tests_failed

echo.
echo Tests passed. Starting the secret-safe GitHub sync...

call "Sync ABA Payment Speaker to GitHub.bat"
exit /b %errorlevel%

:tests_failed
echo.
echo ERROR: Tests failed. Nothing was committed or uploaded.
pause
exit /b 1
