# Worktree isolation for file-only refactors (v1.52.0)

A **file-only** refactor — pure structural moves with no behaviour change (rename, extract, split, dedupe across files) — is the safest candidate for *stronger-than-freeze* isolation: do the whole thing in a throwaway `git worktree`, verify green there, and only merge back to the working branch on success. The main working tree is never touched until a verified merge, so a botched refactor costs a `git worktree remove`, not a `git reset`.

This is an **opt-in** upgrade to the default `freeze.sh` scope guard (soft, warns on out-of-scope edits). It is NOT a new contract: worktree isolation is a harness/git convenience that TRANSPORTS the "don't corrupt the working tree" intent — it must degrade gracefully to the freeze path when unavailable (harness best-effort invariant, global CLAUDE.md).

## Hook path-assumption audit (precondition — all 24 hooks are worktree-safe)

Running a skill with `cwd` inside a linked worktree was audited against every hook in `hooks/`. Result: **no hook blocks, misfires, or corrupts state in a worktree.** Two reasons cover the whole set:

1. **Repo-root detection walks up to `.claude-plugin/plugin.json`, which a worktree checks out.** `careful.sh`, `check-commit-completeness.sh`, and `check-skill-completeness.sh` find the methodology root by walking parent dirs for `.claude-plugin/plugin.json`. A `git worktree` is a full working-tree checkout of a commit, so that file is present at the worktree root — detection resolves exactly as in the main tree. The commit gates parse `git diff --cached`, which operates on the worktree's own index; they fire identically. (`check-skills.sh` uses a **different** lookup — `project_profile(cwd)` reads `cwd/CLAUDE.md` for `itd-profile:` markers and falls back to `git rev-list --count HEAD`; it does NOT walk up for plugin.json. It is still worktree-safe: `CLAUDE.md` is checked out at the worktree root, and a worktree shares the repo history so `git rev-list` returns the same count — same profile as the main tree, via a different mechanism.)

2. **Sentinels are keyed on `session_id`, not on path.** `/tmp/claude-{review,dod,freeze,skill-check,cost,checkpoint}-<session>` are session-scoped. Changing `cwd` into a worktree does not change `CLAUDE_SESSION_ID`, so the `/review`, DoD, freeze, cost, and crash-recovery sentinels are all still found. The commit gates unblock across the worktree boundary as expected.

**Two benign path-coupled cases** (degrade, never break):

- `execution-trace.sh` writes `<cwd>/.claude/traces/session-<id>.jsonl`. In a worktree that lands under the worktree dir and is discarded on `git worktree remove`. Pure debug telemetry — losing an ephemeral trace is harmless; `.claude/` is gitignored so it never enters a commit.
- `handoff-readiness.sh` keys its rate-limit sentinel on an md5 of `cwd`, and nags (soft `systemMessage`) on a dirty tree with no fresh `session_*.md`. In a mid-refactor worktree the tree IS dirty, so it may soft-nag, and the worktree gets its own rate-limit bucket. Soft-only, never blocks — an acceptable, transient nudge.

Each plugin.json-walk-up hook carries its OWN copy of the detection (not shared code): `careful.sh` walks up via `os.getcwd()` (`find_methodology_repo`), while `check-commit-completeness.sh` and `check-skill-completeness.sh` walk up via a path argument (`find_repo_root(start)`). `tests/verify_worktree_hook_safety.py` drives **both** path-arg copies against a real worktree (so a future divergence in either fails the test); `careful.sh`'s copy is the same walk-up logic on `os.getcwd()` and is covered by the audit, not the path-arg test.

No hook needed a code change for worktree safety; this audit is the durable record that the precondition holds.

## Procedure (opt-in)

Use this for a **large, file-only** refactor (multi-file rename/extract/move). For a small in-place edit the default `freeze.sh` (Step 0) is enough — don't spin a worktree for a two-line change.

```bash
# 0. Preconditions — if ANY fails, fall back to the freeze path (Step 0) and say why.
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "not a git repo → freeze fallback"; }
# a reasonably clean tree is preferred so the merge-back is a clean fast-forward
git diff --quiet && git diff --cached --quiet || echo "warning: dirty tree — prefer stashing or use freeze fallback"

# 1. Create an isolated worktree on a throwaway branch off HEAD.
WT="$(git rev-parse --show-toplevel)/../.itd-refactor-wt-$$"
BR="refactor/$$-$(date +%s)"       # $$ (pid) avoids a same-second collision; date via shell is fine here (not a workflow script)
git worktree add "$WT" -b "$BR" >/dev/null

# 2. Do ALL refactor edits against paths under "$WT". Run the project's tests THERE,
#    then COMMIT inside the worktree — the commit is what step 3a merges back.
#    If tests are RED, do NOT commit — go straight to 3b.
( cd "$WT" && pytest -q ) || { echo "tests red → go to 3b (discard)"; }   # project's green baseline
git -C "$WT" add -A && git -C "$WT" commit -qm "refactor: <describe the change>"

# 3a. On GREEN (committed above) — merge the verified branch into the working branch.
if git merge --ff-only "$BR" 2>/dev/null || git merge --no-ff "$BR"; then
  git worktree remove "$WT" && git branch -d "$BR"        # merged cleanly → clean up
else
  # Working branch diverged AND overlaps the refactor textually → conflict.
  # Do NOT leave the tree mid-merge; abort and drop to the Step 0 freeze path.
  # Keep the branch + worktree so the verified work is not lost.
  git merge --abort
  echo "merge conflict → freeze fallback. Verified work kept on branch $BR (worktree $WT); resolve manually, then: git worktree remove \"$WT\""
fi

# 3b. On RED (tests failed, nothing committed) — discard; the main tree was never touched:
git worktree remove --force "$WT" && git branch -D "$BR"
```

### Rules

- **Opt-in, never default.** Trigger it when the user asks for worktree/isolated refactor, or offer it for a large file-only job. The default remains the freeze hook.
- **Graceful fallback is mandatory.** Not a git repo, git too old for worktrees, a dirty tree the user won't stash, or the user declines → drop to Step 0 (`freeze.sh`) and note the downgrade in one line. Never hard-fail the refactor because a worktree could not be created.
- **Verify, then COMMIT, inside the worktree before merge.** The green test run in step 2 is the gate; on green you MUST commit inside the worktree (step 2) — step 3a merges that commit, and without it `git merge` is a silent no-op that discards the work and breaks the `git worktree remove` cleanup. A red run means `3b` (discard, nothing committed), and the working tree stays pristine.
- **Merge-time fallback too.** The graceful-fallback rule covers not just preconditions but the merge: if `3a`'s `--no-ff` hits a conflict, `git merge --abort` and drop to the Step 0 freeze path — never leave the working tree mid-merge. The verified branch is preserved for manual resolution.
- **Behaviour-changing refactors are out of scope for this mode.** If tests must be rewritten (behaviour changed), it is not a file-only refactor — use the normal in-place flow with `/test` first (Rule 2).
- **The worktree is transient.** Do not leave `.itd-refactor-wt-*` dirs around; step 3 always removes them. `git worktree prune` cleans up any orphan from a crashed session.
