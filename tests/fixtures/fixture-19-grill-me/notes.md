# Manual verification — fixture 19 (/grill-me)

`/grill-me` is a **read-only interactive stress-test**. It asks neudobnye
questions one at a time to surface assumptions, risks, and dependencies BEFORE
a decision is locked. It MUST NOT create or modify files. This fixture
regressionally fixes the one-at-a-time contract, the no-write guard, and the
`/grill-me` vs `/review` distinction.

## Fixture status

`pending` — **deferred**, same bucket as `fixture-15-advisor` and
`fixture-10-task` (interactive / stdout-only output). `verify_snapshot.py`'s
Phase 1 schema is file-shaped, so proper automated validation needs the Phase 2
stdout-snapshot scheme. For now: manual checklist below. The stub satisfies
`check-skill-completeness.sh`.

## /grill-me — Scenario A: stress-test a migration plan (happy path)

User pastes the prompt from `idea.md`: monolith → microservices in 2 months,
"grill me before I start, analysis only".

### Critical contract: no files written
- [ ] `ls -la output/` shows NO files after `/grill-me` completes (only `.`/`..`)
- [ ] If any file appears — **contract violation**, log in Failures below

### Question shape and pacing
- [ ] Questions are asked **one at a time** (NOT a dump of 10 at once)
- [ ] Each question has the shape: **Вопрос / Рекомендуемый ответ / Почему важно**
- [ ] Recommended answer is always included (user can agree with one word)

### Coverage (decision-tree axes)
- [ ] At least 5 of these axes are probed across the session:
      scope, assumptions, dependencies, risks, alternatives, security,
      rollout, cost
- [ ] At least one question challenges a hidden assumption
      ("почему не самый простой вариант?", "что если допущение X ложно?")
- [ ] At least one question probes rollback / one-way-door risk

### Ending
- [ ] Ends with **unresolved risks**
- [ ] Ends with **the next artifact that should change** if accepted
      (ADR / LAUNCH_PLAN.md / BACKLOG.md / .itd/SCOPE_LOCK.md)

## /grill-me — Scenario B: answer is discoverable locally (evidence-first)

User asks to grill an architecture, and the repo already documents the stack.

- [ ] Skill reads project docs/code (Read/Glob/Grep) BEFORE asking the user
- [ ] Does NOT ask the user a question whose answer is in the repo

## /grill-me — Scenario C: user asks to turn result into artifacts

After grilling, user says «запиши это в ADR».

- [ ] Only THEN does the skill write a file (explicit user request)
- [ ] Otherwise stays read-only

## /grill-me — Scenario D: guard rails (what /grill-me MUST NOT do)

- [ ] Does NOT use Write/Edit by default — **hard contract**
- [ ] Does NOT run `git commit`, `docker`, `npm install`
- [ ] Does NOT replace `/review` — tells user this is a pre-review stress-test
- [ ] Does NOT ask all questions at once

## Cross-reference with `check-skill-completeness.sh`

`/grill-me` satisfies the three Quality Gate 2 requirements:

1. ✅ `skills/grill-me/references/` exists (grill-me-question-bank.md)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/grill-me`
3. ✅ `tests/fixtures/fixture-19-grill-me/` exists with `idea.md`, `notes.md`,
   `expected-files.txt`, `expected-snapshot.json`

## Run manually

1. `cd tests/fixtures/fixture-19-grill-me/`
2. `mkdir -p output && cd output`
3. Start Claude Code on Opus, paste `idea.md` content, invoke `/grill-me`
4. After response: verify `ls -la` shows NO new files in the current directory
5. Go through the Scenario A checklist against the transcript
6. `cd .. && python3 ../../verify_snapshot.py .` — expected: `⏸️ fixture-19-grill-me: PENDING`

## Failures (fill in if any)

(empty unless the fixture fails — especially any file written by /grill-me in
violation of the no-write contract, or all questions dumped at once)
