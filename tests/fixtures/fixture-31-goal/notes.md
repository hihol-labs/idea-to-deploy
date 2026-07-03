# Fixture 31 — /goal — manual verification notes

`/goal` is a memory-write orchestrator skill (thin layer, not an orchestration
runtime — ADR-001). It writes ONE durable artifact — `.itd-memory/GOAL.json`
(schema: `docs/templates/itd-memory/goal.schema.json`) — and drives the goal's
units through the EXISTING `/task` pipeline; it adds no gates and no new runtime.

Validation deferred (status: pending) — same memory-write artifact bucket as
fixture-09-session-save and fixture-18-handoff. `verify_snapshot.py`'s Phase 1
schema is file-shaped for project scaffolds and cannot assert a
decompose→approve→drive→resume flow, so structural validation is manual via this
file. The GOAL.json artifact itself IS machine-checkable:

    python3 scripts/validate_state.py path/to/.itd-memory/GOAL.json

## Contract to verify manually

`/goal <goal text>` MUST:
- **Resume, never recreate**: if `.itd-memory/GOAL.json` exists with status
  `active`, continue from the first non-verified unit; do NOT re-decompose or
  overwrite the ledger (a second `/goal` call without arguments = resume).
- Decompose a NEW goal into an ORDERED list of units, each with a binary
  `criterion` and an executable `verificationCommand`, statuses start `pending`.
- **Show the decomposition and wait for explicit user approval** before writing
  `GOAL.json` or starting any unit (global rule «Plan before code»).
- Drive exactly ONE unit at a time (WIP=1, enforced by the existing wip-gate):
  next pending unit → standard `/task` pipeline (scope → plan → code → `/test` →
  `/review`) → flip to `verified` only with evidence → next unit.
- Log unit events (`type: "unit"`, activated/verified) to
  `.itd-memory/events.jsonl` so the VCR metric (itd_metrics.py) counts goal work.
- Keep `GOAL.json` valid against `goal.schema.json` on every write
  (`validate_state.py` dispatches on the filename).
- Work on **brownfield** projects — its main case; it must NOT appear in the
  `_GREENFIELD_SKILLS` suppression list in `hooks/check-skills.sh`.

`/goal` MUST NOT:
- Act as a gate, bypass `/review`, `/test`, the DoD pre-commit gate, or any
  other idea-to-deploy gate.
- Mark a unit `verified` without running its `verificationCommand` and recording
  the evidence.
- Mark a unit `skipped` without a non-empty `skippedReason` (fail-closed —
  validate_state.py rejects it).
- Open a second unit while the current one is unverified (WIP=1).
- Recreate or truncate an existing active `GOAL.json`.

## Harness tools (v1.45.0) — covered by tests/verify_goal_tools.py

State transitions are made by the HARNESS, not the agent:

- `skills/goal/scripts/itd_goal_verify.py` («ОТК») — the only writer of
  `verified`: executes the unit's verificationCommand itself; `--activate`
  enforces WIP=1; verify refuses `pending` (gate on passing); failure keeps
  `in_progress`; `--recheck` demotes a regressed verified unit; `--block`
  requires `--reason` (fail-closed); every transition → events.jsonl with
  `actor: "harness"`.
- `skills/goal/scripts/itd_goal_report.py` — deterministic handoff report FROM
  the ledger (progress, backpressure, unit table, first action); /handoff and
  /session-save paste its output verbatim.

Functional coverage is automated: `python3 tests/verify_goal_tools.py`
(20 checks incl. the blocked-only backpressure scenario and Markdown-pipe
escaping, runs on both interpreters + the windows-verify CI leg) — so this
part of the contract is NOT manual-only anymore.

## Pre-flight integration to verify

With an active `GOAL.json` in the project, `hooks/pre-flight-check.sh` must
inject a line like:

    - Цель (/goal): <goal> — N/M юнитов verified, текущий `G-k`

next to the ITD-state block (works even when STATE.json is absent), plus a
resume hint pointing back to /goal.

## Why no expected-files

`GOAL.json` lands in the TARGET project's `.itd-memory/`, not in this fixture's
output dir; see `expected-files.txt`.
