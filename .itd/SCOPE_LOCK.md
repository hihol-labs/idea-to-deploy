# REL-1.105.0

Current unit `REL-1.105.0`, high risk, activated by the goal harness on 2026-09-22
over `origin/main` `fad7915` (goal 3/4 verified: `LEDGER-ARCHIVE-1`, `ROUTE-REPAIR-3`,
`ROUTE-DEBTS-ORACLE-1`). Review claim ids: `REL-1.105.0` (goal claim) and
`REL-1.105.0:general-review` (cache gate). The release criterion and the
sealed verificationCommand live ONLY in `.itd-memory/GOAL.json`; this file references
them and does not restate them. The two acceptance rows of this unit
(`REL-1.105.0-1-version`, `REL-1.105.0-2-mirror`) are narrower review claims, not a
second source: each binds ONE leg of that command, byte-copied from `GOAL.json`, and
asserts nothing about the tag, the release, the rollout or the installed proof.

## Allowed

- The ten version places the unit's own verificationCommand enumerates by name
  (`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `docs/HARNESS_DOCS_STATE.json`, the `Version-`
  badges in `README.md` and `README.ru.md`, `docs/HARNESS_CONFORMANCE_REPORT.md`,
  `docs/api-reviewer/RELEASE_CANDIDATE_CONTRACT.json`, `VERSION` in
  `tests/verify_external_reviewer_release.py`, the `## [1.105.0]` heading in
  `CHANGELOG.md` with `## [Unreleased]` above it).
- `HANDOFF.md`; `.itd/SCOPE_LOCK.md` (this file); the acceptance-contract rows of this
  unit and its `activeFollowup`; canonical unit ledgers (`.itd-memory/GOAL.json`,
  `STATE.json`, `events.jsonl`); `.itd/DECISIONS.md` and `BACKLOG.md` entries.
- The live-model evidence pin under `tests/fixtures/live-model-evidence/`
  (`latest.json` plus one new `runs/<id>/`), re-recorded on a clean temporary detached
  worktree of the exact staged tree and landing in this same candidate (DECISIONS
  2026-09-22). The files under `runs/<id>/output/` are the live model's generated
  artifacts for `fixture-03-cli-tool`, recorded byte-exact and hash-pinned by
  `run-report.json`; their content quality is judged by `tests/verify_snapshot.py` and
  the recorded independent verdict inside the run, not by this review, and they are
  immutable: a finding about their content cannot be repaired in this candidate.
- `.itd-memory/host-inputs/REL-1.105.0/` (git-ignored, host-owned): mirror captures
  `source-<label>/`, native canaries `native-<Host>-<label>/`,
  `REL-1.105.0-native-<Host>-<label>/`, `INSTALLED.json`.

## Required

- The unit's verificationCommand exits 0 end to end (see `GOAL.json`).
- Before the multi-file commit: a `/review` pass (code-reviewer agent), then the
  cross-vendor producer (maker `claude-fable-5-1` / anthropic-subscription, reviewer
  `gpt-5.6-sol`) from authority `~/.cache/itd-review-authority/REL1105-f43de442-a1`
  (minted from merged `fad7915`, parity exit 0), full checker + adjudication for both
  claim ids, `check --require-mandatory-route`.
- Existing accepted evidence stays immutable; every live-model run already in the
  fixture stays byte-identical.
- Release mechanics follow `docs/RELEASE_RUNBOOK.md`: fresh `origin/main` before the
  branch and before the bump; tag only through `gh release create --target <full merge
  sha>`; both installs re-synced and the global `itd`/`pre-push` reinstalled natively
  on each host from that host's own source copy; old content-addressed runtime
  directories are rollback artefacts and are not deleted.

## Declared limits

- The sealed verificationCommand in `.itd-memory/GOAL.json` is outside this candidate's
  repair scope: the goal harness seals the oracle and the owner's standing instruction for
  this unit is not to change it. Weaknesses the independent reviewer finds in that command
  are recorded here and as BACKLOG items for the next release unit, not repaired in this
  candidate; the acceptance rows byte-copy legs of the command and inherit them.
  - Conformance-report place anchored by `rstrip().endswith('idea-to-deploy **v1.105.0**.')`
    on the single line containing `idea-to-deploy **v`: arbitrary leading text on that line
    would pass (gpt-5.6-sol, rel5, medium).
  - Tag leg: it checks that `v1.105.0` lies on the `origin/main` first-parent chain and that
    the tag commit's immediate first parent does not carry 1.105.0, not that NO earlier
    first-parent commit carries it; a revert-and-reintroduce history would pass
    (gpt-5.6-sol, pub1, medium). Not the shape of this release (the version enters main
    exactly once, in this PR), but the oracle does not prove that on its own.
  - Quick-mirror leg: `bash tests/run-all.sh --quick | tail -1 | grep -qx 'DONE fails:none'`
    runs without `set -o pipefail`, so the leg succeeds on the last line alone and would
    not notice a non-zero runner exit that still printed it (gpt-5.6-sol, rel7, medium).
    The declared host input `source-<label>/quick.json` records the runner's exit code
    (0 on every capture of this candidate) and `quick_mirror_check.py` asserts it, so the
    machine receipt carries what the sealed leg does not.

## Forbidden

- Any behavioural code change: this release is a version bump plus the changelog over
  already-merged, already-reviewed units.
- Touching `skills/_shared/*.py`, `hooks/`, `agents/`, skill bodies; relaxing any gate;
  new provider routes; deleting or rewriting any existing live-model run or efficacy
  leg; changes to the campaign, blind protocol or pilot decisions.
- Starting any other unit in this session (one plan item = one session).
- Claiming rollout, tag, release or installed-proof without host-observed artefacts.
- Merge, push, tag and release publication without the owner's explicit command.
