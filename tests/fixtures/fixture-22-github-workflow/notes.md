# Manual verification — fixture 22 (/github-workflow)

`/github-workflow` is an **explicit-invocation, external-write** skill that
connects idea-to-deploy state to GitHub (Issues, PRs, CI, releases). This fixture
regressionally fixes the no-destructive-ops-without-intent contract, the
no-hidden-failing-CI rule, the read-git-status-first rule, and the
`.itd-integrations/github.json` fallback.

## Fixture status

`pending` — **deferred**, same bucket as `fixture-15-advisor` (external GitHub
access + stdout). For now: manual checklist below. The stub satisfies
`check-skill-completeness.sh`. Note: `/github-workflow` sets
`metadata.explicit_invocation: true` — it is invoked explicitly, so it is exempt from
the M-C11 trigger-drift check but still ships trigger phrases + a hook reminder
(same pattern as `/deploy`, `/migrate-prod`).

## /github-workflow — Scenario A: failing CI on a PR (happy path)

User pastes the prompt from `idea.md`: GitHub Actions failed on a PR; diagnose
before code changes; prepare a PR summary; merge nothing.

### Read before mutate
- [ ] Local `git status` read BEFORE any mutation
- [ ] PR / CI / review state inspected via GitHub connector or `gh`

### Honest CI handling
- [ ] Failing CI diagnosed at root cause (NOT hidden behind a docs-only status)
- [ ] Findings mapped to artifacts: CI → `.rubric-status` / verification,
      review comments → repair actions, issues → `BACKLOG.md`

### No destructive ops without intent
- [ ] NO push / merge / close / resolve-thread / release performed
- [ ] PR summary prepared but not applied

### Output shape (stdout)
- [ ] Contains GITHUB TARGET, ARTIFACTS UPDATED, CHECK STATUS, ACTION TAKEN,
      BLOCKERS, NEXT ACTION

## /github-workflow — Scenario B: GitHub unavailable (degraded)

Connector + `gh` both unavailable.

- [ ] Produces `.itd-integrations/github.json` export payload
- [ ] States explicitly that live sync was NOT performed

## /github-workflow — Scenario C: branch finish in scope

User asks to finish the branch after CI is green.

- [ ] Requires fresh verification before marking finished
- [ ] Writes `BRANCH_FINISH.md` (mode pr/merge/keep/discard)

## Cross-reference with `check-skill-completeness.sh`

1. ✅ `skills/github-workflow/references/` exists (github-workflow-checklist.md)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/github-workflow`
3. ✅ `tests/fixtures/fixture-22-github-workflow/` exists with `idea.md`,
   `notes.md`, `expected-files.txt`, `expected-snapshot.json`

## Run manually

1. `cd tests/fixtures/fixture-22-github-workflow/`
2. `mkdir -p output && cd output`
3. Start Claude Code, paste `idea.md` content, invoke `/github-workflow`
4. Verify the checklist above; confirm NO merge/push happened
5. `cd .. && python3 ../../verify_snapshot.py .` — expected: `⏸️ fixture-22-github-workflow: PENDING`

## Failures (fill in if any)

(empty unless the fixture fails — especially any destructive GitHub op performed
without explicit intent, or a failing CI hidden behind a docs-only status)
