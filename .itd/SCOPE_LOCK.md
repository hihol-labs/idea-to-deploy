# CLOSE-DEBT-1: explicit-close repair

## Current Task

- Repair strict handling of unknown runtime signals, update the repository's
  explicit-close budgets and quality freshness, and repair the signed efficacy
  replay's named-function blank-line anchor. Obtain an exact-candidate acceptance
  receipt, commit locally and run explicit close, as requested on 2026-10-16.
- Follow up on PR #366: refresh real source-bound live benchmark evidence,
  include CI's strict evidence replay in explicit close, reaccept the exact
  candidate, commit, push `fix/close-debt` and bring the PR's CI to green, as
  explicitly authorized by the owner. Do not merge or release.
- Owner approval on 2026-10-17 extends this follow-up to the canonical review
  transport's oversized-JSONL-line repair. Independently review the small repair
  with the existing trusted producer before using an exact reviewed temporary
  authority snapshot for the complete PR. Global installations remain unchanged.

## Allowed Change Areas

- `hooks/completion-gate.sh`, `docs/templates/itd/itd_hygiene.py`.
- `docs/SESSION_EXIT_CONTRACT.json`, `docs/VERIFICATION_CONTRACT.json`,
  `docs/QUALITY.json`, `docs/completion-gate.md`, `docs/CLOSE_DEBT_ROOT_CAUSE.md`.
- `tests/verify_strict_completion_policy.py`,
  `tests/verify_session_hygiene_quality.py`, `tests/verify_independent_review_efficacy.py`.
- `.itd/IMPACT_GRAPH.json`, `.itd/REVIEW_PROVIDER_FRESHNESS.json`, this scope and `CHANGELOG.md`.
- Git-ignored runtime signals and Verification Loop artifacts produced by the harness.
- `tests/fixtures/live-model-evidence/latest.json` and the immutable successful
  run `tests/fixtures/live-model-evidence/runs/20261016T193843Z-faa5f07d/`.
- `skills/_shared/itd_review_broker.py`, `skills/_shared/itd_free_reviewer_producer.py`,
  `skills/_shared/itd_review_broker_primitives.py`,
  `skills/_shared/REVIEW_BROKER_POLICY.json`,
  `skills/_shared/REVIEW_BROKER_POLICY.schema.json`,
  `skills/_shared/REVIEW_BROKER_RUNTIME.schema.json`,
  `tests/verify_review_broker.py`, `tests/verify_review_broker_policy.py`,
  `tests/verify_free_reviewer_producer.py`,
  `docs/adr/ADR-004-mandatory-keyless-review-route.md`.

## Forbidden Change Areas

- Frozen efficacy cases, signed reports, immutable history and detection thresholds.
- Other code, global installations, external services outside the authorized
  PR #366 branch update, merge/release/deploy.
- Historical signal outcomes and provenance; never rewrite them to obtain a pass.

## Review Rule

High risk: isolated exact-tree machine evidence and one fresh gpt-5.6-terra
checker for the host-observed maker (gpt-6.1-sol initially, gpt-6-astra after
the 2026-10-17 host model switch), followed by adjudication and receipt
revalidation. No long-running goal is opened; the prior followup remains closed.
