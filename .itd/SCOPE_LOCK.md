# ITD-PLAN-S8: bugfix, test, refactor - strict steps by the project route, the ITD-PLAN-S7 ledger record

## Current Task

- Session 8 of the ITD change plan approved by the owner on 2026-10-20 (ADR-016): the automatic scope freeze, the
  mandatory ROOT_CAUSE.md, the refute pass and the mutation runs of `/bugfix`, `/test` and `/refactor` move to each
  skill's `references/strict.md` and run only on the strict route; the minimal path is reproduce, find the cause,
  minimal fix, regression test, run the suite; the skill descriptions follow the Agent Skills standard (what it
  does, then "Use when ...") for auto-triggering; every text at most 500 lines.
- Owner decision 2026-10-28: the strict route is chosen by an explicit project marker - `itd-route: strict` (or
  `<!-- itd:strict -->`) in the project's `CLAUDE.md`, `.claude/CLAUDE.md` or `AGENTS.md`, first 8 KB,
  case-insensitive; `itd-domain: data-sensitive` counts as strict; `--strict` in the skill arguments and the strict
  task classes of the global rules switch it on for one call. The presence of `.itd/` or `.itd/SCOPE_LOCK.md` does
  not (both exist in ordinary projects). invoices gets the marker by its own PR on the owner's confirmation.
- Acceptance: in an ordinary project `/bugfix` creates no freeze state and no ROOT_CAUSE.md; in invoices the strict
  steps run as before; texts at most 500 lines; the skill tests green; the full suite green.
- The same PR carries (plan rule 5): the ITD-PLAN-S7 verified record with the AC4 measurement (both numbers and the
  reason for the net time) and its followup move, the session 7 DECISIONS of
  `.itd-memory/host-inputs/ITD-PLAN-S7/decisions-after-candidate.md`, the new BACKLOG items.
- Start from merged main `93bec47`. WIP=1: ITD-PLAN-S7 is verified; this unit is the only open one. Criteria live in
  `.itd/ACCEPTANCE_CONTRACT.json`.

## Allowed Change Areas

- `skills/bugfix/SKILL.md`, `skills/test/SKILL.md`, `skills/refactor/SKILL.md` and a new `references/strict.md` in
  each of the three skills; in `skills/refactor/references/worktree-isolation.md` only the fallback wording (the
  in-place path instead of "the Step 0 freeze path").
- Tests: new `tests/verify_strict_route.py`; `tests/verify_test_skill_rules.py` and `tests/verify_refute_fleet.py`
  (the Step 5.5 rules now live in `skills/test/references/strict.md`); `tests/run-all.sh`; the CI steps that run
  `verify_strict_route.py` in `.github/workflows/meta-review.yml` and `windows-verify.yml`; fixtures whose snapshot
  names these skills' files.
- The live benchmark evidence (`tests/fixtures/live-model-evidence/`) if the pin covers these skills.
- Docs: `docs/project-profiles.md` (the `itd-route` marker), `hooks/README.md` (the freeze rows: the skills write
  the freeze state on the strict route only), `CHANGELOG.md` (`## [Unreleased]`).
- Ledger: `.itd/ACCEPTANCE_CONTRACT.json` (the ITD-PLAN-S7 followup move and AC4 evidence, the ITD-PLAN-S8 followup
  and criteria), `.itd/DECISIONS.md`, `BACKLOG.md`, `docs/measurements/ITD-SIMPLIFY-BASELINE.md` (section 11, the
  session 7 measurement), this scope, regenerated `.itd/IMPACT_GRAPH.json`; `.itd-memory/STATE.json`,
  `.itd-memory/events.jsonl` - harness transitions only.
- Git-ignored verification receipts, reports, mutants and hand-over files.
- Outside this repository, each on the owner's confirmation: one marker line in the invoices `CLAUDE.md` on a branch
  and a PR in the invoices repository; `scripts/sync-to-active.sh` on WSL and Windows with a backup.

## Forbidden Change Areas

- Hook bodies (`hooks/freeze.sh` and `hooks/check-dod-before-commit.sh` keep their behaviour; the `/test` session
  marker stays on the minimal path), the dispatcher and the install, the trust policy, the `itd` CLI runtime; other
  skills, agents, `skills/_shared/`.
- The global rules block (`docs/templates/global-claude-md.md`).
- The meaning of the closed ITD-PLAN-S7 criteria beyond the AC4 measurement evidence.
- `HANDOFF.md` in the reviewed diff; hand-written unit statuses.
- Push, PR, merge, sync and global configuration changes without the owner's explicit confirmation of that step.

## Review Rule

One independent review of the final candidate (plan rule 4). Convergence as in sessions 6 and 7: behaviour main
already has (not brought in by this unit) goes to BACKLOG and is ADJUDICATED whatever its severity; a high finding
brought in by the session 8 diff is fixed and brought to the owner; only medium or low findings are ADJUDICATED and
the candidate is published on the owner's confirmation.
