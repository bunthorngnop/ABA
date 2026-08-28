@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title ABA Payment Speaker - GitHub Sync

echo ABA PAYMENT SPEAKER - SAFE GITHUB SYNC
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo ERROR: Git is not installed or is not available in PATH.
  echo Install Git for Windows, then run this file again.
  goto :failed
)

if not exist ".git" (
  echo First GitHub setup for this folder...
  git init
  if errorlevel 1 goto :failed
  git branch -M main
)

git check-ignore -q ".env"
if errorlevel 1 (
  echo ERROR: .env is not protected by .gitignore. Sync stopped.
  goto :failed
)

git remote get-url origin >nul 2>nul
if errorlevel 1 (
  echo.
  echo Create an EMPTY private GitHub repository first - no README or license.
  set /p "ABA_REPO_URL=Paste its GitHub repository URL: "
  if not defined ABA_REPO_URL (
    echo ERROR: No repository URL was entered.
    goto :failed
  )
  git remote add origin "%ABA_REPO_URL%"
  if errorlevel 1 goto :failed
)

git add --all
if errorlevel 1 goto :failed

for /f "delims=" %%F in ('git diff --cached --name-only') do call :check_sensitive "%%F"
if defined ABA_SENSITIVE_FILE (
  git reset -q
  echo ERROR: A sensitive file was about to be committed: %ABA_SENSITIVE_FILE%
  echo It has not been committed or uploaded.
  goto :failed
)

git diff --cached --quiet
if not errorlevel 1 (
  echo No local changes to commit.
) else (
  set "ABA_COMMIT_MESSAGE=ABA Payment Speaker update %date% %time:~0,8%"
  git commit -m "!ABA_COMMIT_MESSAGE!"
  if errorlevel 1 (
    echo.
    echo Git may need your name and email configured. Follow the message above.
    goto :failed
  )
)

echo.
echo Uploading main branch to GitHub...
git push -u origin main
if errorlevel 1 goto :failed

echo.
echo SUCCESS: Source code is synced to GitHub.
echo Secrets, Telegram sessions, virtual environments, logs, and databases were excluded.
pause
exit /b 0

:check_sensitive
set "ABA_FILE=%~1"
if /i "%ABA_FILE%"==".env" set "ABA_SENSITIVE_FILE=%ABA_FILE%"
if /i "%ABA_FILE:~0,9%"==".env copy" set "ABA_SENSITIVE_FILE=%ABA_FILE%"
if /i "%ABA_FILE:~-6%"==".local" if /i "%ABA_FILE:~0,4%"==".env" set "ABA_SENSITIVE_FILE=%ABA_FILE%"
echo(%ABA_FILE%| findstr /i /r "\.session$ \.session-journal$ \.session-shm$ \.session-wal$ \.sqlite3$ \.sqlite3-shm$ \.sqlite3-wal$ \.sqlite3-journal$" >nul && set "ABA_SENSITIVE_FILE=%ABA_FILE%"
exit /b 0

:failed
echo.
echo SYNC DID NOT COMPLETE. Nothing should be assumed uploaded.
pause
exit /b 1
