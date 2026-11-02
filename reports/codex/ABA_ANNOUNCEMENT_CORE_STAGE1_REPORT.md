# ABA Announcement Core — Stage 1 Report

**Status:** Stage 1 development; isolated package only. Stage 2 is not authorized.
**Package version:** `aba_announcement_core` 0.1.0
**Event schema version:** 1 (package-local, privacy-safe schema)

## Scope and compatibility

The new standard-library-only package provides Khmer amount pronunciation, a copied exact-alias registry for the 24 approved institutions, the approved Khmer announcement sentence, validated event records, and local announcement-state transitions. `UNMAPPED` events display as `OTHER BANK` but omit the bank clause from speech. KHR minor units remain whole riel; USD minor units remain cents.

The source behavior is in `app/khmer_numbers.py`, `app/bank_normalizer.py`, and the `build_announcement` function in `app/payment_parser.py`. The package intentionally does not import these modules at runtime. Synthetic parity tests compare number wording and every registered alias with the existing pure helpers. Production parsing, banks, TTS, API, and source behavior were not edited.

## Event and state model

`PaymentEvent` accepts only the versioned allowlist: opaque event/source IDs, ordered source sequence, UTC event/update timestamps, positive integer minor amount, KHR/USD currency, validated display name, approved bank code/display/mapping status, and source announcement status (`QUEUED`, `MUTED`, `SPOKEN`, or `FAILED`). Unknown keys and inconsistent bank fields are rejected. Raw messages, Telegram identifiers, credentials, database fields, and transaction metadata are not part of the schema.

Local state transitions are one-way: `QUEUED` can be claimed, locally muted, or expired; `CLAIMED` can become spoken, failed, or expired. Terminal states cannot be reopened automatically. This conservative rule avoids duplicate playback after an ambiguous failure; any retry policy remains a future owner decision.

## Privacy and dependency audit

- Runtime package imports are limited to Python standard-library modules and package-local modules.
- No Telegram, HTTP/network, SQLite, credentials, production database, live API, audio, or TTS dependencies are imported by the package.
- Synthetic fixtures contain no real payment records or private transaction messages.
- Tests use the existing parser/normalizer/number helpers only for in-process compatibility comparison; they do not start the app, open a database, or make network calls.
- No relay or viewer was created or activated.

## Verification

Focused test command: `py -3.14 -m pytest -p no:cacheprovider tests/test_announcement_core.py -q` with the repository-declared `pytest==8.4.1` and its dependencies installed into a temporary directory outside the workspace. Result: **29 passed**. The tests use synthetic fixtures and local helper imports only; they do not start ABA, open a database, or make network calls. The default and Python 3.12 interpreters in this workspace did not have pytest available, so the test run used the installed Python 3.14 interpreter.

Editor diagnostics reported no errors in the new package or test module. No full regression suite, GUI test, audio test, production test, or API test was run.

## Remaining architectural dependencies

- Future relay/viewer work requires the separately approved v2 source contract described in `ABA_MULTI_PC_DETAILED_IMPLEMENTATION_PLAN.md`, including source epoch, immutable ordered status updates, a content-free high-water barrier, and `MUTED` support.
- Package versioning and release/signing policy, remote freshness and mute policy, transport/authentication, local TTS/runtime deployment, and Stage 2 remain subject to owner approval.
- This source-tree package is not yet wired to production code, installed as a distribution, or used by any live process.

**Stop point:** Stage 1 only. Await owner approval before Stage 2.