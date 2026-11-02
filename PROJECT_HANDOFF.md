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

The latest complete suite contains 122 tests and passed after the single-instance and optional privacy-safe integration API changes.

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
- `PULL FROM GITHUB.bat`: checks that no app is running, displays and refuses a dirty worktree without overwriting local changes, pulls with `--ff-only`, refreshes dependencies, and tests. If the pull is blocked by local changes, preserve and review them or use a clean clone; do not force/reset.

PC3 Windows startup configuration (local operating-system state, not synchronized by GitHub):

- Task Scheduler task: `ABA Payment Speaker`;
- trigger: current user logon;
- action: `C:\ABA Payment Speaker\.venv\Scripts\pythonw.exe "C:\ABA Payment Speaker\main.py"`;
- working directory: `C:\ABA Payment Speaker`;
- configured to continue on battery power with no execution time limit.

The task starts the dashboard automatically after this Windows user signs in. It does not solve cross-PC coordination: every other speaker PC must remain closed to prevent duplicate announcements.

Dashboard display placement:

- startup checks the active Windows monitor work areas for up to approximately eight seconds;
- when an active non-primary monitor is available, the dashboard moves to it and maximizes;
- if multiple non-primary displays exist, it selects the one physically closest to the primary display;
- if no secondary monitor becomes available, the dashboard opens at normal 1180×800 size, centered within the primary monitor where possible;
- monitor placement failure never stops payment monitoring.

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
