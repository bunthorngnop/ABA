# ABA Payment Speaker Bot — Version 1

This Windows application monitors configured Telegram groups through your own authenticated Telegram account, validates the confirmed ABA/PayWay incoming-payment grammar, and announces valid incoming payments in Khmer. Telegram remains the authoritative payment record. Uncertain events stay silent.

## Operational dashboard

The primary screen is a dark, shop-counter dashboard built around the latest validated payment:

- the received KHR or USD amount is the largest element;
- the large local clock stays centered above the payment card, with a readable date beneath it;
- the shop header uses the two-line Khmer title `វីង វណ្ណា-ស្រីមុិច` / `ប្រព័ន្ធទទួលប្រាក់` in Khmer OS Muol Light when installed, with safe Khmer-capable fallbacks;
- KHR amounts use success green while USD amounts use a distinct warm gold;
- the validated payer name appears in blue;
- the normalized originating bank appears in violet;
- `ANNOUNCED` appears only after the audio queue reports successful speech;
- system readiness, spoken-only daily totals, and a three-row recent-payment viewport are shown using privacy-safe fields;
- when today has more than three successfully announced payments, the larger-text recent-payment area scrolls through up to 1,000 current-day records, newest first; complete KHR rows are green, complete USD rows are gold, and sender names are bold;
- the dashboard adapts to shorter displays by tightening sender/bank cards and, only on very short screens, collapsing the secondary status column so the received amount remains visible.
- at application startup, the dashboard waits briefly for an active secondary monitor and maximizes there; if no secondary display becomes available, it opens at normal size on the primary monitor.

Telegram commissioning IDs and the safe parser test remain available under **Settings & Diagnostics**, away from the operational display. No raw Telegram payload, account fragment, transaction ID, APV, merchant, operator, credential, or session data is shown in payment history.

## What changed

Telegram did not expose Bot-to-Bot Communication Mode for the original receiving bot, so the Bot API listener was replaced with a read-only Telethon user-session listener. The parser, Khmer number conversion, bank normalization, SQLite duplicate protection, audio queue, TTS, dashboard, and safety rules remain unchanged.

The listener does not send messages, join groups, modify chats, mark setup IDs as trusted automatically, or expose raw payment messages in the dashboard.

## Requirements

- Windows 10/11 and Python 3.12 (64-bit recommended).
- Internet access for Telegram and the Microsoft Khmer neural voice.
- A Telegram account that is already a member of the payment group.
- Working speakers.

## One-click setup on another PC

Clone the private repository into a normal local folder such as `C:\ABA Payment Speaker`—never inside Dropbox—then double-click `SET UP ON THIS PC.bat`. It verifies 64-bit Python 3.12, creates this PC's `.venv`, installs the pinned dependencies, preserves or creates the private `.env`, and runs the complete regression suite.

The setup script does not start Telegram monitoring. Configure this PC's `.env`, make sure the speaker application is completely closed on every other PC, and then use `Start ABA Payment Speaker.bat`.

Install the project once from a VS Code terminal:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Obtain Telegram API credentials

Use only Telegram’s official developer portal:

1. Open [my.telegram.org](https://my.telegram.org) and sign in with the same Telegram account that belongs to the payment group.
2. Choose **API development tools**.
3. Create an application. A simple title such as `ABA Payment Speaker` is sufficient.
4. Copy the numeric `api_id` and the `api_hash` into `.env`.

Telegram’s official instructions are at [Creating your Telegram Application](https://core.telegram.org/api/obtaining_api_id). Telegram currently permits one API ID per phone number.

Treat `api_hash` as private. Do not paste it into chat, screenshots, logs, or source files.

## Configure `.env`

Copy `.env.example` to `.env` if needed, then configure:

```dotenv
TELEGRAM_API_ID=your_numeric_api_id
TELEGRAM_API_HASH=your_32_character_api_hash
TELEGRAM_PHONE=+855...
TELEGRAM_SESSION_PATH=%LOCALAPPDATA%/ABA Payment Speaker/telegram_user.session

ALLOWED_CHAT_IDS=
ALLOWED_ABA_SENDER_ID=
EXPECTED_ABA_USERNAME=PayWayByABA_bot
DIAGNOSTIC_MODE=true
```

The phone must include its international country code. The default session and database locations are outside Dropbox under Local AppData.

Never commit or share:

- `.env`;
- API hash;
- phone login codes;
- two-step-verification password;
- `.session`, `.session-journal`, `.session-wal`, or `.session-shm` files.

The session file represents a logged-in Telegram account. Anyone who obtains it may be able to access that account. Protect it like a password.

## First login

Start the application:

```powershell
.\.venv\Scripts\python.exe main.py
```

The dashboard shows the setup stages:

```text
API credentials missing
Login required
Verification code required
Session authenticated
Groups detected
PayWay source detected
Production ready
```

On the first valid setup, Telegram sends a login code to your account. Enter that code only into the application’s **Telegram login** dialog. If Telegram two-step verification is enabled, a second masked password dialog appears. Neither value is stored or logged by the application.

After successful login, Telethon creates the configured session file. Later starts reuse it automatically and do not request another code unless Telegram invalidates the session or the file is moved/deleted.

## Dashboard commissioning

Diagnostic mode can observe safe metadata but is always prevented from speaking production payments.

1. Send an ordinary message in an intended group.
2. Confirm the dashboard’s **Observed group** title and numeric **Observed chat ID**.
3. Click **Add Group ID**. Repeat for every group that should announce payments.
4. Leave the application running until a genuine notification arrives from `@PayWayByABA_bot`.
5. Confirm the dashboard shows the expected username, observed numeric sender ID, group title, chat ID, and `Matches expected source: YES`.
6. Click **Verify & Save ABA IDs**. This explicit action saves the observed numeric group and sender IDs without modifying the API credentials.
7. Click **Switch to Production**, close the application, and restart it.

The application never guesses the PayWay numeric ID. Username text is only a commissioning signal and secondary production sanity check. Production requires at least one saved numeric group ID and the saved numeric sender ID.

Groups are stored as a comma-separated numeric allowlist, for example `ALLOWED_CHAT_IDS=-100111,-100222`. The listener ignores every group outside this list. Messages from every other sender remain silent.

## Parser and speaker tests

Use the built-in **Load KHR sample**, **Load USD sample**, **Parse**, and **Speak parsed test** controls. Pasted test input can never become a production payment.

Confirmed announcements:

```text
បានទទួលប្រាក់ ២ ពាន់រៀល ពីឈ្មោះ VAN VET, ធនាគារ ABA។
បានទទួលប្រាក់ ៥ ដុល្លារ ពីឈ្មោះ NHEAN MONYRACHANA, ធនាគារ ACLEDA។
```

Live commissioning also verified these narrow PayWay variations:

- merchant text followed directly by `. Trx. ID` without a later staff `by ...` fragment;
- an optional `Remark:` clause between merchant text and transaction metadata;
- `ABA KHQR (PPCBank)`, explicitly normalized to spoken bank `PPCBank`.

The deterministic institution registry also recognizes the production-observed exact labels and codes `KB PRASAC Bank Plc`, `Cambodia Post Bank Plc`, `Sathapana Bank Plc`, `ACLBKHPPXXX`, and `CPBPKHPPXXX`. Bank display names remain concise while speech uses the approved Khmer bank name. Matching is exact after harmless case, spacing, and period/comma normalization; there is no fuzzy matching.

An unfamiliar `ABA KHQR (LABEL)` does not invalidate an otherwise securely authorized, structurally valid incoming payment. It appears as `OTHER BANK`, and the spoken announcement safely omits the bank clause. The application never guesses a bank or foreign payment network. New cross-border aliases can be added to the registry only after their exact PayWay label or code is verified.

Payer names support validated Unicode letters, including Khmer names. USD cents are preserved with `Decimal` and spoken naturally, for example `$1.25` as `១ ដុល្លារ ២៥ សេន`; whole-dollar `.00` values keep the established shorter form.

These extensions came from actual observed notifications. Other unverified formats still remain silent.

Press **Test Speaker** to hear:

```text
ប្រព័ន្ធប្រកាសការទូទាត់កំពុងដំណើរការ។
```

Microsoft voice `km-KH-SreymomNeural` is used through `edge-tts`, so speech requires internet. Announcements are queued and never overlap.

## Security and duplicate behavior

- The user session is used only for incoming-message monitoring and required authentication/read operations.
- No send, reply, forward, join, leave, edit, or delete methods are called.
- API hash and phone are defensively redacted from application logging.
- Codes and 2FA passwords exist only in memory while signing in.
- Raw Telegram messages are not logged or stored.
- SQLite stores only useful privacy-safe operational fields.
- A SHA-256 key based on chat ID and message ID is reserved before speech, suppressing retries and duplicates across restarts.
- The fail-safe tradeoff favors one missed announcement after a rare crash over duplicate speech.

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## GitHub and another PC

Double-click `Sync ABA Payment Speaker to GitHub.bat` to safely initialize or sync the source repository. On its first run, create an empty private GitHub repository and paste its URL when requested. The script refuses to stage known credential, Telegram-session, or SQLite files.

Follow `OTHER_PC_SETUP.md` on the second PC. Each computer must create its own `.env`, `.venv`, Telegram session, and Local AppData database. Run the speaker on only one PC at a time.

## Troubleshooting

### API credentials missing or invalid

- API ID must be numeric.
- API hash must be the 32-character value from `my.telegram.org`.
- Phone must include `+` and its country code.
- Do not use a BotFather token; the user-session listener does not use one.

### Login code does not appear

- Check the official Telegram app first; Telegram often delivers the code there instead of SMS.
- Confirm the phone number belongs to the account that generated the API credentials.
- Close duplicate application instances.

### Login is requested every startup

- Keep `TELEGRAM_SESSION_PATH` unchanged.
- Confirm the session file still exists in Local AppData.
- Do not synchronize or move the session through Dropbox.

### Group or PayWay source stays Waiting

- Confirm the authenticated user account is a member of the correct group.
- Confirm every saved group ID corresponds to a group receiving real notifications.
- Leave diagnostic mode on until a new genuine `@PayWayByABA_bot` message arrives.
- Never save your personal sender ID as the PayWay source ID.

## Safe Windows auto-start

Only after the dashboard shows **Production ready**, test both parsers and Khmer audio. Then create a shortcut to `Start ABA Payment Speaker.bat` inside the Windows Startup folder (`Win+R`, then `shell:startup`). Do not copy the project, `.env`, or session file into Startup.

## Dependencies

- `Telethon 1.44.0`: mature MTProto user-session authentication and incoming update handling.
- `python-dotenv`: local configuration.
- `edge-tts`: online Microsoft Khmer neural speech.
- `pygame`: Windows MP3 playback.
- Standard library: Tkinter dashboard, SQLite state, logging, queues, and threading.
- `pytest`: development tests only.
