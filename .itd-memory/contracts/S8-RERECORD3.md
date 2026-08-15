# Task Contract — S8-RERECORD3

## Scope
Re-record the live H4 benchmark on the clean tree after S8-POLICY edited
`skills/_shared/itd_review_evidence.py`. Evidence only:
`tests/fixtures/live-model-evidence/latest.json` and
`runs/20260815T150941Z-3c9eb927/`.

## Why
`skills/` is inside `METHODOLOGY_TREE_ROOTS`, so the recording committed in
aae7e0a went stale the moment 7ff247b landed. CI Gate 1 on PR #205 failed
105 passed / 3 failed on exactly that: `current methodology tree is
content-pinned`, `live run used the repository-local adopted ITD harness`,
`source pin matches: methodologyTree`.

## Verification Standards
- `python3 -I tests/verify_live_model_benchmark.py --require-evidence` -> exit 0,
  `108 passed, 0 failed`.
- The recomputed methodology tree pin equals the value recorded in
  `latest.json`, which points at run `20260815T150941Z-3c9eb927`.
- Transcript integrity (matched items, terminal `turn.completed`,
  `run-report.json` agreement) and no secret in the recording.
- `sh skills/_shared/itd_py.sh tests/meta_review.py` -> PASSED.
- Fresh-session checker, mode full, recomputing the pin independently.

## Exclusions
- No code changes; the two earlier recordings stay untouched.
- `.itd-memory/STATE.json` is not part of the evidence candidate: staging it
  breaks the recording's own dirty-state pin, so the ledger lands in a
  following commit.
