# ABA Multi-PC Display & Khmer Voice — Detailed Implementation Plan

**Status:** Planning only; not approved for implementation  
**Prepared:** 19 October 2026  
**Production constraint:** The existing ABA Payment Speaker remains running and unchanged until a separately approved deployment window.

## 1. Objective and non-negotiable boundaries

Provide verified-payment display and independent Khmer announcements on two or three additional Windows PCs on the same trusted private LAN without creating another Telegram listener or distributing ABA credentials, sessions, databases, or production configuration.

The authoritative boundary remains:

```text
Telegram / PayWay
    -> existing ABA Payment Speaker (only Telegram listener and payment authority)
    -> existing authenticated API on 127.0.0.1:8766
    -> new LAN Relay on the authoritative ABA PC
    -> authenticated protected LAN channel
    -> 2–3 Windows Viewer/Speaker clients
```

The relay and viewers must never parse raw Telegram messages, decide whether a payment is genuine, normalize an unapproved bank, alter the ABA database, or control the authoritative listener. The current standalone ABA dashboard, Khmer speaker, duplicate protection, scheduled startup, and loopback-only API remain operational and independently removable from the new system.

## 2. Components and trust model

### 2.1 Existing authoritative ABA Payment Speaker

Responsibilities remain unchanged:

- Telegram authentication and strict group/sender authorization;
- deterministic PayWay/KHQR parsing and bank normalization;
- persistent authoritative duplicate reservation;
- KHR/USD validation and separation;
- authoritative event storage and source announcement status;
- main-PC dashboard and Khmer TTS;
- privacy-safe event/status API bound only to `127.0.0.1:8766`.

It does not bind to the LAN and does not know about individual viewers.

### 2.2 New ABA LAN Relay

A separate process installed on the authoritative ABA PC. It is the only consumer of the ABA loopback API for multi-PC delivery.

Responsibilities:

- authenticate to `127.0.0.1:8766` using the existing local integration credential held only on the authoritative PC;
- poll source events with one serialized poller;
- validate the exact allowlisted event schema;
- persist its source cursor, relay sequence, viewer identities, revocations, and a bounded sanitized event/outbox cache in its own database;
- publish ordered event updates to authenticated viewers;
- distinguish live delivery from bootstrap/recovery delivery;
- expose relay health without exposing the ABA token or production internals;
- terminate safely if configured to a non-loopback ABA source.

The relay must not open the ABA SQLite file. Its database and logs are separate from ABA.

### 2.3 New Windows Viewer/Speaker

A separate application installed on each display PC.

Responsibilities:

- authenticate to the relay with its own revocable device identity;
- display sanitized verified-payment events and connection health;
- persist a per-device relay cursor and an event-ID deduplication ledger;
- generate and play Khmer speech locally using the approved pronunciation code and configured Khmer voice;
- keep authoritative source status separate from local playback status;
- suppress historical/recovered announcements while still permitting an operator-approved recovered display.

The viewer contains no Telegram libraries, ABA credentials, ABA session, ABA database, or source parser.

## 3. Recommended protected LAN transport

### 3.1 Protocol

Use HTTPS plus WebSocket over TLS between relay and viewers:

- HTTPS for enrollment, health, snapshot, and bounded recovery;
- WebSocket for ordered live event updates and acknowledgements;
- TLS 1.2 minimum, TLS 1.3 preferred;
- relay binds to one explicitly configured private IPv4 address, never `0.0.0.0`;
- no router forwarding, UPnP, public DNS, cloud relay, or automatic Tailscale exposure.

Recommended initial relay port: `8767`, subject to owner approval.

### 3.2 Authentication

Recommended policy is mutual TLS with one certificate per viewer:

- a small relay-local private CA issues client certificates;
- the relay certificate is pinned by CA and expected device name/IP;
- each viewer has a unique device ID and private key protected with Windows DPAPI or Windows Certificate Store;
- the ABA loopback bearer token is never sent to viewers;
- certificates have a finite lifetime, recommended 12 months;
- relay keeps an explicit allowlist and revocation list by certificate fingerprint/device ID;
- authentication failures are rate-limited and logged without secrets.

If the owner declines mTLS complexity, the acceptable fallback is TLS with a pinned relay certificate plus a unique 256-bit bearer credential per viewer stored with DPAPI. One shared token for every viewer is not recommended because it prevents precise revocation.

### 3.3 Network restriction

Windows Firewall should allow inbound relay traffic only when all conditions match:

- Private network profile;
- TCP relay port only;
- relay executable/service only where Windows supports program scoping;
- explicitly approved local subnet or individual viewer IPs;
- no Public or Domain profile unless separately reviewed;
- no inbound rule for ABA port `8766`.

The relay startup must refuse public, wildcard, loopback-only-as-LAN, or unapproved interface selection and show a clear offline state.

## 4. Event contract and state separation

### 4.1 Source event fields

Retain the existing privacy-safe fields:

- `schema_version`
- `event_id`
- `occurred_at`
- `amount_minor`
- `currency`
- `sender_display_name`
- `bank_display_name`
- `bank_mapping_status`
- `announcement_status`
- `announced_at`

No raw message, Telegram ID, message ID, username, account fragment, transaction metadata, balance, credential, session data, or merchant/operator text may be relayed.

### 4.2 Current v1 API limits and required v2 contract

The existing loopback API is v1. It permits `QUEUED`, `SPOKEN`, and `FAILED`, but not `MUTED`; it does not provide a stable bank code, a source-database epoch, or a source update timestamp. Its cursor is a `v1-<sequence>` value. The current event query joins update rows to the event's current row, so several queued update rows may return the same latest state rather than immutable historical status snapshots. A source database reset is not reliably distinguishable from an empty page.

Therefore remote production speech must remain disabled until an additive, backward-compatible v2 API contract is separately approved and implemented. V2 must provide:

- a persisted opaque `source_epoch` that changes whenever the source update sequence is reset or its backing event store is recreated;
- strictly increasing `source_sequence` and immutable `source_update_at` on each event update;
- each update's event fields and source announcement status as they stood at that sequence, rather than a join to mutable current state;
- `source_announcement_status` values `QUEUED`, `MUTED`, `SPOKEN`, and `FAILED` for valid payments;
- a stable approved `bank_code` such as `ABA`, `ACLEDA`, or `UNMAPPED`;
- an authenticated bootstrap/high-water response returning the current `source_epoch` and high-water sequence without payment content;
- an explicit cursor-epoch mismatch response that forces resynchronization instead of appearing as an empty page.

The v1 API remains loopback-only and unchanged during this planning task. No relay may infer a source reset or enable production announcements from v1's cursor alone.

### 4.3 Proposed additive event fields

The current contract is insufficient for exact remote Khmer bank pronunciation and does not export `MUTED`. A separately approved additive contract revision should add:

- `contract_version` or incremented `schema_version`;
- `bank_code`: a stable approved identifier such as `ABA`, `ACLEDA`, or `UNMAPPED`, not a raw input label;
- `source_epoch` and `source_sequence`, identifying the authoritative update stream and this immutable update;
- `source_announcement_status`: `QUEUED`, `MUTED`, `SPOKEN`, or `FAILED`;
- `source_update_at`, generated by the authoritative application;
- relay-only envelope fields described below.

Do not transmit a Khmer speech sentence from the server as an opaque command. Viewers should use a versioned, tested, pure pronunciation package containing the approved Khmer number rules, currency rules, announcement template, and bank-code-to-approved-Khmer-name map. This prevents credentials/parser code from spreading while keeping every viewer consistent with the authoritative speaker.

Unknown/unmapped institutions remain valid, display as `OTHER BANK`, and omit the bank clause in Khmer speech.

### 4.4 Relay envelope

Each relay message should include:

```json
{
  "relay_protocol": 1,
  "relay_epoch": "opaque-random-id",
  "relay_sequence": 12345,
  "delivery_class": "LIVE",
  "relay_received_at": "RFC3339 UTC",
  "server_now": "RFC3339 UTC",
  "event": { "...allowlisted source fields...": "..." }
}
```

`delivery_class` is one of:

- `LIVE`: arrived after the viewer completed its live-session barrier;
- `RECOVERY`: replayed after disconnection;
- `SNAPSHOT`: initial display-only state;
- `STATUS_UPDATE`: later state for an already delivered payment.

Only `LIVE` events can become remotely announcement-eligible.

## 5. Source polling and database-lock safety

The relay must use only the existing loopback HTTP API and must never open or copy the ABA SQLite database.

Recommended limits:

- one source event request in flight at a time;
- normal event polling: once per second;
- source status polling: once every five seconds;
- page size: 50 normally, maximum 100 during catch-up;
- HTTP connect timeout: one second;
- total request timeout: two seconds;
- exponential retry with jitter: 1, 2, 4, 8, then maximum 15 seconds;
- no retry storm and no parallel catch-up workers.

Status changes are consumed from the same cursor-ordered immutable update stream; do not add a second event-status poller. A separate lightweight health poll may continue at the stated five-second interval. Until v2 is available, v1 may be exercised only against synthetic fixtures during development and cannot support production remote speech safely.

The ABA API already serializes database reads through its store lock and caps page size at 100. Relay polling must remain short, read-only, and cursor-based so it does not create long transactions or compete materially with payment reservation/speech updates.

Relay persistence should commit its sanitized event/update and new source cursor atomically. If the process crashes before commit, it safely requests the same source page again and resolves duplicates by `(event_id, source status/update identity)`.

## 6. Ordering and deduplication

### 6.1 Relay ordering

- Preserve the source cursor order exactly.
- Assign a strictly increasing `relay_sequence` to every accepted source update.
- Never reorder updates by client time or sender name.
- Keep the latest state per `event_id` plus a bounded append-only relay outbox.
- Treat duplicate source pages as idempotent; do not create a new logical payment.
- A later status for the same `event_id` updates the event but does not create another payment announcement opportunity.

If source timestamps are equal, `relay_sequence`, not time, determines delivery order.

### 6.2 Per-viewer deduplication

Each viewer maintains its own local SQLite database containing only sanitized fields:

- relay epoch and last acknowledged sequence;
- `event_id` unique key;
- first delivery class/time;
- source state;
- local speech claim/result;
- display timestamps and bounded diagnostics.

Before speech generation starts, the viewer atomically reserves the `event_id` as `CLAIMED`. A crash after reservation favors one missed local announcement over duplicate speech. On restart, `CLAIMED`, `SPOKEN`, `EXPIRED`, and terminal `FAILED` records are never automatically spoken again.

Use a single sequential speech queue per viewer. Multiple payments retain relay order and never overlap.

## 7. Freshness and the announcement policy

### 7.1 Recommended eligibility rule

A remote viewer may announce a payment exactly once only when all conditions are true:

1. the viewer is enrolled, authenticated, and in a completed live session;
2. the message is `delivery_class=LIVE`;
3. the event has not previously been claimed on that viewer;
4. the payment currency is `KHR` or `USD` and its amount is positive;
5. the event contract/schema is supported and passes strict validation;
6. the event age is no more than **30 seconds** at claim time;
7. the event is not older than the viewer's live-session barrier;
8. the source status is an eligible verified-payment state;
9. the local viewer is not muted and its speech queue can accept the event before expiry.

The relay supplies `server_now`; the viewer estimates relay clock offset during handshake and does not rely blindly on its local clock. A clock disagreement over five seconds should disable speech and show `CLOCK CHECK REQUIRED` until corrected.

### 7.2 Main-PC playback outcome policy

**Recommendation:** remote announcement eligibility is independent of whether the main PC ultimately speaks, is muted, or fails. The payment has already passed authoritative validation; the main speaker result is an output-device result, not a payment-validity decision.

- `QUEUED`: eligible immediately when received live and fresh. Reserve once and enqueue local Khmer speech.
- `MUTED`: still eligible on a remote viewer if first received live/fresh; show `MAIN SPEAKER MUTED` separately.
- `SPOKEN`: eligible if it is the first live/fresh state seen for that event; if already claimed from `QUEUED`, update display only.
- `FAILED`: still eligible if first received live/fresh because the payment remains valid; show `MAIN ANNOUNCEMENT FAILED` separately.

A later main-PC state must never cause a second remote announcement. A main-PC `FAILED` or `MUTED` state must not cancel speech already claimed locally.

This policy satisfies independent announcements on every PC and allows remote viewers to provide useful coverage when the main speaker is muted or fails. It requires explicit owner approval because some operators may instead want viewers to mirror main-PC mute globally.

### 7.3 Viewer mute and failure

Viewer-local states are separate:

- `LOCAL_QUEUED`
- `LOCAL_SPEAKING`
- `LOCAL_SPOKEN`
- `LOCAL_MUTED`
- `LOCAL_FAILED`
- `LOCAL_EXPIRED`

If the viewer is locally muted when a live event arrives, reserve it as `LOCAL_MUTED` and do not speak it later after unmute. If TTS generation or playback fails, mark `LOCAL_FAILED`; bounded retry is allowed only while the original 30-second freshness window remains. Never replay it minutes later.

## 8. Initial synchronization, reconnection, and cursor reset

### 8.1 Relay first start

Use the v2 authenticated bootstrap/high-water operation to atomically establish `(source_epoch, high_water_sequence)` without returning payment content. Persist that pair before starting event polling. Updates at or below the high-water sequence are historical and display-only (if a separate snapshot is approved); updates strictly after it are candidates for `LIVE`, subject to the freshness and schema checks. This barrier deliberately favors suppressing an event that races with initial enrollment over announcing a payment that may be historical.

Do not derive a live barrier by draining v1 pages or by comparing wall-clock timestamps. V1 cannot distinguish a source sequence reset reliably and its update rows are not immutable snapshots. Relay/viewer production speech remains off until v2's barrier and update semantics are implemented and validated with synthetic data.

### 8.2 Viewer enrollment/first connection

At first connection:

- relay sends a display snapshot and current high-water sequence;
- viewer persists that sequence as its live-session barrier;
- all snapshot events are display-only;
- relay begins `LIVE` delivery only after viewer acknowledges the barrier;
- viewer never announces anything received before that acknowledgement.

### 8.3 Viewer reconnection

On reconnect:

- viewer sends relay epoch and last acknowledged sequence;
- relay may replay bounded missed updates as `RECOVERY` for display consistency;
- all replayed updates are speech-ineligible, even if their timestamps are recent;
- once replay completes, relay sends a new live barrier;
- only later `LIVE` updates can be spoken.

This intentionally means a payment received while a viewer was offline is not announced when it reconnects.

### 8.4 Cursor invalidation/reset

If v2 reports a source-epoch mismatch, or the relay database is lost:

- obtain the current `source_epoch` and high-water sequence through the v2 bootstrap operation;
- change `relay_epoch`;
- enter `RESYNCING` state;
- stop live delivery temporarily;
- persist the new source cursor and repeat the source bootstrap barrier procedure;
- send viewers a display-only snapshot/reset notification;
- require a fresh viewer live barrier;
- never announce updates replayed or discovered during resynchronization; only updates strictly after the new high-water barrier may be considered live.

If proof is ambiguous, suppress speech. Silence is preferred over replaying an old payment.

## 9. Viewer enrollment and revocation

### 9.1 Enrollment workflow

Enrollment must require a person at the authoritative PC:

1. operator starts `relay-admin enroll` locally;
2. relay creates a single-use random enrollment code valid for ten minutes and limited to one device;
3. viewer generates its private key locally and submits a certificate signing request over the protected enrollment endpoint;
4. operator confirms the requested device name and displayed certificate fingerprint on the authoritative PC;
5. relay issues the client certificate and adds the device to its allowlist;
6. viewer stores credentials with DPAPI/Certificate Store and performs a test connection;
7. relay closes the enrollment code after first use.

Enrollment must not reveal the ABA integration token.

### 9.2 Revocation

The relay admin interface must support:

- list device IDs, names, fingerprints, last connection, and status;
- revoke one viewer immediately;
- reject revoked certificates on new connections;
- disconnect an already connected revoked viewer;
- rotate one viewer credential without rotating all viewers;
- rotate the relay CA/certificate through an explicit planned procedure.

Revocation and authentication logs contain device metadata only, never payment secrets or credentials.

## 10. Per-viewer Khmer speech

Create a small versioned `aba_announcement_core` package containing only pure, non-secret behavior:

- natural Khmer integer and USD-cent rendering;
- KHR/USD wording and formatting;
- approved Khmer payment sentence template;
- stable bank-code-to-approved-Khmer-name mapping;
- unknown-bank omission behavior;
- input validation and deterministic unit tests.

The viewer uses the same approved default voice (`km-KH-SreymomNeural`) and allows only local device-level voice/volume configuration. It must not alter authoritative payment data.

Recommended playback pipeline:

1. atomic event claim;
2. render Khmer text from validated sanitized fields;
3. synthesize to a temporary local file with a ten-second timeout;
4. play through the configured Windows output device;
5. delete temporary audio;
6. persist local terminal status;
7. optionally acknowledge local result to relay for fleet health only.

Viewer acknowledgements must never modify the authoritative ABA event or source announcement status.

## 11. Display behavior

The viewer may reuse the visual hierarchy of the standalone dashboard but should clearly identify itself as a remote viewer. Minimum display:

- connection state and relay identity;
- large amount with separate KHR/USD colors;
- sender and safe bank display name;
- source announcement status;
- local viewer speech status;
- last three live/recovered events, with recovered items visibly labeled and never announced;
- last live event time and clock health;
- enrollment/device name.

Never present a recovered event as newly received. Do not expose tokens, certificates, cursors, internal database paths, or raw payloads in the ordinary UI.

## 12. Windows deployment and startup

### 12.1 Relay PC

- install in a normal non-Dropbox directory, proposed `C:\ABA LAN Relay`;
- create a dedicated Python 3.12 virtual environment or signed packaged executable;
- store relay database/logs under `%LOCALAPPDATA%\ABA LAN Relay` or `%PROGRAMDATA%` if run as a service;
- store secrets/keys with DPAPI or Certificate Store, never `.env` in source;
- run under a least-privilege dedicated account where practical;
- use one Windows service or scheduled task with a named single-instance mutex;
- depend on network availability but not on ABA process startup success; retry loopback safely;
- add only the narrowly scoped Private-profile firewall rule after explicit approval.

### 12.2 Viewer PCs

- install in a normal local directory, proposed `C:\ABA Payment Viewer`;
- keep a machine-local virtual environment, viewer database, logs, and certificate;
- use a per-user scheduled task at logon for a visible dashboard;
- enforce a viewer single-instance mutex;
- retry relay connectivity with bounded backoff;
- auto-place/maximize on the configured display using the proven monitor-selection pattern;
- require an explicit selected audio output device or verified Windows default;
- do not require administrator rights during daily operation.

Installers must never contain production tokens, certificates, Telegram data, databases, or real payment fixtures.

## 13. Logging, privacy, and retention

Relay and viewer logs must be structured and redacted. Log only:

- connection transitions;
- device ID/name;
- relay sequence and opaque event ID where operationally necessary;
- schema/freshness/dedup decisions;
- TTS result without speech text;
- exception type, not raw response bodies.

Do not log sender names or amounts by default. A short, explicit diagnostic mode may show sanitized synthetic data only.

Recommended retention:

- relay outbox: 24 hours or 10,000 updates, whichever is smaller;
- viewer dedup ledger: 30 days;
- operational logs: rotating files, seven days;
- certificates/revocations: until expiry plus audit retention.

Retention values require owner approval.

## 14. Synthetic-only testing strategy

No automated test may connect to production Telegram, production ABA port `8766`, the production database, or real payment history.

### 14.1 Unit tests

- schema allowlist and rejection of extra/private fields;
- KHR/USD minor-unit handling;
- approved Khmer numbers, cents, and bank pronunciations;
- unknown bank display/speech omission;
- source and local state machines;
- freshness, clock skew, and live-session barriers;
- relay ordering and idempotency;
- per-viewer atomic dedup claims;
- enrollment expiry, certificate validation, and revocation;
- loopback-only source enforcement and private-LAN bind validation.

### 14.2 Relay integration tests

Use a fake loopback ABA API with synthetic opaque events to test:

- pagination and cursor persistence;
- repeated pages and status transitions;
- cursor invalidation and relay epoch reset;
- events arriving during bootstrap;
- database busy/timeouts without touching ABA SQLite;
- API downtime/backoff;
- multiple viewers with independent acknowledgements;
- revoked and malformed clients;
- TLS certificate expiry and wrong-CA rejection.

### 14.3 Viewer integration tests

Use a fake TLS relay and a fake speech provider:

- initial snapshot never speaks;
- reconnect replay never speaks;
- a fresh live event speaks once;
- repeated/status-updated event never speaks twice;
- offline-period events display but do not speak;
- queue ordering and non-overlap;
- local mute reserves without later replay;
- main `MUTED`/`FAILED` policy;
- TTS timeout within and beyond freshness;
- crash between claim, synthesis, playback, and completion.

### 14.4 LAN laboratory test

Use synthetic events only on an isolated Private-profile test network:

- one relay test PC and three viewer PCs;
- packet loss, sleep/wake, Wi-Fi roaming, relay restart, viewer restart;
- certificate enrollment/revocation;
- firewall validation showing the port unavailable from unapproved addresses/profiles;
- verify no listener on `0.0.0.0`, public interfaces, or port `8766`;
- verify each viewer speaks independently once.

### 14.5 Production commissioning gate

After all synthetic tests pass and the owner separately approves deployment:

- deploy relay disabled;
- verify it can read only localhost status, not event content, in shadow mode;
- deploy one viewer with speech disabled;
- validate authentication, live barrier, display, and recovery using relay-generated synthetic commissioning events kept separate from ABA events;
- enable one viewer's speech for synthetic events only;
- expand to remaining viewers;
- enable production event delivery only in a final explicit window.

No synthetic event may enter ABA production history or be shown as an authoritative payment.

## 15. Implementation stages

### Stage 0 — Owner decisions and threat model

Approve the decisions in Section 17. Freeze protocol/version/security choices. No production change.

### Stage 1 — Pure shared contract and pronunciation package

Build versioned schemas, state machines, Khmer rendering, and synthetic fixtures. No networking and no production dependency.

### Stage 2 — Relay core against fake ABA API

Implement source polling, cursor barriers, sanitized persistence, sequencing, and recovery against a fake server.

### Stage 3 — Relay security and enrollment

Implement TLS/mTLS, device lifecycle, revocation, rate limits, and bind/firewall validation. Complete security tests.

### Stage 4 — Viewer core

Implement authenticated connection, display cache, dedup ledger, freshness gates, local speech queue, and fake-TTS tests.

### Stage 5 — Synthetic multi-PC laboratory

Exercise one relay plus three viewers under failures. Produce a signed-off test report and rollback rehearsal.

### Stage 6 — Additive ABA contract enhancement

Only if approved, add the v2 source epoch, immutable ordered update snapshots, bootstrap/high-water operation, explicit cursor-epoch mismatch, `MUTED`, stable bank-code, and source-update timestamp support behind a disabled feature flag. Run the complete ABA regression suite in a non-production clone. Preserve v1 compatibility and keep the existing API bound to `127.0.0.1`.

### Stage 7 — Disabled production installation

Install relay and viewers disabled. Add no firewall rule until binaries, identities, paths, and hashes are verified.

### Stage 8 — Shadow commissioning

Enable relay source polling and viewer display with production speech disabled. Confirm source load, cursor barriers, no history replay, and no impact to ABA.

### Stage 9 — Controlled activation

Enable viewer speech one PC at a time, observe synthetic commissioning events, then separately approve authoritative live delivery. Retain instant disable controls.

## 16. Rollback

Rollback must not require stopping or changing ABA Payment Speaker.

### Viewer rollback

1. disable viewer speech;
2. stop/disable its scheduled task;
3. revoke its device identity at relay;
4. remove the viewer firewall dependency (normally outbound only);
5. retain or archive sanitized viewer data per policy.

### Relay rollback

1. disable production event publishing;
2. stop/disable relay service/task;
3. remove only the relay's Private-profile firewall rule;
4. preserve ABA API at `127.0.0.1:8766` unchanged;
5. revoke viewer certificates and archive relay state if required.

### ABA contract rollback

If an additive v2 contract was deployed, disable it by feature flag or revert to v1 output. Do not modify Telegram authorization, parser rules, duplicate reservation, authoritative database rows, dashboard, or main-PC speech. The original standalone ABA system continues independently.

Rollback success criteria:

- ABA Telegram monitoring and local announcement continue;
- no relay port listens on LAN;
- viewers show `DISCONNECTED` and do not speak;
- port `8766` remains loopback-only;
- no production credentials/session/database were copied.

## 17. Decisions requiring owner approval

1. **Remote speech policy:** approve the recommendation that each fresh live verified payment may be announced remotely regardless of main-PC `MUTED`, `SPOKEN`, or `FAILED` result.
2. **Freshness window:** approve 30 seconds, including bounded local TTS retry only inside that window.
3. **Recovery policy:** approve display-only recovery with zero speech for all snapshot/reconnection events.
4. **Security:** approve mTLS per viewer, local CA management, and Windows protected key storage; or explicitly choose the less-preferred pinned-TLS/per-viewer-token fallback.
5. **Relay endpoint:** approve the selected private NIC/IP and proposed TCP port `8767`.
6. **Firewall scope:** approve exact Private-profile subnet/IP allowlist and whether viewer IP reservations are required.
7. **Contract v2:** approve adding stable `bank_code`, `MUTED`, source update timestamp, persisted source epoch, immutable ordered update snapshots, bootstrap/high-water response, and explicit cursor-reset signaling while retaining v1 compatibility.
8. **Khmer core distribution:** approve a shared pure package and its release/version-signing process.
9. **TTS dependency:** approve Edge TTS on every viewer and the behavior when a viewer lacks internet; alternatively approve a future local/offline Khmer engine after separate quality validation.
10. **Viewer mute:** approve that locally muted payments are marked consumed and never announced later.
11. **Storage retention:** approve relay outbox, viewer dedup, and log retention periods.
12. **Windows identity:** approve service/scheduled-task accounts and whether relay administration requires local administrator rights.
13. **Display scope:** approve whether recovered events appear in recent history and how they are visually labeled.
14. **Deployment topology:** confirm the authoritative ABA PC is stable enough to host the relay and remains on the approved private LAN while viewers operate.

## 18. Acceptance criteria for a future implementation

Implementation is complete only when synthetic evidence demonstrates:

- exactly one authoritative Telegram listener;
- ABA API still listens only on loopback;
- source epoch changes and cursor resets are detectable; source updates are immutable, ordered snapshots;
- relay is the sole LAN-facing component and accepts only authenticated enrolled viewers;
- no ABA credential/session/database is present on viewers;
- three simultaneous viewers display ordered verified events;
- each viewer independently announces one fresh live event exactly once;
- initial sync, reconnect replay, and cursor reset never speak historical events;
- viewer restart/crash does not duplicate speech;
- unknown banks remain valid, display as `OTHER BANK`, and omit the Khmer bank clause;
- KHR and USD remain separate and preserve approved Khmer pronunciation;
- main `MUTED`/`FAILED` state follows the approved independent-viewer policy;
- relay/viewer failure cannot interrupt ABA monitoring, dashboard, database, or main-PC speech;
- revocation prevents one selected viewer from reconnecting without affecting others;
- rollback removes LAN exposure while ABA continues normally.

---

**Stop point:** This document is an implementation plan only. No relay, viewer, source change, configuration change, credential operation, production test, scheduled-task change, firewall change, restart, or deployment is authorized by this plan.
