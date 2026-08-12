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
