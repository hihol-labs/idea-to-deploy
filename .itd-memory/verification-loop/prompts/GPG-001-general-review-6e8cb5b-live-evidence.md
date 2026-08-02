# Independent full checker prompt — GPG-001 live evidence refresh

Review target: `/home/hihol/projects/idea-to-deploy`

Exact staged candidate tree:
`6e8cb5b387a749a06c66f3fcdbc4e02c9ee4fc68`

Base commit:
`8a29a4b291478cabf3ab4e34ccf3f4127ad4057a`

Scope: the staged change only. It replaces the stale live-model benchmark
pointer with run `20260802T140742Z-1d3fd1db` and adds that run's bounded,
sanitized evidence: six generated documents, `run-report.json`, and the
compressed transcript.

Required review:

1. Confirm `git write-tree` still equals the exact tree above and inspect
   `git diff --cached`.
2. Independently validate that `latest.json`, `run-report.json`, artifact
   hashes, transcript hashes and redaction metadata, methodology-tree pin,
   adopted harness provenance, and deterministic oracle result are internally
   consistent.
3. Run the deterministic methodology oracle:
   `sh skills/_shared/itd_py.sh tests/meta_review.py --verbose`
4. Run the dedicated replay verifier:
   `sh skills/_shared/itd_py.sh tests/verify_live_model_benchmark.py --require-evidence --max-age-days 30`
5. Inspect the staged text evidence and decompressed transcript for secrets,
   credentials, personal data, or other unsafe durable content.
6. Look for Critical or Important defects, stale or forged evidence, missing
   artifacts, candidate self-attestation, or an input/tree mismatch. Do not
   review unrelated unstaged history.

Machine receipt already produced for the same candidate:
`.itd-memory/verification-loop/receipts/360a8d71643b981a/GPG-001-live-evidence-machine-12fd738043afe851.json`

Environment rules:

- Python scripts must be run through
  `sh skills/_shared/itd_py.sh <script.py> [args]`.
- This is read-only review work. Do not edit source, staged files, or the Git
  index. The only permitted write is the report file named below.
- Evidence is required for every conclusion. Mark anything not checked as
  `НЕ ПРОВЕРЕНО`.

Write the durable report incrementally to:
`.itd-memory/verification-loop/reports/GPG-001-general-review-6e8cb5b-live-evidence-terra.md`

End the report with exactly one canonical fenced JSON verdict block:

```json
{
  "verdict": "PASSED | PASSED_WITH_WARNINGS | BLOCKED",
  "findings": [],
  "unverified": []
}
```

Every Critical or Important finding must contain severity, confidence,
category, file, line, and one-line summary. If there are no findings and all
requested checks ran, return `PASSED`.
