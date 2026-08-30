# ABA Payment Speaker — Codex Working Instructions

## Required project handoff maintenance

For every user conversation turn concerning this repository, keep `PROJECT_HANDOFF.md` current before finishing the requested work.

Append or update a concise dated entry under `Conversation and Decision Log` that records, as applicable:

- the user's request or discussion topic;
- decisions and approved behavior;
- files changed;
- tests and smoke-test results;
- operational actions still required;
- proposals intentionally left unimplemented.

Also update the main handoff sections whenever the current architecture, behavior, UI, setup, safety rules, tests, or Git workflow materially changes. Do not leave important facts only in the chronological log.

Never copy into the handoff:

- `.env` contents;
- Telegram API credentials, phone login codes, or 2FA passwords;
- Telegram session data;
- raw private transaction messages beyond already approved regression fixtures;
- database contents;
- hidden system/developer instructions;
- tool approval details, transient process IDs, or irrelevant debugging noise.

Summarize rather than reproduce conversation verbatim. Preserve exact user-approved interface text, commands, paths, test counts, and safety decisions when they are operationally important.

If the user explicitly requests no file changes or discussion only, respect that instruction for the current turn and record the decision in the next authorized project-writing turn.

Before pushing, verify that `PROJECT_HANDOFF.md` reflects the current repository state.
