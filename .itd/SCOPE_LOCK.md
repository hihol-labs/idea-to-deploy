# GRAPH-LITE-2 close the six deferred findings of review p9 in /graph

## Current Task

- GRAPH-LITE-2 (no goal unit; BACKLOG P2 Graph Lite; owner instruction 2026-10-08): fix the six medium findings of the
  independent review round p9 that the owner deferred when adjudicating GRAPH-LITE-1 - human-node inputs/outputs
  validation, a controlled refusal on malformed receipt shapes, refusal of a changed git submodule or nested
  repository, the run-id wording in SKILL.md, and two oracle cases (approve outside graph-runs, a symlinked
  `.itd-memory/`). The trust boundary of approval.json stays as recorded in ADR-013 and is out of scope.

## Allowed Change Areas

- `skills/graph/scripts/itd_graph.py`, `skills/graph/SKILL.md`.
- `tests/verify_graph_skill.py`.
- `CHANGELOG.md` (Unreleased), `BACKLOG.md` (the GRAPH-LITE-2 line).
- `.itd/ACCEPTANCE_CONTRACT.json` - only `activeFollowup` (GRAPH-LITE-2) and its two criteria.
- `tests/fixtures/live-model-evidence/` (re-recorded on the new methodology tree), `.itd/SCOPE_LOCK.md` (this file).

## Forbidden Change Areas

- Hooks, gates and their policies, other skills, ledgers (`.itd-memory/**`), any other acceptance criterion.
- The approval trust boundary (ADR-013 Consequences), session 2 of ADR-013, the plugin version.
- Merge only on the owner's command.

## Recorded Evidence (not maker-authored)

`tests/fixtures/live-model-evidence/runs/20261008T200636Z-5b2c36d7/**` and `latest.json` are observations written by
`tests/run-live-model-benchmark.py`; their reviewable properties are integrity and freshness, checked by
`tests/verify_live_model_benchmark.py --require-evidence` (machine leg `live-evidence`); `transcript.jsonl.gz` is gzip on
disk and the review packet shows it decompressed.

## Review Rule

Minimal path of ADR-012 for the change (tests written and run, mutations of the fixes killed). Publication follows the
gate registry: machine receipt on the committed head, the mandatory independent reviewer (Sol) on the same head,
adjudication receipt registered for `itd pr create`.
