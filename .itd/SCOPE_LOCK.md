# REL-1.109.2: external-write gate false denies and docs freshness

## Current Task

- Session 1 of the ITD change plan approved by the owner on 2026-10-20: patch
  1.109.2 removes false denies of the external-write gate behind
  `hooks/pii-egress-guard.sh` that block product work, and refreshes
  `reviewedAt` so Gate 1 stays green after 2026-10-30.
- Start from merged main `f1aefe5a23a1deaf2963a887cdd8d548ded9a1fe`. WIP=1:
  REL-1.109.1 is verified; this unit is the only open one.
- Owner decisions 2026-10-20: context-mode executors get the Bash text
  classification ("parity with Bash"); this session ends at a local commit and
  a hand-over, publication and rollout are a separate session.
- Publication session 2026-10-20/21 (owner-confirmed): fixes for the findings
  of checkers a3-a11 and of the opposite-GPT review, live-model evidence on the
  final methodology pin, then guarded publication and rollout, each external
  step on the owner's explicit confirmation.
- Criteria live in `.itd/ACCEPTANCE_CONTRACT.json`.

## Allowed Change Areas

- `skills/_shared/itd_external_write_gate.py`: narrow only provably inert word
  matches (path fragments, grep/rg searches, local git chains, inert pipelines
  next to curl), host UI tools by exact `(server, tool)` list, context-mode
  executors through the Bash classification. Every command the 1.109.1 gate
  kept under approval for a real external action stays under approval.
- `tests/verify_external_write_gate.py`: regression cases for each false deny
  and for each bypass found in review, as both `Bash` and `PowerShell`.
- Version mirrors 1.109.2: `.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `README.md`,
  `README.ru.md`, `docs/HARNESS_CONFORMANCE_REPORT.md`,
  `docs/HARNESS_DOCS_STATE.json`, `docs/api-reviewer/RELEASE_CANDIDATE_CONTRACT.json`,
  `docs/templates/github/itd-hygiene.yml`, `tests/verify_external_reviewer_release.py`.
- `docs/HARNESS_DOCS_STATE.json`, `docs/QUALITY.json`: `reviewedAt` refresh.
- `CHANGELOG.md`: one `## [1.109.2]` section under `## [Unreleased]`.
- `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, `BACKLOG.md`, this scope.
- `.itd-memory/STATE.json`, `.itd-memory/events.jsonl`: harness activation only.
- Git-ignored verification receipts, reports and hand-over files.
- Live-model evidence (publication session): new immutable run directories under
  `tests/fixtures/live-model-evidence/runs/` and `latest.json`; existing runs are
  never modified. The generated `output/*.md` documents are a benchmark
  specimen judged by the snapshot oracle; their content flaws are visible
  evidence, not shipped runtime code, and not part of this review.
- Then, each step on the owner's confirmation: guarded publication, CI, merge,
  release and dual-host rollout.

## Forbidden Change Areas

- Secret and PII pattern scanning in `hooks/pii-egress-guard.sh`, the frozen
  external-write policy, trust policy and hook registrations.
- Other hooks, skills, agents, scripts and runtime code; timeouts and parity
  assertions.
- `HANDOFF.md` in the reviewed diff; hand-written unit statuses.
- Push, PR, merge, tag, release and rollout without the owner's explicit
  confirmation of that step.

## Review Rule

Medium risk by path policy, but the unit changes security decisions of a hard
gate: every narrowing must be checked against the 1.109.1 classifier
(differential corpus and fuzz) and regression-tested. Commit needs the exact
staged-tree machine receipt and a fresh checker. Publication additionally needs
the committed-head full machine, live evidence and one fresh canonical
opposite-GPT review.
