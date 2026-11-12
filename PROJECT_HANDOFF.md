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

The Dashboard header is a compact single row: the two-line Khmer shop title at left, time/date/LIVE centered across the full window, and a modern "glass ticker" NBC card at right, drawn on a Tk canvas: rounded dark card (`#0E1626`) with a cyan-to-violet gradient border, live dot, the Khmer title `អត្រាប្តូរប្រាក់ធនាគារជាតិ` (Siemreap) and the date (Orbitron), the rate in large Bahnschrift digits (38 pt, 28 pt below 1080 px) preceded by the owner-supplied NBC logo (`assets/nbc_logo.png`, subsampled to about 40 px / 30 px narrow, near-white pixels transparent, optional) and followed by a Siemreap `៛`, centred horizontally and vertically with its pill (green `▲ +n` / gold `▼ −n` against NBC's previous value, with the rate and `៛` tinted to match; neutral grey `▲▼ 0` while unchanged); the Khmer title uses the date's grey, `KHR / USD` in Montserrat, and a 7-day sparkline from the additive public `nbc_rate_history` table (one NBC value per Cambodia date). The card is 132 px high (112 px below 1080 px), so the header stays 170 px (144 px). The Dashboard is split 50% / 25% / 25% at every size: LAST PAYMENT RECEIVED (announcement status on the same title row since 2026-11-12) and the untitled recent-payments list (starting at its `AMOUNT | SENDER | BANK | TIME` headings) stacked in the left half, and the rates & gold card and the private-rates card each spanning both rows so their bottoms align. The recent-payments list height adapts (minimum two 44 px rows, maximum ten) so the Dashboard does not scroll at 1382×744; below 1080 px its BANK/TIME columns use Bahnschrift SemiCondensed. The rates & gold card `អត្រាប្តូរប្រាក់ និង មាស` is a `BANK | ទិញ $ | លក់ $` table (header row highlighted `#22304A`) for ACLEDA Notes and Wing Telegraphic Transfer Outbound plus a full-width GOLD row (title line `GOLD · XAU/USD · oz · <time>`, then USD per troy ounce, `≈ $… / ដំឡឹង` (37.5 g) and `≈ $… / ជី` (3.75 g) at the same Bahnschrift size, each local unit followed by a programmatically drawn Cambodian flag image at the figure height). Table rows size to their content (no uniform row height) so the taller gold row does not stretch the bank rows. NBC appears only in the header; ABA is not shown (ababank.com refuses automated access). Gold comes from GoldAPI.io's free plan using the owner's private `GOLD_API_KEY` in `.env`, sent only as the `x-access-token` header and redacted from logs; it is fetched at most every 12 hours (cached across restarts) with at least one hour between retries after a failure; without a key the row shows `—`. Rate figures use Bahnschrift (18 pt, 12 pt below 1080 px): ទិញ red, លក់ light blue, gold warm gold, with the gentle pulse; row tints ACLEDA `#193138`, WING `#28243A`, GOLD `#2E2716`. Every rate box shows ▲ green (`#4ADE80`) / ▼ gold (`#FACC15`) right after the figure against its previous different value, or a dim `▲▼` (`#46536B`) while unchanged; bank figures auto-shrink so cells never grow; ACLEDA (round emblem) and WING logos (60 px, 44 px narrow) sit centred under the bank names; the gold row has tight line spacing and row weight 0 so spare height goes to the bank rows; the payment amount is preceded by a currency coin icon (green `៛` for KHR, gold `$` for USD; drawn by the agent, `assets/coin_khr_*.png` / `coin_usd_*.png`) about 1.1× the digit height, vertically centred on the digits (font shrinks to stay on one line) (bank and gold previous values are stored in the public rate cache); no best-rate outline is drawn (removed 2026-11-09); arrows show only the direction of the last change (none before the first change); stale rows dim and lose arrows. The private-rates card is dark with a yellow title bar, connects automatically through a separate Telethon session restricted to one fixed group, fetches the 50 latest posts, keeps up to 200 in memory only, and shows each sender's latest post as two-line offers (tag + Bahnschrift rate with `KHR` + trend arrow + gap from NBC; then Bahnschrift amount + banks) using `USD`/`KHR` text, under a two-line `posts · 15 min` summary strip with range arrows. Posts remain unverified and separate from payment parsing, storage, and speech. When the private card is at least 300 px wide a status dot and short CONNECT/DISCONNECT button share its title bar; otherwise they sit in a yellow footer. The payment listener and group reader have separate session files. Since 2026-11-12 a canvas ticker is placed over the empty part of the notebook tab row (measured from the tab extents, so it never covers DASHBOARD / SETTINGS & DIAGNOSTICS) and scrolls right to left at about 40 px/s: `TODAY N payments · KHR … · USD …` (spoken-only totals; KHR green, USD gold), then `តម្លៃសាំងធម្មតា …៛ ▼n · តម្លៃប្រេងម៉ាស៊ូត …៛ ▼n · អនុវត្តចាប់ពីថ្ងៃទី d ដល់ d ខែ… ឆ្នាំ…` (Western digits) in amber, then a canvas-drawn gold-bar icon and `≈ $… / ដំឡឹង · ≈ $… / ជី` in gold with a dark drop shadow (from the GOLD rate). All ticker arrows use fuel colours (▲ red up, ▼ green down) and appear only after a change; fuel turns grey plus `តម្លៃចាស់` after the announced end date (or 11 days without one). The recent-payments columns are AMOUNT right, SENDER left, BANK centred, TIME right, pinned to computed widths (SENDER:BANK 11:9) so rows and headings align; long text wraps to two lines (rows 68 px instead of 44 px) and is cut with `…` beyond that. Fuel prices come from `app/fuel_prices.py` parsing Ministry of Commerce channel `-1001254362029` posts, read by the rate-group reader account (found in the same dialog scan as the private group; optional, a missing channel only logs a warning), stored in the additive `fuel_price_cache` table (single row, newest message id wins, missing change filled from the saved price). SYSTEM STATUS, TODAY, and CONTROLS are in the scrollable Operations subtab under Settings & Diagnostics. Scheduled time announcements use a separate clock service and the same sequential audio queue, with a per-item voice override so payment speech remains on its configured voice.

Important modules:

- `app/config.py`: private environment configuration and safe `.env` updates.
- `app/telegram_listener.py`: read-only Telethon listener and strict authorization.
- `app/payment_parser.py`: anchored deterministic PayWay parser.
- `app/bank_normalizer.py`: structured exact-alias institution registry.
- `app/khmer_numbers.py`: natural KHR/USD speech, including USD cents.
- `app/database.py`: SQLite duplicate protection, spoken totals, and safe history.
- `app/audio_queue.py`: single sequential non-overlapping audio queue.
- `app/rate_group_reader.py`: separate read-only session, exact target-group filtering, and in-memory post/edit/delete events for display.
- `app/rate_post_format.py`: display-only standard-row formatter, sender short names, and 15-minute summary for private-group posts; imports no payment, database, bank-registry, or speech code.
- `app/exchange_rates.py`: first-party NBC, ACLEDA, and Wing USD/KHR retrieval/parsing, SQLite cache loading, compact display formatting, and 15-minute background refresh monitor.
- `app/scheduled_announcements.py`: Cambodia-time schedule, Khmer wording, and at-most-once daily scheduling.
- `app/tts.py`: Microsoft Khmer neural voice through `edge-tts` and pygame.
- `app/dashboard.py`: Tkinter operational dashboard and safe diagnostics.
- `main.py`: component wiring and privacy-safe logging.
- `app/single_instance.py`: Windows named mutex acquired before Telegram startup.
- `app/integration_contract.py`: strict privacy-safe versioned event serialization.
- `app/integration_api.py`: optional authenticated loopback-only read API.

Optional Unified AI Lab integration is disabled by default. When enabled with a private local token, ABA exposes only sanitized authoritative status and event updates on loopback. The API reads already-approved state and is never placed between Telegram processing, duplicate reservation, the dashboard, or Khmer TTS. API configuration/bind failure never stops the authoritative payment pipeline.

## Authorization and security

Production messages are accepted only when all of these match:

- diagnostic mode is off;
- chat ID is in `ALLOWED_CHAT_IDS`;
- sender numeric ID equals `ALLOWED_ABA_SENDER_ID`;
- sender username equals `EXPECTED_ABA_USERNAME=PayWayByABA_bot`.

Do not weaken these checks. A message that merely looks like PayWay must never bypass authorization.

The private exchange-group reader is independent of payment authorization and has its own session under `%LOCALAPPDATA%\ABA Payment Speaker\rate_group_user.session`. Its source restricts history requests and new/edited/deleted message handling to the fixed target group; startup connects the reader automatically. An in-memory buffer (50 fetched, at most 200 retained) supports showing each recent sender's latest post. Posts are unverified; they are reformatted for display only and never treated as payments, stored, logged, or spoken. Phone numbers and contact/account lines are hidden from the panel. Telegram may return dialog metadata while the reader resolves a private group's access information. The Telegram account itself retains access to its other chats, so use only the consenting group member's account on a trusted PC and revoke its session in Telegram if needed.

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

- Both lines are 24 pt at wider sizes and compact to 20 pt below 1080 px.
- Preferred font is `Khmer OS Muol Light`.
- Safe fallbacks are `Khmer OS Light Moul`, `Khmer OS Muol`, `Leelawadee UI`, and `Segoe UI`.
- The clock is centered across the full window at 56 pt, compacting to 42 pt below 1080 px.
- The date is 13 pt below the clock.
- LIVE/readiness is centered below the date at 12 pt.
- The header's right column shows the glass-ticker NBC official rate card (see the architecture summary). The private exchange-group posts are in the Dashboard's third column (dark card, yellow title bar `អត្រាប្តូរប្រាក់ឯកជន - Private rates`) as two-line offers (see "Private-group display rules" below); no separate UNVERIFIED label is shown.
- The reader connects automatically at startup (CONNECT/DISCONNECT remains available), uses its own Local AppData session, and keeps posts only in memory. Its display formatting never saves posts or enters the payment/TTS path.
- The Dashboard's bank-rate card displays NBC's single official reference rate, ACLEDA Notes buy/sell, and Wing Bank Telegraphic Transfer Outbound buy/sell, all identified as KHR per USD. Its centered one-line title is `អត្រាប្តូរប្រាក់តាមធនាគារ - Bank rates`. The dark card shares the row with LAST PAYMENT RECEIVED at approximately 58% / 42% of combined rendered width and matches its rendered height. Buy figures are bold red at 14 pt; Sell figures are bold light blue at 14 pt; source/category labels are 9 pt and effective/status text is 8 pt. Effective dates are compact; rate age updates locally, and old/missing values are marked stale/unavailable. SQLite cached values display at startup; sources refresh every 15 minutes.
- SYSTEM STATUS, TODAY totals, and CONTROLS are grouped in the scrollable **Settings & Diagnostics → Operations** panel. CONTROLS is no longer on the Dashboard. On short windows, vertical scrollbars preserve access to Dashboard and Operations content rather than clipping cards.
- The private-group panel fits the header's right column independently from the bank-rate card; its height remains 152 px. The single-row header keeps the time/date/LIVE group centered across the full window.

Private-group display rules (owner-approved 2026-11-06; implemented in `app/rate_post_format.py`):

- Rows: `TAG  RATE  SIZE  BANKS`, one block per sender (latest post only, newest first, `HH:MM  short name`, `✎` when edited).
- TAG: `KHR→USD` (light blue) = poster offers riel for dollars; `USD→KHR` (light red) = poster offers dollars for riel; `·` = no clear or conflicting cue (including any `អោយ` line and bare `ABA 4091`). Cues: currency right after `ដូរ`/`ដូ`/`យក`/`ទិញ` (wanted) or after `មាន` (offered), plus a standalone leading currency (offered).
- RATE: four integer digits within 3,800–4,400, optional `.`/`,` plus 1–2 cent digits, thousands separators allowed; displayed with a dot and a `KHR` suffix (e.g. `4089.5 KHR`) at 14 pt bold (12 pt below 1080 px), followed by a memory-only ▲/▼ against the sender's previous different rate in that direction and a small gap from the current NBC official rate (e.g. `+5`). `$4,000` (dollar sign touching a grouped number) and anything followed by `$` are sizes.
- SIZE: shown on the offer's second line at 12 pt bold with the banks; thousands separators; `USD`/`KHR` only if the post marked a currency; `លាន` → `M KHR`; unmarked sizes get no currency. All `$`/`៛` in displayed text become `USD`/`KHR`.
- BANKS: display-only short names `ABA`, `AC`, `Wing`, `Amret`, `ស្ថាបនា`, `KB`, `Cana`, plus `គ្រប់កុង`/`អីក៏បាន`; separate from the payment bank registry.
- Riel words → `៛`, dollar words → `$`, glued text spaced, `*`/`**`/`x`/`=` → `×`. A rate-less line directly above a rate line in the same blank-line group is joined to it; two rate lines are never merged.
- Hidden: phone numbers (removed before rate detection), contact/"Acc" lines, `យក…` receiving-bank lists without numbers, blank lines. Parenthetical notes become small notes (`No ABA`, `min 5,000$`). Rate-less offers show as muted cleaned text.
- Summary strip: one line per direction, low–high tagged rate from each sender's latest post in the last 15 minutes plus `KHR` and a ▲/▼ against the previous different range midpoint, labelled `posts · 15 min`; no best rate, no bank.
- Glow/fade: a sender block glows about 10 seconds for live posts with new or changed offers (history loaded at connect does not glow); posts older than 15 minutes are grey; posts older than one hour move to the bottom.
- Edits update in place; deletions remove the post; photo captions are formatted, captionless photos show `[photo — see Telegram]`; text inside images is not read.
- Short names drop emoji, anything after `(`/`👉`, and 3+ digit groups; cut at about 18 characters.

Scheduled Khmer time announcements use Cambodia time:

- Sunday–Wednesday and Friday–Saturday at 16:10 and 18:10;
- Thursday at 16:05 and 18:05, prefaced with a Khmer equivalent of “Today is Thursday.”

They use `km-KH-PisethNeural` through the existing sequential audio queue. Since 2026-11-10 there are also hourly announcements every day from 08:00 to 22:00 (`នៅពេលនេះម៉ោង {hour} {period}`, no final `។`; ព្រឹក 8–11, `១២ ថ្ងៃត្រង់`, រសៀល 1–5 pm, ល្ងាច 6 pm, យប់ 7–10 pm), skipped if they cannot start within 60 seconds of the hour (`AudioItem.expires_at`). A payment-monitoring alert (`app/system_alerts.py`) speaks pre-recorded male-voice files from `assets/alert_*.mp3` when the listener's 30-second Telegram ping has failed for 2 minutes (network or revoked login), repeats every 10 minutes, announces recovery once, ignores mute (`AudioItem.ignore_mute`), and is enabled only in production mode. Payment announcements retain the configured voice. SQLite claims each daily slot at most once across restarts; missed slots are skipped rather than played late. The scheduler respects mute and does not alter Windows system volume.

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

Settings, Telegram commissioning, IDs, and safe parser tests remain on the secondary Settings & Diagnostics tab. System health, TODAY totals, and Dashboard controls are available together in its Operations subtab.

## Database and history

No schema migration was required for the multi-bank or scrolling-history work. Existing databases remain compatible.

The additive `exchange_rate_cache` table stores only public rate values, categories, source effective dates, last successful fetch times, and refresh errors. The `scheduled_announcements` table stores claimed local dates/slots to prevent repeats across restarts. Neither table stores transaction content or credentials.

Daily summary and scrolling history include only rows where:

```text
parser_status = VALID
announcement_status = SPOKEN
local date = today
```

KHR and USD totals remain separate. No exchange-rate conversion is invented.

## Testing status

The latest complete workspace suite contains 231 tests and passed on 2026-11-07 after the rates & gold card, glass NBC card, and 50%-width recent-payments layout (run with the production installation's Python 3.12.10 interpreter because the workspace `.venv` points to a missing base interpreter).

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
- Dashboard placement of the rate card, Operations placement of SYSTEM STATUS, TODAY, and CONTROLS, exact responsive width matching, and 900×600 responsive/scroll behavior;
- first-party exchange-rate parsing, persistence, previous-value tracking and trend arrows across restarts, refresh failure handling, NBC-versus-buy/sell formatting, compact effective dates, and stale/unavailable display;
- gold price parsing/validation, exact ដំឡឹង/ជី conversion, 12-hour quota-safe refresh with hourly retry after failure, header-only key handling and log redaction, and NBC daily history;
- the 50/25/25 Dashboard columns with stacked payment/recent cards and full-height side cards, rates & gold table, best-rate outlines, glass NBC canvas card with sparkline, today strip, two-line private offers with USD/KHR, sender trends, NBC gaps, glow/fade ordering, and responsive fit at 900×600, 1180×800, and 1382×744;
- fixed-group private-reader isolation from payment and announcement events, including edit/delete filtering and photo placeholders;
- display-only private-post formatting: every rate notation, rate band, direction cues and ambiguity, line joining, contact/phone hiding, bank short names, notes, sender short names, the 15-minute summary, and the formatter's import independence (synthetic phrases only);
- Cambodia-time schedules, Thursday wording, missed-slot skipping, persistent once-per-slot claims, per-item voice routing, and mute handling;
- logging and local-path security.

The master prompt references a complete 69-transaction USD corpus, but only nine exact USD messages were present in the workspace. Import the remaining 60 only if the real source corpus is later supplied; do not fabricate them.

GUI smoke tests passed at 1180×800 and 960×720. The exact `Khmer OS Muol Light` font was detected on PC3. Real Khmer TTS and speaker playback also passed.

The 2026-11-04 Dashboard layout smoke measured the top-right reader at exactly 220×152 px at 900×600 and 250×152 px at 1180×800. At 900×600 the payment/right-column content remains available in a vertically scrollable Dashboard; the header clock remains centered and the right column remains visible. The 1180×800 view also uses scrolling for the full history layout.

## PC and repository workflow

Primary production location on PC3:

```text
C:\ABA Payment Speaker
```

The Dropbox copy has been used as a source workspace but must not be used for production execution. GitHub synchronizes source only.

The approved Dashboard/rate layout is now deployed to the PC3 production clone. The application was restarted through `Start ABA Payment Speaker.bat` and the visible Dashboard was verified after restart. The top-right reader is 220×152 px at the 900×600 minimum layout; the three-bank card, Operations subtab, and responsive Dashboard scrolling are active. The first monitor refresh populated the NBC, ACLEDA, and Wing cache with values and no source errors. Production `.env`, Telegram sessions, SQLite database, and logs remain local and are not part of the deployment.

One-click files:

- `SET UP ON THIS PC.bat`: validates local non-Dropbox location, Python 3.12, `.venv`, dependencies, `.env`, and tests. It never starts production automatically.
- `Start ABA Payment Speaker.bat`: starts the application from the local `.venv`.
- `PUSH TO GITHUB.bat`: tests and invokes the secret-safe commit/push workflow.
- `PULL FROM GITHUB.bat`: checks that no app is running, displays and refuses a dirty worktree without overwriting local changes, pulls with `--ff-only`, refreshes dependencies, and tests. If the pull is blocked by local changes, preserve and review them or use a clean clone; do not force/reset.

PC3 Windows startup configuration (local operating-system state, not synchronized by GitHub):

- Task Scheduler task: `ABA Payment Speaker`;
- triggers (2026-11-09): current user logon, workstation unlock, and an always-on time trigger, each repeating every 1 minute indefinitely as a watchdog; `MultipleInstances=IgnoreNew` plus the app's single-instance mutex prevent duplicates, so a crashed or closed ABA is restarted within about a minute while the user is signed in (verified: 38 s after a simulated crash). The pre-change task definition was exported to the session scratch folder as `aba_task_backup_20261109.xml`;
- action: `C:\ABA Payment Speaker\.venv\Scripts\pythonw.exe "C:\ABA Payment Speaker\main.py"`;
- working directory: `C:\ABA Payment Speaker`;
- configured to continue on battery power with no execution time limit.

The task starts the dashboard automatically after this Windows user signs in.

Deploying with the watchdog active: run `Disable-ScheduledTask -TaskName 'ABA Payment Speaker'` before closing ABA (otherwise it is restarted within a minute, possibly mid-copy), copy and test, then `Enable-ScheduledTask` and `Start-ScheduledTask`. To stop ABA deliberately, disable the task first. Native crash stack traces (code locations only) are written to `C:\ABA Payment Speaker\logs\faulthandler.log` (enabled in `main.py`). Restarting after an agent deployment: start ABA with `Start-ScheduledTask -TaskName 'ABA Payment Speaker'` (or let the owner double-click the launcher), not by running `Start ABA Payment Speaker.bat` from an agent tool session. On 2026-11-09 every copy launched from the agent's tool session was terminated when that session's command ended (about 2–4 minutes, or as soon as the command returned), which looked like a crash but was not an application fault. Copies started by the scheduled task run independently. An instance started by the task may not accept a window-close request from the agent; then ask the owner to close it. The old instance can take about 2 minutes to exit, and the single-instance mutex refuses a new start until it has. It does not solve cross-PC coordination: every other speaker PC must remain closed to prevent duplicate announcements.

Dashboard display placement:

- startup checks the active Windows monitor work areas for up to approximately eight seconds;
- when an active non-primary monitor is available, the dashboard moves to it and maximizes;
- if multiple non-primary displays exist, it selects the one physically closest to the primary display;
- if no secondary monitor becomes available, the dashboard opens at normal 1180×800 size, centered within the primary monitor where possible;
- monitor placement failure never stops payment monitoring.

Git state (2026-11-10, Task A of the architecture review): all features deployed since 2026-11-04 (exchange rates and gold, private-group reader, dashboard redesign, hourly announcements, payment-monitoring alerts, crash logging) are now committed in the Dropbox workspace on `feature/unified-ai-lab-integration`, on top of `3b007d6` (= GitHub `main`). With owner approval they were fast-forwarded into `main` and pushed (`4fe3eba`), followed by the reader shutdown fix: GitHub `main` = `9add224` (2026-11-10). Agents keep working on `feature/unified-ai-lab-integration`. Production (`C:\ABA Payment Speaker`) is still the August `main` clone (`8807561`) with a copied, uncommitted overlay whose app code and assets are byte-identical to the workspace. The review recommends switching production to `git pull` deployments after the push (owner approval needed for the production reset). `.gitignore` now also excludes owner images/documents (`*.jfif`, `*.docx`, root `nbc_logo.png`), `.venv*/`, `.sync-url-test-*/`, `reports/` (two older reports remain tracked), and the review files `SYSTEM_BRIEF_FOR_REVIEW.md`, `PRODUCTION_STATUS_REPORT.md`, `ARCHITECTURE_REVIEW.md`.

Rate-group reader threading rule (2026-11-10): the reader's Telethon client and its SQLite session are used only by the `telegram-rate-group-reader` thread. `RateGroupReader.stop()` never calls client methods; it cancels the reader task on the reader's own loop (`call_soon_threadsafe(task.cancel)`), and the `finally` block in `_run_async` is the only place that disconnects. Calling `client.disconnect()` from another thread is unsafe even inside `run_coroutine_threadsafe(...)`, because Telethon's `disconnect()` runs `run_until_complete` on the calling thread's own loop; this caused the 0x819f2 access violations. Deployed to production 2026-11-10 23:51 (`9add224`); 48-hour watch running. Since 2026-11-12 `TelegramListener.stop()` (payment listener) follows the same rule: it cancels the listener task on the listener's own loop and its `finally` is the only disconnect (owner approved after the 21:34 shutdown crash). Payment handling was not changed. `main.py` logs why the dashboard ended and runs every shutdown step independently (`run_cleanup_steps`).

Git author configured for this repository during setup:

```text
name: bunthorngnop
email: bunthorng.nop@gmail.com
```

Do not copy that identity globally unless the user explicitly requests it.

## Safe transfer sequence

On the PC where source changed:

1. Confirm the intended source changes are on the local `main` branch. The current sync script pushes `main` only.
2. Double-click `PUSH TO GITHUB.bat`; it runs the complete tests before syncing.
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

## ABA Multi-PC Stage 1 status

- `aba_announcement_core/` is a versioned (0.1.0), pure standard-library package for Khmer amount wording, approved exact bank aliases, safe event schema validation, announcement text, and one-way local playback state transitions.
- It is not imported by `main.py`, `app/`, the dashboard, Telegram listener, integration API, or any live process. It does not connect to a network, read a database, or access credentials/sessions.
- Compatibility is covered by synthetic parity tests against the existing Khmer amount and bank normalization helpers. Unknown banks remain display-only as `OTHER BANK` and omit the bank clause from speech.
- The package-local event schema is version 1 and includes a source epoch/sequence, UTC timestamps, integer KHR/USD minor units, approved bank identifiers, and `QUEUED`/`MUTED`/`SPOKEN`/`FAILED` source states. It is not the current production v1 API contract.
- Stage 1 focused tests passed: 29 tests using synthetic fixtures only. See `reports/codex/ABA_ANNOUNCEMENT_CORE_STAGE1_REPORT.md`.
- Future relay/viewer work still depends on a separately approved and implemented v2 loopback source contract with immutable ordered updates, epoch/reset signaling, and a content-free bootstrap/high-water barrier. Do not proceed to Stage 2 without owner approval.

## Conversation and Decision Log

### 2026-11-12 — Compact payment card, tab-row ticker, Ministry fuel prices

- Discussion turns (no changes at the time): owner asked to put the ANNOUNCED status on the LAST PAYMENT RECEIVED row, remove the `RECENT ANNOUNCED PAYMENTS — TODAY` title (list starts at `AMOUNT | SENDER | BANK | TIME`), move today's totals into a right-to-left scrolling ticker in the empty part of the DASHBOARD / SETTINGS & DIAGNOSTICS tab row, and add fuel prices with arrows (▲ red = price up, ▼ green = price down). Research: no fuel company or official site publishes Super/LPG as readable text (PTT, Caltex, Sokimex redirect elsewhere; TotalEnergies does not resolve; Tela shows an image; Khmer Times articles return 403; aggregator figures disagree with Ministry figures). Facebook was ruled out (login wall, automated reading not allowed). Owner then chose regular (សាំង) and diesel (ម៉ាស៊ូត) only, from the official Ministry of Commerce Telegram channel `-1001254362029`, confirmed the rate-group reader account is subscribed, and supplied one public announcement post as the format sample (used as a test fixture; public, not private data).
- Owner approved implementation and deployment. Implemented: new `app/fuel_prices.py` (parser for Khmer/Western digits, `ចុះថ្លៃ` / `ឡើងថ្លៃ` / `នៅដដែល` changes, Khmer month dates, 2,000–10,000 ៛ sanity band, merge rule: newest message id wins and a missing change is filled from the saved price, staleness after the announced end date or 11 days); `app/rate_group_reader.py` finds the channel in the same dialog scan (optional), reads its recent history and listens for new/edited posts, publishing only parsed prices; additive single-row `fuel_price_cache` table in `app/database.py`; `main.py` merges, saves and passes saved prices to the dashboard at startup; `app/dashboard.py` title-row status, untitled list, ticker canvas placed by measuring the tab extents (never covers the tabs), about 40 px/s. Preview at 1382×744: history list 133 → 211 px (about 3 → nearly 5 rows); at 900×600 the Dashboard no longer needs a scrollbar.
- Tests: new `tests/test_fuel_prices.py` (14) and a ticker placement/scroll/fuel test in `tests/test_dashboard_ui.py`. Workspace suite 275 passed; production suite 246 passed after the second deploy.
- Deployed twice, watchdog-safe, with SHA-256 verification: 21:31–21:32 (`6868989`, 8 files), then 21:34–21:35 (`b90c634`, 3 files) after the first run found no fuel post in the latest 30 channel messages. The follow-up scans 200 posts, accepts spelling variants (no header or `=` needed; ម៉ាស៊ុត / ម៉ាសូត) and logs structure-only counts. Result: 200 posts back to 2026-11-07 16:02, only 20 with text, 1 containing the fuel word and none containing សាំង or ម៉ាស៊ូត, so the price lines appear to be inside the announcement image (the owner's sample text was probably copied from the image), or encoded differently. The ticker currently shows `សាំង … · ម៉ាស៊ូត …`. Not yet resolved; options were put to the owner.
- Incident during deployment: native crash at 2026-11-12 21:34:49 (`python312.dll+0x819f2`, Event 1000) in the shutdown before the second deploy. The stack is the deferred payment-listener race: main thread in `TelegramListener.stop()` (`app/telegram_listener.py:238`) → Telethon `disconnect` → `session.close`, while the listener thread was in `set_update_state`. Earlier shutdowns (2026-11-11 12:44, 2026-11-12 21:31) logged the non-fatal form `Shutdown step failed: payment listener` (`sqlite3.InterfaceError`). The rate-group reader shut down cleanly every time. 48-hour watch until 2026-11-12 23:51: no reader InterfaceError and no crash from normal running; the only crash is this listener one at deploy shutdown.
- Shutdown logging confirmed working: the 2026-11-11 12:44 restart was `Dashboard window closed; shutting down` (window closed), not a crash.
- Pending owner decisions: how to obtain the fuel prices if they are image-only; approval to apply the same shutdown fix to `TelegramListener.stop()`; push of `6868989`, `b90c634` and this handoff to GitHub (committed locally on `feature/unified-ai-lab-integration` only; GitHub `main` is still `9add224`).

### 2026-11-12 — Payment-list alignment, Khmer fuel wording, gold in the ticker, listener shutdown fix

- Owner requested: AMOUNT right, SENDER left, BANK centred, TIME right, with long text allowed to wrap to two lines; fuel wording `តម្លៃសាំងធម្មតា … តម្លៃប្រេងម៉ាស៊ូត … អនុវត្តចាប់ពីថ្ងៃទី … ដល់ … ខែ… ឆ្នាំ…`; different colours for the KHR and USD totals; gold per ដំឡឹង and ជី in the ticker with a sizable gold icon and text shadow. Decisions: spelling ដំឡឹង; Western digits everywhere; ticker arrows (gold included) use the fuel colours ▲ red / ▼ green (rates card unchanged); order totals → fuel → gold. Owner said the Ministry prices are written as text under the post, chose the agent's suggestion to fix `TelegramListener.stop()` now, and approved pushing.
- Implemented (`4f04038`): history columns pinned to computed widths (SENDER:BANK 11:9; headings put spare width in an empty fifth column so they stay aligned when the list scrollbar shows), `fit_two_lines` wrapping with `…`, 68 px rows only when wrapping; ticker totals KHR green / USD gold, Khmer fuel labels and `fuel_period_khmer`, canvas-drawn gold bar plus gold text with a `#3B2A00` shadow from the GOLD rate; fuel parsing now compares Khmer marks in canonical order and accepts `៛`; `TelegramListener.stop()` cancels the listener task on its own loop (payment handling untouched). New `tests/test_telegram_listener_shutdown.py` (3; two fail on the old code by detecting `disconnect` on `MainThread`), more fuel and dashboard tests. Workspace suite 283 passed; production 254 passed.
- Deployed 22:12–22:13 (7 files, SHA-256 verified). The 22:12:14 shutdown ran the old listener code and crashed with the known race (`telegram_listener.py:238 stop`, `0x819f2`); the fixed listener is now running (ABA up from 22:13:38).
- Fuel prices still not found after the canonical-order change: the only channel post with the fuel word has no `រៀល`/`៛`, no `=`, and one number group; no post contains សាំង or ម៉ាស៊ូត in any mark order. So the prices are not in the channel posts' own text (likely inside the image, or in comments/another channel). Ticker shows `តម្លៃសាំងធម្មតា … · តម្លៃប្រេងម៉ាស៊ូត …` until resolved; asked the owner where exactly the text appears.

### 2026-11-10 — Production status report and Git recovery (Task A)

- Read-only request: inspect production against the workspace and write `PRODUCTION_STATUS_REPORT.md` for an outside reviewer (kept out of Git). Findings: production app code and assets are byte-identical to the workspace; GitHub `main` lacks every feature since 2026-11-04; production suite 225 passed (the 29 extra workspace tests are `test_announcement_core.py`); 16 `pythonw.exe` access violations in 7 days, and the first faulthandler stack (19:53:11) shows `RateGroupReader.stop()` and the reader thread disconnecting the same Telethon session concurrently; 35 TTS failures (34 HTTP 429) with no retry; `tests/test_single_instance.py` writes into the real `logs/faulthandler.log`.
- The reviewer's `ARCHITECTURE_REVIEW.md` proposed order 3 (Git) → 2 (crash) → 1a/1b (missed speech) → 4 (NBC). Owner then asked for Task A (Git recovery, workspace only) and Task B (reader shutdown race, after A is pushed), stopping for approval before merge/push and before deployment.
- Task A done: `.gitignore` updated per review Priority 3 step 1; six commits on `feature/unified-ai-lab-integration` (ignore rules; exchange-rate monitor; private-group reader and formatter; hourly announcements and alerts; dashboard redesign; main/config/database wiring with crash logging), plus a docs commit. Rate-post test fixtures were confirmed synthetic before committing. Full workspace suite: 254 passed. Intermediate commits are grouped by feature and were not tested individually.
- Owner approved the merge and push: `main` fast-forwarded to `4fe3eba` and pushed; GitHub `main` confirmed at `4fe3eba`.
- Task B (workspace only, uncommitted): `RateGroupReader.stop()` now cancels the reader task on its own loop and never touches the client from another thread; the `finally` disconnect runs to completion even if a second stop arrives; the thread is joined with a 15 s timeout and a warning is logged if it is still alive; the Dashboard DISCONNECT path keeps `stop(wait=False)` so the Tk thread never blocks, under the same rule. Root cause confirmed in the installed Telethon 1.44: `client.disconnect()` called on the main thread runs `run_until_complete` there, so the old `run_coroutine_threadsafe(self._client.disconnect(), loop)` disconnected on the main thread while the reader thread was saving its session (matches the 19:53:11 faulthandler stack). `main.py` now logs `Dashboard window closed; shutting down` or the exception that ended `dashboard.run()`, before cleanup, and runs each cleanup step independently (`run_cleanup_steps`). `tests/test_single_instance.py` writes its crash log to a temp folder (verified: the real `logs/faulthandler.log` is unchanged by a full run).
- Tests: new `tests/test_rate_group_reader_shutdown.py` (7 tests: stop while connecting, while connected, during disconnect, Dashboard non-blocking stop, reconnect after stop, stop without start, cleanup steps). Against the previous code, 4 of its reader tests fail by detecting `disconnect` on `MainThread`. Full workspace suite: 261 passed; `git diff --check` passed.
- Owner approved Task B deployment. Committed as `9add224` ("Fix rate-group reader shutdown race and make shutdown cleanup independent"), fast-forwarded `main` and pushed; GitHub `main` = `9add224`.
- Deployed to production 2026-11-10 23:48–23:51, watchdog-safe: previous production files backed up to the session scratch folder; task disabled; ABA closed (the running instance had started 23:35:40 after another crash); `app/rate_group_reader.py`, `main.py`, `tests/test_single_instance.py`, `tests/test_rate_group_reader_shutdown.py` copied and all four SHA-256 hashes matched; production suite 232 passed (225 + 7 new), and the real `logs/faulthandler.log` was not written by the tests; task re-enabled and started; ABA running and responding from 23:51:02, payment session authenticated 23:51:05. The task's last result `0x800710E0` is Task Scheduler refusing a duplicate start while the instance runs (`IgnoreNew`).
- Further confirmation of the root cause: on the old code, a crash at 23:35:21 (`python312.dll+0x819f2`, Event 1000) had the same two-thread signature with the roles reversed (main thread in `set_update_state` via `rate_group_reader.py:262 stop` → `main.py:192`; reader thread in `session.close`).
- Match check against `9add224`: workspace and GitHub `main` are both `9add224`. In production every `app/*.py`, `main.py`, asset and shared test matches the commit (some files differ only in CRLF line endings). Production still differs in files outside the deployment: `.env.example`, `.gitignore`, `OTHER_PC_SETUP.md`, `PROJECT_HANDOFF.md`, `PULL FROM GITHUB.bat`, `PUSH TO GITHUB.bat` differ, and `aba_announcement_core/`, `tests/test_announcement_core.py`, its fixture, the multi-bank prompt and `reports/codex/*` are absent. Production Git is still the August `8807561` clone with an uncommitted overlay.
- **48-hour watch started 2026-11-10 23:51** (until about 2026-11-12 23:51). Success = no new crash dumps in `logs/faulthandler.log`, no new `pythonw.exe` Event ID 1000, and no `Rate-group reader stopped (InterfaceError)` in `logs/aba-speaker.log`. Also check that any shutdown now logs `Dashboard window closed; shutting down` or `Application stopped by an unexpected error`.
- Owner decisions: do NOT change `TelegramListener.stop()` (the payment listener has the same unsafe pattern, shutdown only) until after the 48-hour watch, as a separate change. Do NOT switch production to `git pull` or run `git reset --hard` yet.

### 2026-11-10 — Hourly time announcements and payment-monitoring alert

- Discussion turns (no changes at the time): owner requested daily hourly male-voice announcements at the exact hour, extended to 08:00–22:00, with wording `នៅពេលនេះម៉ោង …`: 12:00 `ថ្ងៃត្រង់`, 1–5 pm `រសៀល`, 6 pm `ល្ងាច`, 7–10 pm `យប់`, no final `។`; late announcements follow a playing payment but are skipped beyond 60 seconds (agent's suggestion accepted). Asked about other announcement options; agent noted Microsoft offers only two Khmer voices (both in use) and suggested a system alert. Owner approved the alert: two sentences as proposed, 2-minute delay, 10-minute repeat, plays even when muted, at any time (option A), separate `សូមចូល Telegram ឡើងវិញ` for login problems.
- Owner approved implementation and deployment. Implemented: `app/scheduled_announcements.py` (hourly slots and wording, separate `enqueue_hourly`), `app/audio_queue.py` (`expires_at` skip and `ignore_mute`), `app/tts.py` (`RecordedSpeech`, shared playback), new `app/system_alerts.py` (`PaymentHealthAlerts`), `app/telegram_listener.py` (30-second `PingRequest` health loop with a 20-second timeout, login-error classification, unexpected stops reported unhealthy), `main.py` wiring. The three alert sentences were recorded once with edge-tts (Piseth) into `assets/alert_disconnected.mp3`, `alert_login.mp3`, `alert_reconnected.mp3`; the TTS service briefly returned HTTP 429 during recording and succeeded on retry.
- Tests: new `tests/test_hourly_announcements.py`, `tests/test_system_alerts.py`, and additions to `tests/test_audio_queue.py`. Full workspace suite passed (254); `git diff --check` passed.
- Deployment (watchdog-safe: task disabled, ABA closed cleanly after about 22 hours without a crash, 14 files copied and SHA-256 verified, production suite 225 passed, task re-enabled and started). ABA started 19:29 and was still running and responding about 3 minutes later; the app log showed no alert or recovery lines (only those line types were counted), so health pings were succeeding. No commit or push was made.

### 2026-11-09 — Crash logging and watchdog restart (owner approved A, B, and crash logging)

- Owner asked why ABA does not start with Windows: the task starts it at sign-in of user Wing (last full boot was 2026-11-05), not on wake/unlock and not before sign-in; crashes also made it look as if it never started. Agent recommended A (restart after a crash), B (start on unlock), and crash logging, and advised against C (automatic Windows sign-in, a security trade-off). Owner approved A, B, and crash logging.
- Crash logging: `main.py` now enables `faulthandler` (all threads) to `logs/faulthandler.log` with a start marker per run; new `tests/test_crash_log.py`. Workspace suite 238 passed; production suite 209 passed. Deployed `main.py` and the test (backup of the previous `main.py` taken; SHA-256 verified).
- Watchdog: Task Scheduler's restart-on-failure does not reliably cover crashes after start, so the task now has logon, unlock, and an always-on time trigger, each repeating every minute indefinitely, with `IgnoreNew`. A simulated crash (force-stopping the interpreter) was restarted by the task in 38 seconds with a single instance. Task backup XML saved in the session scratch folder.
- Next: when the next real crash occurs, read only the stack frames in `logs/faulthandler.log` to identify the faulting code path, then propose a fix for approval.

### 2026-11-09 — Incident: ABA crashing (access violations), service restored, root cause open

- While deploying the latest approved build, ABA was found not running. Windows Application log (Event ID 1000, module names only) shows repeated `pythonw.exe` access violations (0xC0000005): faulting module `python312.dll` at the same offset (0x819f2) or `sqlite3.dll`. Entries on 2026-11-07 coincide with deployment shutdowns; on 2026-11-09 from about 19:18 copies crashed during normal running, minutes to about 40 minutes after starting. The copy started by the logon task at 08:31 had run about 10.5 hours without crashing.
- Correction to the earlier entry today: the earlier "tool session terminates launched copies" explanation was incomplete; at least the scheduled-task copy started 20:14 crashed by itself (task result 0xC0000005 at 20:52). Starting via the scheduled task is still preferred.
- The stable 2026-11-07 dashboard build (restored from backup) also crashed about 4 minutes after starting, so the crash is not caused by the 2026-11-09 display changes. A 6-minute off-screen stress test of the workspace dashboard with synthetic events (no Telegram/audio/production data) did not crash. All database methods use the shared lock except the rarely used `announced_today` fallback.
- Service restored with the approved current build (production suite 208 passed), started 21:06 via the scheduled task. It may crash again until the cause is found.
- Proposed next steps (awaiting owner approval): enable Python `faulthandler` to write crash stack traces (code locations only) to a file in the production `logs` folder; optionally configure the scheduled task to restart ABA automatically after a failure as a safety net; then fix the identified cause.

### 2026-11-09 — One arrow at a time, no outlines, centred bank names, gold unit arrows, compact payment card

- Discussion turn (no changes at the time): owner noted WING's figures were outlined (the best-rate outline), both arrows showing at once (the dim `▲▼` unchanged marker), bank names not aligned with logos, missing arrows on the gold ដំឡឹង/ជី lines, and wanted more room for RECENT ANNOUNCED PAYMENTS — TODAY. Agent explained tightening bank rows would not add transaction rows; owner chose compacting the payment card (option b) and removing the outline entirely.
- Owner approved implementation and deployment. Implemented: best-rate outline removed; each figure shows only the direction of its last change (green ▲ / gold ▼), or no arrow before its first change; the NBC pill likewise no longer shows `▲▼ 0`; ACLEDA/WING names centred above their logos; gold ដំឡឹង/ជី lines show the gold arrow after their flags; payment card spacing tightened (title, amount row minimum height 96/90/80, announcement, sender/bank boxes, today line) with text sizes unchanged. At 1382×744 the payment card went from about 320 to 273 px and the recent list from 88 to 133 px (three rows), still without a Dashboard scrollbar.
- Files: `app/dashboard.py`, `tests/test_dashboard_ui.py`, README, and this handoff. Full workspace suite passed (237); `git diff --check` passed.

### 2026-11-09 — ABA kept stopping after agent restarts (cause found, not a code fault)

- After deploying the coin icons (production suite 208 passed; 28 files SHA-256 verified; banknote PNGs removed from production `assets\`), ABA started from the agent session stopped within 2–4 minutes. Earlier agent-started copies today had also disappeared. A diagnostic run with crash reporting (only error/traceback lines inspected; none found) stayed up while the agent command ran and vanished when it ended: processes launched from the agent's tool session are terminated with it. The owner's own restart attempt earlier was most likely refused by the single-instance mutex while the previous copy (about 2 minutes to exit) was still shutting down.
- Fix applied: started ABA via `Start-ScheduledTask -TaskName 'ABA Payment Speaker'`; verified it stayed running and responding across separate commands for over 5 minutes. The main PC workflow section now documents this restart method. No application code change was needed.
- Note: an ABA instance started by the task may not accept the agent's close request; ask the owner to close it when deploying.

### 2026-11-09 — Currency coin icons replace banknotes

- Owner felt banknote images could confuse and supplied `riel_logo.jfif` and `dollar_logo.jfif`. Discussion (no changes at the time): the riel image carries a faint diagonal watermark grid typical of stock-icon previews, and the two images have mismatched styles. Owner chose option A: a matching pair drawn by the agent.
- Implemented: anti-aliased coin icons drawn with Windows System.Drawing (green gradient circle with a white `៛` in Noto Sans Khmer; gold gradient circle with a white `$` in Segoe UI; glyphs scaled to the same drawn height), composited on the payment-card surface, at heights 64 down to 22 px in `assets/coin_khr_*.png` / `coin_usd_*.png`. The payment amount uses them at about 1.1× digit height (56 px at 56 pt), vertically centred and on one line. The banknote PNGs were removed from `assets/` in the workspace and production. The owner's `riel_logo.jfif` and `dollar_logo.jfif` are not used and remain in the workspace root.
- Files: `app/dashboard.py`, `tests/test_dashboard_ui.py`, coin PNGs, README, and this handoff. Full workspace suite passed (237); `git diff --check` passed; previews unchanged in geometry (no scrollbar at 1382×744).

### 2026-11-09 — Larger centred bank logos, compact gold row, larger centred banknote

- Owner requested: double the ACLEDA and WING logos and centre them in the bank column; tighter gold-row line spacing to give the two bank rows more room; a larger banknote centred vertically.
- Implemented in the workspace: regenerated `acleda_logo_60/44.png`, `wing_logo_60/44.png`, and banknotes up to 70 px with the same System.Drawing conversion; logos 60 px (44 px narrow) centred under the bank names; gold row labels without extra padding, Khmer unit names 12 pt (9 pt narrow), title padding reduced, and gold row weight 0; banknote target height 1.25× digit height (64 px at 56 pt) with a computed top offset so it centres on the digits rather than the label box. Card geometry at 1382×744 unchanged (no scrollbar).
- Files: `app/dashboard.py`, `tests/test_dashboard_ui.py`, new PNGs in `assets/`, README, and this handoff. Full workspace suite passed (237); `git diff --check` passed.
- Owner approved deployment. Backed up the four production files; no ABA process was running at deployment time (nothing to close). Deployed `app\dashboard.py`, `tests\test_dashboard_ui.py`, README, this handoff, and all `assets\*.png` (33 files, SHA-256 verified). Production suite passed (208). Started with `Start ABA Payment Speaker.bat`; maximized at 1382×744 and responding. No commit or push was made.

### 2026-11-09 — Bank logos, private-style arrows, banknote before the payment amount

- Discussion turns (no file changes at the time): owner asked for bank-box arrows matching the private card, ACLEDA/WING logos, fixed row/column sizes, and banknote images replacing `$`/`៛` in LAST PAYMENT RECEIVED. Agreed details: arrows right after each figure, `▲` green / `▼` gold, a dim `▲▼` while unchanged (owner rejected `↕`); logos replace the "Notes" / "TT outbound" text under the bank names; ACLEDA uses its round emblem cropped from the supplied wide logo (agent's suggestion accepted); the banknote height equals the digit height with natural width; amount and note never wrap.
- Owner approved implementation and deployment ("approve, implement and deploy").
- Owner-supplied JPEGs (`acleda_logo.jfif`, `wing_logo.jfif`, `khmer_20000_riel.jfif`, `100_dollars.jfif`, plus `nbc_logo.png`) were converted once, with Windows System.Drawing high-quality resampling, into display-sized PNGs in `assets/` composited onto their background colours: `nbc_logo_40/30.png` (white removed), `acleda_logo_30/22.png` (anti-aliased circle), `wing_logo_30/22.png` (rounded square), `note_khr_*` and `note_usd_*` at heights 52/46/40/34/28/22. The original files stay in the workspace root and are not deployed. Tk loads PNG natively, so no image library was added.
- Code: `app/dashboard.py` (asset loader, bank logos, `▲▼` flat arrows, per-cell figure fitting, banknote amount row with one-line fitting, digits-only main amount; history rows keep `៛`/`$`). Tests: `tests/test_dashboard_ui.py`. Docs: README and this handoff.
- Verification: full workspace suite passed (237); `git diff --check` passed; previews at 1382×744 and 900×600 showed unchanged card geometry, no Dashboard scrollbar at 1382×744, logos under the names, and the riel note at digit height.
- Deployment: backed up the four production files to be replaced. The running instance (started 08:31 by the logon task) ignored the window-close request, apparently because it ran with higher privileges than the agent session; it was not force-killed. The owner closed it and tried a restart, but no instance was running when re-checked, so the files were deployed then: `app\dashboard.py`, `tests\test_dashboard_ui.py`, README, this handoff, and 18 new PNGs in `assets\` (all SHA-256 verified). Production suite passed (208). Started with `Start ABA Payment Speaker.bat`; maximized at 1382×744 and responding. Operational note: an instance started by the logon task may not accept a close request from the agent; ask the owner to close it. No commit or push was made.

### 2026-11-07 — NBC logo and weekend NBC handling

- Owner explained the NBC rate disappears on weekends (the page shows no rate for today; yesterday's is available) and supplied an NBC logo PNG in the workspace root (owner's choice of file; agent did not download it).
- Implemented in the workspace: copied the logo to `assets/nbc_logo.png` (original left in place); the NBC card shows it before the rate, scaled with Tk `subsample` (no image library) and with near-white pixels made transparent, centred with the rate, `៛`, and pill; the card works unchanged if the file is missing. When the NBC reader finds no published rate (`NBC official USD/KHR reference rate was not found`), the monitor now treats it as "no new publication" — it clears any error and keeps the last published rate — and NBC counts as stale only after 4 days (other sources: 24 hours). Other NBC errors and bank failures are still recorded as errors.
- Files: `app/dashboard.py`, `app/exchange_rates.py`, `app/database.py` (`clear_exchange_rate_error`), new `assets/nbc_logo.png`, `tests/test_dashboard_ui.py`, `tests/test_gold_price.py`, README, and this handoff.
- Verification: full workspace suite passed (235); `git diff --check` passed; previews at 1382×744 and 900×600 show the logo before the centred rate.
- Owner approved deployment of all pending changes (NBC title colour, `៛`, gold down arrows, grey `↕`, full-size gold units with flags, NBC logo, weekend handling). Backed up the seven production files to be replaced; closed the dashboard normally (it exited on its own); deployed `app\dashboard.py`, `app\database.py`, `app\exchange_rates.py`, `tests\test_dashboard_ui.py`, `tests\test_gold_price.py`, README, this handoff, and new `assets\nbc_logo.png` with matching SHA-256 hashes. Production suite passed (206). Restarted with `Start ABA Payment Speaker.bat`; window maximized at 1382×744 and responding. `.env`, sessions, database file, and logs were not opened or copied. No commit or push was made.

### 2026-11-07 — NBC rate stale on the live screen (source format change suspected)

- Owner reported the NBC Khmer title still differs from the date colour and the date looks gold. The title-colour fix exists only in the workspace (deployment pending approval); the gold/orange date is the existing stale styling.
- Diagnosis: a read-only run of the app's own source readers showed ACLEDA and Wing parse correctly, but the NBC reader raises "NBC official USD/KHR reference rate was not found", so NBC has been stale (orange date, grey figure, no arrows). The page is fetched but no longer matches the expected `<date> | Official rate: <n> Riel / US Dollar` text.
- The NBC page could not be inspected: a standard web reader received HTTP 403, and a browser-style request was blocked as bot-check circumvention and not pursued. Next step: the owner copies the official-rate section of https://nbc.gov.kh/en/statistics/exchange-rate from a normal browser so the parser can be updated, with tests, and deployed after approval.
- No files other than this handoff changed in this turn; nothing deployed.

### 2026-11-07 — Gold local units at full size with Cambodian flags

- Owner requested the ដំឡឹង and ជី gold prices at the same size as the ounce price, each followed by a Cambodian flag of matching size.
- Implemented in the workspace: the GOLD row now spans the whole table (the 18 pt lines need about 240 px); the ounce, ដំឡឹង and ជី prices share one Bahnschrift size (18 pt, 12 pt below 1080 px); each local unit is followed by a small Cambodian flag image (blue/red/blue with a white Angkor Wat, 2:3) drawn in code at 18 px (12 px narrow) because Tk cannot render the flag emoji. Table rows no longer share a uniform height. Updated `app/dashboard.py`, `tests/test_dashboard_ui.py`, README, and this handoff.
- Verification: full workspace suite passed (232); `git diff --check` passed; 1382×744 preview has no Dashboard scrollbar. Deployment of this and the previous change awaits owner approval.

### 2026-11-07 — NBC title colour, riel sign, gold down arrows, always-visible trend markers

- Owner requested: NBC Khmer title in the same colour as the date; `៛` after the NBC rate at a matching size; visible up/down indication (green up, gold down as an alternative); and arrows in the bank-rate card, where none were visible.
- Explained cause: arrows only appear once a value changes after tracking began (previous values started with the 2026-11-07 deployments), and NBC/ACLEDA/WING had not changed since.
- Implemented in the workspace: title uses the date colour; Siemreap `៛` after the rate (32 pt beside 38 pt digits; 24/28 pt narrow); down arrows/pills now gold `#FACC15` instead of orange; NBC rate and `៛` tint green/gold when NBC moves; bank and gold cells show a grey `↕` while unchanged (compact enough for 1180 px and 900 px cells). Updated `app/dashboard.py`, `tests/test_dashboard_ui.py`, README, and this handoff.
- Verification: full workspace suite passed (231); `git diff --check` passed; 1382×744 and 900×600 previews checked. Deployment awaits owner approval.

### 2026-11-07 — NBC card Khmer title, centred rate, header-row highlight

- Owner requested: replace `NBC OFFICIAL RATE` with the Khmer `អត្រាប្តូរប្រាក់ធនាគារជាតិ`; centre the NBC rate horizontally and vertically; keep up/down arrows visible; highlight the bank-rate table header row. Owner reported adding the gold key to the production `.env` (not viewed); ABA reads `.env` only at startup, so it takes effect on the next restart.
- Implemented in the workspace: Khmer caption in Siemreap; rate and pill centred as one group between the caption and bottom rows; a neutral grey `▲▼ 0` pill when NBC has not changed (or no previous value is recorded yet), green/orange arrows when it has; header row background `#22304A`. Updated `app/dashboard.py`, `tests/test_dashboard_ui.py`, README, and this handoff.
- Verification: full workspace suite passed (231); `git diff --check` passed; 1382×744 and 900×600 previews checked.
- Owner approved deployment. Backed up the four production files to be replaced, closed the dashboard normally (it exited on its own), deployed `app\dashboard.py`, `tests\test_dashboard_ui.py`, README, and this handoff with matching SHA-256 hashes, and ran the production suite (202 passed). Restarted with `Start ABA Payment Speaker.bat`; the window is maximized at 1382×744 and responding with one process pair. This restart also loads the owner's newly added `GOLD_API_KEY`; the agent did not open `.env`, the database, or logs, so the first gold fetch was not verified directly — operator to confirm the GOLD row shows a price. No commit or push was made.

### 2026-11-07 — Rates & gold card, glass NBC card, 50%-width recent payments

- Owner requested: remove NBC from the bank-rate card and add an international gold price with arrows; redesign the header NBC card in a modern style with different fonts; shrink RECENT ANNOUNCED PAYMENTS — TODAY to the 50% width under LAST PAYMENT RECEIVED and extend the rates and private cards down into the freed space.
- Gold source research (read-only, provider pages): no free plan supports 15–30 minute refreshes (GoldAPI.io 150/month; Metals.dev and MetalpriceAPI 100/month; MetalpriceAPI's and Metals-API's free plans forbid commercial use). Owner chose a free daily price; implemented GoldAPI.io free plan, refreshing at most every 12 hours. The owner must create a free account and add `GOLD_API_KEY` to the production `.env` themselves; the key was never requested in chat.
- Owner approved: card title `អត្រាប្តូរប្រាក់ និង មាស`; gold shown in USD/oz plus `≈ / ដំឡឹង` and `≈ / ជី`; design concept A (glass ticker) with Bahnschrift rate figures and a 7-day NBC sparkline (agent's suggestion accepted); at narrow widths the recent-payments BANK/TIME columns use a smaller condensed font rather than being dropped.
- Files changed: `app/config.py` (`gold_api_key`), `app/exchange_rates.py` (GoldAPI parsing/fetch, 12-hour schedule, retry backoff, unit conversion), `app/database.py` (additive `nbc_rate_history` table), `app/dashboard.py`, `main.py` (gold key wiring and log redaction, NBC history callback), `tests/test_dashboard_ui.py`, new `tests/test_gold_price.py`, `.env.example` (empty `GOLD_API_KEY=` placeholder; workspace only), `README.md`, and this handoff. Payment parsing, authorization, payment storage, bank registry, and speech are unchanged.
- Verification: full workspace suite passed (231); `git diff --check` passed. Off-screen previews with synthetic data at 1382×744 showed no Dashboard scrollbar, aligned bottoms (payment + recent vs side cards), the private text area about 423 px tall (previously 228), and the header unchanged at 170 px.
- Deployment (owner: "approved, implement and deploy"): backed up the eight production files to be replaced outside the production tree with verified hashes; closed the dashboard normally (it exited on its own); deployed `app\config.py`, `app\dashboard.py`, `app\database.py`, `app\exchange_rates.py`, `main.py`, `tests\test_dashboard_ui.py`, new `tests\test_gold_price.py`, README, and this handoff with matching SHA-256 hashes. `.env.example` was not deployed. The production `.env` hash is unchanged; `.env`, sessions, the database file, and logs were not opened, copied, or replaced.
- Production suite passed (202). Restarted with `Start ABA Payment Speaker.bat`: one launcher/interpreter pair from the production `.venv`, maximized on the secondary monitor at 1382×744 and responding. On first start the app creates the empty public `nbc_rate_history` table; the sparkline appears once at least two daily NBC values exist. Gold shows `—` until the owner adds `GOLD_API_KEY` to the production `.env` and restarts ABA. No commit or push was made.

### 2026-11-07 — Three-column Dashboard, bank-rate table, NBC header, USD/KHR private offers

- Owner discussed adding a third Dashboard column and approved: Dashboard row 50% / 25% / 25% (three columns at every size, no two-column fallback); the private exchange-group box moves from the header into the third column as a dark card with yellow accents (option B); the bank-rate card becomes a `BANK | ទិញ $ | លក់ $` table with NBC, ACLEDA, and WING rows; the freed header column shows a big NBC official rate.
- ABA row: a read-only check found ababank.com returns HTTP 403 to automated requests (including the owner-supplied `https://www.ababank.com/en/forex-exchange/`). A browser-impersonating request was blocked as bot-check circumvention and was not attempted further. Owner chose to remove the ABA row.
- Owner approved trend arrows on all rate boxes (▲ green / ▼ orange); storing previous public bank values was left to the agent, which chose additive previous-value columns in the existing public-rate cache (private-group values stay memory-only).
- Owner approved replacing `$`/`៛` with `USD`/`KHR` in private rates, rates shown with `KHR`, two-line offers, rate 14 pt / amount 12 pt, and the recommended extras: best-rate outline, "checked … ago" footer with dimmed stale rows, new-post glow, fading/sinking of old posts, gap from NBC, NBC header details, and the payment-card today strip. Not implemented: spread column, change flash, pinned senders, rates-only filter.
- Files changed: `app/dashboard.py`, `app/database.py` (additive cache columns and previous-value update), `app/exchange_rates.py` (previous values, `rate_trend`), `app/rate_post_format.py` (USD/KHR text), `tests/test_dashboard_ui.py` (rewritten for the new layout), `tests/test_exchange_rates.py`, `tests/test_rate_post_format.py`, `README.md`, and this handoff. Payment parsing, authorization, payment storage, bank registry, and speech are unchanged.
- Verification: full workspace suite passed (217); `git diff --check` passed. Off-screen previews with synthetic data at 1382×744 and 900×600: card shares 50.0% / 24.6% / 25.3% with equal heights, header 170 px (144 px at 900 px), clock centred, NBC card within the clock column height, titles and bank cells fit.
- Deployment: owner authorized implementation and deployment in the same message ("approved implement and also deployment"). Confirmed the nine production files to be replaced were unchanged since the previous deployments and backed them up outside the production tree with verified hashes. Closed the dashboard with a normal window close; it exited on its own. Deployed only `app\dashboard.py`, `app\database.py`, `app\exchange_rates.py`, `app\rate_post_format.py`, `tests\test_dashboard_ui.py`, `tests\test_exchange_rates.py`, `tests\test_rate_post_format.py`, README, and this handoff; all SHA-256 hashes match the workspace. The production `.env` hash is unchanged; `.env`, Telegram sessions, the database file, and logs were not opened, copied, or replaced.
- Production suite passed (188). Restarted with `Start ABA Payment Speaker.bat`: one launcher/interpreter pair from the production `.venv`, window maximized on the secondary monitor at 1382×744 and responding. On this first start the app itself added the three nullable `previous_*_rate` columns to the production `exchange_rate_cache` table (public rates only; no payment data touched). Bank arrows appear after a figure next changes at a 15-minute refresh; private arrows after a sender changes a rate. The live private-group content was not viewed or captured. Operator check: confirm the three-column layout, the NBC header card, and the green status dot on the private card.
- No commit or push was made.

### 2026-11-06 — Private-group standard-row display (workspace only)

- New session onboarding (discussion only): re-verified project state read-only. Workspace on `feature/unified-ai-lab-integration` at `3b007d6` with pre-existing uncommitted/untracked work (preserved). Production `C:\ABA Payment Speaker` is on `main` at `8807561` with an uncommitted file-copy overlay; all key runtime modules matched the workspace byte-for-byte (11 files differ only in line endings; production `OTHER_PC_SETUP.md` is older; production lacks `tests/test_announcement_core.py`). Note: deployed features (private reader, bank rates, scheduled announcements) are not committed on any branch. One responsive `ABA Payment Speaker` window was running; the scheduled task last returned 1 at 09:43 (cause unverified). Baseline workspace suite passed (185).
- Owner shared sample group posts in chat to study writing styles. They were analysed in conversation only and not stored; tests use short synthetic phrases instead.
- Owner approved the standard-row design and its rules (recorded in "Private-group display rules" above): standard rows instead of cleaned sentences, `៛`/`$` normalisation, `៛→$`/`$→៛`/`·` tags, rates 3,800–4,400 with `.`/`,` cents and thousands separators shown as `4089.5៛`, unmarked sizes left plain, `M៛`, display-only short bank names with `ស្ថាបនា`, phones and contact lines hidden completely, identical/alternating reposts folded into one row per sender, line joining within a group, the 15-minute summary line, edit/delete/photo handling, and short sender names.
- Owner approved the box changes after a geometry inspection: 164 px high at ≥1080 px header width (header unchanged at 170 px), title/status dot/short button on one row when wide, thinner scrollbar, slightly smaller padding; the 900 px layout keeps 152 px and a bottom footer. Wider columns and taller-than-clock boxes were intentionally not implemented.
- Files changed: new `app/rate_post_format.py` and `tests/test_rate_post_format.py`; updated `app/rate_group_reader.py` (50-post history, edit/delete handlers, photo placeholder, timestamp/edited payload), `app/dashboard.py` (per-sender rendering, summary, layout, mixed Khmer/Latin fonts so number rows use shorter lines), `tests/test_rate_group_reader.py`, `tests/test_dashboard_ui.py`, `README.md`, and this handoff. The payment parser, payment authorization, bank registry, database, and speech are unchanged.
- Verification: focused formatter/reader/dashboard tests passed (49); full workspace suite passed (210); `git diff --check` passed. Off-screen previews at 1382×744 and 900×600 confirmed header heights 170/158 px unchanged, the clock and title unmoved, the title fitting at 8 pt, the message area about 111 px at wide size (about 8 compact lines, previously 5), and the scrollbar 8 px.
- Owner then approved deployment ("approved, deploy"). Confirmed the six production files to be replaced were unchanged since the 2026-11-05 deployment and backed them up outside the production tree (session scratch folder) with verified hashes. Requested a normal window close; the dashboard exited cleanly on its own after its listener/reader shutdown (about 2 minutes; nothing was force-terminated).
- Deployed only `app\dashboard.py`, `app\rate_group_reader.py`, new `app\rate_post_format.py`, `tests\test_dashboard_ui.py`, `tests\test_rate_group_reader.py`, new `tests\test_rate_post_format.py`, README, and this handoff; all SHA-256 hashes match the workspace. The production `.env` hash is unchanged; `.env`, Telegram sessions, database, and logs were not opened, copied, or replaced.
- Production suite passed (181 = previous 156 + 25 new); focused formatter/reader/dashboard tests passed (49).
- Restarted with `C:\ABA Payment Speaker\Start ABA Payment Speaker.bat`: one launcher/interpreter pair from the production `.venv`, window maximized on the secondary monitor at 1382×744 and responding. The live private-group content was not viewed or captured. Operator check still required: confirm the top-right status dot turns green and the posts appear as standard rows.
- No commit or push was made.

### 2026-11-05 — Private-group panel startup and message presentation

- Owner approved automatic private-group reader connection at ABA startup, a one-line Khmer/English title, Siemreap font with fallback for Khmer content, single line spacing, amount-only digit styling, alternating message backgrounds, display of two posts preferring distinct senders, and bottom-left connection status beside the Connect/Disconnect button.
- Implemented startup scheduling, two-message rendering with a 10-post in-memory history buffer, currency-marked amount digit styling (USD and KHR use distinct colors; only digits are bold and one point larger), alternating row colors, and compact footer status. The fixed-group-only reader, separate Telegram session, raw in-memory-only message handling, and payment/speech independence are preserved.
- Updated focused Dashboard and reader tests plus README and this handoff. Focused tests passed (24); the complete workspace suite passed (185); `git diff --check` passed.
- Gracefully closed the production dashboard, backed up only the six files being replaced outside the production tree, deployed only `app\dashboard.py`, `app\rate_group_reader.py`, `tests\test_dashboard_ui.py`, `tests\test_rate_group_reader.py`, README, and this handoff, and verified their SHA-256 matches. The production suite passed (156).
- Restarted using `C:\ABA Payment Speaker\Start ABA Payment Speaker.bat`; verified the live window was responsive at 1382×744. The deployment did not copy, display, or alter `.env`, Telegram sessions, the database, or logs. No commit or push was made.

### 2026-11-05 — Distinct bank-rate row colors

- Owner approved the proposed subtle differentiated row tints: NBC blue-slate (`#182438`), ACLEDA teal-slate (`#193138`), and WING violet-slate (`#28243A`). Updated each row background while keeping borders, rate text, and pulse colors unchanged.
- Added a focused assertion that all three bank rows use their designated distinct colors. Updated README and this handoff. Focused Dashboard UI tests passed (13); `git diff --check` passed.
- Owner subsequently authorized deployment of this color-only refinement. Backed up only the four files to replace (`app\dashboard.py`, `tests\test_dashboard_ui.py`, README, and this handoff), deployed those reviewed files with verified SHA-256 matches, and ran the production regression suite (153 passed).
- Restarted using `Start ABA Payment Speaker.bat`; verified the live Dashboard responds at 1382×744. Confirmed the production `.env` hash is unchanged and the database, Telegram sessions, and logs remain in their runtime locations. No unrelated workspace files were deployed; no commit or push was made.

### 2026-11-04 — Approved bank-rate card highlights and Khmer labels

- Owner approved full-row highlighting for NBC, ACLEDA, and WING; same-line Khmer labels beside ACLEDA/WING rates (`ដុល្លារដូរយកលុយរៀល` for Buy and `លុយរៀលទិញដុល្លារ` for Sell); a single centered NBC reference figure; and a subtle, synchronized, continuous brightness pulse that remains within red Buy, light-blue Sell, and white-to-cyan NBC colors.
- Added responsive label sizing to keep each Khmer label and its figure on one line at 900×600 and wider layouts. The pulse uses a 2.4-second smooth cycle and its recurring Tk callback is cancelled when the window is destroyed. Rate retrieval/cache remains every 15 minutes; the displayed age/status remains locally updated each second.
- Updated `app\dashboard.py`, `tests\test_dashboard_ui.py`, `README.md`, and this handoff. Focused Dashboard UI tests passed (13); the complete workspace suite passed (182); the production suite passed (153). `git diff --check` passed.
- Owner approved deployment after tests passed. Backed up only the four files to be replaced, deployed only those reviewed files to `C:\ABA Payment Speaker`, and verified production hashes. Restarted through `Start ABA Payment Speaker.bat`; the live Dashboard responded at 1382×744.
- Confirmed the production `.env` hash was unchanged; the database, Telegram sessions, and logs were not copied or replaced and remain in their runtime locations. No commit or push was made.

### 2026-11-04 — Proposed Dashboard card proportions and bilingual titles

- Owner requested a ready-to-use implementation prompt for the discussed Dashboard redesign; this turn provides the prompt without changing application code or production.
- Approved design direction in the prompt: equal rendered heights for LAST PAYMENT RECEIVED and the three-bank rates card; reduce the payment card's current 70% share by 20% to 56% and allocate the freed space to rates (44%), accounting for actual gaps/padding; use the Dashboard dark theme instead of a yellow bank-rate card; center each concise one-line title with Khmer first: `អត្រាប្តូរប្រាក់តាមធនាគារ - Bank rates` and `អត្រាប្តូរប្រាក់ឯកជន - Private rates`.
- Recommended rate typography: bold figures at 13–14 pt, source/category labels at 9 pt, title at 11 pt, and compact effective-date/status labels at 7–8 pt. Preserve Buy/Sell colors and private-reader UNVERIFIED labeling.
- At the time, implementation and tests were pending use of the prompt; the subsequent implementation and validation are recorded below. Any production deployment/restart requires a separate explicit approval.

### 2026-11-04 — Implemented Dashboard card redesign

- Implemented the requested approximately 56% / 44% payment-to-rates width allocation with matched rendered card heights, the dark bank-rate card, and centered single-line Khmer-first titles. The rate figures use 14 pt bold text, source/category labels 9 pt, and effective/status labels 8 pt; the private reader retains yellow styling and its separate UNVERIFIED label.
- Added responsive title fitting and a responsive header arrangement that keeps the private panel's rendered width equal to the rate card while preserving the centered clock without overlap. At 900×600, 1180×800, and 1382×744, the two Dashboard cards had equal heights and aligned top edges; the payment card occupied approximately 55–57% of their combined rendered width, and both titles fit on one line.
- Added fixture-based rate-formatting and responsive-layout tests, including private-reader independence/styling assertions. Focused Dashboard tests passed (12); the full workspace regression suite passed (181).
- Updated README.md and this handoff. Production deployment was pending separate approval at the time of this implementation.

### 2026-11-04 — Approved three-column Dashboard header redesign

- Owner approved a single-row, three-column header: left Khmer shop title, centered time/date/LIVE status, and a right private Telegram reader titled `អត្រាប្តូរប្រាក់ឯកជន - Private rates` with its messages. Starting allocation is approximately 28% / 39% / 33%; keep the header compact so it does not push Dashboard transactions down.
- Owner approved reducing the bank-rate card width by 5% from the current approximately 44% share, targeting about 42% bank rates / 58% payment, while preserving equal card heights. The reader no longer needs to match the bank-rate card width and should fit its header column at the existing 152 px height.
- Remove the visible UNVERIFIED label from the private reader as specifically requested. This is a presentation-only change; preserve its optional, read-only, fixed-group-only handling and strict separation from payment parsing, storage, and speech.
- Owner authorizes deployment and restart of this redesign after implementation and tests pass. Back up files being replaced, deploy only reviewed relevant files, preserve `.env`, Telegram sessions, database, and logs, run the production test suite, and verify the live layout. Deployment has not yet occurred.

### 2026-11-04 — Implemented and deployed approved header redesign

- Implemented the compact single-row header with the Khmer shop title at left, time/date/LIVE centered across the full window, and the 152 px private-group panel in its own right column. Balanced 30% / 40% / 30% columns keep the clock truly centered while fitting the side content at the 900×600 minimum; the reader title wraps only before `rates`, and the visible UNVERIFIED label is removed. Reader authorization, optional read-only behavior, separate session/lifecycle, in-memory display, and independence from payment parsing/storage/speech are unchanged.
- Tuned the payment/rate grid to account for padding and verify the actual rendered share is approximately 58% / 42%; the cards retain aligned top/bottom edges and equal heights. The existing dark bank-rate card, typography, rate sources, cache, refresh cadence, and status behavior are unchanged.
- Focused Dashboard/private-reader tests passed (20); the full workspace suite passed (181). The production installation's full regression suite passed (152). `git diff --check` passed.
- After backing up only `app\dashboard.py`, `tests\test_dashboard_ui.py`, `README.md`, and this handoff, deployed those four reviewed files to `C:\ABA Payment Speaker` and verified their SHA-256 matches. Restarted with `Start ABA Payment Speaker.bat`; the live window responded at 1382×744.
- Verified the production `.env` SHA-256 remained unchanged. The production database, Telegram sessions, and logs were not copied or replaced; their runtime directories and files remained present. No commit or push was made.

### 2026-11-04 — Authorized Dashboard redesign deployment

- Owner explicitly authorized deployment and restart. Backed up the four production files replaced, then deployed only `app/dashboard.py`, `tests/test_dashboard_ui.py`, `README.md`, and this handoff to `C:\ABA Payment Speaker`; verified SHA-256 hashes after copying.
- Production full regression suite passed (152 tests). Restarted using `Start ABA Payment Speaker.bat`; the `ABA Payment Speaker` window appeared at 1382×744 and responded to a window-message smoke check.
- Verified the production `.env` hash remained unchanged. No Telegram sessions, database, or logs were copied or modified.

### 2026-11-04 — Controls relocation and reader-width alignment request

- Owner requested removing CONTROLS from the Dashboard and placing it in the hidden Operations panel under Settings & Diagnostics, alongside SYSTEM STATUS and TODAY.
- Owner also requested that the top-right private-group panel have exactly the same width as the three-bank exchange card.
- Workspace implementation moves controls into Operations and synchronizes the reader-panel width to the rendered rates-card width at each layout change. Focused Dashboard layout tests passed (11), including exact width equality at 900×600, 1180×800, and 1382×744, plus Operations scrolling; the full workspace regression suite passed (180). `git diff --check` passed. A separate Tk geometry smoke timed out, so geometry verification is based on the focused tests.
- Owner explicitly approved deployment and restart. Backed up the four production files replaced, deployed only `app/dashboard.py`, `tests/test_dashboard_ui.py`, `README.md`, and this handoff, and verified their SHA-256 hashes. The production regression suite passed (151). Restarted using `Start ABA Payment Speaker.bat`; the `ABA Payment Speaker` window appeared at 1382×744 and responded to a window-message smoke check. The production `.env`, Telegram sessions, database, and logs were not copied or modified.

### 2026-11-04 — Live Dashboard inspection after layout change

- Owner reported no visible interface change and authorized inspection/testing of the current application.
- Confirmed one visible ABA Payment Speaker window is running from the production installation at `C:\ABA Payment Speaker`; its current bounds are 1382×744. The production `app\dashboard.py`, `main.py`, and `app\exchange_rates.py` do not match the workspace files.
- Instantiated the production dashboard safely at both 900×600 and the live 1382×744 geometry. It has no exchange-rate card; its Dashboard right column remains SYSTEM STATUS, TODAY, CONTROLS, and its private reader remains 200×127 px at 900×600 / 263×127 px at 1382×744. This accounts for the unchanged interface: the approved workspace implementation was not deployed to production.
- The workspace Dashboard smoke at 900×600 confirmed the exchange-rate card exists, SYSTEM STATUS and TODAY are under Operations, the private reader measures 220×152 px, and the short Dashboard scrolls with the right column visible. At 1382×744 the workspace build has the same layout with a 250×152 px reader.
- Focused dashboard/rate/reader tests passed: 29. The production app was not changed during the initial inspection. Owner then explicitly authorized deployment and confirmed the requested pre-deployment approval.

### 2026-11-04 — Authorized Dashboard deployment to PC3

- Gracefully closed the old production Dashboard after the owner confirmed deployment; created a session-local backup of the seven existing production source/docs/test files that would be replaced. Did not copy or modify production `.env`, Telegram sessions, SQLite database, or logs. Existing database/config/private-reader/scheduled-announcement/audio modules already matched the reviewed workspace and were preserved.
- Deployed and SHA-256 verified the reviewed Dashboard, exchange-rate monitor, `main.py` lifecycle wiring, README, handoff, and focused Dashboard/rate tests to `C:\ABA Payment Speaker`.
- Production focused tests passed: 29. Full suite passed: 180. Production Tk geometry smoke passed at 900×600 and 1382×744: reader panel measured 220×152 px and 250×152 px respectively; rate card and relocated Operations cards are present, right column remains visible, and short layouts scroll.
- Restarted using `Start ABA Payment Speaker.bat`; verified the live window is responsive at 1382×744. The first cache check found populated NBC official reference, ACLEDA Notes, and Wing Telegraphic Transfer Outbound values with no recorded source errors. The production process remains running.

### 2026-11-04 — Dashboard layout implementation prompt

- Owner requested a ready-to-use prompt for the next implementation step after reviewing the deployed private-group reader and Dashboard layout.
- Recommendation to carry forward: keep and modestly enlarge the private Telegram panel in the top-right header; place the three-source USD/KHR rate card in the Dashboard right column where SYSTEM STATUS and TODAY currently appear; move SYSTEM STATUS and TODAY into Settings & Diagnostics; keep payment display/history and CONTROLS on Dashboard.
- No application code, dashboard layout, production files, or deployment state changed in this turn. A copy-ready implementation prompt is being provided in the conversation.

### 2026-11-04 — Approved Dashboard layout and rate refresh restoration

- Owner approved the Dashboard layout implementation: retain the optional fixed-group private reader at top right, replace the Dashboard status/summary cards with public NBC/ACLEDA/Wing rates, move SYSTEM STATUS and TODAY to Settings & Diagnostics → Operations, and keep payment display/history and CONTROLS on Dashboard.
- Enlarged the reader to 220×152 px at 900×600 and 250×152 px at wider layouts. It still displays up to five posts as UNVERIFIED, with sender and Cambodia-local time; its session, lifecycle, content handling, and payment/TTS separation were not changed.
- Added the light-yellow, blue-text USD/KHR rate card with NBC's single official reference value, ACLEDA Notes buy/sell, and Wing Telegraphic Transfer Outbound buy/sell. Buy values are bold red; Sell values are bold light blue. Compact effective dates/times, age, stale, and unavailable states are displayed.
- Restored cache loading at startup and an independent 15-minute background refresh. Rate-source failures are logged and surfaced in the rates card without blocking payment monitoring, the private reader, scheduled announcements, or speech. Short Dashboard windows now scroll vertically instead of hiding the right column.
- Updated `README.md`; focused dashboard/rates/reader tests passed (29), and the complete suite passed (180). Tk geometry smoke passed at 900×600 and 1180×800; at 900×600 the reader measured 220×152 px, the clock remained centered, and the Dashboard scrollbar/right column were present. `git diff --check` passed.
- No production files were deployed, no production process was restarted, and no credentials, sessions, databases, logs, or private-group content were accessed. Production remains unchanged; deployment/restart requires separate approval.

### 2026-11-04 — Separate private exchange-group reader

- Owner approved a separate, read-only viewer for a private exchange group using the consenting member's Telegram account. The existing payment session and payment authorization remain unchanged.
- Added an opt-in top-right panel reader restricted in application code to the fixed target group. It displays up to five raw posts with sender and Cambodia-local time, labels them unverified, keeps them in memory only, and never parses, stores, forwards, or speaks them.
- Added a distinct Local AppData Telegram session and local GUI prompts for phone, login code, and optional two-step password; phone/code/password are not saved. Dialog enumeration may return Telegram metadata to resolve the private group's access information, but message history and live updates are requested only for the target group. The account itself can access other chats.
- Replaced the active dashboard's public bank-rate refresh with the private group panel; payment monitoring, existing payment-session configuration, payment voice, and scheduled announcements remain separate. Updated README operational/security documentation.
- Focused reader/config/dashboard/auth tests passed: 29; full regression suite passed: 176. A Tk geometry smoke at 900×600 measured a 127 px panel height and 182 px message viewport; the application window and payment flows were not started for network use. `git diff --check` passed.
- Pylance reports unresolved `telethon` imports because the workspace `.venv` points to a missing base Python path; test execution used the available Python 3.12.10 environment at `C:\ABA Payment Speaker\.venv`. No code diagnostics were reported for `main.py`; existing dashboard warnings are unrelated.
- Owner approved deployment. Closed the production dashboard gracefully, backed up the specific source/docs/test files, copied eight reviewed files to `C:\ABA Payment Speaker`, and verified the production `.env` hash was unchanged; `.venv`, data, logs, and Local AppData session directory were preserved. No session, database, log, or credential file was copied or modified.
- Production-focused reader/local-path/dashboard tests passed: 18; production imports succeeded. Restarted using `Start ABA Payment Speaker.bat`; verified the ABA dashboard process is running. The group reader remains disconnected, and no group messages or wife-account credentials have been accessed.
- Next operator step: the group member can click **CONNECT GROUP** in the top-right panel and enter her phone, Telegram code, and optional two-step password in the local dialogs only. The reader should show **UNVERIFIED** posts from the fixed group; disconnecting leaves the separate session signed in.

### 2026-11-04 — Recommended production update sequence

- Owner asked what to do after confirming the currently running board is using an older production copy.
- Recommended leaving the current board running until ready to update; then close it normally, transfer only the reviewed application source/documentation/tests into `C:\ABA Payment Speaker`, preserve that installation's `.env`, `.venv`, Telegram session, database, logs, and audio settings, run focused tests there, restart, and visually verify the rates and scheduled-announcement behavior.
- No production update, restart, file transfer, commit, or push was authorized or performed in this turn.

### 2026-11-04 — Approved production deployment and dashboard verification

- Owner approved deploying the exchange-rate display and daily time announcements to `C:\ABA Payment Speaker`.
- Closed the previous dashboard gracefully, deployed the feature modules, wiring, tests, and README, and preserved the local `.env`, `.venv`, data/log directories, and integration modules.
- Production-clone tests passed: 26 focused tests and 139 total. Production imports succeeded. Restarted through `Start ABA Payment Speaker.bat`.
- Verified the app window responds, the populated NBC/ACLEDA/Wing rates appear in the yellow/blue header, the date and LIVE status are centered as agreed, and a 900-pixel-fit layout is visually clear. No exchange-source or TTS errors were logged after restart.
- The next 18:10 scheduled announcement had not yet occurred at verification; actual scheduled male-voice playback remains to be confirmed. No commit or push was made.

### 2026-11-04 — Unchanged production dashboard diagnosis

- Owner reported that the running board still looked unchanged and requested inspection and testing.
- Confirmed a running `main.py` process uses the local production Python environment at `C:\ABA Payment Speaker`; that production `app\dashboard.py` has no exchange-rate box or responsive-header implementation, and `app\exchange_rates.py` and `app\scheduled_announcements.py` are absent there. The Dropbox workspace contains the newer code, so workspace edits were not deployed to the running installation.
- The relevant workspace test set passed: 26 tests across dashboard UI, exchange rates, scheduled announcements, and audio queue.
- No production files were copied or modified, and the running board was not stopped or restarted. Next operational step is to deploy the reviewed source changes to the local production clone and restart ABA when authorized.

### 2026-11-04 — Exchange rates and scheduled time announcements

- Owner approved implementation of a compact top-right three-bank USD/KHR rate box with yellow background/blue text, LIVE status centered under the date, and scheduled daily Khmer time announcements. Payment speech remains on the configured female voice; scheduled times use `km-KH-PisethNeural`.
- Implemented background refresh from the NBC official reference-rate page, ACLEDA Notes buy/sell page, and Wing Bank Telegraphic Transfer Outbound page; UI age updates once per second, source fetches every 15 minutes, successful values are locally cached, and failed/unavailable data is labeled.
- Implemented Cambodia-time schedules (regular days 16:10/18:10; Thursday 16:05/18:05 with Thursday wording), durable once-per-date slot claims, missed-slot skipping, and queued playback without system-volume changes.
- Added responsive header typography below 1080 px so the title, clock, and populated rate rows fit within the 900 px minimum window. Updated `README.md` and this handoff.
- Focused dashboard UI suite: 9 passed; complete suite after the layout change: 168 passed. Existing focused rate parsing/cache, schedule, persistence, and per-item audio voice tests also passed (19 tests); Pylance diagnostics found no errors in the new/modified implementation files.
- Live source-fetch smoke test successfully parsed NBC Official reference, ACLEDA Notes buy/sell, and Wing Bank Telegraphic Transfer Outbound buy/sell values with their source effective dates.
- A populated Tk header geometry smoke at 900×600 verified the title, clock, and rate box fit without overlap. No production dashboard was changed or restarted; no screenshot/visual review or real-speaker male-voice test was performed.
- Operational follow-up: the Dropbox workspace is a source/editing copy, not a production runtime. Transfer the reviewed changes to the normal local clone and restart ABA when ready; then verify the rate box visually and test the male Khmer scheduled voice through the speaker.

### 2026-11-02 — VS Code prompt for the other PC

- Owner requested a ready-to-paste prompt for preparing/testing the other PC.
- Prompt should direct VS Code/Copilot to use the fresh local clone, follow `OTHER_PC_SETUP.md`, preserve per-PC secrets/session/database, verify the one-PC-at-a-time rule, and report setup/test results without copying private runtime files.

### 2026-11-02 — Safe source transfer to the other PC

- Owner wants to test the ABA speaker on the other PC while continuing to open Dropbox files in VS Code, and confirms only one PC should run the speaker at a time.
- Inspected `C:\Users\Wing\Dropbox\AI_STUDIO\ABA Payment Speaker`: it is a Git clone with the existing test-before-push, safe-sync, pull-and-test, first-time-setup, and local launch scripts.
- Recommended source-only transfer using `PUSH TO GITHUB.bat` on the source PC and `PULL FROM GITHUB.bat` in the other PC's normal local clone, followed by that PC's `Start ABA Payment Speaker.bat`. Dropbox remains a source/editing location, not a production runtime.
- Do not copy `.env`, `.venv`, Telegram session files, SQLite databases, or logs; set up per-PC credentials and Telegram login locally. No files were transferred, no scripts were run, and no code/configuration changed.

### 2026-11-02 — Safe pull script PowerShell check

- Owner reported the other-PC `PULL FROM GITHUB.bat` passed a literal `^|` to PowerShell, then correctly refused to overwrite local source changes/untracked files.
- Replaced the escaped pipeline with a `foreach` check that avoids shell pipe escaping; dirty-worktree failure now displays `git status --short` and tells the operator to preserve changes or use a clean clone.
- Applied the corrected pull helper both in this repository and in the Dropbox AI_STUDIO clone where the owner ran it. Updated `OTHER_PC_SETUP.md` and the pull-script handoff instructions. The dirty worktree remains protected; no changes were stashed, discarded, committed, or pulled.
- Verified the exact `cmd.exe` → PowerShell process check exits successfully; exercised matching and nonmatching process cases; ran the helper from the exact Dropbox clone and confirmed it prints the modified/untracked paths and exits without pulling.
- Inspection found a separate transfer blocker: this workspace is on `feature/unified-ai-lab-integration` at `175e2f8`, while its local/remote `main` is at `eaa2429`; the Dropbox AI_STUDIO clone is on `main`/`origin/main` at `8807561` and has local edits/untracked files. The sync helper publishes `main` only. Do not push, merge, discard, stash, or pull until the owner chooses how to preserve/integrate the changes.
- Owner authorized publishing the source branch to `main`, leaving the AI_STUDIO clone's other local edits/untracked files preserved.
- Full regression suite passed on the feature branch with the pull-helper/docs fix: 151 tests. `git diff --check` passed. The exact AI_STUDIO pull script reports its dirty files and stops safely.
- Committed the focused fix as `a6d7600`, fast-forwarded local `main` from the feature branch, and pushed normally. Verified `origin/main` matched local `main` at `a6d760044cf5362878845ae6bbaebc2d2067d02f`; no force push was used.
- The AI_STUDIO clone remains on its older `main` with its other local modifications and untracked files intact; it was not pulled, stashed, committed, or reset. For PC2 testing, use a fresh normal local clone rather than pulling over that dirty Dropbox worktree. No other-PC runtime, credentials, Telegram session, or database were changed.

### 2026-11-02 — Speaker operation restored

- Owner confirmed the ABA speaker is working successfully as of 18:22 +07:00.
- No code, configuration, session, or database changes were requested or made; no tests or live checks were run.

### 2026-11-02 — ABA announcement failure investigation

- User clarified the incident is in `C:\ABA Payment Speaker`: the app will not open, last observed on 2026-11-02.
- Read-only inspection confirmed the local Python 3.12.10 virtual environment and required runtime packages are available, and the launcher and scheduled-task action point to the expected local clone. No matching `pythonw.exe` process was running at inspection.
- The scheduled task's last result was `0x00000001`. `main.py` can return 1 when the Windows single-instance mutex rejects a second launch; the recorded result alone does not establish that this was the cause.
- The local log contains a 2026-11-02 `SessionRevokedError` from the Telegram listener. This explains a stopped Telegram session, but the listener runs in a background thread, so it does not by itself explain a missing dashboard.
- User confirmed clicking the exact `C:\ABA Payment Speaker\Start ABA Payment Speaker.bat`, but the visible window showed the Python 3.12 interactive-shell banner. The verified local batch and scheduled task both invoke `pythonw.exe` with `main.py`, so the shell's origin remains unexplained. No matching local virtualenv Python process remained at follow-up.
- User confirmed no other speaker PC is running. The Dropbox workspace's `.venv` is unusable and its system interpreters lack test dependencies; tests were not run. The local clone has uncommitted changes, so it was not pulled, edited, or launched. No configuration, Telegram session, database, or transaction contents were read or changed.
- Next operational check: determine whether the Python prompt is a leftover/separate window or whether the local launcher opens the ABA dashboard behind it. If the dashboard opens, address the revoked Telegram session through the app's normal authentication flow; do not copy or delete the session file.

### 2026-10-19 — Multi-PC display and Khmer voice detailed planning

- Owner approved detailed implementation planning only for two or three additional Windows viewer/speaker PCs on the same private LAN; no implementation, deployment, production test, restart, configuration, credential, database, scheduled-task, firewall, or network change was authorized.
- Created `reports/codex/ABA_MULTI_PC_DETAILED_IMPLEMENTATION_PLAN.md` describing a separate relay that consumes only the existing loopback API plus independently authenticated viewer/speaker clients; exactly one authoritative Telegram listener remains.
- The plan specifies ordered cursor delivery, persistent per-viewer deduplication, live-session freshness barriers, display-only bootstrap/recovery, local Khmer speech, enrollment/revocation, loopback/source polling limits, Windows deployment, synthetic-only tests, staged rollout, and rollback.
- Recommended policy awaiting owner approval: a fresh verified live payment may be announced once by each viewer independently even if the main PC is `MUTED` or `FAILED`; historical/snapshot/recovery events never speak.
- Owner decisions remain open for mTLS versus token fallback, 30-second freshness, contract-v2 `MUTED`/stable-bank-code additions, relay IP/port/firewall scope, viewer mute behavior, TTS dependency, retention, service identities, and recovered-event display.

### 2026-09-03 — Authoritative Unified AI Lab integration

- Reproduced the previously documented 111-test baseline after replacing the stale development-only `.venv`; no production credentials, session, database, or logs were copied.
- Preserved and checkpointed the four pre-existing secondary-display changes before integration work.
- Added a Windows named mutex acquired before any Telegram initialization; a rejected second instance exits safely without starting the listener.
- Added the optional versioned, read-only, bearer-authenticated loopback API and privacy-safe cursor/event contract. Unknown banks remain valid and export as `OTHER BANK`/`UNMAPPED`; exact USD cents and whole KHR use integer minor units.
- Added an additive integration-update table and event columns without changing duplicate reservation, parser authority, spoken history, or existing dashboard behavior.
- Invalid API configuration or bind failure disables only integration and does not stop ABA payment monitoring.
- Complete suite passed with 122 tests. Live production activation remains pending because the authoritative non-Dropbox runtime was not present on this PC; no Telegram listener or real payment test was started.

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

### 2026-08-30 — GitHub synchronization confirmed

- Operator confirmed the one-click sync completed successfully and the source code reached GitHub.
- Secrets, Telegram sessions, virtual environments, logs, and databases remained excluded from the upload as required.

### 2026-09-02 — Windows automatic startup enabled on PC3

- User requested automatic Windows startup and asked that the working speaker remain running.
- Ran the complete installed regression suite from `C:\ABA Payment Speaker`: 110 tests passed.
- Registered the per-user Task Scheduler task `ABA Payment Speaker` to start the installed application at Windows logon with the correct working directory.
- Removed the temporary Startup-folder shortcut created during testing so only one automatic-start mechanism remains.
- Closed the two extra test-launched application trees and verified the scheduled instance remained `Running`; its dashboard window was responsive.
- No payment-processing, Telegram authorization, parser, database, duplicate-protection, security, or Khmer TTS code was changed.

### 2026-09-02 — Secondary-screen startup placement

- User approved automatic secondary-display placement after discussing the behavior; the requested fallback is normal size on the primary monitor, not application failure.
- Updated `app/dashboard.py` to retry secondary-monitor discovery, maximize on the closest active non-primary monitor, and fall back safely to a normal primary-monitor window.
- Added monitor-selection regression coverage in `tests/test_dashboard_ui.py` and documented the behavior in `README.md`.
- Complete working-tree suite passed with 111 tests.
- GUI smoke test detected PC3's 1366×728 secondary work area below the primary display and verified the dashboard entered the maximized state at that secondary monitor's coordinates.
- Simulated missing-secondary smoke test verified the normal 1180×800 fallback centered on the primary display.
- Deployed the change to `C:\ABA Payment Speaker`; the installed suite passed all 111 tests.
- Restarted the scheduled production instance and verified one normal two-process Python launcher/interpreter tree, a responsive `ABA Payment Speaker` window, maximized state, and window bounds on the secondary display. The application was left running.

### 2026-09-03 — Unified Lab integration proposed

- User asked how to brief Codex on the Main PC about integrating ABA Payment Speaker with an existing Unified Lab project.
- Recommended an inspect-and-plan-first integration: read this handoff and both projects, preserve ABA source authorization and payment safeguards, avoid duplicate Telegram listeners, keep private runtime data local, define a narrow event/status interface, and wait for approval before implementation.
- No Unified Lab integration or application behavior change was implemented in this turn.

### 2026-09-03 — Unified Lab production commissioning paused safely

- Verified the authoritative non-Dropbox ABA installation at `C:\ABA Payment Speaker`, one existing private Telegram session, one existing ABA SQLite database, and the existing `ABA Payment Speaker` scheduled task.
- Confirmed Unified AI Lab is present on this same PC, so the approved `http://127.0.0.1:8766` loopback design is applicable and cross-PC exposure is not required.
- Verified branch `feature/unified-ai-lab-integration` contains commits `1876d08` (single-instance protection) and `b948867` (privacy-safe localhost API); its full suite passed with 122 tests while the scheduled task was requested to stop.
- Deployed only the reviewed integration source delta to the production directory. The deployment target list excluded `.env`, Telegram session files, SQLite databases, logs, and audio settings.
- Commissioning then paused because an ABA dashboard process running under another Windows integrity/user context retained an established Telegram connection and could not be terminated by this session. No integration token was generated, neither ABA nor Unified integration was enabled, and no API listener was started.
- Required next action: operator must close the visible ABA Payment Speaker dashboard completely, then commissioning can resume with listener-off production regression testing.

### 2026-09-03 — ABA localhost integration commissioned

- Operator closed the remaining dashboard; verified zero ABA processes/connections and exclusive access to the existing session/database before testing.
- Deployed source only from `feature/unified-ai-lab-integration`, including commits `1876d08` and `b948867`, into `C:\ABA Payment Speaker`; private `.env`, Telegram session, SQLite database, logs, dashboard behavior, scheduled task, and audio settings were preserved.
- Listener-off production suite passed all 122 tests.
- Generated one strong random token locally, stored it only in ignored ABA and Unified `.env` files, and enabled the ABA API at `127.0.0.1:8766`.
- Live verification passed: scheduled task running, one normal two-process launcher/interpreter tree, responsive dashboard, named mutex rejected a second launch, existing Telegram session authenticated without a login prompt, production monitoring online, unauthorized API requests rejected, authenticated status/events valid, allowlisted event schema, and exactly one loopback listener with no LAN/Tailscale/public bind.
- Real Khmer TTS generation and speaker playback completed successfully.
- Unified AI Lab is on this same PC and its private adapter configuration is prepared, but its existing `.venv` referenced another Windows profile. An in-place rebuild was blocked by Dropbox file locks, so Unified was not started; repair it in a normal non-Dropbox production location before launch.

### 2026-10-17 — New-thread onboarding prompt requested

- User requested one comprehensive prompt for introducing a new Codex conversation to the complete ABA Payment Speaker project from first principles through its latest known operational state.
- The prompt directs the new thread to read the authoritative repository documents and inspect current machine state rather than trusting a stale summary; it preserves all secret, session, database, transaction, authorization, duplicate-protection, Khmer TTS, startup, display-placement, and localhost-integration safety boundaries.
- No application behavior or source code was changed in this turn.

### 2026-10-19 — Codex startup question in VS Code

- User asked why Codex could not start in VS Code from this workspace.
- Workspace inspection found no `.vscode` folder or Codex-specific launch configuration. `AGENTS.md` provides instructions for an active agent but does not launch or register one. The project handoff also prohibits running the production speaker from Dropbox; that restriction applies to the app, not to starting a coding agent.
- No extension-specific error or startup log was available, so the exact VS Code-side cause remains unverified. Need the user's intended Codex entry point and displayed error to diagnose further.
- No application code or configuration was changed.

### 2026-10-19 — Multi-PC display and Khmer voice detailed plan

- Owner authorized detailed implementation planning only for one LAN relay and two or three Windows viewers; implementation, deployment, tests against production, application/configuration changes, production restarts, credentials/sessions/database access, scheduled-task changes, and network/firewall changes remain prohibited.
- Updated `reports/codex/ABA_MULTI_PC_DETAILED_IMPLEMENTATION_PLAN.md` to specify that remote speech requires a separately approved additive v2 source API: v1 does not expose `MUTED`, stable bank codes, source epoch/update timestamps, immutable ordered status snapshots, or reliable source-reset detection. V2 must provide a source epoch, ordered immutable updates, a content-free bootstrap/high-water barrier, and explicit cursor-epoch mismatch handling.
- Recommended policy remains independent per-viewer announcements for fresh live events even when the main speaker is `MUTED` or `FAILED`; all snapshot/recovery/resynchronization data is display-only. The plan lists outstanding owner approvals, including this policy, the 30-second freshness limit, mTLS/enrollment, endpoint/firewall scope, contract v2, TTS dependencies, local mute behavior, retention, Windows identities, and deployment topology.
- Documentation only: changed the plan and this handoff. No application behavior or operational state was touched. No tests were run; validation was a focused review of the edited plan sections. Work stops pending owner approval.

### 2026-10-19 — Multi-PC Stage 1 announcement core

- Owner authorized Stage 1 only: an isolated reusable Khmer announcement core, privacy-safe event/state models, synthetic fixtures, and offline unit tests. Stage 2 relay/viewer work remains unauthorized.
- Added `aba_announcement_core/`, `tests/test_announcement_core.py`, `tests/fixtures/announcement_core_events.json`, and `reports/codex/ABA_ANNOUNCEMENT_CORE_STAGE1_REPORT.md`; updated this handoff with package boundaries and remaining dependencies.
- The package copies approved Khmer number wording and the 24-bank exact alias/spoken-name registry without runtime imports from production modules. It validates event allowlists and local one-way playback states. It remains unwired from production code.
- Focused isolated suite passed: 29 tests on Python 3.14, including representative amount parity, all registered bank aliases, schema/privacy rejection, state transitions, and runtime/static dependency checks. No network, database, production API, app, audio, or Telegram behavior was exercised.
- Existing `PROJECT_HANDOFF.md` changes and the untracked `reports/` plan were preserved. No production code/configuration/data, scheduled task, network setting, commit, or push was changed. Await owner approval before Stage 2.
