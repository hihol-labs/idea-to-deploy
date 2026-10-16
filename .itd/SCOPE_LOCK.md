# GATE-OPTIN-1

## Current Task

- GATE-OPTIN-1: the global pre-push gate protects only registered repositories (owner 2026-10-16). Criteria:
  `.itd/ACCEPTANCE_CONTRACT.json` GATE-OPTIN-1-AC1..AC2 (the post-merge registry rollout is closure evidence, not a criterion).

## Allowed Change Areas

- `scripts/itd_pre_push.py` (opt-in enforcement), `scripts/itd.py` (`gate unregister`).
- `tests/verify_git_gate_hooks.py`, `tests/verify_gate_registry_profiles.py`.
- `docs/CI.md`, `docs/API_REVIEWER.md`, `README.md`, `README.ru.md` - the registry/opt-in text where the gate is described.
- `CHANGELOG.md` ([Unreleased]), `BACKLOG.md` (P1 entry), `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`,
  `.itd/SCOPE_LOCK.md`, `.itd/IMPACT_GRAPH.json` - records.
- Live machine state at rollout (not in the diff): `~/.config/itd/gates.json` on WSL and `%LOCALAPPDATA%\ITD\gates.json`
  on Windows - backup, then `itd gate unregister` for the five product repositories.

## Forbidden Change Areas

- `HANDOFF.md`; skills, hooks, agents; the review route of this repository; version files (no release in this unit).

## Review Rule

Machine oracles on the exact candidate; one independent checker (gpt-5.6-sol); findings on shipped code fixed, other
classes BACKLOG + disclosure (owner rule 2026-10-15).
