# Scope Lock — S2-FLAKE: oracle/hygiene nondeterminism root-caused and pinned

## Current Task

Close unit S2-FLAKE (S2 in PLAN-CLOSEOUT-2026-08-11): the two 2026-08-11
BACKLOG P0 nondeterminism items. Diagnosis (evidence in
`tests/ROOT_CAUSE-s2-oracle-nondeterminism.md`): both flakes share one root —
transient fork-level `EAGAIN` under user-wide host process pressure, with a
per-run hit probability that scales with subprocess count (≈4429 git spawns in
`run-all.sh --quick` vs ≈328 in the U16 verifier). Oracle receipts a45/a46/a47
(same tree `862d3416`, serial runs, fresh isolated checkouts) rule out temp
paths and command ordering. The hygiene flake specifically: the unguarded
`subprocess.run` in `itd_hygiene.py::git()` turned a spawn failure into an
uncaught crash of `close` — rc=1 with EMPTY stdout — which the suite misread
as a wrong gate verdict. Reproduced 40/40 under RLIMIT_NPROC pressure.

The candidate fixes the runner fail-closed and pins both causes with
regression tests that are red on the pre-fix runner (verified via stash runs).

## Allowed zones

- `docs/templates/itd/itd_hygiene.py` — `git()` gains a bounded spawn retry
  (spawn-level OSError only; FileNotFoundError not retried) degrading to a
  synthetic rc=127 `CompletedProcess`; `is_tracked` is replaced by a
  three-state `tracking_state` and `cleanup_manifest` deletion now requires
  positive proof of untracked-ness (`ls-files --error-unmatch` rc=1); any
  other git rc is the fail-closed error "tracking state could not be proven".
  No other behaviour change.
- `tests/verify_session_hygiene_quality.py` — two added pins:
  `test_close_survives_spawn_pressure` (POSIX RLIMIT_NPROC=1: close must emit
  a structured fail-closed report, never an empty-stdout crash) and
  `test_cleanup_requires_tracking_proof` (git shim rc=2: cleanup must refuse
  deletion). No existing check weakened.
- `tests/ROOT_CAUSE-s2-oracle-nondeterminism.md` — new evidence document.
- `BACKLOG.md` — the two S2 items move to `[x]` with root-cause pointers;
  historical text retained.
- `.itd/SCOPE_LOCK.md` and `.itd/ACCEPTANCE_CONTRACT.json` — this unit's
  frozen scope and its two evidence-first criteria
  (`S2-FLAKE:general-review-1/2`), superseding the closed U-NTFS-DIRSIZE
  scope; prior units' criteria are retained untouched.
- `.itd-memory/STATE.json` — bookkeeping only: `currentUnit` advances from
  the closed U16 (merged PR #192, ledger verified) to `S2-FLAKE`
  (in_progress, high). No other state field changes.

Post-review CI amendment (2026-08-13, same unit):

- `tests/verify_session_hygiene_quality.py` — `test_cleanup_requires_tracking_proof`
  becomes POSIX-only: Windows CreateProcess resolves `git` to `git.exe` only,
  so the `.cmd` shim never intercepts the runner's subprocess and windows-verify
  correctly failed; the guard under test is platform-neutral, the staging of a
  failing git is not.
- `tests/fixtures/live-model-evidence/latest.json` and
  `tests/fixtures/live-model-evidence/runs/20260812T220745Z-3d92147a/` — the
  standing live-benchmark evidence re-pin (precedent a8b0885/de4f9c1): the S2
  change to `docs/templates` staled the previous pin and failed Gate 1; fresh
  live run fixture-03-cli-tool PASS, replay verifier 39/39.
- `tests/fixtures/live-model-evidence/runs/20260812T222109Z-f2abf181/` — the
  corrected re-pin run: the 3d92147a run was executed with the test fix still
  uncommitted, so its evidence pinned a dirty `workingTreeStatusSha256` and
  Gate 1 failed on CI's clean checkout ("dirty-state digest is pinned").
  f2abf181 re-ran the identical fixture on the clean committed tree;
  `latest.json` now points to it. The superseded 3d92147a run directory stays
  as history, matching how prior pinned runs are retained.

  Transcript-artifact contract (for reviewers of this diff): each run's
  `transcript.jsonl.gz` IS part of this candidate and is committed as a git
  binary blob, exactly like every prior pinned run. It is genuine gzip (magic
  `1f8b 08`); the run's own `run-report.json` binds it twice —
  `transcriptGzipSha256` = sha256 of the committed gzip bytes, and
  `transcriptSha256`/`transcriptBytes` = digest and size of the decompressed
  stream. For the active pinned run f2abf181 those values are
  4dc363ddd6008a24a9e88dc3989c36b2a3efbd8a4dfe5b59570e3f3d11de14fb (gzip,
  verified equal to the staged blob) and 53856 decompressed bytes; the
  superseded 3d92147a history run carries its own matching pair
  (2b798c1e…, 59630). The declared-transparent review transport may render
  this artifact decompressed or omit binary blobs from a unit's text path
  list; that rendering is not the repository content. The self-containment
  claim is machine-checked by `tests/verify_live_model_benchmark.py`
  (39/39 on this tree), which hash-verifies the artifact against the report
  before any consumer trusts it.

## Out of scope (honest limits)

- The host transient itself is not eliminable from the repository; a shared
  spawn-retry helper for the other ~60 verify tests is a recorded backlog
  candidate, not part of this unit.
- `verify_independent_review_efficacy` is deterministically red on clean main
  `b5fd588` ("wsl semantic result binding is foreign") — pre-existing live-pin
  friction (S6, user-deferred). Not an S2 flake; not touched by this unit.
- Promoting the quick suite back into the U16 exact-candidate oracle
  (SCOPE_LOCK criterion 4 amendment of the U16 era) stays blocked on S6.

## Machine-oracle shape

The exact-candidate machine oracle for this unit runs, in isolation on the
staged tree: `tests/meta_review.py` (repo-wide static rubric, deterministic)
and `tests/verify_session_hygiene_quality.py` (the S2-pinned behavioural
suite, 50 checks). Operator evidence besides the receipt: 5 consecutive green
runs of the hygiene suite and of the U16 verifier, and 5 quick-suite runs
whose only red each time is the deterministic pre-existing efficacy pin.
