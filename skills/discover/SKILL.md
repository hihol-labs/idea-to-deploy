---
name: discover
description: 'Product discovery phase — market analysis, user personas, competitor research, feature prioritization (MoSCoW + RICE). Outputs DISCOVERY.md ready for /blueprint.'
argument-hint: product idea or problem statement
license: MIT
allowed-tools: Read Write Edit Glob Grep
context: fork
agent: business-analyst
metadata:
  author: HiH-DimaN
  version: 1.17.0
  category: project-planning
  tags: [discovery, market-analysis, personas, prioritization, moscow, rice]
---


# Discover


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- исследуй рынок, анализ рынка, market analysis, market research
- целевая аудитория, кто пользователь, user personas, target audience
- конкуренты, конкурентный анализ, competitor analysis, competitive research
- приоритизация фич, какие фичи важнее, feature prioritization
- product discovery, discovery phase, discovery фаза
- что строить, что делать первым, what to build first
- TAM SAM SOM, value proposition, ценностное предложение
- проверь идею, валидация идеи, validate idea, idea validation

## Recommended model

**opus** — Deep market analysis, competitor research, and multi-dimensional prioritization benefit from Opus reasoning. Sonnet can do Lite mode (MoSCoW only, no RICE).

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 0: Detect model and select mode

- Opus → **Full mode** (default)
- Sonnet → **Lite mode** (MoSCoW only, no RICE, shorter competitor analysis)
- Haiku → refuse: "Этот скилл требует Sonnet или Opus."
- `--lite` flag → Lite mode (explicit override)
- `--full` flag → Full mode (explicit override)

### Step 1: Understand the idea

Collect from the user (ask if not provided):
- **What** — что делает продукт? (one sentence)
- **Who** — для кого? (target users)
- **Why** — какую проблему решает? (pain point)
- **How** — как монетизируется? (business model, can be "don't know yet")
- **Constraints** — бюджет, сроки, платформа, команда

### Step 2: Market Analysis

**2.1 — TAM / SAM / SOM estimation**

| Level | Description | Estimate |
|-------|-------------|----------|
| **TAM** (Total Addressable Market) | Everyone who could theoretically use this | ${estimate} |
| **SAM** (Serviceable Available Market) | Reachable with our channels/language/geo | ${estimate} |
| **SOM** (Serviceable Obtainable Market) | Realistic in Year 1 with our resources | ${estimate} |

Use public data, industry reports, comparable products for estimates. Rough is OK — the goal is order of magnitude, not precision.

**2.2 — Competitor Analysis (minimum 3, aim for 5)**

| Competitor | What they do | Pricing | Strengths | Weaknesses | Our differentiation |
|-----------|-------------|---------|-----------|------------|-------------------|

For each competitor: name, URL, pricing tier, key features, what they do poorly, and how our product would be different.

In **Lite mode**: minimum 3 competitors, brief analysis (1-2 sentences per cell).
In **Full mode**: aim for 5 competitors, deeper analysis with feature matrix.

### Step 3: User Personas

Create 2-4 personas:

```markdown
### Persona: {Name}
- **Role:** {who they are}
- **Pain:** {what frustrates them today}
- **Goal:** {what they want to achieve}
- **Current solution:** {what they use now, or nothing}
- **Willingness to pay:** {free / $X/mo / enterprise budget}
- **Discovery channel:** {how they'd find us}
```

In **Lite mode**: 2 personas.
In **Full mode**: 3-4 personas with Jobs-to-be-Done framing.

### Step 4: Value Proposition Canvas

| | Our Product |
|---|---|
| **Customer jobs** | {what they're trying to do} |
| **Pains** | {what makes the job hard} |
| **Gains** | {what would make them happy} |
| **Pain relievers** | {how we remove pains} |
| **Gain creators** | {how we create gains} |
| **Products & services** | {what we actually build} |

One sentence per cell. This feeds into the UTP (unique value proposition) in the strategic plan.

### Step 5: Feature Prioritization

**5.1 — Feature list**

Brainstorm all features based on personas and competitor gaps. Aim for 10-20 features.

**5.2 — MoSCoW prioritization**

| Feature | MoSCoW | Rationale |
|---------|--------|-----------|
| {feature} | **Must** / **Should** / **Could** / **Won't** | {why} |

Rules (same as in /blueprint Step 1.5):
- **Must** — MVP cannot ship without this
- **Should** — Important, but MVP can launch without it
- **Could** — Nice to have, only if time permits
- **Won't** — Explicitly out of scope for v1

**5.3 — RICE scoring (Full mode only)**

For each Must and Should feature:

| Feature | Reach (1-10) | Impact (1-5) | Confidence (%) | Effort (days) | RICE Score |
|---------|-------------|-------------|---------------|--------------|------------|
| {feature} | {R} | {I} | {C} | {E} | R×I×C/E |

Sort by RICE descending. Top features become MVP scope.

**5.4 — Validate with user**

Present all tables. Ask:
- "Согласны с приоритизацией? Хотите переместить что-то?"
- "Какие Must фичи вызывают сомнения?"
- Wait for confirmation before writing DISCOVERY.md.

### Step 6: Generate DISCOVERY.md

Write `DISCOVERY.md` in the project root with all outputs from Steps 2-5. Consult `references/discovery-template.md` for exact structure.

### Step 7: Integration with /blueprint

After DISCOVERY.md is created, tell the user:
- "DISCOVERY.md готов. Следующий шаг: `/blueprint` — он подхватит приоритизацию и создаст архитектуру + план реализации."
- The /blueprint skill's Step 1.5 will detect DISCOVERY.md and skip its own lightweight prioritization, using the deeper discovery output instead.


## Examples

### Example 1: SaaS idea
User says: "хочу сделать CRM для малого бизнеса"

Actions:
1. Clarify: ниша (какой бизнес?), бюджет, команда
2. TAM/SAM/SOM: CRM market $80B → SMB segment $12B → RU market $0.5B → first year $50K
3. Competitors: Bitrix24, AmoCRM, Salesforce, HubSpot, Pipedrive
4. Personas: Владелец малого бизнеса, Менеджер по продажам, Бухгалтер
5. Features: 15 features, MoSCoW + RICE prioritized
6. DISCOVERY.md generated

### Example 2: Telegram bot
User says: "бот для записи к парикмахеру"

Actions:
1. Clarify: Telegram vs WhatsApp, одна точка vs сеть, оплата онлайн?
2. TAM/SAM/SOM: beauty services booking → Telegram bots niche
3. Competitors: YCLIENTS, Booksy, simple Google Calendar bots
4. Personas: Парикмахер-одиночка, Администратор салона
5. Features: 12 features prioritized
6. DISCOVERY.md generated


## Rules

- Match the language of the user's request
- Be specific with numbers — rough estimates backed by reasoning are better than vague statements
- Don't overanalyze for small projects (Telegram bot doesn't need a 5-page TAM analysis)
- Scale depth to project complexity: side project → Lite, startup → Full
- DISCOVERY.md is a living document — user can re-run /discover to update it
- Do not generate code — only analysis and prioritization


## Self-validation

Before presenting DISCOVERY.md, verify:

**Minimum requirements:**
- At least 3 competitors analyzed
- At least 2 user personas defined
- MoSCoW table with at least 8 features categorized
- At least 3 Must features identified
- RICE table present (Full mode only, at least 5 features scored)
- TAM/SAM/SOM estimates present (can be rough)
- Value proposition canvas filled

If any requirement is not met, fix it before presenting. If you cannot meet it, warn:
"⚠️ DISCOVERY.md не соответствует минимальным требованиям: {reason}."


## Troubleshooting

**DISCOVERY.md is too shallow / generic.**
Re-run `/discover` with more specific constraints (niche, budget, geography). The skill scales depth to the input — vague input produces vague output. Adding "--full" forces Full mode even on Sonnet.

**Competitor analysis misses key players.**
The skill relies on the model's training data. If you know competitors the model missed, provide them explicitly: "конкуренты: X, Y, Z" — the skill will incorporate them into the analysis table.

**RICE scores seem arbitrary.**
RICE scoring is approximate by design — the model estimates Reach, Impact, Confidence, and Effort based on the persona and market context you provided. Treat RICE as a conversation starter, not a final verdict. Adjust scores manually after review.

**`/blueprint` does not pick up DISCOVERY.md.**
Ensure `DISCOVERY.md` is in the project root (not a subdirectory). `/blueprint` Step 1.5 scans the root for this file by name. If the file exists but is not detected, check for typos in the filename.
