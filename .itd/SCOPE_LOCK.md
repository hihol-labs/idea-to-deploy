# ITD-PLAN-S5: default hooks, the ITD-PLAN-S4 ledger record and the session 4 follow-ups

## Current Task

- Session 5 of the ITD change plan approved by the owner on 2026-10-20 (ADR-016): one default hook registration for
  a new user and for the owner - the core hooks plus the hooks that stay silent without `.itd-memory`; the
  diagnostics off by default and enabled through `itd-enabled-hooks.txt`; check-skills, check-tool-skill and
  check-review-before-commit unregistered (record-agent-skill and check-dod-before-commit stay, session 3
  decision); `hooks/codex-dispatch.py` reads the same disabled and enabled lists as `scripts/sync-to-active.sh`; the
  `/adopt` project templates do not register hooks already registered globally; one live benchmark run (the pin
  changes). Inputs from BACKLOG: P2 "Codex on WSL skips the pre_tool_use:4:* group as untrusted" and P2
  "check-dod-before-commit on Windows is cut by the 5 s host timeout".
- The same PR carries (plan rule 5, owner 2026-10-23): the ITD-PLAN-S4 verified record and its followup move; the
  owner's convergence rule and the a4 adjudication in DECISIONS; the three a4 findings fixed with tests.
- Start from merged main `a32a12edd25106f396b7f739f0cc73154d39503d`. WIP=1: ITD-PLAN-S4 is verified; this unit is
  the only open one. Criteria live in `.itd/ACCEPTANCE_CONTRACT.json`.

## Allowed Change Areas

- Hook registrations: `scripts/sync-to-active.sh` (step 5: the registration, the selection by the two lists, the
  merge that keeps user hooks), `hooks/hooks.json`, `skills/adopt/references/project-settings-template.json`,
  `skills/adopt/references/codex-project-hooks.json`, `scripts/verify-sync-to-active.sh` (exempt list).
- `hooks/codex-dispatch.py` (the selection by the two lists and the check-dod deadline), no other hook body.
- `skills/_shared/itd_project_hooks.py` (the same selection for `/adopt`), `skills/adopt/SKILL.md` and
  `skills/adopt/references/codex-adoption.md` (the hook paragraphs), `hooks/README.md` (the default registration).
- `docs/HARNESS_TRUST_POLICY.json`: the `unregisteredHardGates` entry only.
- New `scripts/itd_codex_hook_trust.py` (read-only report) and the tests `tests/verify_hook_selection.py`,
  `tests/verify_codex_hook_trust.py`; the registration tests that name the unregistered hooks or read the user's
  real hook lists (`verify_all_hard_gate_host_parity`, `verify_host_adapters`, `verify_graduated_trust`,
  `verify_hooks_autoinstall`, `verify_registration_and_counts`, `verify_sync_manifest`); `tests/run-all.sh`.
- The a4 follow-ups: `docs/measurements/itd-simplify/run_rounds.sh` and its test, `tests/verify_global_routers.py`,
  the count in `docs/measurements/ITD-SIMPLIFY-BASELINE.md`.
- The live benchmark evidence under `tests/fixtures/live-model-evidence/` (the budgeted run and, by the owner's
  decision of 2026-10-23, a second one) and `tests/itd_benchmark_pin.py` (`skills/session-save`, read by the first
  run, joins the dynamic half).
- `CHANGELOG.md` (`## [Unreleased]`), `.itd/ACCEPTANCE_CONTRACT.json` (the ITD-PLAN-S4 followup move, the
  ITD-PLAN-S5 followup and criteria), `.itd/DECISIONS.md`, `BACKLOG.md`, this scope, regenerated
  `.itd/IMPACT_GRAPH.json`.
- `.itd-memory/STATE.json`, `.itd-memory/events.jsonl`: harness transitions only.
- Git-ignored verification receipts, reports and hand-over files.
- Outside git, each on the owner's confirmation with a backup: `scripts/sync-to-active.sh` on WSL and Windows, the
  Codex plugin update and the trust of its entries in `/hooks`, the owner's hook lists.

## Forbidden Change Areas

- Hook bodies other than `hooks/codex-dispatch.py`; skills other than the `/adopt` hook paragraphs and helper;
  agents, CI, installation runtime; the other parts of the trust policy.
- The meaning of the ITD-PLAN-S4 criteria and of the released 1.109.2 code.
- `HANDOFF.md` in the reviewed diff; hand-written unit statuses.
- Push, PR, merge, sync and any external model call without the owner's explicit confirmation of that step.

## Review Rule

One independent review of the final candidate (plan rule 4). Convergence (owner 2026-10-23): the fourth round is the
last; BLOCKED with only medium or low findings goes to the owner (ADJUDICATED under ADR-007); a high finding is fixed
and brought to the owner. A reviewer finding outside this scope is brought to the owner before another round.
The generated benchmark sample (`tests/fixtures/live-model-evidence/runs/*`: outputs and transcripts) is the
recorded evidence of a live run, not shipped content (owner 2026-10-23, after review a1, as in REL-1.109.2): its
content defects stay visible as evidence and are not edited - an edit would falsify the record; limits of the
benchmark oracle go to BACKLOG.
