# GRAPH-LITE-PLAN record the GRAPH-LITE-2 closure and the approved Graph Lite measurement plan

## Current Task

- GRAPH-LITE-PLAN (records only, no goal unit): GRAPH-LITE-2 was merged as PR #353 -> `2219fe0` and rolled out. This
  candidate moves its follow-up to `closedFollowups` (no active unit), records the owner's decisions of 2026-10-09
  (the goal - a mandatory, automatic graph for money and access tasks; enablement on a won measurement through a hook
  trigger on strictClasses money/auth; the measurement protocol approved and frozen in `~/projects/itd-graph-exp`) and
  updates the Graph Lite plan in BACKLOG. No code, no test, no skill change.

## Allowed Change Areas

- `.itd/ACCEPTANCE_CONTRACT.json` - only `activeFollowup` (set to none) and one appended `closedFollowups` entry.
- `BACKLOG.md` - the P2 Graph Lite section (session 2 done, sessions 3-5 and the enablement unit).
- `.itd/DECISIONS.md` - one entry appended at the end.
- `docs/measurements/GRAPH-LITE-PROTOCOL.json` (new) - a byte copy of the frozen protocol
  `~/projects/itd-graph-exp` commit `2e7eea0`:`PROTOCOL.json`, sha256 `7a00414033272c0f42dd50fb45d9db63b0ab8e589eb71a03dfc7964d681d5c17`, so the recorded plan is reviewable
  inside the repository.
- `docs/measurements/GRAPH-LITE-PROTOCOL-AMENDMENT-1.json` (new) - a byte copy of amendment 1 of the protocol
  (`~/projects/itd-graph-exp` commit `7fff57b`:`PROTOCOL-AMENDMENT-1.json`, sha256 `49bd56dae125b607faea1ba8166015b72d1b5d3c8e3d01966ffe6dfc38e36b8b`), approved by the owner
  before any seeding or run after the independent review of the protocol copy.
- `.itd/SCOPE_LOCK.md` (this file).

## Forbidden Change Areas

- Code, hooks, skills, tests, CI, ADRs, ledgers (`.itd-memory/**`), any acceptance criterion.
- The enablement itself (trigger, ADR-013 amendment) - only after a won verdict, as its own unit.
- Merge only on the owner's command.

## Review Rule

Records only: machine receipt (`meta-review`) and the mandatory independent reviewer (Sol) bound to the exact candidate
tree of this branch against its base.
