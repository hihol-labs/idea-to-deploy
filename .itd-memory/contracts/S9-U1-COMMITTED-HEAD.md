# S9-U1-COMMITTED-HEAD — the producer cannot route an already-committed candidate

**Unit:** `S9-U1-COMMITTED-HEAD` · riskTier **medium** · branch `fix/s9-harness-debts`
**Impact classes:** correctness, error-handling, repository-hygiene

## Root cause

`freeze_packet` in `skills/_shared/itd_free_reviewer_producer.py` assumed the
candidate is always **staged on top of HEAD**:

```python
parent = str(git(root, "rev-parse", "HEAD")).strip()
...
machine_diff_raw = git(root, "diff", "--cached", "--binary", ..., parent, "--")
if not machine_diff_raw:
    raise FreeReviewError("UNVERIFIED", "staged machine candidate diff is empty")
```

Once the candidate is committed, the index equals the HEAD tree, so
`git diff --cached HEAD` is empty **by construction** and the producer fails
closed on a perfectly valid submission. The free isolated reviewer route was
therefore usable only before the commit, and an accepted-then-committed
candidate could not be re-routed at all.

`itd_verification_loop.py` already solved exactly this
(`skills/_shared/itd_verification_loop.py:251-276`): `--candidate-mode
committed-head` binds `parent -> HEAD` after proving HEAD is a single-parent
commit and the index equals the committed HEAD tree.

## Scope

- `skills/_shared/itd_free_reviewer_producer.py`:
  - `freeze_packet(..., candidate_mode="staged"|"committed-head")`;
  - in committed-head, the parent comes from
    `git rev-list --parents -n 1 HEAD` and a commit with anything other than
    exactly one parent is rejected;
  - the index must equal `HEAD^{tree}`, so the packet cannot describe an index
    that drifted from the commit it claims to review;
  - an unknown mode is rejected fail-closed;
  - `review --candidate-mode {staged,committed-head}` on the CLI, default
    `staged`, so every existing caller keeps byte-identical behaviour.
- `tests/verify_free_reviewer_producer.py` — behavioural coverage.

The diff plumbing is deliberately NOT duplicated: because committed-head also
requires index == HEAD tree, the existing `git diff --cached <parent>` yields
exactly `parent..HEAD`. One parent resolution changes; the exact-candidate
math stays the one already reviewed.

## Exclusions

- **The clean-tree requirement is not relaxed.** Unstaged tracked changes and
  untracked non-ignored files still fail closed, in both modes.
- **`staged` stays the default.** No existing caller changes behaviour; the
  new binding is opt-in per invocation.
- **The route of THIS unit does not use the producer.** A producer cannot be
  the independent reviewer of its own fix. This unit is routed exactly like
  U4/U3/U2: isolated machine oracles plus a fresh-session checker of another
  model, neither of which loads `itd_free_reviewer_producer.py` as a reviewer.
- **No transport, keyring, scrubber or policy change.**

## Verification standards

- RED-first / defect reproduction: the suite proves that staged mode on a
  committed candidate still fails with the production error
  `staged machine candidate diff is empty` — the exact symptom this unit
  exists to remove — and that committed-head mode routes the same candidate.
- Equivalence: the packet frozen in staged mode from an index, and the packet
  frozen in committed-head mode from the commit of that very same index, agree
  on `tree`, `diffSha256`, `parentCommit` and `baseCommit`. Committing the
  candidate does not change what is reviewed.
- Mutation: making the mode ignored (so committed-head resolves the parent as
  HEAD) restores the original empty-diff failure; dropping the
  index-equals-HEAD-tree assertion turns the dirty-index assertion red.
  Restoring returns the suite to green.
- Fail-closed coverage: a merge commit (two parents), an index that differs
  from HEAD, and an unknown candidate mode are each rejected with their own
  distinct reason.
- Coverage: `tests/verify_free_reviewer_producer.py` 174 -> 184 checks,
  `liveExternalCalls: 0`, `paidApiCalls: 0`.
