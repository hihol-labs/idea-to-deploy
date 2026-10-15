# BROKER-SKEW-CLOCK-1

## Current Task

- BROKER-SKEW-CLOCK-1: make the "beyond skew" check of `tests/verify_review_broker.py` deterministic and point the
  `.itd-memory/STATE.json` event cursor at the last event (BACKLOG P2/P3; owner 2026-10-14 "доделай все три пункта").

## Allowed Change Areas

- `tests/verify_review_broker.py` - the clock substitution of `bind_with_clock_at` and one check.
- `.itd-memory/STATE.json` - the `eventLog` cursor only.
- `BACKLOG.md`, `CHANGELOG.md`, `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` - records.

## Forbidden Change Areas

- `HANDOFF.md`; shipped code in `skills/`, `hooks/`, `agents/`, `scripts/`; other tests; other ledger fields.

## Review Rule

One independent checker (gpt-5.6-sol) on the exact committed candidate before `itd pr create`.
