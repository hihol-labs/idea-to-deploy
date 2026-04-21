# Manual verification — fixture 15 (/advisor)

`/advisor` is **read-only analysis mode**. It prints recommendations to stdout and MUST NOT create or modify any files. This fixture exists to regressionally fix the "files not written" contract plus the structured-output contract (5 sections, 2 subagents).

## Fixture status

`pending` — **deferred**, same bucket as `fixture-10-task` (router with stdout-only output). verify_snapshot.py's Phase 1 schema is file-shaped, so proper automated validation of /advisor needs the Phase 2 stdout-snapshot scheme (v1.16.0 candidate). For now: manual verification via the checklist below.

The stub still satisfies `check-skill-completeness.sh` and anchors future regression work.

## /advisor — Scenario A: A/B/C comparison, happy path

User pastes the prompt from `idea.md`: 3 project directions (marketplace for clinics / SaaS for booking / Telegram bot for patients), budget 200K ₽, deadline 3 months. Request: only analysis, no code.

### Critical contract: no files written
- [ ] `ls -la output/` shows NO files after `/advisor` completes (only `.` and `..`, plus optional `.rubric-status`)
- [ ] If any file appears — **contract violation**, log as regression in Failures below

### Output structure (stdout)
- [ ] Response contains section **Analysis** — factual context, not yet a recommendation
- [ ] Response contains section **Pros** — per option, with concrete numbers or references
- [ ] Response contains section **Cons** — per option, with real trade-offs (not "может быть сложно")
- [ ] Response contains section **Recommendation** — names ONE option (not "зависит")
- [ ] Response contains section **Risk** — top 3 risks of the recommended option with mitigation

### Multi-perspective analysis
- [ ] At least 2 perspectives visible in the analysis:
  - business-analyst subagent: market size, competitive positioning, revenue potential
  - devils-advocate subagent: counter-arguments, worst-case scenarios, hidden costs
- [ ] Perspectives disagree on at least one point — synthesis is explicit, not silent consensus

### Specificity
- [ ] Budget constraint (200K ₽) referenced concretely — "200K покрывает 2-3 месяца разработки при ставке X"
- [ ] Deadline (3 months) referenced concretely — "MVP за 3 месяца требует scope X из полного Y"
- [ ] Recommendation is NOT "A" or "B" as a letter — it names the actual project type ("SaaS для записи в салоны")

## /advisor — Scenario B: vague question (edge case)

User says: «что мне делать?»

- [ ] Skill asks ONE clarifying question (not more): «Уточни: ты сравниваешь конкретные варианты или ищешь новые идеи?»
- [ ] Does NOT proceed with analysis on a vague prompt — clarity is a precondition
- [ ] If user refuses to clarify: skill degrades gracefully, gives generic framework (not fabricated recommendations)

## /advisor — Scenario C: user asks to implement recommendations

After the advisor analysis, user says «давай начнём делать B».

- [ ] Skill does NOT silently start building — still in analysis-only mode
- [ ] Skill tells user: «Рекомендации готовы. Для реализации используй подходящий скилл: /kickstart (новый проект), /strategy (обновление плана), /task (конкретная задача).»
- [ ] User must explicitly exit /advisor and invoke a build skill

## /advisor — Scenario D: guard rails (what /advisor MUST NOT do)

- [ ] Does NOT use Write / Edit tools — **hard contract**, violation = regression
- [ ] Does NOT run `git commit`, `docker ...`, `npm install`, or any state-changing command
- [ ] Does NOT generate DISCOVERY.md even if the user says "и discovery заодно" — that's /discover
- [ ] Does NOT skip devils-advocate even on obvious cases — adversarial review is the skill's core value
- [ ] Does NOT return "нет данных" without attempting at least a framework-level analysis

## Cross-reference with `check-skill-completeness.sh`

`/advisor` satisfies the three Quality Gate 2 requirements:

1. ✅ `skills/advisor/references/` exists
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/advisor`
3. ✅ `tests/fixtures/fixture-15-advisor/` exists with `idea.md`, `notes.md`, `expected-files.txt`, `expected-snapshot.json`

## Why active validation is deferred

`verify_snapshot.py` validates:
1. Presence of required files in output dir
2. Required sections / content markers within those files
3. Counts (endpoints, user stories, implementation steps)
4. Rubric status (if `.rubric-status` file present)

None of the above apply cleanly to a stdout-only recommendation. The closest existing schema field is `no_write_allowed` (currently an unused hint in the JSON), but verify_snapshot.py does not enforce "no files" — it only checks "these files exist". Proper /advisor validation requires either:
- Phase 2 stdout-snapshot scheme (chat-log capture + regex validation) — v1.16.0 candidate
- Or an extension to verify_snapshot.py with a `files.forbidden` or `max_count: 0` contract

Until then: manual checklist above is the contract.

## Run manually

1. `cd tests/fixtures/fixture-15-advisor/`
2. `mkdir -p output && cd output`
3. Start Claude Code on Opus, paste `idea.md` content, invoke `/advisor`
4. After response: verify `ls -la` shows NO new files in the current directory
5. Go through the Scenario A checklist against the transcript
6. `cd .. && python3 ../../verify_snapshot.py .` — expected: `⏸️ fixture-15-advisor: PENDING`

## Failures (fill in if any)

(empty unless the fixture fails — leave space for documenting regressions, especially any file written by /advisor in violation of the no-write contract)
