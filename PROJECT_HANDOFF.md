# ABA Payment Speaker — Project Handoff

## Purpose

This document gives another PC, developer, or Codex session the complete operational and engineering context needed to continue this project safely. It summarizes the decisions and completed work from the project conversation without copying credentials, login codes, Telegram sessions, raw private configuration, or other secrets.

Read this file together with:

- `README.md`
- `OTHER_PC_SETUP.md`
- `ABA_PAYMENT_SPEAKER_MASTER_BUILD_PROMPT.md`
- `ABA_PAYMENT_SPEAKER_UI_UPGRADE_CODEX_PROMPT.md`
- `ABA_PAYMENT_SPEAKER_MULTI_BANK_KHQR_CODEX_MASTER_PROMPT.md`

Treat the keyword instructions in the multi-bank master prompt as hard constraints.

## Non-negotiable operating rules

1. Run ABA Payment Speaker on only one PC at a time. Two PCs can announce the same Telegram payment because each PC has an independent database.
2. Never run the production application from a Dropbox folder. Use a normal local clone such as `C:\ABA Payment Speaker`.
3. Each PC keeps its own `.env`, `.venv`, Telegram `.session`, SQLite database, and logs.
4. Never commit, upload, print, or paste Telegram API credentials, login codes, 2FA passwords, session files, databases, or `.env` values.
5. Telegram source authorization must remain stricter than parser flexibility.
6. Silence is better than a false payment announcement, but an unknown bank alone does not invalidate an otherwise securely verified incoming payment.

## Current architecture

```text
Configured Telegram user session
→ allowed group ID check
→ verified PayWay numeric sender ID check
→ expected @PayWayByABA_bot username sanity check
→ deterministic incoming-payment parser
→ persistent SQLite duplicate reservation
→ dashboard update
→ sequential Khmer TTS queue
→ spoken/failed status persisted
```

Important modules:

- `app/config.py`: private environment configuration and safe `.env` updates.
- `app/telegram_listener.py`: read-only Telethon listener and strict authorization.
- `app/payment_parser.py`: anchored deterministic PayWay parser.
- `app/bank_normalizer.py`: structured exact-alias institution registry.
- `app/khmer_numbers.py`: natural KHR/USD speech, including USD cents.
- `app/database.py`: SQLite duplicate protection, spoken totals, and safe history.
- `app/audio_queue.py`: single sequential non-overlapping audio queue.
- `app/tts.py`: Microsoft Khmer neural voice through `edge-tts` and pygame.
- `app/dashboard.py`: Tkinter operational dashboard and safe diagnostics.
- `main.py`: component wiring and privacy-safe logging.

## Authorization and security

Production messages are accepted only when all of these match:

- diagnostic mode is off;
- chat ID is in `ALLOWED_CHAT_IDS`;
- sender numeric ID equals `ALLOWED_ABA_SENDER_ID`;
- sender username equals `EXPECTED_ABA_USERNAME=PayWayByABA_bot`.

Do not weaken these checks. A message that merely looks like PayWay must never bypass authorization.

The listener is read-only. It does not send, reply, forward, join, leave, edit, or delete Telegram content. Raw Telegram messages are not logged or stored. SQLite stores only privacy-approved operational fields.

Duplicate protection uses a SHA-256 event key derived from Telegram chat ID and message ID. The row is reserved before speech. This intentionally favors a possible missed announcement after a rare crash over duplicate speech.

## Parser and multi-bank behavior

Supported payment structure remains anchored to verified PayWay incoming-payment grammar:

- KHR and USD;
- exact USD cents using `Decimal`;
- comma-separated amounts;
- Latin, mixed-case, long, and validated Unicode/Khmer payer names;
- payer extracted only from `paid by NAME (*NNN)`;
- `ABA PAY`;
- `ABA KHQR (LABEL)`;
- optional `Remark:`;
- merchant text with or without a later staff `by ...` fragment.

The parser never speaks masked account fragments, merchant/location, staff/operator, dates, times, transaction IDs, APV, balances, Telegram IDs, or credentials.

Institution processing is separated into raw label, canonical institution, display name, Khmer spoken name, and mapping status. Matching is deterministic after harmless case, spacing, and period/comma normalization. There is no fuzzy matching.

Production-observed aliases include:

- `ABA PAY` → ABA
- `ACLEDA Bank Plc.` / `ACLBKHPPXXX` → ACLEDA
- `KB PRASAC Bank Plc` → KB PRASAC
- `Cambodia Post Bank Plc` / `CPBPKHPPXXX` → Cambodia Post Bank
- `Sathapana Bank Plc` → SATHAPANA
- `PPCBank` → PPCBank

The registry contains all 24 user-approved Cambodian institution display and Khmer speech names from the multi-bank master prompt.

Unknown bank/network behavior:

- payment remains valid if authorization and incoming-payment structure are valid;
- institution status remains `UNMAPPED`;
- dashboard displays `OTHER BANK`;
- TTS omits the bank clause;
- no bank or foreign network is guessed.

Literal `TESTONLY` transaction fixtures are rejected by production parsing and accepted only through the explicit safe parser-test path. Parser-test data never enters production totals or history.

## Khmer speech

Payment speech is Khmer-only:

```text
បានទទួលប្រាក់ {natural_amount} ពីឈ្មោះ {payer}, ធនាគារ {approved_khmer_bank_name}។
```

For an unmapped institution:

```text
បានទទួលប្រាក់ {natural_amount} ពីឈ្មោះ {payer}។
```

Whole-dollar `.00` values omit unnecessary cents. Non-zero cents are spoken naturally, for example `$1.25` as `១ ដុល្លារ ២៥ សេន`.

The configured online voice is normally `km-KH-SreymomNeural`. Announcements are sequential and never overlap.

## Current dashboard design

The normal dashboard hierarchy remains:

1. received amount;
2. sender name;
3. originating bank.

Current approved header:

```text
វីង វណ្ណា-ស្រីម៉ិច
ប្រព័ន្ធទទួលប្រាក់
```

- Both lines are 24 pt.
- Preferred font is `Khmer OS Muol Light`.
- Safe fallbacks are `Khmer OS Light Moul`, `Khmer OS Muol`, `Leelawadee UI`, and `Segoe UI`.
- The clock is centered at 56 pt, matching the incoming amount size.
- The date is 13 pt below the clock.
- LIVE/readiness remains at the top right.

Currency presentation:

- KHR uses bright green.
- USD uses warm gold.
- The main payment amount pulses briefly and returns to the correct currency color.

Recent announced payments:

- fixed three-row viewport;
- 14 pt row text and 44-pixel row height;
- newest successful announcement first;
- up to 1,000 successfully spoken payments from the current local day;
- scrollbar appears when more than three rows exist;
- mouse-wheel scrolling is supported;
- the complete KHR row is green;
- the complete USD row is gold;
- sender name and amount are bold;
- history refreshes after successful speech and resets on a new local day;
- rejected, muted, failed, duplicate, and test payments are excluded.

Settings, Telegram commissioning, IDs, and safe parser tests remain on the secondary Settings & Diagnostics tab.

## Database and history

No schema migration was required for the multi-bank or scrolling-history work. Existing databases remain compatible.

Daily summary and scrolling history include only rows where:

```text
parser_status = VALID
announcement_status = SPOKEN
local date = today
```

KHR and USD totals remain separate. No exchange-rate conversion is invented.

## Testing status

The latest complete suite contains 109 tests and passed after the current dashboard/history changes.

Coverage includes:

- strict Telegram authorization;
- wrong group/sender rejection;
- diagnostic-mode silence;
- duplicate persistence;
- exact KHR and USD parsing;
- Khmer Unicode payer names;
- optional remarks;
- USD cents;
- 23 supplied real KHR transactions;
- 9 explicit supplied real USD transactions;
- exact bank aliases and verified BIC codes;
- unknown bank/network safety;
- Khmer bank pronunciations;
- spoken-only totals/history;
- more than five current-day history rows;
- failed/test data exclusion;
- dashboard amount/status formatting;
- logging and local-path security.

The master prompt references a complete 69-transaction USD corpus, but only nine exact USD messages were present in the workspace. Import the remaining 60 only if the real source corpus is later supplied; do not fabricate them.

GUI smoke tests passed at 1180×800 and 960×720. The exact `Khmer OS Muol Light` font was detected on PC3. Real Khmer TTS and speaker playback also passed.

## PC and repository workflow

Primary production location on PC3:

```text
C:\ABA Payment Speaker
```

The Dropbox copy has been used as a source workspace but must not be used for production execution. GitHub synchronizes source only.

One-click files:

- `SET UP ON THIS PC.bat`: validates local non-Dropbox location, Python 3.12, `.venv`, dependencies, `.env`, and tests. It never starts production automatically.
- `Start ABA Payment Speaker.bat`: starts the application from the local `.venv`.
- `PUSH TO GITHUB.bat`: tests and invokes the secret-safe commit/push workflow.
- `PULL FROM GITHUB.bat`: refuses a running app or dirty worktree, pulls with `--ff-only`, refreshes dependencies, and tests.

Git author configured for this repository during setup:

```text
name: bunthorngnop
email: bunthorng.nop@gmail.com
```

Do not copy that identity globally unless the user explicitly requests it.

## Safe transfer sequence

On the PC where source changed:

1. Run the complete tests.
2. Double-click `PUSH TO GITHUB.bat`.
3. Wait for `SUCCESS`.

On the other PC:

1. Close ABA Payment Speaker completely.
2. Double-click `PULL FROM GITHUB.bat` in its local clone.
3. Wait for `SUCCESS`.
4. Confirm every other PC is closed.
5. Start with `Start ABA Payment Speaker.bat`.

Never copy `.env`, `.venv`, Telegram sessions, SQLite databases, or logs between PCs.

## Future improvements discussed but not approved or implemented

- named Windows single-instance lock;
- explicit TTS generation/playback timeouts;
- richer startup error dialogs;
- stricter comma-group validation for amounts;
- audio-device-tested readiness state;
- SQLite busy timeout/WAL review;
- version/commit identifier in the dashboard;
- private GitHub CI;
- complete remaining USD corpus;
- cross-PC active-instance coordination.

Do not implement these without a new explicit approval. Do not rebuild working components or add unrelated features.

## Instructions for a future Codex session

Before changing anything:

1. Read this handoff and all authoritative prompts completely.
2. Inspect the current Git status and preserve user changes.
3. Do not display `.env` values or secrets.
4. Run the complete baseline suite.
5. Keep Telegram authorization, parser validation, duplicate protection, privacy, database, and Khmer TTS behavior unchanged unless the user explicitly approves a scoped change.
6. Add tests for every behavior change.
7. Run the full suite and a proportionate GUI/speaker smoke test.
8. Update this handoff when decisions or operational behavior materially change.

## Automatic handoff maintenance

Repository-level instructions in `AGENTS.md` require future Codex sessions to maintain this document during every project conversation turn. Updates must be dated, concise, privacy-safe summaries rather than verbatim transcripts. Exact approved UI text, behavior, files, verification results, and outstanding operator actions should be preserved when relevant.

This mechanism applies when Codex is actively working in this repository. It cannot capture conversations held outside the repository/session, and it must not override an explicit request for discussion only or no file changes.

## Conversation and Decision Log

### 2026-08-30 — Cross-PC handoff and GitHub controls

- User requested a persistent project/conversation handoff plus one-click push and pull controls.
- Created `PROJECT_HANDOFF.md` as the consolidated privacy-safe source of project context.
- Upgraded `PUSH TO GITHUB.bat` to run the complete regression suite before invoking the existing secret-safe sync workflow.
- Created `PULL FROM GITHUB.bat` to refuse a running speaker or dirty worktree, pull with fast-forward-only protection, refresh pinned dependencies, and run the complete suite.
- Verified `.env` remains ignored and the complete suite passed with 109 tests.

### 2026-08-30 — Automatic future conversation summaries

- User requested that new project conversations be added automatically to the handoff.
- Added `AGENTS.md` with a mandatory handoff-maintenance protocol for future Codex sessions.
- Conversation records must remain concise and privacy-safe; credentials, session data, hidden instructions, and transient debugging details are prohibited.

### 2026-08-30 — Responsive small-display dashboard

- User approved protecting the large received amount on shorter maximized displays.
- Added normal, compact, and short responsive modes; compact mode reduces sender/bank card height, while short mode temporarily collapses the secondary status/control column so payment information retains priority.
- Reduced recent-payment viewport from five rows to three, enlarged row text from 12 pt to 14 pt, and retained scrolling through all current-day announced payments.
- Verification completed: 110 automated tests passed in both the working tree and installed application; GUI smoke checks passed at 1180×900, 1024×720, and 1024×600 with the amount visible at every size.

### 2026-08-30 — One-click test temporary-folder repair

- The GitHub push preflight reported 100 passes and 10 setup errors because pytest could not access its default `pytest-of-Wing` temporary directory; this was an environment permission failure, not an application test failure.
- Updated `PUSH TO GITHUB.bat`, `PULL FROM GITHUB.bat`, and `SET UP ON THIS PC.bat` to use a unique writable pytest base directory and disable pytest cache writes.
- Re-ran the repaired push-equivalent preflight with the fallback production runtime: all 110 tests passed.
- No commit or GitHub upload was performed automatically; the operator may double-click `PUSH TO GITHUB.bat` when ready.

### 2026-08-30 — Setup-file behavior clarified

- Confirmed `SET UP ON THIS PC.bat` prepares a normal local clone for operation: it validates 64-bit Python 3.12, creates or repairs `.venv`, installs pinned dependencies, preserves an existing `.env` or creates one from `.env.example`, and runs the full tests.
- It refuses setup from inside Dropbox and does not start Telegram monitoring or the payment speaker; the operator must close other active PCs and then use `Start ABA Payment Speaker.bat`.
