# ITD-PLAN-S6: hook performance - one dispatcher per event, install-time bytecode, the ITD-PLAN-S5 ledger record

## Current Task

- Session 6 of the ITD change plan approved by the owner on 2026-10-20 (ADR-016): one dispatcher per hook event for
  Claude Code by the pattern of `hooks/codex-dispatch.py` - one Python process runs the selected hooks in memory; the
  heavy modules (the egress classifier, predeploy) are imported, their bytecode prepared at install and listed in an
  inventory (the 1.109.1 rule "no .pyc written at run time" kept); a failing dispatcher denies for a hard gate and
  stays silent for an advisory hook. Inputs from BACKLOG: P2 "check-dod-before-commit on Windows: slow hook start" and
  P2 "false denies of the pre-deploy gate on `$(...)` next to `cd`".
- Acceptance: the session 2 measurement repeated on WSL and Windows (median hook latency per call -50% or more, at
  most 4 hook processes per Bash), every behavioural hard-gate test green in both directions, the full suite green,
  the Windows acceptance on a fresh copy of the tree in `C:\itd-src` (native Python, Git Bash through ITD_BASH and
  WSLENV).
- The same PR carries (plan rule 5, owner 2026-10-23): the ITD-PLAN-S5 verified record and its followup move, the a4
  adjudication of session 5 in DECISIONS.
- Start from merged main `c94c50ab61b3fb6c34cb6f018b2d2e01d610f202`. WIP=1: ITD-PLAN-S5 is verified; this unit is
  the only open one. Criteria live in `.itd/ACCEPTANCE_CONTRACT.json`.

## Allowed Change Areas

- New `hooks/claude-dispatch.py` (entry point) and `hooks/itd_dispatch.py` (dispatcher), new
  `scripts/itd_hook_bytecode.py` (install-time bytecode and inventory).
- `scripts/sync-to-active.sh`: the routing table and the one registration per event (step 5), the ownership of the
  dispatcher command, the bytecode step (new step 6).
- Hook bodies: `hooks/cross-review-precommit.sh` (the sanitizer loaded on first use) and
  `hooks/check-predeploy-gate.sh` (substitution bodies judged by their own invocations, BACKLOG P2); no other hook.
- `skills/_shared/itd_project_hooks.py` (a user-level dispatcher counts as the registration of its table's hooks),
  `hooks/README.md`.
- Tests: new `tests/verify_itd_dispatch.py`; `verify_all_hard_gate_host_parity`, `verify_hook_selection`,
  `verify_hooks_autoinstall`, `verify_sync_manifest`, `verify_predeploy_independent_review`; `tests/run-all.sh`.
- The measurement: `docs/measurements/ITD-SIMPLIFY-BASELINE.md` (section 10, after session 6).
- `CHANGELOG.md` (`## [Unreleased]`), `.itd/ACCEPTANCE_CONTRACT.json` (the ITD-PLAN-S5 followup move, the
  ITD-PLAN-S6 followup and criteria), `.itd/DECISIONS.md`, `BACKLOG.md`, this scope, regenerated
  `.itd/IMPACT_GRAPH.json`.
- Owner 2026-10-25 (the full suite turned red on every tree): `scripts/graph_v2_study.py` - the hard-coded end of the
  Graph Lite study authorization window (`expiresAt` 2026-10-25T00:00Z) becomes the module constant
  `POLICY_EXPIRES_AT` with the same value; `tests/verify_graph_study.py` sets a future date for its synthetic study.
  The recorded study and its behaviour do not change.
- `.itd-memory/STATE.json`, `.itd-memory/events.jsonl`: harness transitions only.
- Git-ignored verification receipts, reports, measurement outputs and hand-over files.
- Outside git, each on the owner's confirmation with a backup: `scripts/sync-to-active.sh` on WSL and Windows.
  Temporary bench installs and tree copies under the session scratchpad and `C:\itd-src\s6-*`.

## Forbidden Change Areas

- `hooks/codex-dispatch.py` and the other files of the benchmark pin (`tests/itd_benchmark_pin.py`): a change there
  needs a live benchmark run, not budgeted for this session; `hooks/hooks.json` (Codex stays as it is).
- Other hook bodies, skills other than the `/adopt` helper, agents, CI, the `itd` CLI runtime
  (`scripts/itd_install_runtime.py`), the trust policy.
- The meaning of the ITD-PLAN-S5 criteria and of the released 1.109.2 code.
- `HANDOFF.md` in the reviewed diff; hand-written unit statuses.
- Push, PR, merge, sync and global configuration changes without the owner's explicit confirmation of that step (the
  one independent review of the final candidate is requested by the owner's session 6 task).

## Review Rule

One independent review of the final candidate (plan rule 4). Convergence (owner 2026-10-23): the fourth round is the
last; BLOCKED with only medium or low findings goes to the owner (ADJUDICATED under ADR-007); a high finding is fixed
and brought to the owner. A reviewer finding outside this scope is brought to the owner before another round.
The generated benchmark sample (`tests/fixtures/live-model-evidence/runs/*`) is recorded evidence, not shipped content
(owner 2026-10-23); findings about it are out of scope.
