---
name: refactor
description: Refactor code for better readability, maintainability, and structure. Preserves behavior while improving quality. TRIGGER when user says "отрефактори", "упрости код", "refactor this", "слишком сложный код", or when code has deep nesting, long functions, duplication, or poor naming that hinders understanding.
argument-hint: file, function, or area to refactor
license: MIT
effort: medium
metadata:
  author: HiH-DimaN
  version: 1.0.0
  category: code-quality
  tags: [refactoring, clean-code, readability]
---


# Refactor

## Instructions

### Step 1: Analyze
Read the code, understand its purpose and ALL callers/usages.

```bash
# Find all usages before changing anything
grep -r "functionName" src/
```

### Step 2: Identify problems
- Long functions (>30 lines) — extract meaningful sub-functions
- Deep nesting (>3 levels) — use early returns, guard clauses
- Duplicate code — extract shared logic
- Poor naming — rename for clarity
- God objects/functions — split by responsibility
- Complex conditionals — simplify or extract to named functions

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
