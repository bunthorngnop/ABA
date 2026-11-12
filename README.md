# ABA Payment Speaker Bot — Version 1

This Windows application monitors configured Telegram groups through your own authenticated Telegram account, validates the confirmed ABA/PayWay incoming-payment grammar, and announces valid incoming payments in Khmer. Telegram remains the authoritative payment record. Uncertain events stay silent.

## Operational dashboard

The primary screen is a dark, shop-counter dashboard built around the latest validated payment:

- the received KHR or USD amount is the largest element; instead of `៛`/`$` it is preceded by a currency coin icon (green with a white `៛` for KHR, gold with a white `$` for USD) about 1.1× the digit height, centred vertically on the digits, and the amount font shrinks if needed so note and amount always stay on one line;
- the compact header is a single row with the shop's two-line Khmer title at left, time/date/LIVE centered across the full window, and a modern "glass ticker" NBC card at right: a rounded dark card with a cyan-to-violet gradient border, a live dot, the Khmer title `អត្រាប្តូរប្រាក់ធនាគារជាតិ` (Siemreap) and the date in Orbitron, the owner-supplied NBC logo (`assets/nbc_logo.png`, scaled to the digit height with its white background made transparent; the card works without it) followed by the official rate in large Bahnschrift digits and a matching `៛`, centred horizontally and vertically together with a pill — green `▲ +2` / gold `▼ −2` against NBC's previous value (the rate itself also turns green or gold), or a neutral grey `▲▼ 0` while unchanged; the Khmer title uses the same grey as the date — `KHR / USD` in Montserrat, and a 7-day sparkline built from one stored public NBC value per day; the header stays 170 px high at 1080 px and wider;
- the Dashboard is split 50% / 25% / 25% at every window size: `LAST PAYMENT RECEIVED` (with its announcement status on the same title row, e.g. `LAST PAYMENT RECEIVED · ✓ ANNOUNCED`) with the recent-payments list below it in the left half, and the rates & gold card and private-rates card each spanning the full height of both, so their bottom edges line up with the payment history;
- a scrolling ticker in the empty part of the tab row (right of DASHBOARD and SETTINGS & DIAGNOSTICS, never covering them) shows today's totals, e.g. `TODAY 23 payments · KHR 1,250,000 · USD 340.00` (successfully announced payments only; KHR green, USD gold), then the fuel prices `តម្លៃសាំងធម្មតា 4,350៛ ▼700 · តម្លៃប្រេងម៉ាស៊ូត 5,300៛ ▼350 · អនុវត្តចាប់ពីថ្ងៃទី 11 ដល់ 21 ខែវិច្ឆិកា ឆ្នាំ2026` (Western digits), then a drawn gold-bar icon with `≈ $… / ដំឡឹង · ≈ $… / ជី` in gold text with a dark shadow; every ticker arrow uses the fuel colours (▲ red = price up, ▼ green = price down) and appears only after a change; fuel prices turn grey with `តម្លៃចាស់` once the announced period has ended;
- the rates card (`អត្រាប្តូរប្រាក់ រៀល ដុល្លារ និងយ័ន (ចិន)`; until 2026-11-12 the rates & gold card `អត្រាប្តូរប្រាក់ និង មាស`) is a `BANK | ទិញ $ | លក់ $` table (header row highlighted in slate blue) for ACLEDA Notes and Wing Telegraphic Transfer Outbound (KHR per USD) plus a full-width international GOLD row: a small `GOLD · XAU/USD · oz · <time>` line, then the price per troy ounce, `≈ $… / ដំឡឹង` and `≈ $… / ជី` (exact conversions from 37.5 g and 3.75 g), all three at the same Bahnschrift size, each local unit followed by a small Cambodian flag drawn at the figure height (Tk cannot show the flag emoji); NBC is shown only in the header card; ABA is not shown because ABA's website does not permit automated access. Figures use Bahnschrift (18 pt, 12 pt below 1080 px): ទិញ red, លក់ light blue, gold warm gold, with the existing gentle pulse; rows keep dark tints (ACLEDA teal-slate, WING violet-slate, GOLD dark gold);
- every rate box shows one trend arrow right after its figure, in the private card's style: `▲` green or `▼` gold for the direction of its last change (no arrow before the first change, or when the value is missing or outdated); the gold ដំឡឹង and ជី lines repeat the gold arrow after their flags; no cell is outlined; bank figures shrink, never their cells, so figure and arrow stay on one line; ACLEDA and WING show their names centred above their logos (60 px, 44 px below 1080 px), and the compact gold row leaves spare height to the bank rows; the best fresh ACLEDA/WING quotes (highest ទិញ, lowest លក់) get a thin gold outline; an outdated row dims and loses its arrows/outline; the footer shows when bank rates were last checked;
- bank rates load from the local SQLite cache at startup and are fetched in the background approximately every 15 minutes; on weekends and holidays NBC publishes no new rate, so the last published NBC rate (with its date) stays current for up to 4 days instead of being marked stale; gold is fetched at most every 12 hours (see **Gold price** below); the cache keeps each figure's previous different value so arrows survive restarts; displayed age/status refreshes locally once per second without network requests;
- the private-rates card is dark with a yellow title bar (`អត្រាប្តូរប្រាក់ឯកជន - Private rates`); when the card is at least 300 px wide a status dot and a short CONNECT/DISCONNECT button share the title bar, otherwise the status chip and button sit in a yellow footer;
- private-group posts remain unverified and are only reformatted for display; they are never treated as bank quotes, stored, or spoken; the visible UNVERIFIED label has been removed; the group reader connects automatically when ABA starts, using a separate Telegram session from the payment listener;
- Khmer text in the private card uses Siemreap when installed and the application's Khmer-capable font fallback otherwise; number-only and Latin segments use the UI font;
- SYSTEM STATUS, TODAY totals, and CONTROLS are available together in the scrollable Operations subtab under Settings & Diagnostics; CONTROLS is no longer on the Dashboard;
- the shop header uses the two-line Khmer title `វីង វណ្ណា-ស្រីម៉ិច` / `ប្រព័ន្ធទទួលប្រាក់` in Khmer OS Muol Light when installed, with safe Khmer-capable fallbacks;
- KHR amounts use success green while USD amounts use a distinct warm gold;
- the validated payer name appears in blue; the two boxes under the amount are headed `● បានទទួលប្រាក់ពីឈ្មោះ` (sender) and `▥ ផ្ទេរមកពីធនាគារ` (bank) in Siemreap 9 pt (Bokor was tried but is too thin at that size), with all text centred; the sender name uses Khmer OS Muol Light regular, the bank name is unchanged;
- the normalized originating bank appears in violet;
- `ANNOUNCED` appears only after the audio queue reports successful speech;
- the recent-payments list (no title; it starts at the `AMOUNT | SENDER | BANK | TIME` headings; AMOUNT right-aligned, SENDER left, BANK centred, TIME right; long text wraps to at most two lines, ending in `…` if longer) sits under the payment card at the same 50% width; its list grows or shrinks (minimum two rows) to fill the space left in the window, so the Dashboard avoids scrolling at the shop screen size; below 1080 px the BANK and TIME columns use a smaller condensed font (Bahnschrift SemiCondensed);
- when today has more announced payments than fit, the recent-payment list scrolls through up to 1,000 current-day records, newest first; complete KHR rows are green, complete USD rows are gold, and sender names are bold;
- the Dashboard adapts to shorter displays by tightening sender/bank cards and the amount typography; a vertical scrollbar keeps the payment, rates, and history accessible when they cannot fit in the available height.
- at application startup, the dashboard waits briefly for an active secondary monitor and maximizes there; if no secondary display becomes available, it opens at normal size on the primary monitor.

Telegram commissioning IDs and the safe parser test remain available under **Settings & Diagnostics**, away from the operational display. No raw Telegram payload, account fragment, transaction ID, APV, merchant, operator, credential, or session data is shown in payment history.

## What changed

Telegram did not expose Bot-to-Bot Communication Mode for the original receiving bot, so the Bot API listener was replaced with a read-only Telethon user-session listener. Payment parsing, Khmer amount conversion, bank normalization, SQLite duplicate protection, payment wording, and the configured payment voice remain unchanged. The dashboard also supports a separate read-only viewer for posts from one fixed private exchange group, first-party public bank-rate refresh from NBC/ACLEDA/Wing, and scheduled time announcements through the existing audio queue.

The payment listener and private-group reader use different session files. The private-group reader does not send messages, join groups, modify chats, parse messages as payments, or queue speech. It does not expose raw payment messages in the dashboard. Exchange-rate fetch/parse/cache failures are isolated from payment monitoring, the private reader, scheduled announcements, and speech.

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

Microsoft voice `km-KH-SreymomNeural` is used through `edge-tts` for payment announcements, so speech requires internet. Announcements are queued and never overlap.

### Daily time announcements

The application queues Khmer time announcements using Cambodia local time:

- Sunday–Wednesday and Friday–Saturday: 16:10 and 18:10;
- Thursday: 16:05 and 18:05, prefaced with a Khmer equivalent of “Today is Thursday.”

Scheduled announcements use the male Khmer voice `km-KH-PisethNeural`; payment announcements continue using the configured voice. Each date/time slot is claimed once in the local SQLite database. Missed slots are skipped rather than announced late, and the existing speaker mute setting is respected. The application must be running, awake, online for TTS, and unmuted at the scheduled time. It does not change Windows system volume.

### Hourly time announcements

Every day, exactly on the hour from 08:00 to 22:00, the male voice says `នៅពេលនេះម៉ោង {hour} {period}` (no final `។`): ព្រឹក for 08:00–11:00, `១២ ថ្ងៃត្រង់` at 12:00, រសៀល for 13:00–17:00 (spoken as ១–៥), ល្ងាច at 18:00 (៦), and យប់ for 19:00–22:00 (៧–១០). These are in addition to the 16:10/18:10 (Thursday 16:05/18:05) announcements. If a payment announcement is speaking, the hourly announcement follows it; if it cannot start within 60 seconds of the hour it is skipped, never played late. Each hour is claimed once per day in SQLite, and mute is respected.

### Payment-monitoring alert

The payment listener pings Telegram every 30 seconds. If payment monitoring stays down for 2 minutes (including no connection at startup), the male voice says `សូមជូនដំណឹង ប្រព័ន្ធទទួលប្រាក់ត្រូវបានផ្តាច់ សូមពិនិត្យអ៊ីនធឺណិត`, or `សូមចូល Telegram ឡើងវិញ` when Telegram has revoked or expired the login, and repeats every 10 minutes until it recovers, when `ប្រព័ន្ធទទួលប្រាក់បានភ្ជាប់ឡើងវិញ` is said once. Alerts play from pre-recorded files in `assets/` (no internet needed), are heard even when the speaker is muted, run at any time of day, and are active only in production mode.

### USD/CNY official rate (rates card, third row)

The rates card is titled `អត្រាប្តូរប្រាក់ រៀល ដុល្លារ និងយ័ន (ចិន)` (two centred lines when the card is narrow). Its third row, below the unchanged ACLEDA and WING rows, shows the official USD/CNY central parity (人民币汇率中间价) published by CFETS under People's Bank of China authority each China working day at 9:15 Beijing time (08:15 Cambodia): one figure centred across the ទិញ and លក់ columns with a small `¥`, the owner-supplied logo (`assets/cny_logo_60.png` / `cny_logo_44.png`), ▲ green / ▼ gold after a change, and the caption `PBOC central rate · <date>`. It is read every 15 minutes with the other rates from `https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json`. That server omits its intermediate certificate, so the public intermediate `assets/certs/sheca_ov_tls_rsa_ca_a1.pem` (issued by UCA Global G2 Root, which Windows trusts) is supplied for those requests only; certificate and hostname verification stay on. The PBOC website is not used because its certificate chain ends at a root Windows does not trust. Gold no longer has a row in the card; it appears in the ticker.

### Gold price

The GOLD row uses GoldAPI.io's free plan (150 requests per month), which permits displaying the data to the app's users. To enable it:

1. Create a free account at goldapi.io and copy your API key.
2. Add one line to this PC's private `.env`: `GOLD_API_KEY=your-key-here`. Never commit, paste, or share the key.
3. Restart ABA.

The app sends the key only as a request header, redacts it from logs, and fetches gold at most every 12 hours (about 60 requests per month), including across restarts because the last price is cached. After a failed request it waits at least one hour before retrying. Without a key the gold row shows `—` and everything else works normally. The `≈ / ដំឡឹង` and `≈ / ជី` lines are exact conversions of the world price (37.5 g and 3.75 g per troy ounce of 31.1034768 g) and do not include local shop premiums.

### Fuel prices (Ministry of Commerce channel)

The private-group reader account also follows the fuel-price Telegram channel `-1003653280106` (owner-chosen; the account must already be subscribed; the Ministry of Commerce channel `-1001254362029` posts its prices only as images). Only posts containing `ថ្លៃលក់រាយប្រេងឥន្ធនៈ` with `សាំង = … រៀល` and `ម៉ាស៊ូត = … រៀល` are used; nothing else from the channel is shown. Khmer vowel and sign marks are compared in one canonical order, so words typed with the marks in a different order still match. Prices may use Khmer or Western digits with spaces or commas and end in `រៀល` or `៛`; the change in brackets (`ចុះថ្លៃ…` down, `ឡើងថ្លៃ…` up, `នៅដដែល` unchanged) sets the arrow, otherwise the previous saved price is used; the `ថ្ងៃទី … ខែ … ឆ្នាំ …` dates give the period. On connect the latest of the 30 most recent channel posts is used, and new or edited announcements update the ticker live. The latest prices are kept in the local database (`fuel_price_cache`) so they show immediately after a restart. Display only; never used for payments.

### Private exchange-group posts

The private-rates card (third Dashboard column) connects automatically when ABA starts and shows posts from the private exchange group already accessible to the group member's account. Each sender appears once with their latest post (reposts replace the earlier entry), newest sender first, under a `HH:MM  short name` header. Short names drop emoji, anything after `(` or `👉`, and 3+ digit groups, and are cut at about 18 characters.

Posts are converted, for display only, into two-line offers:

```text
USD→KHR   4090.5 KHR ▼  +5.5      ← tag, rate (14 pt bold), trend arrow, gap from NBC
          30,000 USD  ABA·AC      ← amount (12 pt bold), banks
```

- **Tag**: `KHR→USD` (light blue) when the poster offers riel for dollars, `USD→KHR` (light red) when the poster offers dollars for riel, and `·` when the direction is unclear (for example `អោយ ABA 4091`, or both currencies offered on one line). The tag comes only from the words around `ដូរ`/`ដូ`/`យក`/`ទិញ`/`មាន` and the leading currency; nothing is guessed.
- **Rate**: a four-digit figure between 3,800 and 4,400 with optional 1–2 cent digits after `.` or `,` (thousands separators allowed, e.g. `4,089,5`), always shown with a dot and `KHR`, e.g. `4089.5 KHR`. Sizes and phone fragments are never treated as rates. Below 1080 px the rate and amount use 12 / 10 pt.
- **Trend arrow**: `▲` green / `▼` orange against that sender's previous different rate in the same direction (memory only, so it restarts with the app). **Gap**: the small `+5` / `−2` is the difference from the current NBC official rate.
- **Amount**: thousands separators added; `USD`/`KHR` only when the post marked a currency, `M KHR` for `លាន`, and no currency when the post gave none.
- **Banks**: display-only short names (`ABA`, `AC`, `Wing`, `Amret`, `ស្ថាបនា`, `KB`, `Cana`) plus `គ្រប់កុង`/`អីក៏បាន`; this list is separate from the payment bank registry.
- `$`/`៛` and riel/dollar words become `USD`/`KHR`, glued words are spaced, and `*`, `**`, `x`, `=` become `×` in cleaned text. A line without a rate that sits directly above a rate line in the same group is joined to it; two rate lines are never merged.
- Offers without a rate are shown as muted cleaned text; notes such as `No ABA` and `min 5,000 USD` appear in small muted text. Phone numbers, contact/"Acc" lines, "receive into" bank lists (`យក…` with no number), and blank lines are hidden.
- The summary strip shows, one line per direction, the low–high tagged rate from each sender's latest post in the last 15 minutes (e.g. `KHR→USD  4089 – 4090 KHR ▲`), marked `posts · 15 min`, with an arrow against the previous different range. It does not pick a best rate or a bank.
- A sender's block glows for about 10 seconds when a live post brings new or changed offers (posts loaded at connect do not glow); posts older than 15 minutes turn grey and posts older than one hour move to the bottom.
- Edited posts update in place with `✎`; deleted posts are removed; a photo's caption is formatted like text, and a photo without a caption shows `[photo — see Telegram]`. Text inside images is not read.

The app does not validate or label posts as official bank rates. They remain unverified, but no visible UNVERIFIED label is shown. The title stays on one line as `អត្រាប្តូរប្រាក់ឯកជន - Private rates`. Khmer text uses Siemreap when installed, otherwise the application's Khmer-capable fallback font.

The reader fetches the 50 most recent posts from the fixed target group and keeps up to 200 posts only in memory; the panel does not display or process other dialogs, and nothing from the group is saved or logged. On first connection, the phone number, one-time code, and any two-step-verification password are entered in the application dialog and are not saved. The separate session is stored under `%LOCALAPPDATA%\ABA Payment Speaker\rate_group_user.session`; it is not the payment listener's session. **DISCONNECT** stops reading but leaves that local Telegram session signed in. To resolve access to a private Telegram group, Telegram may return dialog metadata while the app locates that group. A Telegram user session itself can access other chats available to that account, so the account holder should use the dedicated session only on a trusted PC and may revoke it through Telegram at any time. The reader remains independent; payment monitoring and announcements continue if it is unavailable.

## Security and duplicate behavior

- The user session is used only for incoming-message monitoring and required authentication/read operations.
- No send, reply, forward, join, leave, edit, or delete methods are called.
- API hash and phone are defensively redacted from application logging.
- Codes and 2FA passwords exist only in memory while signing in.
- Raw Telegram messages are not logged or stored.
- SQLite stores only useful privacy-safe operational fields.
- A SHA-256 key based on chat ID and message ID is reserved before speech, suppressing retries and duplicates across restarts.
- The fail-safe tradeoff favors one missed announcement after a rare crash over duplicate speech.

## Unified AI Lab integration

The optional integration API is read-only, bearer-authenticated, and restricted to `127.0.0.1`/loopback. It exports only an opaque event ID, authoritative timestamp, integer minor-unit amount, currency, privacy-approved sender display name, safe bank display/mapping status, and announcement status. It never exports raw Telegram messages, Telegram identifiers, usernames, account fragments, merchant data, transaction metadata, credentials, sessions, or diagnostics.

The API reads already-approved database state and is not in the Telegram, parser, duplicate-reservation, dashboard, or Khmer TTS critical path. Bind or configuration failure disables only integration; payment monitoring continues. The standalone dashboard and startup method remain authoritative.

Private `.env` variables:

```dotenv
ABA_INTEGRATION_ENABLED=false
ABA_INTEGRATION_HOST=127.0.0.1
ABA_INTEGRATION_PORT=8766
ABA_INTEGRATION_TOKEN=private-local-token-at-least-32-characters
```

Endpoints:

- `GET /integration/v1/status`
- `GET /integration/v1/health`
- `GET /integration/v1/events?after={opaque_cursor}&limit=50`

Do not expose this port to LAN, Tailscale, router forwarding, or a browser. Unified is only a secondary display/cache and never becomes payment authority.

At process startup a Windows named mutex is acquired before any Telegram initialization. A second local instance exits with `ABA Payment Speaker is already running.` This does not coordinate multiple PCs; the rule **ONLY ONE ABA PAYMENT SPEAKER PC ACTIVE AT A TIME** still applies.

Rollback: set `ABA_INTEGRATION_ENABLED=false` and restart ABA. Telegram monitoring, payment parsing, duplicate protection, Khmer TTS, and the standalone dashboard remain unchanged.

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
