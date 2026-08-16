# Task Contract — S9-U4-PRCREATE

## Root cause

`create_draft_pr` derives the push decision from **PR existence** instead of from
the **remote ref state**: when `pr_view` returns `None` the function always issues
`git push --set-upstream origin HEAD`, even when the remote branch head already
equals local `HEAD`. Git still runs the guarded pre-push hook for a no-op push but
feeds it an empty update stream, and `scripts/itd_pre_push.py:55`
(`parse_updates`) rejects an empty stream fail-closed
("pre-push update stream is empty or invalid"). Observed 2026-08-14: a first
attempt timed out AFTER its push succeeded, no PR existed yet, and every retry
died in the hook — the branch was already delivered but the transport could never
reach `gh pr create`.

## Scope

Files: `scripts/itd.py` (`remote_branch_head`, `create_draft_pr`),
`tests/verify_itd_cli.py`.

The fix resolves the remote head of the current branch directly
(`git ls-remote --heads origin refs/heads/<branch>`) and skips the push when it
already equals local `HEAD`. The already-existing-Draft path keeps its exact
`--force-with-lease` pinned to the PR's `headRefOid` — that lease is the stronger
one (GitHub's own view) and is pinned by two existing assertions.

## Verification Standards

- `sh skills/_shared/itd_py.sh tests/verify_itd_cli.py` -> exit 0, with the new
  `absent PR with synced remote skips empty-stream push` and
  `absent PR with stale remote still pushes` cases PASS.
- Mutation (RED-first): with the fix reverted, the first new case fails because
  `run` is still called with the plain push command.
- `sh skills/_shared/itd_py.sh tests/verify_git_gate_hooks.py` -> exit 0
  (pre-push hook contract unchanged).
- `sh skills/_shared/itd_py.sh tests/verify_gate_registry_profiles.py` -> exit 0.
- `bash tests/run-all.sh` -> `DONE fails:none`.
- Fresh-session checker of the opposite vendor, mode full, over the exact
  parent->HEAD candidate; adjudicated receipt with `findings=[]`.

## Exclusions

- **`parse_updates` is NOT relaxed.** An empty pre-push update stream stays
  fail-closed; the caller stops producing one. Teaching the hook to accept an
  empty stream would remove the only place that notices a push whose ref
  coordinates never arrived.
- **`pr_view` stays BEFORE the push.** BACKLOG suggests push-first ordering to
  decouple a GitHub lookup outage from the transport. Deliberately not taken:
  the pre-push draft check is what rejects a ready (non-draft) PR before any
  push happens (`verify_itd_cli.py`: "ready PR rejected before push"). With a
  lookup outage the draft state is unknown, so failing closed is correct. The
  lookup-outage coupling stays open in BACKLOG as a separate debt.
- No change to `guarded_push_environment`, the lease semantics of the
  existing-Draft path, or any registry/receipt binding.
