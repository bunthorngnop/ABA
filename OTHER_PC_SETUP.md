# ABA Payment Speaker — Other PC Setup

Use this guide on the other Windows PC. Each PC keeps its own credentials, Telegram login session, database, and Python environment. GitHub synchronizes source code only.

## Important operating rule

Run the speaker application on only one PC at a time. Close it completely on PC1 before starting PC2. If both copies run, both computers may announce the same payment.

## First-time PC2 setup

1. Install Git for Windows and 64-bit Python 3.12 if they are not already installed.
2. Clone the private GitHub repository into a normal local folder, such as `C:\ABA Payment Speaker`. Do not clone it inside Dropbox.
3. Open PowerShell in the cloned folder and run:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

4. Open the new local `.env` and enter this PC's Telegram API settings and the already verified group/sender IDs. Never commit or upload `.env`.
5. Keep these local paths unchanged:

   ```dotenv
   TELEGRAM_SESSION_PATH=%LOCALAPPDATA%/ABA Payment Speaker/telegram_user.session
   DATABASE_PATH=%LOCALAPPDATA%/ABA Payment Speaker/aba_payment_speaker.sqlite3
   ```

6. For the first PC2 run, temporarily use `DIAGNOSTIC_MODE=true`, then run:

   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```

7. Complete Telegram's one-time login inside the application. The login session stays only in PC2's Local AppData folder.
8. Confirm the detected group IDs and PayWay sender ID, switch to production, close the app, and restart it with `Start ABA Payment Speaker.bat`.

## Normal transfer between PCs

On the PC where work was changed, close the application and double-click `PUSH TO GITHUB.bat`. It runs the regression suite and then starts the safe GitHub sync. The sync script publishes the local `main` branch only; confirm the intended changes are on `main` first. Do not expect changes on another branch to be published by this script.

On the other PC, ensure the application is closed, then double-click `PULL FROM GITHUB.bat` in its normal local clone. It checks that ABA is not running, refuses to overwrite a dirty worktree, pulls with fast-forward-only protection, refreshes dependencies, and runs the complete test suite.

If the pull script reports local source changes or untracked files, do not delete them or force the pull. Review `git status --short`; preserve and push/commit the work from its source PC, or create a fresh clone for testing.

After a successful pull, confirm every other speaker PC is closed, then start with `Start ABA Payment Speaker.bat`. Do not copy `.env`, `.venv`, the Telegram `.session`, the SQLite database, or logs between PCs.

## Prompt for Codex on PC2

```text
Read OTHER_PC_SETUP.md, README.md, .env.example, and the current project before changing anything.

Prepare this PC as an independent ABA Payment Speaker installation. Keep .env, the Telegram session, SQLite database, logs, and .venv local and excluded from GitHub. Do not print or expose any secret values. Verify Python 3.12, create/install the virtual environment if needed, run the complete test suite, confirm the Local AppData paths, and start the application for the one-time Telegram login or normal operation. Do not run it if another PC is currently running the speaker. Fix safe in-scope setup problems autonomously, then report exactly what was verified and what I must do next.
```
