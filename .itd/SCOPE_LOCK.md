# REL-1.109.1: runtime bytecode fix and dual-host rollout

## Current Task

- Owner explicitly authorized on 2026-10-17: fix bytecode suppression in Python
  startup code, verify Windows and publish v1.109.1, without new workarounds.
- Start from merged main `582a093386254b231592d4458ebbddab9a8b5fa9`.
  WIP=1: replace the incomplete 1.109.0 Windows rollout follow-up with this
  patch-release follow-up, retaining its negative and Linux acceptance evidence.
  Do not claim 1.109.0 dual-host acceptance or rewrite the completed GOAL.
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
- `scripts/itd.py`, `scripts/itd_pre_push.py`, `scripts/itd_machine_oracle.py`,
  `skills/_shared/itd_verification_loop.py`: set bytecode suppression before
  project dependencies, no other runtime behavior change.
- `tests/verify_itd_runtime_install.py`: direct ordinary/isolated no-B launch
  regressions and lazy/path-loaded dependency inventory proof.
- `docs/CODEX_ADAPTER.md`: exact direct-execution guarantee and import boundary.
- `.itd/IMPACT_GRAPH.json`: regenerate with unchanged tests/build_impact_graph.py
  after the new regression dependency, preserving the freshness oracle.
- `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, this scope:
  evidence-backed release and prior-follow-up records.
- `tests/fixtures/live-model-evidence/latest.json` and one newly generated
  immutable successful release run; preserve all historical run archives.
- Git-ignored verification, handoff, branch-finish and native host-input files.
- `.itd-memory/STATE.json` and `.itd-memory/events.jsonl`: harness activation
  and evidence-backed reconciliation of this release unit; completed GOAL and
  historical events remain unchanged.
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
  the declared entrypoint fix, runtime regression and version mirrors; frozen
  efficacy inputs and observations. Do not change timeouts or parity assertions.
- ACL changes, cache-ignore exceptions, interpreter-global configuration,
  direct pushes or alternate publication transports bypassing the installed gate.
- Historical dates/outcomes/hashes, old runtimes, secrets, unrelated settings,
  disabled-hook choices and unrelated project checkouts.
- Handwritten goal/unit verified statuses, acceptance without exact evidence,
  unrequested releases/deploys, branch deletion or forceful main rewrites.

## Review Rule

Medium risk: bounded runtime startup suppression and packaging metadata. No
security-decision, provider selection, acceptance, timeout or inventory change.
Require exact-tree machine evidence and one fresh
canonical opposite-GPT review before publication. Old PR receipts and owner
dispositions do not authorize a changed release candidate. Use host-native
installed interpreters and verify actual installed runtimes after rollout.
