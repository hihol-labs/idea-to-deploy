---
name: session-save
description: 'Save session context to project memory — what was done, decisions, blockers, next steps. Ensures continuity between sessions and flags parallel sessions via an active-session lockfile.'
argument-hint: (no arguments needed — gathers context automatically)
license: MIT
allowed-tools: Read Write Bash Glob Grep
metadata:
  author: HiH-DimaN
  version: 1.5.0
  category: workflow
  tags: [session, memory, context, persistence, continuity, parallel-sessions]
---

# Session Save


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- сохрани контекст, сохрани сессию, запомни что делали
- итоги сессии, конец сессии, закончили работу
- на сегодня всё, заканчиваем работу
- save session, save context, end of session
- wrap up session, session summary
- любой сигнал завершения сессии

**Автоматическое срабатывание (без явного запроса):**

Claude должен вызывать этот скилл самостоятельно в следующих ситуациях:
- После завершения значимой фичи (коммит + тесты пройдены)
- После принятия архитектурного или бизнес-решения в разговоре
- После исправления сложного бага (root cause найден и пофикшен)
- После завершения фазы в /kickstart (Phase 2 → Phase 3 и т.д.)
- После успешного `/review` который прошёл на 9+/10 и привёл к merge/PR
- Если сессия длится долго (5+ значимых действий без сохранения)
- После любого `git commit` в feature-ветке подготавливаемой к pull request

Это не заменяет явный вызов в конце сессии, а дополняет его — чтобы при резком закрытии терялся минимум контекста. **Каждый вызов также обновляет `.active-session.lock`** (см. Step 4.5) — чем чаще вызывается session-save, тем свежее lockfile и тем точнее работает parallel-session warning в pre-flight хуке других Claude-сессий.


## Recommended model

**sonnet** — Reading git log, summarizing session context, writing a file. No complex analysis needed.

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 1: Gather context

Collect all available information about the current session:

```bash
# Git context
git branch --show-current
git log --oneline -15
git diff --stat
git status --short
```

Also check:
- Current working directory (project path)
- Open plans in `.claude/plans/`
- Current task list (if any)
- What was discussed in the conversation (summarize from memory)

### Step 2: Summarize the session

Using the checklist from `references/session-save-checklist.md`, compose all 9 required fields:

1. **Дата** — today's date in ISO 8601
2. **Проект** — repo path + current branch
3. **Резюме** — 2-5 sentences about what was done (concrete, not vague)
4. **Ключевые решения** — decisions with rationale (WHY, not just WHAT)
5. **Изменённые файлы** — from `git diff --stat` or conversation context
6. **Блокеры** — anything preventing progress
7. **Следующие шаги** — actionable next actions
8. **Неочевидный контекст** — anything that can't be derived from code or git

Quality rules:
- Summaries must be specific: "Реализовал JWT-аутентификацию" not "работал над проектом"
- Decisions must include WHY: "Выбрали Redis, потому что уже используется для кеша"
- Next steps must be actionable: can start executing immediately without guessing
- Non-obvious context: verbal agreements, constraints not in code, user preferences

### Step 3: Write the session memory file

Determine the memory directory for the current project:

```bash
# The memory directory is at the Claude Code project memory path
# Usually: ~/.claude/projects/<project-hash>/memory/
```

Find the correct directory by checking which `~/.claude/projects/*/` directory corresponds to the current working directory.

Write the file with frontmatter:

```markdown
---
name: session_YYYY-MM-DD
description: "One-line summary for MEMORY.md index"
type: project
---

## Дата
YYYY-MM-DD

## Проект
/path/to/project (ветка: branch-name)

## Что сделано
- Item 1
- Item 2

## Ключевые решения
- **Decision** — rationale

## Изменённые файлы
- file1.py (новый / изменён)
- file2.py (изменён)

## Блокеры
- Blocker description (or "Нет блокеров")

## Следующие шаги
1. Step 1
2. Step 2

## Неочевидный контекст
- Context item
```

File naming:
- `session_YYYY-MM-DD.md` — primary format
- `session_YYYY-MM-DD_2.md` — if a file for today already exists

### Step 4: Update MEMORY.md

Add a line to `MEMORY.md` in the same memory directory:

```markdown
- [Сессия YYYY-MM-DD](session_YYYY-MM-DD.md) — краткое описание до 150 символов
```

If `MEMORY.md` doesn't exist, create it with the first entry.

### Step 4.5: Write active-session lockfile (v1.5.0)

Write `.active-session.lock` in the same memory directory. This file
lets the `pre-flight-check.sh` hook in OTHER parallel Claude sessions
know that someone is (or was very recently) working on this project —
so they don't unknowingly duplicate the work (see NeuroExpert 2026-04-11
incident: same kong.yml tech debt fixed twice in parallel).

Format (JSON, one line is fine):

```json
{
  "timestamp": 1712845200.0,
  "pid": 12345,
  "branch": "feat/session-save-lockfile",
  "project": "/home/user/projects/example",
  "note": "Saved session 2026-04-11: implemented feature X, blocker on Y"
}
```

Fields:
- `timestamp` — Unix epoch seconds (`date +%s` or Python `time.time()`).
  `pre-flight-check.sh` treats locks older than 10 minutes as stale.
- `pid` — current shell pid (`$$` in bash, `os.getpid()` in Python).
- `branch` — current git branch from `git branch --show-current`.
- `project` — absolute path to the project (current `pwd`).
- `note` — one-line summary, same as the MEMORY.md index entry.

Bash example:

```bash
cat > "$MEM_DIR/.active-session.lock" <<EOF
{
  "timestamp": $(date +%s),
  "pid": $$,
  "branch": "$(git branch --show-current 2>/dev/null || echo unknown)",
  "project": "$(pwd)",
  "note": "$SUMMARY"
}
EOF
```

Python example (for skills that use python):

```python
import json, os, subprocess, time
lock = mem_dir / ".active-session.lock"
branch = subprocess.run(
    ["git", "branch", "--show-current"], capture_output=True, text=True
).stdout.strip() or "unknown"
lock.write_text(json.dumps({
    "timestamp": time.time(),
    "pid": os.getpid(),
    "branch": branch,
    "project": str(Path.cwd()),
    "note": summary,
}))
```

The lockfile MUST be idempotent — it's rewritten on every `/session-save`
call, never appended. Stale locks self-expire (the pre-flight hook
ignores any lock older than 10 minutes).

### Step 5: Confirm to user

Tell the user:
- What file was created and where
- Brief summary of what was saved
- Remind that this context will be available in the next session

Example output:
```
Контекст сессии сохранён:
  Файл: ~/.claude/projects/.../memory/session_2026-04-09.md
  Резюме: JWT-аутентификация, Redis для сессий, 8 тестов
  Блокеры: нужен SMTP-сервер
  Следующие шаги: login endpoint, email verification

В следующей сессии я прочитаю этот файл и продолжу с того же места.
```


## Examples

### Example 1: End of feature development session

User says: «На сегодня всё, сохрани контекст»

Session context:
- Branch: `feature/payment-integration`
- 3 commits: added Stripe webhook handler, payment schemas, integration tests
- Decision: use Stripe Checkout instead of custom payment form (faster to implement)
- Blocker: need production Stripe API key from client
- Next: add subscription management, webhook signature verification

Actions:
1. Run `git log --oneline -15`, `git diff --stat`, `git status`
2. Compose session file with all 9 fields
3. Write `session_2026-04-09.md` to memory directory
4. Update MEMORY.md: `- [Сессия 2026-04-09](session_2026-04-09.md) — Stripe Checkout интеграция, блокер: API ключ`
5. Confirm to user

### Example 2: Planning session (no code changes)

User says: «Сохрани сессию, мы только обсуждали архитектуру»

Session context:
- No commits, no file changes
- Discussed microservices vs monolith — decided on modular monolith
- Drew data model on whiteboard (user described it verbally)
- Agreed on tech stack: FastAPI + Vue + PostgreSQL
- Next: create project with /kickstart

Actions:
1. Git shows no changes — that's OK
2. Compose session file focusing on decisions and non-obvious context
3. Emphasize: decisions (modular monolith rationale), verbal agreements (data model), chosen stack
4. Write file, update MEMORY.md
5. Confirm — note that even without code, the decisions are preserved


## Troubleshooting

### Memory directory not found
If `~/.claude/projects/` doesn't have a matching directory for the current project:
1. Create the memory directory manually
2. Or write to a `session_YYYY-MM-DD.md` file in the project root as a fallback
3. Inform the user about the fallback location

### MEMORY.md conflicts
If MEMORY.md already has an entry for today's date (from a previous save):
1. Don't overwrite — append the new entry
2. Name the file `session_YYYY-MM-DD_2.md` (or `_3.md`, etc.)

### No git repository
If the current directory is not a git repo:
1. Skip git-based context gathering
2. Focus on conversation context: what was discussed, decisions made, next steps
3. Note in the file that no git data was available

### Large session with many changes
If there are 50+ changed files or 20+ commits:
1. Group changes by area/module rather than listing every file
2. Focus on the most significant changes
3. Use `git diff --stat` summary rather than individual files
