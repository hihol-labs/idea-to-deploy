# CLOSE-DEBT-1: explicit-close repair

## Current Task

- Repair strict handling of unknown runtime signals, update the repository's
  explicit-close budgets and quality freshness, and repair the signed efficacy
  replay's named-function blank-line anchor. Obtain an exact-candidate acceptance
  receipt, commit locally and run explicit close, as requested on 2026-10-16.

## Allowed Change Areas

- `hooks/completion-gate.sh`, `docs/templates/itd/itd_hygiene.py`.
- `docs/SESSION_EXIT_CONTRACT.json`, `docs/VERIFICATION_CONTRACT.json`,
  `docs/QUALITY.json`, `docs/completion-gate.md`, `docs/CLOSE_DEBT_ROOT_CAUSE.md`.
- `tests/verify_strict_completion_policy.py`,
  `tests/verify_session_hygiene_quality.py`, `tests/verify_independent_review_efficacy.py`.
- `.itd/IMPACT_GRAPH.json`, `.itd/REVIEW_PROVIDER_FRESHNESS.json`, this scope and `CHANGELOG.md`.
- Git-ignored runtime signals and Verification Loop artifacts produced by the harness.

## Forbidden Change Areas

- Frozen efficacy cases, signed reports, immutable history and detection thresholds.
- Other code, global installations, external services, push/PR/release/deploy.
- Historical signal outcomes and provenance; never rewrite them to obtain a pass.

## Review Rule

High risk: isolated exact-tree machine evidence and one fresh gpt-5.6-terra
checker for the observed gpt-6.1-sol maker, followed by adjudication and receipt
revalidation. No long-running goal is opened; the prior followup remains closed.
