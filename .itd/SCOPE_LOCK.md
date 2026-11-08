# CODEX-ASK-MUTANTS-1: refusal-case tests for the Codex ask gate, the ITD-PILOT-TESTGAP closure

## Current Task

- CODEX-ASK-MUTANTS-1: the four mutations of `hooks/codex-dispatch.py` from BACKLOG P2 2026-11-07 survive
  `tests/verify_codex_ask_gates.py` on main 3e14262; add a refusal-case test that kills each. The criteria live only in
  `.itd/ACCEPTANCE_CONTRACT.json` (CODEX-ASK-MUTANTS-1-AC1..AC2).
- Start from merged main 3e14262 (PR #395). WIP=1: ITD-PILOT-TESTGAP is verified in this candidate; this unit is the
  only open one.

## Allowed Change Areas

- `tests/verify_codex_ask_gates.py`: the new checks.
- `docs/measurements/itd-testgap/k0_mutants.py`: an optional path argument and an exit code with it.
- Ledgers: `.itd-memory/STATE.json` and `.itd-memory/events.jsonl` through `itd_unit_log.py` only,
  `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, `BACKLOG.md`, this file.

## Forbidden Change Areas

- `hooks/codex-dispatch.py` and all other hooks, skills, agents and scripts; the trust policy and hook registrations.

## Review Rule

- One independent review of the final candidate by gpt-6.1-sol on the machine receipt of the exact commit. After 3
  BLOCKED rounds the route stops for the owner's decision under ADR-007.

## Declared limits

- `pilot_run.audit` is recorded in BACKLOG P3 and is not changed here.
