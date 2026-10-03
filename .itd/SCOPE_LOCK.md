# MEMORY-COLLISION-DENY-1 state-guard: a Write over a fresh session memory file is refused

## Current Task

- MEMORY-COLLISION-DENY-1 (fifth unit of the goal approved by the owner 2026-10-01; criterion
  checked against `hooks/state-guard.sh` and approved by the owner 2026-10-03 before activation,
  with the defaults: no file-ownership check, the shell channel stays soft):
  `hooks/state-guard.sh` denies a Write that would replace an existing `session_*.md` memory file
  younger than the collision window and names the next free suffix in its reason, while Edit, an
  append and a Write to a new file pass, within the existing per-session deny budget. The criterion
  and the verificationCommand live ONLY in `.itd-memory/GOAL.json`.

## Allowed Change Areas

- `hooks/state-guard.sh` - the Write branch of the PreToolUse gate, a shared freshness helper for the
  existing soft warning, the next-free-suffix helper and the module docstring.
- `tests/verify_memory_collision_deny.py` (new), `tests/run-all.sh` - register the oracle next to
  `verify_state_hardening`.
- `tests/verify_state_hardening.py` - the one P8 check that pinned the superseded soft contract
  ("Write via main() surfaces the collision warning") now expects the refusal.
- `CHANGELOG.md` (Unreleased), `BACKLOG.md` (P2 item (e) of the TIER-WORDING-2 traps marked as taken,
  the shell-channel remainder recorded).
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/MEMORY-COLLISION-DENY-1.md` (new); `.itd-memory/GOAL.json`,
  `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - status transitions only through the goal
  harness.
- `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md` (this file), `.itd/ACCEPTANCE_CONTRACT.json` (the
  activeFollowup and criteria of this unit).

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- The ledger single-writer gate, the shell-channel detection (`bash_memory_collision_context`,
  `LEDGER_WRITE_TARGET_RE`), the heartbeat, the PostToolUse validation and `MAX_DENIES` itself.
- `skills/session-save/SKILL.md` - it already writes the next suffix and appends to the current file.
- The other pending units of the goal (one unit per session).
- Further changes to the unit criterion and verificationCommand; editing unit statuses by hand.
- Push of the branch and the PR follow the route; merge only on the owner's command.

## Review Rule

Low tier: `/review` before the multi-file commit and machine-only adjudication (receipt legs `unit`,
`meta-review`, `ledger-state`). If the diff touches an area outside allowed scope, pause and
reclassify the task before continuing.
