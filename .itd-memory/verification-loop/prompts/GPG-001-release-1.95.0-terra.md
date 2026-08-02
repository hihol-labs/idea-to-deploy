# GPG-001 release 1.95.0 exact-candidate review

Review only the staged candidate relative to base commit
`234752828d463821814020bebf2cc3dc40399beb`.

- staged tree: `aee9ee16c45974d0d822675d4912ed27f5505c45`
- binary diff hash: `063088c1472a5d339f9f87da31d83102df70bc9d`
- purpose: atomically publish the 1.95.0 changelog entry and switch the
  fail-closed release oracle from candidate-state validation to published-state
  validation

Use read-only local inspection. Check correctness, false PASS/FAIL behavior,
date validation, duplicate handling, stale candidate markers, runbook
consistency, and release completeness. A PASSED verdict requires empty
`findings` and `unverified` arrays.
