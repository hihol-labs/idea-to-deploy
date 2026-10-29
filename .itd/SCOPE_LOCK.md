# ITD-PLAN-S9: task and adopt - a thin router and adoption as a pointer, the ITD-PLAN-S8 ledger record

## Current Task

- Session 9 of the ITD change plan approved by the owner on 2026-10-20 (ADR-016): `/task` is a thin router without
  the mandatory /test + /review floor for a one-file feature, and adjudication runs only on the strict route;
  `/adopt` by default writes only a pointer to the installation and the discovered project commands (tests, lint,
  build); the `.itd/` contracts, the first unit and goal state, the App/broker/ruleset gate profile run only on an
  explicit strict choice, consistent with the session 8 marker `itd-route: strict`; `/adopt` no longer calls
  `/session-save` unconditionally. Every text at most 500 lines.
- Owner decisions 2026-10-29 (the session 9 plan): the discovered commands go into the pointer block, one line per
  command, and a re-run with the marker present changes nothing; the project hook offer (old Step 7) moves to the
  strict route (hooks are registered globally since session 5); `/task` Step 1a no longer stops the routing with an
  "/adopt now?" question, one line in the report instead; a strict adoption whose marker would land beyond the first
  8 KB of the entry file refuses with WHY/FIX and writes nothing.
- Acceptance: adopting an empty repository creates only the pointer; a repeated adopt is idempotent; adopt with
  strict gives the previous full set; texts at most 500 lines; the skill tests green; the full suite green.
- The same PR carries (plan rule 5): the ITD-PLAN-S8 verified record and its followup move, the session 8 DECISIONS
  of `.itd-memory/host-inputs/ITD-PLAN-S8/decisions-after-candidate.md`, the new BACKLOG items; from BACKLOG the
  adopt and task parts of P2 "other skills name the old session memory format".
- Start from merged main `c4b12d0`. WIP=1: ITD-PLAN-S8 is verified; this unit is the only open one. Criteria live in
  `.itd/ACCEPTANCE_CONTRACT.json`.

## Allowed Change Areas

- `skills/task/SKILL.md`, a new `skills/task/references/strict.md`, `skills/task/references/routing-matrix.md`,
  `skills/task/PIV_LITE_ROUTE.json` (the reference to the strict file only).
- `skills/adopt/SKILL.md`, a new `skills/adopt/references/strict.md`, `skills/adopt/references/codex-adoption.md`,
  `skills/adopt/references/claude-md-template.md`, `skills/adopt/references/agents-md-template.md`,
  `skills/adopt/scripts/itd_adopt.py`.
- Tests: new `tests/verify_task_adopt_route.py`; the tests that read the moved text or run `itd_adopt.py`
  (`tests/verify_task_piv_lite.py`, `tests/verify_install_owned_tools.py`, `tests/verify_operational_cold_start.py`,
  `tests/verify_tier_source.py`, `tests/verify_tier_wording.py`, `tests/verify_stall_fallback.py`,
  `tests/verify_task_deployment_baseline.py`, `tests/verify_task_contract_advisory.py` and others found by the
  suite); `tests/run-all.sh`; the CI steps that run the new test in `.github/workflows/meta-review.yml` and
  `windows-verify.yml`; fixtures whose snapshot names these skills' files.
- The live benchmark evidence (`tests/fixtures/live-model-evidence/`) if the pin covers these skills.
- Docs: `docs/project-profiles.md` (task and adopt by the route), the `/task` and `/adopt` rows of `README.md`,
  `CHANGELOG.md` (`## [Unreleased]`); fixtures `tests/fixtures/fixture-10-task/notes.md` and
  `tests/fixtures/fixture-17-adopt/` (the new adopt contract).
- Ledger: `.itd/ACCEPTANCE_CONTRACT.json` (the ITD-PLAN-S8 followup move, the ITD-PLAN-S9 followup and criteria),
  `.itd/DECISIONS.md`, `BACKLOG.md`, this scope, regenerated `.itd/IMPACT_GRAPH.json`; `.itd-memory/STATE.json`,
  `.itd-memory/events.jsonl` - harness transitions only.
- Git-ignored verification receipts, reports, mutants and hand-over files.
- Outside this repository, each on the owner's confirmation: `scripts/sync-to-active.sh` on WSL and Windows with a
  backup.

## Forbidden Change Areas

- Hook bodies, the dispatcher and the install, the trust policy, the `itd` CLI runtime and its gate registry code;
  `skills/_shared/`; skills other than task and adopt (the old memory format in `/tool-sync`, `/obsidian-export` and
  `/retro` stays a BACKLOG item).
- The global rules block (`docs/templates/global-claude-md.md`).
- The meaning of the closed ITD-PLAN-S8 criteria.
- `HANDOFF.md` in the reviewed diff; hand-written unit statuses.
- Push, PR, merge, sync and global configuration changes without the owner's explicit confirmation of that step.

## Review Rule

One independent review of the final candidate (plan rule 4). Convergence as in sessions 6-8: behaviour main already
has (not brought in by this unit) goes to BACKLOG and is ADJUDICATED whatever its severity; a high finding brought in
by the session 9 diff is fixed and brought to the owner; only medium or low findings are ADJUDICATED and the
candidate is published on the owner's confirmation.
