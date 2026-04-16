---
name: strategy
description: 'Strategic replanning for existing projects — analyze current state, update LAUNCH_PLAN.md, create ADRs for pivot decisions. For NEW projects use /blueprint instead.'
argument-hint: project path, LAUNCH_PLAN.md, or "from scratch"
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash(git:*) Bash(ls:*) Agent(business-analyst) Agent(devils-advocate)
context: fork
metadata:
  author: HiH-DimaN
  version: 1.19.0
  category: project-planning
  tags: [strategy, replanning, pivot, launch-plan, adr, kpi]
---

# Strategy

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- пересмотри стратегию, обнови стратегию, стратегический пересмотр
- обнови launch plan, пересмотри план запуска, переоценка проекта
- проект не работает как планировали, нужен pivot
- что изменить в проекте, куда двигаться дальше
- обнови roadmap проекта, пересмотри roadmap
- KPI gap, не достигаем целей, метрики не растут
- strategic review, replan project, update launch plan
- pivot decision, project reassessment, strategic pivot
- что делать с проектом, проект буксует

## Recommended model

**opus** — Strategic analysis, multi-factor evaluation, and ADR generation benefit from deep reasoning. Sonnet can do a lightweight review.

## Instructions

### Step 0: Context assessment

1. Check for existing strategic documents:
   ```bash
   ls -la LAUNCH_PLAN.md BACKLOG.md ROADMAP*.md STRATEGIC_PLAN.md DISCOVERY.md PRD.md 2>/dev/null
   ```
2. Read `LAUNCH_PLAN.md` (or equivalent) if it exists
3. Check git history: `git log --oneline -20 --all`
4. Ask the user: "Что изменилось? Какой контекст привёл к необходимости пересмотра?"

### Step 1: Situation analysis

Analyze the current state across 5 dimensions:

| Dimension | Questions to answer |
|---|---|
| **Market** | Изменился ли рынок? Новые конкуренты? Сдвиг в спросе? |
| **Product** | Какие фичи работают? Какие не используются? Что просят пользователи? |
| **Metrics** | KPI vs targets — где gap? Retention? Revenue? Growth rate? |
| **Resources** | Бюджет, команда, время — что изменилось? |
| **External** | Регуляторные изменения? Платформенные изменения? Сезонность? |

Use `business-analyst` subagent for market/competitor analysis if the user provides enough context.

### Step 2: Gap identification

For each dimension:
- **Current state** — where are we now (с числами)
- **Target state** — where we planned to be (из LAUNCH_PLAN.md)
- **Gap** — delta
- **Root cause** — why the gap exists

Format as table:
```markdown
| Dimension | Current | Target | Gap | Root Cause |
|---|---|---|---|---|
| MRR | 50K ₽ | 200K ₽ | -75% | Низкая конверсия trial→paid |
```

### Step 3: Option generation

Generate 2-3 strategic options:

**Option A: Stay the course** — minor adjustments, fast (1-2 weeks)
**Option B: Pivot** — significant direction change, medium (1-3 months)
**Option C: Expand** — add revenue stream, medium-high (2-4 months)

Use `devils-advocate` subagent to stress-test each option.

### Step 4: ADR for selected option

After user selects, generate ADR:
```markdown
## ADR-NNN: [Decision Title]
**Date:** YYYY-MM-DD
**Status:** Accepted
**Context:** [What changed]
**Decision:** [Selected option]
**Alternatives considered:** [Others and why rejected]
**Consequences:** Positive / Negative / Risks
**Review date:** [30-90 days out]
```

### Step 5: Update LAUNCH_PLAN.md

Rewrite or create with blocks:
```markdown
# LAUNCH PLAN — [Project Name]
**Last reviewed:** YYYY-MM-DD
**Target:** [Primary KPI + deadline]

## Block 1: [Name] (~N days)
**Goal:** [Measurable outcome]
**Acceptance criteria:**
- [ ] Criterion 1
**Priority:** P0/P1/P2
```

### Step 6: Update BACKLOG.md

Reprioritize or create from LAUNCH_PLAN blocks:
```markdown
## P0 — Must do
## P1 — Should do
## P2 — Nice to have
## Icebox (deprioritized)
```

### Step 7: Report

Summarize: selected option, key changes, ADR, next review date, first actionable step.


## Examples

### Example 1: Revenue target miss
User: "Проект не достигает целей по выручке"
→ Read LAUNCH_PLAN → gap analysis → 3 options → devil's advocate → user picks → ADR → updated plan

### Example 2: Post-launch reassessment
User: "Запустились 3 месяца назад, что работает что нет"
→ No LAUNCH_PLAN → create from scratch → situation analysis → focus on winning features


## Self-validation

Before presenting results, verify:
- [ ] All 5 dimensions analyzed (market, product, metrics, resources, external)
- [ ] Gap table has concrete numbers (not vague)
- [ ] At least 2 strategic options generated with pros/cons
- [ ] ADR follows standard format with review date
- [ ] LAUNCH_PLAN.md blocks have measurable acceptance criteria
- [ ] BACKLOG.md priorities align with selected strategy
- [ ] Next review date set (30-90 days)


## Troubleshooting

### No LAUNCH_PLAN.md exists
Create one from scratch using the situation analysis. Focus on what the user describes verbally — decisions and direction are more valuable than historical metrics you don't have.

### User can't provide concrete metrics
Use qualitative assessment: "growing/flat/declining" with approximate ratios. Better to have directional data than wait for perfect numbers.

### User wants to skip gap analysis and jump to solution
Push back gently: "Без анализа мы можем выбрать неправильное направление. Давай потратим 5 минут на оценку текущего состояния." If they insist, document the skip in the ADR.

### Multiple stakeholders with conflicting views
Document each perspective in the situation analysis. Present options that address different stakeholder priorities. Let the decision-maker choose.


## Rules

- **Never recommend a strategy without gap analysis first.**
- **Always generate multiple options.** Single-option = advocacy, not analysis.
- **Concrete numbers over vague assessments.**
- **ADR is mandatory for any pivot decision.**
- **Review date is mandatory.** Strategy without re-evaluation trigger becomes stale.
- **Match the user's language** for all generated artifacts.
