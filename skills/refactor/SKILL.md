---
name: refactor
description: 'Refactor code for readability and maintainability while preserving behavior. Uses Fowler-style catalog (Extract Function, Replace Conditional with Polymorphism, etc.). TRIGGER when user says "отрефактори", "упрости код", "перепиши понятнее", "refactor this", or when code has deep nesting/duplication/long functions. No feature changes. See `## Trigger phrases` in body for full list.'
argument-hint: file, function, or area to refactor
license: MIT
metadata:
  author: HiH-DimaN
  version: 1.2.0
  category: code-quality
  tags: [refactoring, clean-code, readability]
---


# Refactor


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- отрефактори, рефактор, упрости код, перепиши понятнее
- вынеси в функцию, убери дублирование, длинная функция
- глубокая вложенность, code smell, слишком сложный код
- улучши читаемость, refactor this, clean up
- code that has poor naming, magic numbers, god class

## Instructions

### Step 1: Analyze
Read the code, understand its purpose and ALL callers/usages.

```bash
# Find all usages before changing anything
grep -r "functionName" src/
```

### Step 2: Identify problems and pick a refactoring
- Long functions (>30 lines) — extract meaningful sub-functions
- Deep nesting (>3 levels) — use early returns, guard clauses
- Duplicate code — extract shared logic
- Poor naming — rename for clarity
- God objects/functions — split by responsibility
- Complex conditionals — simplify or extract to named functions

For each smell, **consult `references/refactoring-catalog.md`** — it contains a Fowler-style catalog with 12 specific refactorings (Extract Function, Replace Nested Conditional with Guard Clauses, Introduce Parameter Object, Extract Class, Replace Conditional with Polymorphism, Introduce Null Object, Split Function, Pull Up Method, Replace Method with Method Object, Replace with Return Value, etc.). Each entry has when-to-apply, before/after code, and pitfalls. Use that as a menu — don't invent your own technique when a documented one fits.

### Step 3: Refactor
Apply changes following these rules:
- Preserve ALL existing behavior — no functional changes
- Make small, incremental changes
- Keep the existing code style and patterns of the project
- Do NOT add unnecessary abstractions for one-time code

### Step 4: Verify
Run existing tests to confirm nothing broke.

```bash
pytest tests/ -v          # Python
npm test                  # JS/TS
go test ./...             # Go
```

Explain what you changed and why for each significant change.

## Examples

### Example 1: Extract guard clauses
User says: "упрости эту функцию, слишком много вложенности"

Before:
```python
def process(order):
    if order:
        if order.status == "pending":
            if order.items:
                # 20 lines of logic
```

After:
```python
def process(order):
    if not order:
        return
    if order.status != "pending":
        return
    if not order.items:
        return
    # 20 lines of logic (no nesting)
```

### Example 2: Extract duplicate logic
User says: "отрефактори src/api/ — много копипасты"

Actions:
1. Find repeated patterns across handlers
2. Extract shared validation/formatting into utils
3. Keep handler-specific logic in handlers

## Troubleshooting

### Tests fail after refactoring
Revert. The refactoring changed behavior. Re-read the code more carefully — there may be a side effect you missed.

### Not sure if behavior is preserved
If there are no tests, write tests FIRST (use /test skill), then refactor.

### Refactoring scope is too large
Break it into smaller PRs. Refactor one module/file at a time.
