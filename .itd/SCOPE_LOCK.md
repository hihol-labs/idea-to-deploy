# Scope Lock — U6: installed-skill parity (evidence-only closure, docs commit)

## Current Task

Close unit U6 «Installed-skill parity (F6)» from the GPG-004 ladder plan on
fresh read-only evidence (2026-08-10, main @ 7ed8e43, after the v1.96.0
rollout): the installed cross-review skill matches the repository version by
content hash on WSL, and the same check is recorded for Windows. No install
mutations, no code changes — parity is already factual; only the ledgers and
this contract change.

## Allowed zones

- `.itd-memory/STATE.json` (unit bookkeeping via `itd_unit_log.py`:
  activated + verified U6)
- `BACKLOG.md` (one follow-up line: `__pycache__` noise in
  `sync-to-active.sh --check`)
- `.itd/SCOPE_LOCK.md` (this contract, rewritten for the unit)

Untracked local stores updated alongside (not part of the git candidate):
`.itd-memory/GPG-004_UNIT_PLAN.json` (U6 → verified + evidence),
`.itd-memory/contracts/U6.md`, `.itd-memory/events.jsonl` (harness writer).

## Acceptance (this unit)

1. Unit verificationCommand exit 0: sha256(repo skills/cross-review/SKILL.md)
   == sha256(~/.claude/skills/cross-review/SKILL.md) —
   c82ea90e56e9bd7e6070976351c6c604f5ef16c4000730608a14cd5db9f6a201.
2. `scripts/sync-to-active.sh --check`: zero pending changes outside
   `skills/_shared/__pycache__/*.pyc` bytecode (0 non-pyc diffs; 40 skills /
   32 hooks / 10 agents / 41 templates unchanged).
3. Windows install byte-identical for cross-review
   (`/mnt/c/Users/Дмитрий/.claude/skills/cross-review/SKILL.md`, cmp exit 0).
4. Machine oracle on the exact committed-head candidate: the three checks
   above plus meta-review and `tests/run-all.sh --quick` green.

## Risk tier

low — read-only verification plus ledger/docs bookkeeping. The plan's
declared high tier guarded against rolling out unreviewed WIP (user decision
A5); that rollout has since happened through the reviewed v1.96.0 release, so
no mutation class remains in this unit.

## Out of scope

Excluding `__pycache__` from the sync scan (queued in BACKLOG); a fresh
full-tree hash re-scan of both installs — the v1.96.0 rollout scan is
recorded only in the local session memory (`session_2026-08-10.md`:
skills/hooks/agents trees wsl==win, agents byte-identical to repo, deltas
explained; the Windows install intentionally carries no plugin manifest),
and this unit re-checked only the cross-review skill per its criterion
(WSL sync --check full, Windows single-file cmp); any install mutation or
rollout; U16/U17.
