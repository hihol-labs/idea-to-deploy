# ITD-PLAN-S7: session-save and handoff - one continuity document per workstream, the ITD-PLAN-S6 ledger record

## Current Task

- Session 7 of the ITD change plan approved by the owner on 2026-10-20 (ADR-016): one continuity document (the next
  action, state, decisions, check results, blockers; the history kept apart and never competing with the current
  state); session-save SKILL.md at most 200 lines, run at milestones and before irreversible steps, not after every
  sub-step; sync-to-active and the methodology-memory push only in the ITD repository and only by a flag; handoff in
  the same format, kept for a transfer without a way back.
- Owner decisions 2026-10-28: one document per workstream `.itd-memory/continuity/<topic>.md` (buying runs parallel
  topics in one checkout) plus the append-only `.itd-memory/HISTORY.md`; pre-flight lists the open topics with the
  next action instead of the MEMORY.md index; state-guard refuses a Write over a document another session changed
  less than 10 minutes ago (CONTINUITY-WRITER-1); the session-save time in buying is measured after the merge and the
  sync from the buying transcripts (`transcript_stats.py`, the session 2 baseline median 154 s) and carried by the
  ITD-PLAN-S7 verified record in the session 8 PR (plan rule 5).
- Acceptance: a new session recovers the next action from one document; the skill tests green; the full suite green;
  the hook changes green on WSL and Windows.
- The same PR carries (plan rule 5): the ITD-PLAN-S6 verified record and its followup move, the session 6 DECISIONS
  records after a7 missing on main, the S6 AC1 bytecode wording and the AC3 owner exception for the Codex legs on
  Windows, the new BACKLOG items of `.itd-memory/host-inputs/ITD-PLAN-S6/decisions-after-a7.md`.
- Start from merged main `0436ab5`. WIP=1: ITD-PLAN-S6 is verified; this unit is the only open one. Criteria live in
  `.itd/ACCEPTANCE_CONTRACT.json`.

## Allowed Change Areas

- `skills/session-save/SKILL.md`, `skills/handoff/SKILL.md`; their `references/` files are removed (the format lives
  in SKILL.md).
- Hook bodies: `hooks/pre-flight-check.sh` (the continuity section), `hooks/session-open-diagnostic.sh`,
  `hooks/handoff-readiness.sh` (a continuity document is a checkpoint), `hooks/state-guard.sh`
  (CONTINUITY-WRITER-1); `hooks/README.md`.
- Tests: new `tests/verify_continuity.py`; `tests/run-all.sh`; the fixtures `tests/fixtures/fixture-09-session-save`
  and `fixture-18-handoff`; the CI steps that run `verify_continuity.py` in `.github/workflows/meta-review.yml` and
  `windows-verify.yml`.
- The live benchmark evidence (`tests/fixtures/live-model-evidence/`): `skills/session-save` is in the dynamic half
  of the pin (DECISIONS 2026-10-23), so the final tree needs one live run.
- Docs: `README.md`, `README.ru.md` (the session-save contract row), `docs/HARNESS_ENGINEERING_MAP.md` (H2),
  `docs/CONTRACTS.md` (branch finish), `CHANGELOG.md` (`## [Unreleased]`).
- Ledger: `.itd/ACCEPTANCE_CONTRACT.json` (the ITD-PLAN-S6 followup move and the AC1/AC3 wording, the ITD-PLAN-S7
  followup and criteria), `.itd/DECISIONS.md`, `BACKLOG.md`, this scope, regenerated `.itd/IMPACT_GRAPH.json`;
  `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - harness transitions only.
- Git-ignored verification receipts, reports, measurement outputs and hand-over files.
- Outside git, each on the owner's confirmation with a backup: `scripts/sync-to-active.sh` on WSL and Windows.
  Tree copies under `C:\itd-src\s7-*`.

## Forbidden Change Areas

- The dispatcher and the install (`hooks/claude-dispatch.py`, `hooks/itd_dispatch.py`, `hooks/codex-dispatch.py`,
  `hooks/hooks.json`, `scripts/sync-to-active.sh`, `scripts/itd_hook_bytecode.py`), the trust policy, the `itd` CLI
  runtime; other hook bodies, other skills, agents.
- The meaning of the closed ITD-PLAN-S6 criteria beyond the two wordings named above.
- The global rules block (`docs/templates/global-claude-md.md`): `/session-save` and `/session-save --close` keep
  their names.
- `HANDOFF.md` in the reviewed diff; hand-written unit statuses.
- Push, PR, merge, sync and global configuration changes without the owner's explicit confirmation of that step (the
  one independent review of the final candidate is requested by the owner's session 7 task).

## Review Rule

One independent review of the final candidate (plan rule 4). Convergence as in session 6 (owner 2026-10-27):
behaviour main already has (not brought in by this unit) goes to BACKLOG and is ADJUDICATED whatever its severity; a
high finding brought in by the session 7 diff is fixed and brought to the owner; only medium or low findings are
ADJUDICATED and the candidate is published on the owner's confirmation. The generated benchmark sample
(`tests/fixtures/live-model-evidence/runs/*`) is recorded evidence, not shipped content; findings about it are out of
scope.
