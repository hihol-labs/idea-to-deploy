---
name: explain
description: 'Explain how code works — architecture, data flow, key decisions. Uses ASCII diagrams and step-by-step walkthroughs.'
argument-hint: file, function, module, or concept
license: MIT
allowed-tools: Read Glob Grep
metadata:
  author: HiH-DimaN
  version: 1.3.1
  category: code-understanding
  tags: [code-review, architecture, learning]
---


# Explain


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- объясни код, как это работает, как устроен, что делает эта функция
- что здесь происходит, разбери код, расскажи про этот модуль
- walkthrough, разбери этот файл, explain this, how does this work
- multi-file/multi-module exploration
- любой вопрос о существующем коде, не о новом

## Recommended model

**haiku** — Read-only walkthrough. Haiku is fast enough for most files. Use Sonnet only for very complex cross-module flows (>10 files).

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 1: Purpose
What does this code do and why does it exist? (1-2 sentences)

### Step 2: How it works
Step-by-step walkthrough of the logic flow. Reference specific line numbers.

### Step 3: Key concepts
Explain any patterns, algorithms, or domain concepts used.

### Step 4: Data flow
What goes in, what comes out, what gets transformed along the way.

```
Input → [Step A] → intermediate → [Step B] → Output
```

Use ASCII diagrams for architecture or complex flows:
```
Client → API Gateway → Auth Middleware → Handler → DB
                                            ↓
                                        Response
```

### Step 5: Dependencies
What does this code depend on, and what depends on it?

### Step 6: Gotchas
Non-obvious behavior, edge cases, or common mistakes.

Adapt the explanation depth to the complexity of the code.

## Examples

### Example 1: Explain a function
User says: "объясни функцию processPayment в src/services/billing.ts"

Result:
- Purpose: Processes a payment via YuKassa, updates order status
- Flow: validate amount → create YuKassa payment → poll status → update DB
- Gotcha: YuKassa webhook may arrive before polling returns — handled by idempotency key

### Example 2: Explain architecture
User says: "как работает авторизация в проекте"

Result:
- ASCII diagram of auth flow (login → token → middleware → protected route)
- Key files involved with line references
- Why JWT + refresh token was chosen over sessions

## Rules

1. READ-ONLY — скилл /explain никогда не редактирует код, только читает и объясняет
2. Используй ASCII-диаграммы для архитектуры и data flow — визуальная схема обязательна для любого объяснения, затрагивающего >2 файлов
3. Отвечай на заданный вопрос, а не пересказывай весь файл — если пользователь спросил про одну функцию, не объясняй весь модуль
4. Подстраивай глубину под уровень пользователя: если спрашивает "что такое middleware" — объясняй с основ, если спрашивает "почему здесь двойная буферизация" — не объясняй что такое буфер
5. Ссылайся на конкретные номера строк (`file.py:42-58`), а не на абстрактные "в этом блоке"


## Self-validation

Before presenting explanation to user, verify:
- [ ] Explanation covers all files/functions the user asked about
- [ ] At least one ASCII diagram included for non-trivial flows
- [ ] Technical accuracy verified against actual code (not assumptions)
- [ ] Complexity level matches user's expertise (from memory/context)

## Troubleshooting

### Code is too large to explain at once
Break into layers: "Let me explain the API layer first, then the service layer, then the data layer."

### Code has no comments and unclear naming
Focus on WHAT it does (trace inputs/outputs), not WHY (that requires domain knowledge — ask the user).
