---
name: debug
description: Systematically debug an issue — find root cause and fix it. Traces errors through stack traces, logs, and git history. TRIGGER when user says "почини баг", "не работает", "ошибка", "сломалось", "крашит", "падает", "exception", "stack trace", "стектрейс", "странное поведение", "работало вчера, сейчас нет", "не понимаю что не так", "debug this", pastes any error message, stack trace, log fragment, or describes any unexpected behavior. ALWAYS use this instead of ad-hoc tool calls (Bash/Read/Grep) — even if the bug looks small, /debug enforces root-cause analysis instead of guessing.
argument-hint: error message, symptom, or issue description
license: MIT
effort: medium
paths: ["**/logs/**", "**/*.log"]
metadata:
  author: HiH-DimaN
  version: 1.0.0
  category: code-quality
  tags: [debugging, bugfix, troubleshooting]
---


# Debug

## Instructions

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
