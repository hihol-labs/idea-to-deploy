# Manual verification — fixture 13 (/strategy)

`/strategy` replans an **existing** project that is under-performing vs its targets. This fixture uses the NeuroExpert case (MRR 50K ₽, target 200K ₽ by Q2, trial→paid conversion 8% vs 25% target). It is **not** a first-time planning skill — for new projects use `/blueprint`.

## /strategy — Scenario A: 5-dimension gap analysis, happy path

User pastes the prompt from `idea.md`. A baseline `LAUNCH_PLAN.md` already exists (or the user asks to create one).

### Step 0 — Context assessment
- [ ] Skill runs `ls -la LAUNCH_PLAN.md BACKLOG.md ROADMAP*.md STRATEGIC_PLAN.md DISCOVERY.md PRD.md`
- [ ] Skill runs `git log --oneline -20 --all` to see recent activity
- [ ] Skill asks ONE clarifying question: «Что изменилось? Какой контекст привёл к пересмотру?» — does not force extensive Q&A

### Step 1 — Situation analysis (5 dimensions)
- [ ] `LAUNCH_PLAN.md` contains a dimension table with rows for: **Market, Product, Metrics, Resources, External**
- [ ] Each dimension has Current state (numeric), Target state (from original plan), Gap (delta), Root cause
- [ ] For NeuroExpert: MRR row has Current=50K, Target=200K, Gap=-75%, Root Cause referencing trial→paid conversion
- [ ] `business-analyst` subagent consulted for market/competitor analysis (visible in the output trace)

### Step 2 — Gap identification
- [ ] At least 3 dimensions show a real gap (not just the one mentioned in the prompt)
- [ ] Root causes distinguish *symptom* (low MRR) from *cause* (low trial→paid conversion, low TAM, wrong channel)

### Step 3 — Option generation
- [ ] At least 2 options generated (recommended: 3 — Stay / Pivot / Expand)
- [ ] Each option has: effort estimate, time-to-value, risk list
- [ ] `devils-advocate` subagent consulted to stress-test each option (counter-arguments visible)

### Step 4 — ADR for selected option
- [ ] After the user picks, skill generates an ADR with: Date, Status (Accepted), Context, Decision, Alternatives considered (others + why rejected), Consequences (Positive / Negative / Risks), Review date 30–90 days out
- [ ] ADR is saved either inline in LAUNCH_PLAN.md or as a separate file under `docs/adr/NNNN-*.md`

### Step 5 — Updated LAUNCH_PLAN.md
- [ ] `LAUNCH_PLAN.md` contains sections: Situation Analysis, Gap, Root Cause, Option A, Option B, ADR, Block (workstreams), Acceptance criteria
- [ ] Block / workstream list is actionable — not "improve onboarding" but "rewrite onboarding copy, A/B-test 3 variants, ship by 2026-05-15"
- [ ] Acceptance criteria are measurable — "trial→paid ≥ 15%" not "better conversion"

### Pivot markers
- [ ] If a pivot is selected, LAUNCH_PLAN.md includes explicit markers (`pivot`, `pivot decision`, `pivot-решение`) so future `/strategy` runs can detect the transition in git history

## /strategy — Scenario B: no baseline plan (edge case)

User runs `/strategy` on a project that has no LAUNCH_PLAN.md yet.

- [ ] Skill detects absence and asks: «LAUNCH_PLAN.md не найден. Создать с нуля или это новый проект (тогда /blueprint лучше)?»
- [ ] Does NOT silently create a plan from thin data — that's /blueprint's job
- [ ] If user insists: skill proceeds but warns the output is a stub, not a replanning outcome

## /strategy — Scenario C: re-run idempotency

User runs `/strategy` a second time on the same project after 30 days.

- [ ] Previous ADR is preserved — new ADR gets an incremented number (ADR-0002)
- [ ] LAUNCH_PLAN.md gets a new dated entry, old entries retained (append-only in spirit, even if file is rewritten)
- [ ] Review date from first ADR triggers a prompt: «ADR-0001 should be reviewed today — reaffirm or supersede?»

## /strategy — Scenario D: guard rails (what /strategy MUST NOT do)

- [ ] Does NOT write product code — this is plan-only
- [ ] Does NOT touch STRATEGIC_PLAN.md (that belongs to /blueprint) — reads it, references it, but does not rewrite
- [ ] Does NOT write PROJECT_ARCHITECTURE.md
- [ ] Does NOT skip the devils-advocate subagent when generating options (adversarial review is Step 3's contract)
- [ ] Does NOT auto-select an option — waits for explicit user choice before writing ADR

## Cross-reference with `check-skill-completeness.sh`

`/strategy` satisfies the three Quality Gate 2 requirements:

1. ✅ `skills/strategy/references/` exists (adr-template.md, gap-analysis.md)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/strategy`
3. ✅ `tests/fixtures/fixture-13-strategy/` exists with `idea.md`, `notes.md`, `expected-files.txt`, `expected-snapshot.json`

## /review status

- [ ] After LAUNCH_PLAN.md is regenerated, run `/review` on it
- [ ] Expected status: `PASSED` or `PASSED_WITH_WARNINGS`
- [ ] If `BLOCKED`, log the failing checks in Failures below

## Run manually

1. `cd tests/fixtures/fixture-13-strategy/`
2. `mkdir -p output && cd output`
3. Write a stub `LAUNCH_PLAN.md` with fake baseline (or create an empty file to simulate missing-plan scenario)
4. Start Claude Code on Opus, paste `idea.md` content, invoke `/strategy`
5. Answer clarifying questions; pick one option when prompted
6. `cd .. && python3 ../../verify_snapshot.py .`

Expected: `✅ fixture-13-strategy: PASSED`.

## Failures (fill in if any)

(empty unless the fixture fails — leave space for documenting regressions)
