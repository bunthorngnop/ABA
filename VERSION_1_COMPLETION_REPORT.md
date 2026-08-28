# Version 1 User-Session Migration Completion Report

Date: 2026-08-29

## 1. Files changed

- `app/telegram_listener.py`: replaced Bot API polling with a read-only Telethon user-session listener and dashboard-driven authentication.
- `app/config.py`: added API ID/hash, phone and session-path configuration plus validation.
- `app/dashboard.py`: added setup-state display and secure login-code/masked 2FA dialogs; retained ID discovery/copy/save controls.
- `main.py`: supplies the new settings and defensively redacts API hash and phone from logs.
- `.env.example`, `.gitignore`, `requirements.txt`: migrated configuration/dependency and protected session file patterns.
- `README.md`: replaced BotFather instructions with official Telegram developer-portal and one-time login instructions.
- Tests: adapted transport tests and added user-session configuration, group-scope, sender authorization, diagnostic, credential-redaction and commissioning coverage.
- Removed obsolete `diagnose_telegram.py` Bot API utility.

The parser, Khmer numbers, bank normalization, database, TTS and audio queue were preserved.

## 2. Library selected

Telethon 1.44.0 was selected. It provides mature MTProto user authentication, persistent SQLite sessions, code/2FA sign-in, incoming event handling and automatic reconnection without requiring the unavailable Bot-to-Bot Communication Mode.

## 3. Migration details

- The application authenticates the operator’s existing Telegram user account.
- First login requests a Telegram code through a dashboard dialog and a masked two-step-verification password only when Telegram requires it.
- Successful authentication creates a persistent local session; subsequent starts reuse it.
- Only incoming `NewMessage` events are registered.
- With one or more configured group IDs, all other groups and private chats are rejected before sender resolution or parsing.
- Diagnostic mode shows safe group and sender metadata but can never speak.
- Production requires a numeric group allowlist, verified numeric PayWay sender ID and matching expected username.
- Both confirmed ABA formats and their exact Khmer announcements remain unchanged.

## 4. Security protections

- Default session location: `%LOCALAPPDATA%/ABA Payment Speaker/telegram_user.session`, outside Dropbox.
- `.env` and all common Telethon session sidecar patterns are ignored by Git.
- API hash and phone are redacted defensively from logs.
- Login codes and 2FA passwords are neither stored nor logged.
- Session entity caching is disabled to minimize retained metadata.
- No Telegram send, reply, forward, join, leave, edit or delete operations exist.
- Raw notification messages are not logged or persisted.
- No PayWay numeric ID is embedded or guessed.

## 5. Verification

- Complete regression suite after four-group allowlist support: **55 tests passed**.
- Python compilation: passed.
- Commissioning dashboard render/state smoke test: passed.
- Exact KHR and USD real-message regression tests: passed.
- Duplicate, sequential audio, privacy, unauthorized sender, wrong group and diagnostic-silence tests: passed.

Live commissioning confirmed authenticated session reuse, the configured group, the observed numeric `@PayWayByABA_bot` sender ID, and production-ready configuration. Five recent messages from the verified source were checked read-only and all now validate.

Actual observed format extensions were added narrowly and test-first: messages without the later staff fragment, messages with an optional `Remark:` clause, and the verified `PPCBank` KHQR label. No speculative ABA formats were added.

The listener now supports a comma-separated `ALLOWED_CHAT_IDS` allowlist. The same verified PayWay numeric sender and username checks apply independently in every allowed group, while all other groups remain silent. The legacy single `ALLOWED_CHAT_ID` key remains readable for backward compatibility.

## 6. Exact first-run steps

1. Obtain API ID/hash from `my.telegram.org` → **API development tools**.
2. Put API ID, API hash and international-format phone number in `.env`.
3. Start `main.py`.
4. Enter the Telegram login code in the dashboard dialog; enter the masked 2FA password only if prompted.
5. Send an ordinary message in each desired group and click **Add Group ID**.

## 7. Discover PayWay ID and enter production

1. Keep diagnostic mode active and wait for a new genuine `@PayWayByABA_bot` group notification.
2. Review its displayed username, group title, chat ID and numeric sender ID.
3. Click **Verify & Save ABA IDs**; username alone is not production authorization.
4. Click **Switch to Production**.
5. Close and restart the application; confirm the dashboard shows **Production ready**.

No unrelated Version 2 work was started.
