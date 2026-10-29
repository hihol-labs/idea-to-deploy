---
name: bugfix
description: 'Finds the root cause of a bug and fixes it with the smallest change - reproduce, trace through stack traces, logs and git history, fix, add a regression test, run the suite. Use when something is broken, throws an error or a stack trace, fails silently, or worked before and does not now.'
argument-hint: error message, symptom, or issue description [--strict]
license: MIT
allowed-tools: Read Edit Glob Grep Bash
metadata:
  effort: medium
  side_effect: command-execution
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.110.0
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

### Step 0: Route - minimal or strict

From the project root, check whether the project declares the strict route - a line `itd-route: strict` or `itd-domain: data-sensitive` by itself, or the comment `<!-- itd:strict -->` / `<!-- itd:data-sensitive -->`:

```bash
( cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" && for f in CLAUDE.md .claude/CLAUDE.md AGENTS.md; do head -c 8192 "$f" 2>/dev/null; echo; done ) | grep -Eiq '^[[:space:]]*(itd-route:[[:space:]]*strict|itd-domain:[[:space:]]*data-sensitive)[[:space:]]*$|<!--[[:space:]]*itd:(strict|data-sensitive)[[:space:]]*-->' && echo strict || echo minimal
```

Take the **strict route** when it prints `strict`, when the arguments contain `--strict`, or when the task falls in a strict class of the global rules (ITD's own critical mechanisms, money, access, deploy, migrations, production data): read `references/strict.md` now and run its steps together with the steps below. Otherwise this is the **minimal path** - Steps 1-5, no scope freeze, no ROOT_CAUSE.md file. The `.itd/` directory alone does not make a project strict; the marker is described in the methodology's `docs/project-profiles.md`.

### Step 1: Reproduce
Understand the exact symptoms. Find the error in logs/output.

```
Expected: What should happen
Actual: What happens instead
Error: Exact error message or unexpected behavior
```

**Рекомендация (goal-driven fix, v1.5.0):** по возможности напиши **failing test**, который воспроизводит баг, **до** правки. Это превращает размытое «почини баг» в verifiable goal: «сделай, чтобы этот тест прошёл». Преимущества:

- Root cause становится явным (если тест не падает — ты ловишь не тот баг).
- Автоматический регрессионный тест (Step 5 выполняется за счёт Step 1).
- Проверка фикса — не ручная, а по зелёному тесту.

Когда failing test писать нельзя (UI glitch без testable API, race condition без reproduction harness, env-specific баг) — зафиксируй явный критерий успеха в виде текста: «после фикса `curl /health` возвращает 200», «форма сохраняет данные после повторного submit». Критерий должен быть бинарным.

Адаптировано из [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) principle #4 (Goal-Driven Execution).

### Step 2: Locate
Trace from the error back to the root cause:
- Read the stack trace / error message carefully
- Find the relevant code path
- Check recent changes: `git log --oneline -10` and `git diff HEAD~3`

If the bug is language- or stack-specific (Python pdb, JS source maps, Go race detector, Bash quoting, SQL query plans, frontend rendering), consult `references/debugging-patterns.md` for the idiomatic tools and common pitfalls of that ecosystem.

### Step 3: Find the cause
Explain WHY it fails, not just WHERE. Identify the incorrect assumption or state.

Before writing the fix, state the root cause in **one sentence with evidence** (the failing line, the log entry, the wrong value) in your report. This is **fail-closed**: if you cannot state it, the cause is not found yet - keep analysing (Step 2), do not patch the symptom. On the minimal path the sentence is enough; the strict route also records `ROOT_CAUSE.md` (`references/strict.md`).

### Step 4: Fix
Implement the minimal correct fix. Do not refactor surrounding code.

### Step 5: Regression test and the suite
Keep the failing test of Step 1, or add one now: it fails on the old code and passes on the fix. Then run the project's whole test suite, not only the new test.

```bash
pytest tests/test_affected_module.py -v   # the regression test: red before the fix, green after
pytest                                    # the whole suite
```

Where a test is impossible (Step 1), check the binary success criterion instead and say so.

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
2. Каждый исправленный баг должен сопровождаться регрессионным тестом, который падает на старом коде и проходит на новом. **Предпочтительно** написать failing test до фикса (Step 1), а не после (Step 5) — это превращает задачу в verifiable goal и делает root cause явным (goal-driven, v1.5.0)
3. Минимальный фикс — не рефактори окружающий код, не добавляй фичи, не меняй форматирование в незатронутых строках
4. Перед фиксом объясни WHY (Step 3) вслух — если не можешь сформулировать причину в одном предложении, root cause ещё не найден
5. Не меняй тесты, чтобы они проходили — если тест падает после фикса, значит тест проверял корректное поведение, а фикс сломал контракт

## Self-validation

Before reporting fix to user, verify:
- [ ] Root cause stated in one sentence with evidence (not just symptom fix); strict route: `ROOT_CAUSE.md` too
- [ ] Fix addresses the specific error/behavior described by user
- [ ] Tests pass after fix (the whole existing test suite was run)
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
