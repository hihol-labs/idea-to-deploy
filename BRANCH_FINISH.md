# Branch Finish

Recorded: 2026-07-18

## Decision

- Mode: merge
- Branch: `codex/harness-engineering-positioning`
- PR URL: https://github.com/hihol-labs/idea-to-deploy/pull/167

## Verification

- `tests/verify_host_adapters.py`: PASS (28 shared registrations; all 11 hard
  gates registered for Codex).
- `tests/verify_harness_docs_freshness.py`: 4 PASS.
- `tests/verify_gate_taxonomy.py`: 9 passed, 0 failed.
- `tests/verify_work_deadline_docs.py`: 8 passed, 0 failed.
- `tests/meta_review.py --verbose`: Critical 0, Important 0, PASSED.
- `tests/verify_live_model_benchmark.py --require-evidence`: 81 passed,
  0 failed; the native Codex run selected by the content-pinned
  `tests/fixtures/live-model-evidence/latest.json` pointer replayed through the
  independent snapshot oracle.
- `bash tests/run-all.sh`: `DONE fails:none`.
- Independent exact-tree methodology review: PASSED, no findings or unverified
  areas.
- Independent bounded-recovery/transport review: PASSED, no findings; the live
  success completed in one attempt, so the second-attempt path remains covered
  by deterministic red/green and mutation tests rather than claimed live use.

## Cleanup

- Keep the branch until required GitHub checks pass and PR #167 is
  squash-merged.
- Publish tag/release v1.91.1 from the merged `main` tree, then synchronize both
  local host installations and verify the machine-level default router.
