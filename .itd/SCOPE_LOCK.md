# RETRO-DOCS-2026-10-04 publish the 2026-10-04 retrospective and the pause of methodology goals

## Current Task

- RETRO-DOCS-2026-10-04 (docs only, no goal unit; the goal "route traps of TIER-WORDING-2" is done 8/8):
  publish the retrospective of 2026-10-04 that the owner accepted (candidates 1 and 2 - measure the
  methodology's value on a product project; pause new goals on the methodology until then). The texts were
  written on 2026-10-04 and kept back while OTK-HOST-TREE-1 ran; they get a dated status line (2026-10-06)
  and house-style typography. No code, no test, no ledger transition.

## Allowed Change Areas

- `docs/retros/RETRO-2026-10-04.md` (new) - the retrospective report.
- `BACKLOG.md` - one P1 entry inserted at the top, with its status line of 2026-10-06.
- `.itd/DECISIONS.md` - one entry appended at the end (the retro decision with the owner's clarification).
- `.itd/SCOPE_LOCK.md` (this file).

## Forbidden Change Areas

- Code, hooks, skills, tests, CI, ledgers (`.itd-memory/GOAL.json`, `STATE.json`, `events.jsonl`),
  `.itd/ACCEPTANCE_CONTRACT.json`.
- The result of the value measurement in `~/projects/itd-value-exp` and the owner's decision on it - only a
  pointer to the report is recorded here, the decision is the owner's.
- `sync-to-active` (frozen until the owner decides on the measurement).
- Merge only on the owner's command.

## Review Rule

Docs only: `/review` before the commit, machine receipt (`meta-review`) and the mandatory independent
reviewer (Sol) on the committed head, as the gate registry requires a signed route for `itd pr create`.
