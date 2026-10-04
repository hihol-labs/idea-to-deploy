# Task Contract — OTK-FAILED-ATTEMPT-1 a failed harness attempt does not block the next one

- **Root cause:** `skills/goal/scripts/itd_goal_verify.py` (`cmd_verify`, failure branch) appended the
  `verification_failed` event to the tracked `.itd-memory/events.jsonl`. After a failed committed-head
  attempt the checkout differed from the committed candidate: `assert_checkout_matches_candidate`
  (`skills/_shared/itd_verification_loop.py`) refused the next attempt with the same receipt ("working
  tree differs from the staged candidate"), and `check_events` of `scripts/itd_closure_delta.py` rejected
  the line in the ledger-close delta (TIER-WORDING-2 ledger-close: the line had to be kept outside git and
  the journal reset to the commit; BACKLOG P2 2026-10-01, trap (b)).
- **Scope (owner variant A, 2026-10-04):** the failed attempt is not a transition, so its event goes to
  the untracked attempts journal `.itd-memory/attempts/attempts.jsonl` (`attempts_journal()`; the
  directory writes its own `.gitignore` = `*`, so it stays out of the candidate even where `.itd-memory/`
  is tracked); `append_event` takes the journal as a parameter; `itd_retro_scan.py` counts
  `failedVerifications` from both journals. A tracked attempts path is refused before any write (an
  ignore rule does not untrack a path; Sol s1): the attempt stays FAILED with exit 1 and the line
  `ERROR: the failed attempt is not journalled ... tracked by git`; only a positively established
  "no git" (no binary, or "not a git repository" in the C locale) skips that guard, any other git
  failure refuses the journal too (Sol s2). Transitions (`activated`, `verified`, `regressed`, `blocked`,
  `verification_unverified`) stay in `events.jsonl`; closure-delta is not changed.
- **Verification Standards:** the unit verificationCommand exits 0; the new oracle
  `tests/verify_otk_failed_attempt.py` is RED on the bytes of e725c07 (7 passed, 9 failed; log
  `.itd-memory/verification-loop/reports/OTK-FAILED-ATTEMPT-1-red-first.log`, sha256 43aac4f1f0a662e5) and
  GREEN after (16/0); mutations of the fix on isolated copies (failure back to events.jsonl, no
  self-ignore, a wrong ignore pattern, the journal parameter ignored, the retro scan skipping the journal, the tracked-path
  check switched off, a git failure treated as no git)
  are lethal, the control copy is green; `tests/verify_closure_delta.py`, `tests/verify_retro_scan.py`,
  `tests/verify_goal_tools.py`, `tests/verify_goal_verify_failpath.py`, `tests/verify_goal_verify_shell.py`
  stay green; medium route - `/review`, machine receipt legs `unit`, `meta-review`, `ledger-state`,
  targeted checker.
- **Exclusions:** the completion signal `.claude/completion/signals.jsonl` under a non-ignored `.claude/`
  (BACKLOG P2 2026-10-04), bounded-run `attempts[]`, closure-delta, the goal reporter label; the other
  pending units of the goal.
