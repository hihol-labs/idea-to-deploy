# Root Cause

Recorded: 2026-07-30

## Summary

The review broker assumes every changed Git blob is raw UTF-8 text and passes
it directly to the canonical diff builder. The repository's required live
model evidence stores a sanitized UTF-8 JSONL transcript as `transcript.jsonl.gz`,
so the exact release PR is rejected as `UNVERIFIED` before provider dispatch.

## Reproduction

1. Compare `origin/main` with Draft PR #177.
2. The added
   `tests/fixtures/live-model-evidence/runs/20260730T065213Z-d5716dad/transcript.jsonl.gz`
   is a valid gzip stream containing sanitized JSONL.
3. `build_candidate()` fetches the complete blob and `_canonical_diff()` calls
   `_diff_lines()` on the compressed bytes.
4. UTF-8 decoding fails at byte `0x8b`, producing
   `BrokerError("UNVERIFIED", "candidate blob is not valid UTF-8")`.

## Evidence

- The failing full-PR simulation identified exactly one non-UTF-8 changed blob:
  the 32,306-byte transcript archive above.
- `skills/_shared/REVIEW_BROKER_POLICY.json` deliberately has
  `"allowBinary": false`; changing it to a generic allow would create an
  unreviewed and unscrubbed contour.
- `tests/verify_live_model_benchmark.py --require-evidence --max-age-days 30`
  requires the compressed transcript and verifies its compressed and
  sanitized hashes.

## Fix Hypothesis

Treat only the explicitly declared `.jsonl.gz` transparent-text container as a
reviewable logical blob. Stream-decompress it under a frozen expansion limit,
require one canonical gzip member, UTF-8 without NUL, syntactically valid JSONL,
and no sensitive content, then build the diff over the logical JSONL while
retaining raw Git blob SHA/bytes plus logical SHA/bytes/encoding in the
candidate manifest. All other non-UTF-8/binary blobs remain `UNVERIFIED`.

## Regression Test

- A bounded valid `.jsonl.gz` candidate is accepted and its logical JSONL
  appears in the exact review diff.
- Invalid gzip, multiple members, decompression overflow, non-UTF-8, invalid
  JSONL, secret-bearing content, and generic binary blobs are rejected before
  provider dispatch.
- The full PR candidate can be reconstructed without truncation and stays
  within the hierarchical unit/call bounds.

## Constraints

- No generic `allowBinary`.
- No archive extraction to disk and no candidate code execution.
- Reject before provider dispatch on ambiguity, expansion overflow, malformed
  JSONL, redaction, or evidence mismatch.
- Preserve exact raw Git coordinates and make the logical transform explicit
  and hash-bound in durable evidence.
