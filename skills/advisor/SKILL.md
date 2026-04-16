---
name: advisor
description: 'Advisory/consulting mode — analysis and recommendations only, no code changes. Uses business-analyst and devils-advocate subagents for multi-perspective evaluation.'
argument-hint: question, comparison, or strategic decision
license: MIT
allowed-tools: Read Glob Grep Agent(business-analyst) Agent(devils-advocate)
context: fork
metadata:
  author: HiH-DimaN
  version: 1.19.0
  category: project-planning
  tags: [advisor, consulting, analysis, strategy, recommendations]
---

# Advisor

## Trigger phrases

- посоветуй, дай совет, стратегический совет
- консалтинг, консультация, что ты думаешь о стратегии
- оцени идею, сравни варианты, какой вариант лучше
- анализ без кода, только анализ, без изменений в код
- advisor mode, give advice, strategic advice
- consulting mode, just analyze, analysis only
- compare options, which option is better
- помоги выбрать направление, какую нишу выбрать

## Recommended model

**opus** — Multi-perspective analysis and strategic reasoning require deep thinking. Sonnet can handle simple comparisons.

## Instructions

### CRITICAL CONSTRAINT: No code modifications

This skill operates in **read-only analysis mode**. You MUST NOT:
- Use Write or Edit tools
- Create or modify any files
- Run commands that change state (no `git commit`, no `docker`, no `npm install`)

You MAY:
- Read files (Read, Glob, Grep)
- Run read-only commands (`git log`, `cat`, `ls`)
- Use Agent subagents for analysis

If the user asks to implement recommendations after the analysis, say:
> "Рекомендации готовы. Для реализации используй подходящий скилл: /kickstart (новый проект), /strategy (обновление плана), /task (конкретная задача)."

### Step 1: Understand the question

Clarify what the user wants advice on:
- **Comparison:** "A vs B vs C — что лучше?"
- **Evaluation:** "Стоит ли делать X?"
- **Direction:** "Куда двигаться дальше?"
- **Risk assessment:** "Какие риски у подхода X?"

If the question is vague, ask ONE clarifying question (not more):
> "Уточни: ты сравниваешь конкретные варианты или ищешь новые идеи?"

### Step 2: Context gathering (read-only)

Read relevant project files if they exist:
- `LAUNCH_PLAN.md`, `BACKLOG.md`, `PRD.md`, `STRATEGIC_PLAN.md`
- `DISCOVERY.md`, `ARCHITECTURE.md`
- `docs/competitive-analysis.md`
- `package.json` / `pyproject.toml` (tech stack context)

Check market context if the user provides enough info for the `business-analyst` subagent.

### Step 3: Multi-perspective analysis

**Always use at least 2 perspectives:**

1. **Business Analyst perspective** (via `business-analyst` subagent):
   - Market opportunity size
   - Competitive positioning
   - Revenue potential
   - User demand signals

2. **Devil's Advocate perspective** (via `devils-advocate` subagent):
   - What could go wrong?
   - Hidden assumptions being made?
   - What would a skeptic say?
   - Counter-arguments to the dominant option

### Step 4: Structured output

Format the analysis as:

```markdown
## Анализ: [Question/Topic]

### Контекст
[Brief summary of what was analyzed]

### Вариант A: [Name]
**Pros:**
- Pro 1
- Pro 2

**Cons:**
- Con 1
- Con 2

**Риски:**
- Risk 1 (вероятность: high/medium/low, impact: high/medium/low)

**Оценка:** [X/10]

### Вариант B: [Name]
[Same structure]

### Сравнительная таблица
| Критерий | Вариант A | Вариант B | Вариант C |
|---|---|---|---|
| Стоимость | $$$ | $ | $$ |
| Время | 3 мес | 1 мес | 2 мес |
| Риск | Высокий | Низкий | Средний |
| Потенциал | Высокий | Средний | Средний |

### Рекомендация
[Clear recommendation with reasoning]

### Что нужно для решения
[If more info needed, list what exactly]
```

### Step 5: Confirm before any implementation

After presenting analysis, ALWAYS ask:
> "Это анализ. Хочешь реализовать рекомендацию? Тогда используй соответствующий скилл."

Do NOT proceed to implementation without explicit user request.


## Examples

### Example 1: Compare project directions
User: "Посоветуй: маркетплейс для клиник vs SaaS для записи vs Telegram-бот"

Actions:
1. Clarify: budget, timeline, team size
2. Business analyst: market size for each, competition level
3. Devil's advocate: challenges each option, finds hidden risks
4. Structured comparison table
5. Recommendation with reasoning

### Example 2: Evaluate a pivot
User: "Стоит ли переходить с B2C на B2B?"

Actions:
1. Read current LAUNCH_PLAN.md for B2C metrics
2. Business analyst: B2B market analysis
3. Devil's advocate: challenges B2B assumption
4. Pros/cons of staying B2C vs pivoting B2B
5. Recommendation with conditions ("если X, то B2B; иначе оставайся B2C")

### Example 3: Technology choice
User: "Redis vs Memcached vs in-memory для кеширования"

Actions:
1. Read project tech stack (what's already used?)
2. Compare on: performance, complexity, ops burden, cost
3. Devil's advocate: "а нужен ли вам кеш вообще?"
4. Recommendation aligned with existing stack


## Self-validation

Before presenting analysis, verify:
- [ ] No Write/Edit tools used during this skill
- [ ] At least 2 perspectives consulted (business-analyst, devils-advocate)
- [ ] Each option has explicit pros, cons, and risks
- [ ] Comparison table included for multi-option questions
- [ ] Clear recommendation with reasoning (not "it depends" without specifics)
- [ ] Implementation deferred to appropriate skill


## Troubleshooting

### User asks to implement recommendations immediately
Redirect: "Анализ завершён. Для реализации используй /strategy (обновление плана), /kickstart (новый проект), или /task (конкретная задача)." Do NOT start implementing.

### Not enough context for meaningful analysis
Ask the user for specifics: current metrics, constraints, timeline. If they can't provide them, state assumptions explicitly and mark the analysis as "preliminary — refine when data available."

### Business-analyst or devils-advocate subagent unavailable
Fall back to manual multi-perspective analysis. Structure your response with explicit "Perspective 1: Optimist" and "Perspective 2: Skeptic" sections.

### User wants a definitive answer, not options
Provide your strongest recommendation but always include at least one alternative with conditions: "Рекомендую A. Но если [condition], то B будет лучше."


## Rules

- **NEVER modify files.** This is analysis-only mode. No Write, no Edit, no Bash that changes state.
- **Always use multiple perspectives.** Single-viewpoint advice is opinion, not analysis.
- **Quantify when possible.** "Market is ~$2B" not "market is large".
- **Acknowledge uncertainty.** "При условии что..." not false confidence.
- **Recommend, don't decide.** The user makes the final call.
- **Match the user's language** for all output.
