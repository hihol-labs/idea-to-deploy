# REL-1.109.0: release preparation and dual-host rollout

## Current Task

- Owner explicitly authorized on 2026-10-17: prepare and publish v1.109.0,
  update WSL and Windows installations, and verify that they work.
- Start from merged main `9484d980e4f1b321564263c596770fa6e6e07bc3`.
  Package already accepted GATE-OPTIN-1 and CLOSE-DEBT-1 changes without new
  runtime behavior. WIP=1: archive completed CLOSE-DEBT-1-LIVE with its real
  ADJUDICATED, merge and CI evidence; preserve the completed GOAL and STATE.
- Preparation criteria live in `.itd/ACCEPTANCE_CONTRACT.json`. Publication
  and installation are subsequent authorized stages, not claims implied by
  passing preparation tests.

## Allowed Change Areas

- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `.codex-plugin/plugin.json`: release version only.
- `README.md`, `README.ru.md`, `docs/HARNESS_DOCS_STATE.json`,
  `docs/HARNESS_CONFORMANCE_REPORT.md`, `docs/templates/github/itd-hygiene.yml`,
  `docs/api-reviewer/RELEASE_CANDIDATE_CONTRACT.json`,
  `tests/verify_external_reviewer_release.py`: current version mirrors only.
- `CHANGELOG.md`: release notes and an empty next Unreleased cycle.
- `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, this scope:
  evidence-backed release and prior-follow-up records.
- `tests/fixtures/live-model-evidence/latest.json` and one newly generated
  immutable successful release run; preserve all historical run archives.
- Git-ignored verification, handoff, branch-finish and native host-input files.
- After acceptance and green CI: guarded release PR publication, squash merge,
  tag/GitHub Release creation at the full merge SHA, then installation of that
  exact release into existing WSL and Windows plugin/runtime targets.

## Evidence Boundary

H4 records a real generated blueprint and its separate fresh adversarial review.
PASS means the unchanged structural/workflow oracle passed, not that the example
CLI is production-ready. Keep real design flaws visible in the immutable
specimen and advocate report. Do not edit or resample archived text merely to
obtain a clean semantic vote.

## Forbidden Change Areas

- Runtime implementation, skills, hooks, agents, policies and test logic beyond
  the version mirror above; frozen efficacy inputs and observations.
- Historical dates/outcomes/hashes, old runtimes, secrets, unrelated settings,
  disabled-hook choices and unrelated project checkouts.
- Handwritten goal/unit verified statuses, acceptance without exact evidence,
  unrequested releases/deploys, branch deletion or forceful main rewrites.

## Review Rule

Medium risk: packaging metadata and immutable experimental evidence, not new
implementation behavior. Require exact-tree machine evidence and one fresh
canonical opposite-GPT review before publication. Old PR receipts and owner
dispositions do not authorize a changed release candidate. Use host-native
installed interpreters and verify actual installed runtimes after rollout.
