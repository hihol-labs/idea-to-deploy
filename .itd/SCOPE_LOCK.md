# G-002 CONTEXT-BUDGET-1 - the pre-flight hook stops re-dumping the world on every prompt

Unit `G-002` (low) is `verified` in `.itd-memory/GOAL.json` (harness activation
2026-09-23T16:29:37Z, harness verification 2026-09-23T19:03:30Z with receipt
`G-002-adjudication-a2-ch.json` committed-head over `d927053`, tree `cd4e3a9e` = commit
`453f28b`; goal PROPORTIONALITY-DEFAULT, 2/5 verified); the criterion and the
verificationCommand live ONLY there and are not restated here. Branch
`feat/g-002-context-budget` over main `d927053`. Review claim ids: `G-002`,
`G-002:general-review`. Risk tier `low` (sealed at decomposition): machine-only review
route - the machine receipt is adjudicated alone, no fresh-session checker, no producer
round unless a strict-class signal appears (none: no money/prod-config/db-schema/auth/
secrets surface is touched).

Measured before the first edit (main `d927053`): `hooks/pre-flight-check.sh` emits the
full dump on EVERY `UserPromptSubmit` (git context, ITD state, contract drift, memory
index, staleness) - ~4-6 KB per prompt on this repository; the only per-session state it
keeps is the cwd history for context-switch detection. `hooks/session-open-diagnostic.sh`
already implements the once-per-session pattern (tempdir sentinel keyed by session id).
The host memory index `~/.claude/projects/-home-hihol-projects-idea-to-deploy/memory/MEMORY.md`
is 50 525 bytes, 141 lines, 89 lines longer than 200 characters (budget: <= 24 400 bytes,
every line <= 200 characters).

## In scope

- `hooks/pre-flight-check.sh`: per-session, per-repository state file in the temp dir
  (`claude-preflight-<session>-<repo-key>.json`) recording that the full dump fired and
  the last seen HEAD sha + the last seen parallel-session lock timestamp. First prompt
  of a session (or first prompt in a repository the session has not visited): full dump
  as today, state written. Later prompts: ONLY the delta - commits that appeared since the
  last prompt (`git log --oneline <last>..HEAD`, capped) and the parallel-session warning
  if a fresh lock appeared or its timestamp advanced; the whole output is capped at 1024
  bytes; no delta -> no output at all (exit 0, nothing on stdout). Context-switch to a
  different repository counts as a first prompt for that repository. State-file
  failures fall back to the full dump (fail-open toward more context, never toward
  silence on the first prompt).
- `tests/verify_preflight_budget.py` (new, registered in `tests/run-all.sh`): drives the
  real hook as a subprocess in a throwaway git repository with an isolated HOME/TMPDIR
  and a fresh session id: first prompt carries the full dump; second prompt with no
  change is empty; a new commit yields a delta <= 1024 bytes naming the commit and
  nothing else; a fresh `.active-session.lock` yields the warning; a second repository in
  the same session gets its own first dump; an unreadable state file degrades to the full
  dump; RED on the pre-fix hook (measured); `--mutations` >= 3 lethal (sentinel never
  written, delta cap removed, commit delta ignored). The host memory index budget
  (<= 24 400 bytes, lines <= 200 chars) is checked when that file exists on the host and
  reported as skipped otherwise (CI has no host memory).
- Host memory index consolidation (durable state, approval-diff gate): older session
  entries moved into a dated archive topic file, remaining hooks shortened to one line
  <= 200 characters; shown as a before/after diff and applied only after the owner's go.
- `.itd/IMPACT_GRAPH.json` regeneration; `CHANGELOG.md` [Unreleased]; the hook table row
  in `docs/HARNESS_ENGINEERING_MAP.md` (one line: first prompt full, then delta).

## Allowed Change Areas

- `hooks/pre-flight-check.sh`
- `tests/verify_preflight_budget.py`, `tests/run-all.sh`
- `.itd/IMPACT_GRAPH.json`, `CHANGELOG.md`, `docs/HARNESS_ENGINEERING_MAP.md`
- `.itd/SCOPE_LOCK.md`, `.itd-memory/contracts/G-002.md`, `.itd/DECISIONS.md`, `BACKLOG.md`
- host memory index `~/.claude/projects/-home-hihol-projects-idea-to-deploy/memory/MEMORY.md`
  (+ archive topic file) - outside the repository, after approval

## Forbidden Change Areas

- `hooks/session-open-diagnostic.sh` and every other hook (G-003 owns hook tier exits).
- `skills/**`, `.claude/settings.json`, `docs/templates/**` (G-004 owns auto-install).
- Goal ledger transitions by hand (`GOAL.json` / `STATE.json` / `events.jsonl` are written
  by `itd_goal_verify.py` only); `.itd/ACCEPTANCE_CONTRACT.json` until the publication step.
- Any change to what the FIRST prompt prints (the full dump keeps its sections and order).

## Declared limits

- The delta is git-visible state only: new commits and a parallel-session lock. Changes
  to GOAL/STATE, contracts, drift or the memory index between prompts are NOT re-emitted
  (they are re-read by the skills that need them); the next full dump is the next session.
- The 1024-byte cap truncates the commit list from the end and appends a marker; it never
  drops the parallel-session warning (emitted first).
- Session identity follows the hook's existing rule (payload session_id, then
  `CLAUDE_SESSION_ID`, then parent pid); a host that changes the id per prompt gets a full
  dump per prompt - unchanged from today, not a regression.

## Out of scope

- Hook early-exit by tier (G-003), hook auto-install (G-004), external pilot (G-005).
- `MEMORY_INDEX_MAX_LINES` and the shape of the first-prompt dump.
- The `.itd-memory/MEMORY.md` project-local index (54 KB): same rule applies later, not
  part of the G-002 criterion (host index only).

## Route history

- Machine-only route (low): oracle RED-first on the pre-fix hook (13 failed), GREEN after,
  mutations 3/3 lethal; m1 x2 (staged cd4e3a9e) -> a1 x2 -> check 0 x2 -> review cache
  PASSED -> commit `453f28b`; live evidence pin intact (154/0, the hook is outside the
  60-file pin); m2-ch/a2-ch (committed-head) -> harness verified. Ledger-close (this
  commit): GOAL/STATE/events by the harness, acceptance followup G-002 with two
  evidence-first criteria (oracleIds = machine run ids preflight-budget / meta-review /
  ledger-state), this file.
- Publication round PUB1 (producer UNVERIFIED before any review): the followup's
  reviewPolicy carried minimumIndependentReviewers=1 copied from the medium unit; a low
  review requires zero independent reviewers - set to 0 (ledger-only commit).
