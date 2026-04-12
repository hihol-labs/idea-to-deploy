---
name: bugfix
description: 'Systematically debug an issue — find root cause and fix it. Traces errors through stack traces, logs, git history.'
argument-hint: error message, symptom, or issue description
license: MIT
allowed-tools: Read Edit Glob Grep Bash
paths: ["**/logs/**", "**/*.log"]
metadata:
  author: HiH-DimaN
  version: 1.4.0
  category: code-quality
  tags: [debugging, bugfix, troubleshooting]
---


# Bugfix

> **Note:** this skill was renamed from `/debug` to `/bugfix` in v1.4.0 to avoid a
> name collision with Claude Code's built-in `/debug` slash command. The built-in
> `/debug` has `disableModelInvocation: true` baked into the Claude Code binary,
> which prevented the model from invoking this skill via the Skill tool. Use
> `/bugfix` everywhere — the methodology is unchanged.


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- почини баг, не работает, ошибка, сломалось, крашит, падает
- exception, stack trace, стектрейс, traceback
- странное поведение, работало вчера сейчас нет, не понимаю что не так
- debug this, fix this bug, troubleshoot
- любая вставка error message, log fragment, panic
- симптом без явной ошибки (тихий сбой)

## Recommended model

**sonnet** — Reading logs, grepping, running tests, applying focused fixes. Sonnet handles this well; Opus only helps for very deep/cross-language root-cause analysis.

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 0: Auto-freeze scope (v1.17.0)

After identifying the target file/directory from $ARGUMENTS or the error context, automatically activate scope freeze:

```bash
# Write freeze state — limits edits to the bug's directory
echo "/path/to/bug/directory" > /tmp/claude-freeze-${CLAUDE_SESSION_ID:-default}.state
```

This prevents accidental edits outside the bug's scope during debugging. The freeze is cleared automatically when the skill completes (Step 5+). If the fix legitimately requires changes outside the frozen scope (e.g., a shared utility), the freeze hook will warn and ask for confirmation — which is correct behavior.

### Step 1: Reproduce
Understand the exact symptoms. Find the error in logs/output.

```
Expected: What should happen
Actual: What happens instead
Error: Exact error message or unexpected behavior
```

### Step 2: Locate
Trace from the error back to the root cause:
- Read the stack trace / error message carefully
- Find the relevant code path
- Check recent changes: `git log --oneline -10` and `git diff HEAD~3`

If the bug is language- or stack-specific (Python pdb, JS source maps, Go race detector, Bash quoting, SQL query plans, frontend rendering), consult `references/debugging-patterns.md` for the idiomatic tools and common pitfalls of that ecosystem.

### Step 3: Understand
Explain WHY it fails, not just WHERE. Identify the incorrect assumption or state.

### Step 4: Fix
Implement the minimal correct fix. Do not refactor surrounding code.

### Step 5: Verify
Run the relevant tests or reproduce steps to confirm the fix works.

```bash
# Run specific test
pytest tests/test_affected_module.py -v
# Or verify manually
curl http://localhost:8000/api/health
```

### Step 6: Prevent
If appropriate, add a test that would have caught this bug.

Report your findings at each step. If you hit a dead end, say so and try a different angle.

## Examples

### Example 1: Runtime error
User says: "TypeError: Cannot read properties of undefined (reading 'map')"

Actions:
1. Search codebase for `.map(` calls on potentially undefined variables
2. Check the component/function where the error occurs
3. Trace data flow — where does the undefined value come from?
4. Fix: add null check or fix the data source

Result: Identified that API response changed format, added optional chaining and default value.

### Example 2: Silent failure
User says: "Форма отправляется, но данные не сохраняются"

Actions:
1. Check network tab — is the API call made? What's the response?
2. Check backend logs — does the request reach the handler?
3. Check database — is the query executed?
4. Trace the gap between where data exists and where it disappears

Result: Found that validation middleware silently rejected the request due to missing field.

## Rules

1. Ищи root cause, а не маскируй симптомы — `try/except: pass`, подавление ошибок, fallback на default value без логирования запрещены как "фикс"
2. Каждый исправленный баг должен сопровождаться регрессионным тестом, который падает на старом коде и проходит на новом (Step 6 не опционален)
3. Минимальный фикс — не рефактори окружающий код, не добавляй фичи, не меняй форматирование в незатронутых строках
4. Перед фиксом объясни WHY (Step 3) вслух — если не можешь сформулировать причину в одном предложении, root cause ещё не найден
5. Не меняй тесты, чтобы они проходили — если тест падает после фикса, значит тест проверял корректное поведение, а фикс сломал контракт

## Self-validation

Before reporting fix to user, verify:
- [ ] Root cause identified and documented (not just symptom fix)
- [ ] Fix addresses the specific error/behavior described by user
- [ ] Tests pass after fix (run existing test suite)
- [ ] No new warnings or errors introduced
- [ ] Fix does not break other functionality (check related tests)
- [ ] If regression test needed, it has been added or recommended

## Troubleshooting

### Dead end: No error message
If there's no visible error:
1. Add logging at key points in the code path
2. Check browser console / server logs at DEBUG level
3. Use `git bisect` to find the commit that broke it

### Dead end: Error is in a dependency
If the bug is in node_modules or a library:
1. Check the library's GitHub issues for the exact error
2. Try upgrading/downgrading the dependency
3. Look for a workaround in the library's docs

### Fix breaks other tests
If your fix causes new failures:
1. The root cause is likely deeper — revert and re-analyze
2. Check if the failing tests relied on the buggy behavior
