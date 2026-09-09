# Project instructions

## SUMMED development ownership

- All SUMMED work, including implementation, modification, testing, review, status reporting, documentation, and handoff, is performed in Codex.
- Antigravity and other agents must not perform SUMMED work unless the user explicitly changes this invariant again.
- prestudy (`src/prestudy/`) may also be developed and tested by Codex.

## SUMMED architecture invariants

1. SUMMED's AI execution engine is the local Codex CLI authenticated with the user's ChatGPT subscription account.
2. Do not use the OpenAI API, API keys, or API-key-based billing for SUMMED.
3. The app invokes `codex exec` locally and validates its structured output before using it.
4. Never copy or store the user's Codex credentials, login tokens, or authentication files in this project.
5. SUMMED runs in the user's trusted local environment; do not silently redesign it as an untrusted or multi-tenant service.
6. Read `SUMMED.md` and the latest file in `docs/handoffs/` before resuming SUMMED development.

## Execution & Interaction Policy

- All actions are set to "Always Allow" / Turbo mode.
- Proceed autonomously: do not prompt the user for intermediate confirmation, modal question tools (`ask_question`), or plan approval before executing tasks unless an unrecoverable fatal ambiguity arises.
