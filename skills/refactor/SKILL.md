---
name: refactor
description: 'Restructures code for readability and maintainability without changing its behavior - Fowler-catalog refactorings in small steps, with the test suite green before and after; no feature changes. Use when code is hard to read or change: long functions, deep nesting, duplication, poor names, magic numbers, god classes.'
argument-hint: file, function, or area to refactor [--strict]
license: MIT
allowed-tools: Read Edit Glob Grep Bash
metadata:
  effort: medium
  side_effect: local-write
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.110.0
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

## Recommended model

**sonnet** — Mechanical transformation guided by the Fowler catalog in references/. Sonnet handles all cataloged refactorings.

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 0: Route - minimal or strict

From the project root, check whether the project declares the strict route - a line `itd-route: strict` or `itd-domain: data-sensitive` by itself, or the comment `<!-- itd:strict -->` / `<!-- itd:data-sensitive -->`:

```bash
( cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" && for f in CLAUDE.md .claude/CLAUDE.md AGENTS.md; do head -c 8192 "$f" 2>/dev/null; echo; done ) | grep -Eiq '^[[:space:]]*(itd-route:[[:space:]]*strict|itd-domain:[[:space:]]*data-sensitive)[[:space:]]*$|<!--[[:space:]]*itd:(strict|data-sensitive)[[:space:]]*-->' && echo strict || echo minimal
```

Take the **strict route** when it prints `strict`, when the arguments contain `--strict`, or when the task falls in a strict class of the global rules (ITD's own critical mechanisms, money, access, deploy, migrations, production data): read `references/strict.md` now - it freezes the edit scope to the refactoring target before Step 1 and lifts the freeze after Step 4. Otherwise this is the **minimal path** - Steps 1-4 without a scope freeze. The `.itd/` directory alone does not make a project strict; the marker is described in the methodology's `docs/project-profiles.md`.

### Step 0.5: Optional worktree isolation for a large file-only refactor (v1.4.0)

For a **large, file-only** refactor (multi-file rename / extract / move, no behaviour change), you may use **git-worktree isolation**: do the whole refactor in a throwaway worktree, verify green there, and merge back only on success — the main working tree is never touched until then. This is **opt-in**, not the default.

Use it when the user asks for an isolated/worktree refactor, or offer it for a large file-only job. For a small in-place edit, work in place (with the scope freeze on the strict route) — do not spin a worktree for a two-line change.

**Read `references/worktree-isolation.md`** for the full procedure and the hook path-assumption audit (all 24 hooks are worktree-safe — repo-root detection finds `.claude-plugin/plugin.json` in the worktree, sentinels are session-scoped). The shape:

1. Preconditions (git repo, worktree-capable git, ideally a clean tree). If ANY fails → **fall back to the in-place refactor (Step 0 route) and say why in one line**. Never hard-fail the refactor because a worktree could not be created (harness best-effort invariant — worktree isolation transports the intent, it is not the contract).
2. `git worktree add <path> -b refactor/<name>` off HEAD; make ALL edits against paths under the worktree.
3. Run the project's tests **inside the worktree** (the green baseline is the gate). On green, **commit inside the worktree** (`git -C <wt> add -A && git -C <wt> commit`) — that commit is what step 4 merges back; without it the merge is a silent no-op that loses the work.
4. On green → `git merge --ff-only` (or `--no-ff`) the branch into the working branch, then `git worktree remove` + delete the branch. **If the merge conflicts** (the working branch diverged and overlaps), `git merge --abort` and drop to the in-place refactor, keeping the branch/worktree so the verified work is not lost. On red (nothing committed) → `git worktree remove --force` and discard; the main tree stays pristine.

Behaviour-changing refactors are out of scope for this mode (they need `/test` first, Rule 2) — worktree isolation is only for structure-preserving, file-only work.

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

## Rules

1. Поведение должно быть сохранено — рефакторинг не меняет функциональность. Если после рефакторинга тесты падают, рефакторинг неправильный, а не тесты
2. Прогони тесты ДО рефакторинга (green baseline) и ПОСЛЕ — если тестов нет, сначала напиши их через /test, потом рефактори
3. Используй каталог Фаулера из `references/refactoring-catalog.md` — не изобретай свои техники, когда задокументированная подходит
4. Не добавляй абстракции "на будущее" — Extract Interface для одной реализации, Strategy для одного варианта, Factory для одного типа запрещены
5. Маленькие инкрементальные шаги — каждый шаг компилируется и проходит тесты. Не переписывай весь файл за один Edit


## Self-validation

Before presenting refactoring to user, verify:
- [ ] All existing tests still pass after refactoring
- [ ] No behavior change — only structure/readability improved
- [ ] Each refactoring step maps to a named Fowler pattern
- [ ] No new dependencies introduced without justification
- [ ] Code is measurably simpler (fewer lines, less nesting, clearer naming)

## Troubleshooting

### Tests fail after refactoring
Revert. The refactoring changed behavior. Re-read the code more carefully — there may be a side effect you missed.

### Not sure if behavior is preserved
If there are no tests, write tests FIRST (use /test skill), then refactor.

### Refactoring scope is too large
Break it into smaller PRs. Refactor one module/file at a time.
