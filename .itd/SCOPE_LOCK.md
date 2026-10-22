# ITD-PLAN-S4: short global instructions, the ITD-PLAN-S2 ledger record and the session 2-3 follow-ups

## Current Task

- Session 4 of the ITD change plan approved by the owner on 2026-10-20 (ADR-016 item 3): the managed block of
  `docs/templates/global-claude-md.md` is rewritten to at most 60 lines - the minimal route as the normal mode of
  ITD, when the strict route applies, what is always mandatory, where the skills live, with no skill-decision line
  and no bypass ritual; `docs/templates/global-codex-agents.md` says the same for Codex without lines that
  contradict the owner's decision; the personal section after `ITD:END` is left with personal data only.
- The same PR carries (plan rule 5, owner 2026-10-22): the ITD-PLAN-S2 verified record and its followup move; the
  two low findings of review sol a6 fixed with tests; the session 3 before/after table in the baseline with its
  scripts; four session 3 findings in BACKLOG; DECISIONS entries for the a6 adjudication and for the kept
  record-agent-skill + check-dod-before-commit pair.
- Start from merged main `2be6dd04bb4ca0e85f781c1336f2c0b40a16afe2`. WIP=1: ITD-PLAN-S2 is verified; this unit
  is the only open one. Criteria live in `.itd/ACCEPTANCE_CONTRACT.json`.

## Allowed Change Areas

- `docs/templates/global-claude-md.md`, `docs/templates/global-codex-agents.md`, `docs/instruction-registry.json`.
- `tests/verify_fable_snippets.py`: the checks of the global templates; the other template-reading tests only if
  their assertions name removed text. New `tests/verify_global_routers.py`: the host acceptance of the four global
  routers (reads the user homes, not part of run-all) and its row in `tests/OUT_OF_MIRROR.json`.
- `docs/FABLE5_FEATURE_LEDGER.md`: the quoted heading of the harness invariant.
- `docs/measurements/ITD-SIMPLIFY-BASELINE.md` (header, section 8 command, new section 9) and
  `docs/measurements/itd-simplify/` (the two a6 fixes, `run_rounds.sh`, `summarize_rounds.py`, their tests; the
  scripts run hooks only with inert payloads and read transcripts, they change no project file).
- `CHANGELOG.md`: the `## [Unreleased]` entry.
- `.itd/ACCEPTANCE_CONTRACT.json` (the ITD-PLAN-S2 followup move, the ITD-PLAN-S4 followup and criteria),
  `.itd/DECISIONS.md`, `BACKLOG.md`, this scope.
- `.itd-memory/STATE.json`, `.itd-memory/events.jsonl`: harness transitions only.
- Regenerated `.itd/IMPACT_GRAPH.json` if its check asks for it.
- Git-ignored verification receipts, reports and hand-over files.
- Outside git, each on the owner's confirmation with a backup: `scripts/sync-to-active.sh` on WSL and Windows, the
  copy of the Codex template to `~/.codex/AGENTS.md` on both hosts, the personal section of `~/.claude/CLAUDE.md`.

## Forbidden Change Areas

- Skills, hooks, agents, `scripts/`, CI, trust policy, hook registrations and installation runtime; the live
  benchmark pin.
- The meaning of the ITD-PLAN-S2 criteria and of the released 1.109.2 code.
- `HANDOFF.md` in the reviewed diff; hand-written unit statuses.
- Push, PR, merge, sync and any external model call without the owner's explicit confirmation of that step.

## Review Rule

One independent review of the final candidate (plan rule 4). A reviewer finding outside this scope (pattern H4 of
REL-1.109.2) is brought to the owner before another round (BACKLOG P2, review convergence).
