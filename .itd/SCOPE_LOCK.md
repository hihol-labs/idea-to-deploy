# REL-1.106.0

## Current Task

REL-1.106.0 - release 1.106.0 over `origin/main` `2a1ea19`: version bump, changelog entry,
live-model evidence re-record, publication, native rollout on WSL and Windows, installed proof.

Current unit `REL-1.106.0`, high risk, activated by the goal harness on 2026-09-27 over
`origin/main` `2a1ea19` (goal TIER-SOURCE-1 -> REL-1.106.0, 1/2 verified: `TIER-SOURCE-1`).
Review claim ids: `REL-1.106.0` (goal claim) and `REL-1.106.0:general-review` (cache gate).
The release criterion and the verificationCommand live ONLY in `.itd-memory/GOAL.json`; this
file references them and does not restate them. The two acceptance rows of this unit
(`REL-1.106.0-1-version`, `REL-1.106.0-2-mirror`) are narrower review claims, not a second
source: each binds ONE leg of that command, byte-copied from `GOAL.json`, and asserts nothing
about the tag, the release, the rollout or the installed proof.

## Allowed Change Areas

- The ten version places the unit's own verificationCommand enumerates by name
  (`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `docs/HARNESS_DOCS_STATE.json`, the `Version-`
  badges in `README.md` and `README.ru.md`, `docs/HARNESS_CONFORMANCE_REPORT.md`,
  `docs/api-reviewer/RELEASE_CANDIDATE_CONTRACT.json`, `VERSION` in
  `tests/verify_external_reviewer_release.py`, the `## [1.106.0]` heading in
  `CHANGELOG.md` with `## [Unreleased]` above it).
- `HANDOFF.md`; `.itd/SCOPE_LOCK.md` (this file); the acceptance-contract rows of this
  unit and its `activeFollowup`; canonical unit ledgers (`.itd-memory/GOAL.json`,
  `STATE.json`, `events.jsonl`); `.itd/DECISIONS.md` and `BACKLOG.md` entries.
- The live-model evidence pin under `tests/fixtures/live-model-evidence/`
  (`latest.json` plus one new `runs/<id>/`), recorded on a clean temporary detached
  worktree of a staged tree of this candidate and landing in this same candidate (DECISIONS
  2026-09-22). The run is bound to the candidate by the content pin of
  `tests/itd_benchmark_pin.py` (the methodology tree digest over the pinned file set), not by
  the whole tree: later edits of files outside that set do not invalidate it, an edit of a
  pinned file does and requires a new recording. The binding is checked by
  `tests/verify_live_model_benchmark.py --require-evidence` on a clean materialisation of the
  final staged tree before the commit, in CI on the PR (`.github/workflows/meta-review.yml`,
  `--require-evidence --max-age-days 30`), and by the last leg of the unit's verificationCommand
  (same flags) on the release checkout, which therefore has to be clean when the goal harness
  runs it (the dirty-state digest of the run is pinned). The files under `runs/<id>/output/` are the live model's generated
  artifacts, recorded byte-exact and hash-pinned by `run-report.json`; their content
  quality is judged by `tests/verify_snapshot.py` and the recorded independent verdict
  inside the run, not by this review, and they are immutable: a finding about their
  content cannot be repaired in this candidate.
- `.itd-memory/host-inputs/REL-1.106.0/` (git-ignored, host-owned): mirror captures
  `source-<label>/`, native canaries `native-<Host>-<label>/`,
  `REL-1.106.0-native-<Host>-<label>/`, `INSTALLED.json`.

## Required

- The unit's verificationCommand exits 0 end to end (see `GOAL.json`).
- Before the commit: `tests/verify_live_model_benchmark.py --require-evidence` exits 0 on a
  clean materialisation of the staged tree that is committed.
- Before the multi-file commit: a `/review` pass (code-reviewer agent) over the candidate
  diff, and after every later change of the candidate a delta `/review` of the changed files
  on the tree that is committed; then the
  cross-vendor producer (maker `claude-opus-5-5` / anthropic-subscription, reviewer
  `gpt-5.6-sol`) from authority `~/.cache/itd-review-authority/REL1106-0a60e71e-a1` (minted from merged `2a1ea19`, parity exit 0),
  full checker + adjudication for both claim ids, `check --require-mandatory-route`.
- Existing accepted evidence stays immutable; every live-model run already in the
  fixture stays byte-identical.
- Release mechanics follow `docs/RELEASE_RUNBOOK.md`: fresh `origin/main` before the
  branch and before the bump; tag only through `gh release create --target <full merge
  sha>`; both installs re-synced and the global `itd`/`pre-push` reinstalled natively
  on each host from that host's own source copy; old content-addressed runtime
  directories are rollback artefacts and are not deleted.

## Declared limits

- The REL-1.106.0 verificationCommand was approved by the owner on 2026-09-26 as a copy of
  the REL-1.105.0 command. On 2026-09-27, before any review round, the owner chose to repair
  the three weaknesses of that command recorded in BACKLOG P2 2026-09-22, and later the same
  day, after the delta `/review`, a fourth one; four legs changed and the other six stay
  byte-identical (DECISIONS 2026-09-27):
  - quick mirror: the runner's stdout goes to a temp file, and the leg requires the runner's
    exit code 0 AND the last line exactly `DONE fails:none` (`/bin/sh` is dash, which has no
    `pipefail`);
  - conformance place: the single line containing `idea-to-deploy **v` must equal the whole
    expected line, not only end with it;
  - tag: no first-parent commit of `origin/main` older than the tag may carry 1.106.0 (every
    older change point of `.claude-plugin/plugin.json` is read), replacing the check of the
    immediate first parent only;
  - live-model evidence (last leg): the verifier runs with `--require-evidence --max-age-days
    30`, the flags CI uses; without them it ran only the pin module's self-checks and never
    checked that the recorded run is bound to the release tree.
  The acceptance rows byte-copy the amended mirror and version legs. What the command still does not prove:
  the criterion's claims outside its ten legs, and anything about hosts other than this WSL
  (the Windows side is proved only through `INSTALLED.json` and the Windows `--check`).

## Forbidden

- Any behavioural code change: this release is a version bump plus the changelog over
  already-merged, already-reviewed units.
- Touching `skills/_shared/*.py`, `hooks/`, `agents/`, skill bodies, `skills/goal/scripts/`;
  relaxing any gate; new provider routes; deleting or rewriting any existing live-model run
  or efficacy leg; changes to the campaign, blind protocol or pilot decisions.
- Repairing the `[machine_only]` label of `itd_goal_report.py` in this unit (BACKLOG P2
  2026-09-27; a separate unit after the release).
- Starting any other unit in this session (one plan item = one session).
- Claiming rollout, tag, release or installed-proof without host-observed artefacts.
- Merge, push, tag and release publication without the owner's explicit command.
