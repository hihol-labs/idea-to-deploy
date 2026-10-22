# ITD-PLAN-S2: ADR-016, closure convention, baseline and the REL-1.109.2 ledger record

## Current Task

- Session 2 of the ITD change plan approved by the owner on 2026-10-20: ADR-016 records the bounded lift of
  ADR-012 item 5 for this program only, `docs/RELEASE_RUNBOOK.md` gets the closure convention, and
  `docs/measurements/ITD-SIMPLIFY-BASELINE.md` the "before" measurement with the command for every number.
- The same PR carries the ledger record of REL-1.109.2 (plan rule 5, owner decision 2026-10-21): the unit is
  verified through `itd_unit_log.py`, its followup moves to `closedFollowups`, the deferred minors (AC3 tense,
  CHANGELOG quoted-argument note) and owner decision N-1 (AC1 names the `curl $OPTS` limit, fix in BACKLOG P2).
- Start from merged main `162c9d3356b8a735792a5a214b6cf31d8162f248`. WIP=1: REL-1.109.2 is verified; this unit
  is the only open one. Criteria live in `.itd/ACCEPTANCE_CONTRACT.json`.

## Allowed Change Areas

- `docs/adr/ADR-016-itd-default-everywhere-program.md` (new) and the Amended-by note in
  `docs/adr/ADR-012-minimal-path-default.md`.
- `docs/RELEASE_RUNBOOK.md`: the "Конвенция закрытия" section only.
- `docs/measurements/ITD-SIMPLIFY-BASELINE.md` and `docs/measurements/itd-simplify/` (measurement scripts; they
  run hooks only with inert payloads and read transcripts, they change no project file).
- `CHANGELOG.md`: the `## [Unreleased]` entry and the quoted-argument note inside `## [1.109.2]`.
- `.itd/ACCEPTANCE_CONTRACT.json` (REL-1.109.2 AC1 text, AC3 evidence, the followup move, the ITD-PLAN-S2
  followup and criteria), `.itd/DECISIONS.md`, `BACKLOG.md`, this scope.
- `.itd-memory/STATE.json`, `.itd-memory/events.jsonl`: harness transitions only.
- Regenerated `.itd/IMPACT_GRAPH.json` if its check asks for it.
- Git-ignored verification receipts, reports and hand-over files.

## Forbidden Change Areas

- Skills, hooks, agents, scripts, tests, CI, trust policy, hook registrations and installation runtime; the live
  benchmark pin.
- The meaning of REL-1.109.2 AC2 and AC3 criteria and of the released 1.109.2 code.
- `HANDOFF.md` in the reviewed diff; hand-written unit statuses.
- Push, PR, merge and any external model call without the owner's explicit confirmation of that step.

## Review Rule

One independent review of the final candidate (plan rule 4). A reviewer finding outside this scope (pattern H4 of
REL-1.109.2) is brought to the owner before another round (BACKLOG P2, review convergence).
