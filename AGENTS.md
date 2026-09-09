# Project instructions

## SUMMED development ownership

- Code implementation, code modification, and test execution for SUMMED (`src/summed/` and SUMMED-specific tests and launchers) are performed in Antigravity.
- This ownership rule does not apply to prestudy (`src/prestudy/`), which may be developed and tested by Codex.
- Outside Antigravity, agents should restrict SUMMED work to review, status reporting, documentation, and handoff unless the user explicitly changes this invariant.

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
