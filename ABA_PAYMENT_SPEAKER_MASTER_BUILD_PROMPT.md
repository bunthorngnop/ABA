# ABA Payment Speaker Bot — Version 1 Master Build Prompt

## 1. Mission

Build a small, reliable, production-oriented Windows application named **ABA Payment Speaker Bot**.

The application will run locally on a Windows PC and will be developed and managed through **VS Code**.

Its job is to monitor one configured Telegram group for Cambodia ABA payment-notification messages posted by the authorized ABA notification bot/source, validate genuine incoming payments, extract only the fields needed for an audible announcement, and speak the payment through the PC speakers in **Khmer only**.

The normal operator should not need to use VS Code after setup.

### Core workflow

```text
ABA payment notification bot/source
        ↓
Configured Telegram group
        ↓
ABA Payment Speaker Bot
        ↓
Verify source + validate message
        ↓
Deterministic payment parser
        ↓
Amount + payer + originating bank
        ↓
Natural Khmer announcement
        ↓
PC speakers
```

Do not add English announcement mode.

---

## 2. Primary Spoken Format

For a successfully validated payment, use:

```text
បានទទួលប្រាក់ {amount_in_natural_khmer} ពីឈ្មោះ {sender_name}, ធនាគារ {bank_name}។
```

Examples:

```text
បានទទួលប្រាក់ ៥ ដុល្លារ ពីឈ្មោះ NHEAN MONYRACHANA, ធនាគារ ACLEDA។
```

```text
បានទទួលប្រាក់ ២ ពាន់រៀល ពីឈ្មោះ VAN VET, ធនាគារ ABA។
```

If the originating bank cannot be determined reliably, do not invent it. Use a safe fallback announcement that omits the bank clause:

```text
បានទទួលប្រាក់ {amount_in_natural_khmer} ពីឈ្មោះ {sender_name}។
```

---

## 3. Khmer-Only Speech

All audible system and payment announcements must be in Khmer.

English in the original ABA notification may be parsed internally.

Customer names and bank brands may remain in their reliable original Latin spelling when appropriate. Do **not** invent Khmer transliterations of customer names.

The TTS engine must be able to pronounce Khmer text. Keep TTS behind an interface/module so the provider can be replaced later.

Do not add a paid AI/TTS API unless absolutely necessary. Document any internet dependency.

---

## 4. Natural Khmer Amount Rules

### 4.1 KHR

Use natural Cambodian counting units. Prefer:

- ពាន់
- ម៉ឺន
- សែន
- លាន

Do not mechanically read large riel amounts digit by digit.

Confirmed examples:

```text
2,000 KHR     → ២ ពាន់រៀល
10,000 KHR    → ១ ម៉ឺនរៀល
20,000 KHR    → ២ ម៉ឺនរៀល
50,000 KHR    → ៥ ម៉ឺនរៀល
100,000 KHR   → ១ សែនរៀល
250,000 KHR   → ២ សែន ៥ ម៉ឺនរៀល
500,000 KHR   → ៥ សែនរៀល
1,000,000 KHR → ១ លានរៀល
1,500,000 KHR → ១ លាន ៥ សែនរៀល
2,350,000 KHR → ២ លាន ៣ សែន ៥ ម៉ឺនរៀល
```

Implement amount conversion in a separate tested module.

Support reasonable combinations above and below one million without losing natural Khmer phrasing.

### 4.2 USD

USD must also be spoken naturally in Khmer.

Examples:

```text
$1.00   → ១ ដុល្លារ
$5.00   → ៥ ដុល្លារ
$10.00  → ១០ ដុល្លារ
$25.00  → ២៥ ដុល្លារ
$100.00 → ១០០ ដុល្លារ
```

Do not speak unnecessary `.00`.

Support cents if genuine payment notifications contain them. Implement and test a sensible Khmer cents form rather than reading decimal punctuation mechanically.

---

## 5. Two Confirmed Real ABA Notification Formats

These are authoritative Version 1 examples. Do not replace them with fabricated ABA formats.

### Confirmed Sample A — KHR / ABA PAY

Exact real message:

```text
៛2,000 paid by VAN VET (*571) on Aug 28, 07:34 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178792044713371, APV: 761253.
```

Expected extraction:

```text
amount: 2000
currency: KHR
sender_name: VAN VET
bank: ABA
payment_channel: ABA PAY
valid_incoming_payment: true
```

Expected spoken announcement:

```text
បានទទួលប្រាក់ ២ ពាន់រៀល ពីឈ្មោះ VAN VET, ធនាគារ ABA។
```

Confirmed rules from this sample:

1. `៛` means KHR.
2. Extract the amount immediately following `៛`.
3. The payer is between `paid by` and the masked-account parentheses.
4. `VAN VET` is the payer.
5. Ignore `(*571)`.
6. `via ABA PAY` means the bank for the spoken announcement is `ABA`.
7. Ignore the date and time.
8. Ignore merchant/location text such as `at Wing Mart R`.
9. Ignore the later operator/staff fragment `by S.NHEL`.
10. Ignore `Trx. ID`.
11. Ignore `APV`.
12. There are multiple occurrences of `by`; do not confuse the later `by S.NHEL` with the payer.

### Confirmed Sample B — USD / ABA KHQR / Interbank

Exact real message:

```text
$5.00 paid by NHEAN MONYRACHANA (*298) on Aug 28, 08:55 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178792533376804, APV: 360850.
```

Expected extraction:

```text
amount: 5.00
currency: USD
sender_name: NHEAN MONYRACHANA
bank: ACLEDA
payment_channel: ABA KHQR
valid_incoming_payment: true
```

Expected spoken announcement:

```text
បានទទួលប្រាក់ ៥ ដុល្លារ ពីឈ្មោះ NHEAN MONYRACHANA, ធនាគារ ACLEDA។
```

Confirmed rules from this sample:

1. `$` means USD.
2. `$5.00` is spoken as `៥ ដុល្លារ`.
3. The payer is between `paid by` and the masked-account parentheses.
4. `NHEAN MONYRACHANA` is the payer.
5. Ignore `(*298)`.
6. `via ABA KHQR (ACLEDA Bank Plc.)` means:
   - payment channel = `ABA KHQR`
   - originating bank = `ACLEDA`
7. For speech, use the originating bank, not merely the ABA receiving/payment channel.
8. Normalize a known safe legal bank label:
   - `ACLEDA Bank Plc.` → `ACLEDA`
9. Ignore the date and time.
10. Ignore merchant/location text such as `at Wing Mart D`.
11. Ignore the later operator/staff fragment `by S.NHEL`.
12. Ignore `Trx. ID`.
13. Ignore `APV`.
14. Do not assume every ABA notification has originating bank ABA.
15. When `ABA KHQR (...)` reliably contains an originating bank, that parenthesized bank takes precedence for the spoken bank field.

---

## 6. Parser Design

Create a deterministic parser in its own module.

Do **not** use OpenAI, an LLM, OCR, or other AI for Version 1.

The parser should return a structured result containing at least:

```text
amount
currency
sender_name
bank
payment_channel
valid_incoming_payment
confidence/status
reason_if_rejected
```

Use precise format-specific parsing for confirmed formats.

Design the parser so new real ABA formats can be added later without rewriting the whole application.

Do not fabricate unsupported formats simply to increase apparent coverage.

### Fail-safe rule

**SILENCE IS BETTER THAN A FALSE PAYMENT ANNOUNCEMENT.**

If critical parsing is uncertain, malformed, contradictory, or unsupported:

- do not speak;
- mark the event as `NEEDS_REVIEW` or equivalent;
- log a privacy-safe diagnostic reason.

---

## 7. Incoming-Payment Validation

Only speak sufficiently validated incoming payments.

Reject or remain silent for:

- outgoing transfers;
- failed transactions;
- cancelled transactions;
- pending transactions;
- advertisements/promotions;
- balance notifications;
- OTP/security messages;
- login alerts;
- ordinary Telegram conversations;
- unknown or malformed formats;
- messages from unauthorized Telegram senders;
- messages from the wrong group.

Do not infer payment success from vague text.

The Telegram/ABA transaction record remains authoritative. This speaker application is an audible convenience, not independent financial proof.

---

## 8. Telegram Source Security

### Confirmed ABA notification source

The real Telegram bot that sends the user's daily ABA/PayWay payment notifications is:

```text
@PayWayByABA_bot
```

Treat this username as the confirmed expected notification source for Version 1.

However, do **not** guess or fabricate its numeric Telegram sender ID.

During setup/diagnostic mode, the application must observe an actual message from `@PayWayByABA_bot`, display its Telegram `from.id` / numeric sender ID, and allow the user to place that verified value into `.env`.

For production filtering:

1. `ALLOWED_ABA_SENDER_ID` (verified numeric Telegram sender ID) is the authoritative sender check.
2. `EXPECTED_ABA_USERNAME=PayWayByABA_bot` is a secondary diagnostic/sanity check.
3. A message that looks exactly like an ABA notification but comes from any other sender must never trigger a payment announcement.
4. If the numeric sender ID has not yet been verified/configured, production payment announcements must remain disabled. Diagnostic mode may continue to observe sender metadata safely.

Never hard-code an unverified numeric sender ID.

Configuration must include at least:

```text
TELEGRAM_BOT_TOKEN
ALLOWED_CHAT_ID
ALLOWED_ABA_SENDER_ID
EXPECTED_ABA_USERNAME=PayWayByABA_bot
```

Use `.env`.

Provide `.env.example`.

Add `.env` to `.gitignore`.

Never hard-code or log the bot token.

Process only:

1. the configured Telegram group/chat; and
2. messages from the configured authorized ABA notification bot/source.

Use Telegram long polling for Version 1 so no cloud server, public domain, webhook, or Docker deployment is required.

### Bot-to-bot visibility

Before relying on production behavior, verify using the **current Telegram documentation/library behavior** that the receiving bot can actually receive messages posted by the ABA notification bot/source in the group.

Document the exact current BotFather/group configuration required, including any relevant:

- bot-to-bot communication setting;
- privacy mode;
- administrator requirement;
- group permissions.

Do not silently assume bot-to-bot messages are visible.

Create a diagnostic mode that can confirm:

```text
Telegram connection
configured group detected
sender username observed
sender numeric ID observed
message type observed
@PayWayByABA_bot source detected
```

For the first verified message from the expected source, show a clear setup result similar to:

```text
Expected source: @PayWayByABA_bot
Observed username: @PayWayByABA_bot
Observed numeric sender ID: <actual from.id>
Configured group/chat ID: <actual chat id>
Status: READY TO VERIFY
```

Do not automatically trust a sender merely because its username text matches. Require the operator to save/configure the observed numeric ID before enabling production announcements.

The diagnostic output must not reveal secrets.

---

## 9. Privacy

The audible announcement should contain only:

- payment amount;
- currency;
- payer name;
- originating bank, when reliable.

Do not announce:

- masked account digits;
- account numbers;
- transaction IDs;
- APV;
- balances;
- phone numbers;
- dates/times;
- merchant/location details;
- staff/operator identifiers;
- OTP/security information.

For the two confirmed samples specifically, do not speak:

```text
*571
*298
Aug 28 / times
Wing Mart R
Wing Mart D
S.NHEL
Trx. ID
APV
```

Avoid persisting unnecessary sensitive fields.

---

## 10. Bank Rules

Bank extraction must be deterministic.

Confirmed behavior:

```text
via ABA PAY
→ spoken bank = ABA
```

```text
via ABA KHQR (ACLEDA Bank Plc.)
→ payment channel = ABA KHQR
→ spoken originating bank = ACLEDA
```

Create a small explicit normalization map for verified bank names as real samples are collected.

Do not guess unfamiliar bank names.

Do not strip words blindly with a generic regex if doing so could corrupt a legitimate bank name.

Unknown/unreliable bank:

- keep the payment valid only if all other required fields are confidently validated;
- omit the bank clause from speech;
- never invent a bank.

---

## 11. Duplicate Protection — Mandatory

A payment must not be announced twice because of:

- Telegram retries;
- polling reconnects;
- program restart;
- duplicate update delivery;
- internal processing retry.

Use persistent duplicate protection, preferably SQLite.

Use stable Telegram identifiers when available. A privacy-safe deterministic fingerprint may be used as a secondary safeguard.

Persist announcement state before/around audio processing carefully enough to avoid accidental repeated speech after restart.

Document the chosen strategy and its tradeoffs.

---

## 12. SQLite Persistence

Use SQLite for lightweight local state.

Store only useful operational data, such as:

```text
Telegram update/message identifier
timestamp
amount
currency
sender name
normalized bank
payment channel
parser status
announcement status
privacy-safe error/review reason
```

Do not store the Telegram bot token.

Do not unnecessarily store account fragments, APV, transaction IDs, balances, or other banking-sensitive text.

If a raw message is useful in development mode, handle it separately and make retention explicit/minimal.

---

## 13. Khmer Text-to-Speech

Choose a practical Khmer-capable TTS solution that works on Windows.

Requirements:

- Khmer-capable speech;
- clear output;
- no English announcement mode;
- announcements do not overlap;
- TTS errors do not crash Telegram monitoring;
- provider isolated behind an interface;
- volume adjustment if reasonably supported;
- document whether internet is required.

Test the actual Khmer output, not merely that an audio function returns successfully.

A harmless speaker-test sentence is:

```text
ប្រព័ន្ធប្រកាសការទូទាត់កំពុងដំណើរការ។
```

---

## 14. Audio Queue

Implement a single sequential announcement queue.

If three valid payments arrive quickly:

```text
Payment A
Payment B
Payment C
```

required behavior:

```text
Speak A completely
→ Speak B completely
→ Speak C completely
```

Never overlap voices.

Queue/TTS failure for one item must not permanently block later announcements.

---

## 15. Local Operator Dashboard

Create a small Windows-friendly local interface.

Keep it simple and reliable.

Display:

```text
ABA PAYMENT SPEAKER

Telegram: Connected / Disconnected
Speaker: Ready / Error / Muted
ABA Source: Detected / Waiting

Last payment amount
Last payer
Last bank
Last spoken announcement
Payments announced today
```

Provide working controls:

```text
Test Speaker
Mute / Unmute
```

Optional, if simple and reliable:

```text
Recent announcement history
Parser review count
```

Do not expose sensitive transaction fields in the normal dashboard.

The operator should not need to interact with VS Code during normal use.

---

## 16. Development/Test Mode

Provide a safe local test tool where sample notification text can be pasted without performing a real bank transfer.

It should show:

```text
Original test input
↓
Parsed structured fields
↓
VALID / REJECTED / NEEDS REVIEW
↓
Generated Khmer announcement
```

Provide an explicit button/command to speak the generated test announcement.

Do not automatically treat arbitrary pasted text as a real production payment.

Include both confirmed real messages as built-in regression fixtures/tests.

---

## 17. Connection Reliability

The application should survive ordinary network interruptions.

Implement:

- automatic reconnect/retry;
- reasonable backoff;
- error logging;
- no process crash from temporary Telegram failure;
- duplicate protection across reconnection;
- clean shutdown.

Do not create noisy repeated spoken network warnings unless explicitly useful. Connection state should be visible on the dashboard.

---

## 18. Logging

Provide useful local operational logs.

Never log:

- Telegram bot token;
- passwords;
- OTP/security codes;
- full unnecessary banking-sensitive messages in normal mode.

Use privacy-safe structured logging where practical.

Diagnostic logging may include enough information to identify parser problems without exposing unnecessary financial details.

---

## 19. Windows / VS Code Operation

Target:

- Windows PC;
- VS Code during development;
- Python;
- older i5-class CPU;
- approximately 8 GB RAM.

Keep resource usage light.

Do not require:

- Docker;
- Linux;
- cloud hosting;
- GPU;
- local AI models;
- webhooks;
- microservices.

During development, the app must run easily from the VS Code terminal.

After successful testing, README must explain a safe Windows auto-start method so the application can start after reboot without requiring VS Code to remain open.

---

## 20. Recommended Project Structure

Use a clean structure similar to:

```text
ABA-Payment-Speaker/
│
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── app/
│   ├── config.py
│   ├── telegram_listener.py
│   ├── payment_parser.py
│   ├── khmer_numbers.py
│   ├── bank_normalizer.py
│   ├── tts.py
│   ├── audio_queue.py
│   ├── database.py
│   └── dashboard.py
│
├── tests/
│   ├── test_real_aba_messages.py
│   ├── test_payment_parser.py
│   ├── test_khmer_numbers.py
│   ├── test_bank_normalizer.py
│   └── test_duplicates.py
│
├── data/
└── logs/
```

You may improve this structure for a clear engineering reason, but do not overengineer.

---

## 21. Mandatory Automated Tests

### 21.1 Natural KHR speech

Test at least:

```text
2,000       → ២ ពាន់រៀល
10,000      → ១ ម៉ឺនរៀល
20,000      → ២ ម៉ឺនរៀល
50,000      → ៥ ម៉ឺនរៀល
100,000     → ១ សែនរៀល
250,000     → ២ សែន ៥ ម៉ឺនរៀល
500,000     → ៥ សែនរៀល
1,000,000   → ១ លានរៀល
1,500,000   → ១ លាន ៥ សែនរៀល
2,350,000   → ២ លាន ៣ សែន ៥ ម៉ឺនរៀល
```

### 21.2 USD speech

```text
$5.00  → ៥ ដុល្លារ
$10.00 → ១០ ដុល្លារ
$25.00 → ២៥ ដុល្លារ
```

### 21.3 Exact Real Sample A

Input:

```text
៛2,000 paid by VAN VET (*571) on Aug 28, 07:34 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178792044713371, APV: 761253.
```

Expected:

```text
amount = 2000
currency = KHR
sender_name = VAN VET
bank = ABA
payment_channel = ABA PAY
valid_incoming_payment = true
```

Expected speech:

```text
បានទទួលប្រាក់ ២ ពាន់រៀល ពីឈ្មោះ VAN VET, ធនាគារ ABA។
```

### 21.4 Exact Real Sample B

Input:

```text
$5.00 paid by NHEAN MONYRACHANA (*298) on Aug 28, 08:55 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178792533376804, APV: 360850.
```

Expected:

```text
amount = 5.00
currency = USD
sender_name = NHEAN MONYRACHANA
bank = ACLEDA
payment_channel = ABA KHQR
valid_incoming_payment = true
```

Expected speech:

```text
បានទទួលប្រាក់ ៥ ដុល្លារ ពីឈ្មោះ NHEAN MONYRACHANA, ធនាគារ ACLEDA។
```

### 21.5 Safety tests

Test that:

- a duplicate notification is not announced twice;
- outgoing transfer is rejected;
- failed payment is rejected;
- pending payment is rejected;
- unrelated Telegram text is rejected;
- unauthorized sender is rejected;
- wrong group is rejected;
- malformed payment remains silent;
- unknown bank is not guessed;
- the later `by S.NHEL` is never parsed as payer;
- masked account fragments are never included in speech;
- Trx. ID and APV are never included in speech;
- reconnect/reprocessing does not produce duplicate announcements.

---

## 22. README Requirements

Write README.md for a non-expert operator.

Include step-by-step:

1. prerequisites;
2. recommended Python version;
3. opening the project in VS Code;
4. creating a virtual environment;
5. installing dependencies;
6. creating/configuring the Telegram receiving bot;
7. current required BotFather settings;
8. adding/configuring the bot in the Telegram group;
9. obtaining the allowed chat/group ID;
10. obtaining/confirming the authorized ABA sender ID;
11. creating `.env` from `.env.example`;
12. running the app;
13. using diagnostic mode;
14. testing the two confirmed real samples;
15. testing Khmer speaker output;
16. using mute/unmute;
17. troubleshooting bot-to-bot visibility;
18. troubleshooting Khmer TTS;
19. logs and privacy;
20. safe Windows auto-start after the application is validated.

Never instruct the user to commit `.env` or expose the bot token.

---

## 23. Implementation Sequence

Work autonomously, but follow this order:

1. Inspect the existing project directory.
2. Preserve useful existing work.
3. Create a concise implementation plan.
4. Verify current Telegram bot-to-bot/group-message requirements from authoritative Telegram documentation.
5. Select stable Python dependencies.
6. Select and validate a practical Khmer TTS approach.
7. Implement configuration/security.
8. Implement Khmer number conversion.
9. Implement bank normalization.
10. Implement the deterministic parser using the two confirmed real samples.
11. Implement automated tests.
12. Implement SQLite duplicate protection.
13. Implement Telegram listener/filtering.
14. Implement TTS and sequential audio queue.
15. Implement the local dashboard.
16. Implement development/diagnostic mode.
17. Run the complete test suite.
18. Fix failures.
19. Perform a local smoke test where possible.
20. Complete README.
21. Report results and stop.

Do not stop after scaffolding. Produce a runnable Version 1.

---

## 24. Explicit Non-Goals for Version 1

Do not add:

- OpenAI API;
- LLMs;
- image recognition;
- OCR;
- voice recognition;
- English announcement mode;
- cloud database;
- cloud server requirement;
- Docker;
- microservices;
- customer accounts;
- unnecessary authentication systems;
- unnecessary web infrastructure;
- speculative ABA message formats.

Do not modify unrelated projects or files.

---

## 25. Source-of-Truth Rule

The confirmed Telegram notification-source username is:

```text
@PayWayByABA_bot
```

Its numeric Telegram sender ID is **not yet known** and must be discovered/verified from a real observed message during diagnostic setup. Never invent it.

For payment parsing, these two real messages are the confirmed starting source of truth:

```text
៛2,000 paid by VAN VET (*571) on Aug 28, 07:34 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178792044713371, APV: 761253.
```

```text
$5.00 paid by NHEAN MONYRACHANA (*298) on Aug 28, 08:55 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178792533376804, APV: 360850.
```

If future real ABA notifications differ, do not silently generalize in a risky way.

Make parser extensions explicit and test-driven.

---

## 26. Completion Report

When Version 1 is complete, report:

1. what was built;
2. project structure;
3. files created/changed;
4. dependencies chosen;
5. Khmer TTS solution chosen and why;
6. whether TTS requires internet;
7. Telegram/BotFather configuration required;
8. how bot-to-bot visibility was verified;
9. parser behavior for both confirmed real messages;
10. automated test results;
11. duplicate-protection design;
12. privacy/security protections;
13. any unresolved issue;
14. any additional real ABA notification samples that would improve coverage;
15. exact next steps for the user in VS Code.

Do not begin Version 2.

Stop after the completion report and wait for further instruction.
