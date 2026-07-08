---
name: session-save
description: 'Save session context to project memory — what was done, decisions, blockers, next steps. Ensures continuity between sessions and flags parallel sessions via an active-session lockfile.'
argument-hint: optional — brief note to append to the session summary
license: MIT
allowed-tools: Read Write Bash Glob Grep
metadata:
  effort: low
  side_effect: memory-write
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.8.0
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

Память — костяк непрерывности (v1.35.0): чекпоинт делается при КАЖДОЙ значимой
смене состояния, а не только в конце сессии. Дешёвый инкрементальный чекпоинт
(обнови/допиши текущий `session_YYYY-MM-DD.md` + lockfile) предпочтительнее
редкого большого — при резком закрытии теряется минимум контекста.

Claude должен вызывать этот скилл самостоятельно в следующих ситуациях:
- После завершения значимой фичи (коммит + тесты пройдены)
- После принятия архитектурного или бизнес-решения в разговоре
- После исправления сложного бага (root cause найден и пофикшен)
- После завершения фазы в /kickstart (Phase 2 → Phase 3 и т.д.)
- После завершения подшага многошаговой задачи (закрыт пункт плана/roadmap)
- После verified-юнита долгой цели `/goal` (юнит закрыт — инкрементальный чекпоинт)
- После успешного `/review` который прошёл на 9+/10 и привёл к merge/PR
- После применения миграции к тест/прод-БД или иной необратимой мутации данных
- Перед рискованной или необратимой операцией — чекпоинт ДО неё как фиксация точки возврата (деплой / force-push / массовый ре-пост)
- После отправки внешнего артефакта (письмо/отчёт/PR-описание ушли адресату)
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
- `.itd-memory/GOAL.json` — активная долгая цель (`/goal`): срез генерирует
  репортёр харнеса, вставь вывод в session-файл как есть (v1.45.0):
  `GT="skills/goal/scripts"; [ -f "$GT/itd_goal_report.py" ] || GT="$HOME/.claude/skills/goal/scripts"; python3 "$GT/itd_goal_report.py" --goal .itd-memory/GOAL.json`
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

> **Memory hygiene (periodic) — approval-diff mode only (v1.52.0).** When `MEMORY.md`
> or the memory dir grows large or accumulates duplicate/stale facts, run the
> `anthropic-skills:consolidate-memory` skill to merge duplicates, fix stale entries,
> and prune the index. `MEMORY.md` and the session files are **durable state** — the
> consolidation follows the data-sensitive gate (global CLAUDE.md, harness best-effort
> invariant): **model the changes read-only first → show the before/after diff → get
> explicit human approval → only then write.** Never a blind rewrite, never an
> out-of-band/async writer (ADR-001 async-memory note): a merge that silently drops a
> fact is worse than a slightly stale index. Concretely — before applying, surface the
> proposed deletions/merges as a diff (which facts are being removed or rewritten, and
> why), and wait for the user's go. idea-to-deploy does not build its own consolidation
> engine; it delegates to that skill, but the approval-diff gate is ITD's, not optional.

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

### Step 4.6: Cost snapshot (v1.31.0 — New-SDLC port)

Attach a token/cost snapshot to the session memory so OpEx is *visible* at wrap-up —
context engineering is a financial lever, and a fleet of agents needs cost-awareness,
not just correctness. **No new collector:** read the ledger that `hooks/cost-tracker.sh`
already maintains for this session (shipped since v1.18.0, hard-ceiling ASK since
v1.30.0). This is lightweight accounting, **not** an observability platform (see
ADR-001 — we delegate runtime to existing hooks, we don't build our own).

```bash
tmpd="$(python3 -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || echo /tmp)"
ledger="$(ls -1t /tmp/claude-cost-${CLAUDE_SESSION_ID:-*}.json "$tmpd"/claude-cost-${CLAUDE_SESSION_ID:-*}.json 2>/dev/null | head -1)"
if [ -n "$ledger" ] && [ -f "$ledger" ]; then
  echo "— Cost snapshot —"; cat "$ledger"
else
  echo "cost ledger not found (cost-tracker.sh inactive this session)"
fi
```

If a ledger exists, add a **`## Стоимость сессии`** line to the session memory file
(estimated tokens + blended USD, and whether the soft/hard ceiling was hit). If
`ctx-stats` is available (context-mode installed), note its context-savings figure on
the same line — the two together are the "where to see cost" picture. If no ledger
exists, this step is a soft no-op — never block `/session-save` on it.

### Step 4.7: Auto-sync methodology (v1.18.1)

If the current project IS the idea-to-deploy methodology repo (detected by
`.claude-plugin/plugin.json` existence), run the sync script to propagate
any changes to the active Claude Code install:

```bash
if [ -f ".claude-plugin/plugin.json" ]; then
  bash scripts/sync-to-active.sh
fi
```

This prevents the recurring bug where new skills/agents/hooks are added to
the repo but not copied to `~/.claude/` (see: /discover not registered,
business-analyst missing from global agents, 6 hooks missing after v1.18.0).

**For non-methodology projects:** This step is a no-op (the guard clause
skips it).

### Step 4.7b: Methodology-memory auto-push (v1.64.0)

If `~/.claude/methodology-memory/` is a git repo (it has a private remote —
`idea-to-deploy-memory`), commit and push any changes so every checkpoint of
the methodology memory is backed up off-machine:

```bash
MM="$HOME/.claude/methodology-memory"
if [ -d "$MM/.git" ]; then
  git -C "$MM" add -A
  git -C "$MM" diff --cached --quiet || \
    git -C "$MM" commit -q -m "memory: session checkpoint $(date +%F)"
  if git -C "$MM" remote get-url origin >/dev/null 2>&1; then
    git -C "$MM" push -q origin HEAD || echo "memory push failed (offline?) — commit is local, will push next time"
  fi
fi
```

Rules:
- **Best-effort** — a network/auth failure NEVER blocks `/session-save`;
  report one line and move on (the local commit still preserves the state).
- **Scope guard** — only methodology notes (`*.md` + index) live in this repo.
  Never move project/business memory there, and never write secret VALUES into
  memory files (env-var names are fine — the standing egress guard applies;
  the remote must stay private).
- No repo / no remote → soft no-op (e.g. a machine where the memory dir was
  never initialized).

### Step 4.8: Branch-finish decision (v1.21 — PFO port)

If this session is wrapping up work on a **feature branch** (not `main`/`master`) and the branch looks done or is being parked, record an explicit branch-finish decision so no branch is left in an ambiguous state. Scaffold `BRANCH_FINISH.md` from `docs/templates/BRANCH_FINISH.md` and fill:

- **Mode** — one of `PR` | `merge` | `keep` | `discard` (an explicit choice, never implicit).
- **Verification** — *fresh* evidence collected now (re-run the relevant check at finish time; do not reuse evidence from an earlier step).
- **Cleanup** — keep the branch/worktree for PR feedback unless `merge` or `discard` is explicitly selected.

Hard rule: **never discard work without explicit typed confirmation** from the user. If the mode is unclear, default to `keep` and ask. On `main`/`master`, or mid-task (branch not finishing), this step is a soft no-op.

### Step 4.9: Skill-coverage self-audit (v1.23.0 — Layer 2)

Before confirming, run a self-audit so a session never quietly skips a mandatory skill (the exact failure this layer exists to catch). Two cheap inputs:

1. **Bypass ledger** — every `SKILL_BYPASS:` recorded this session by `check-tool-skill.sh` (`/tmp/claude-skill-ledger-<session>.jsonl`).
2. **Skill sentinels** — which skills actually ran (`/tmp/claude-<skill>-done-*`), cross-checked against the *risk signals* in the work you did this session.

```bash
tmpd="$(python3 -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || echo /tmp)"
ledger="$(ls -1t /tmp/claude-skill-ledger-*.jsonl "$tmpd"/claude-skill-ledger-*.jsonl 2>/dev/null | head -1)"
echo "— SKILL_BYPASS за сессию —"
if [ -n "$ledger" ]; then echo "записей: $(wc -l < "$ledger")"; tail -n 20 "$ledger"; else echo "нет"; fi
echo "— sentinel'ы скиллов (свежие/этой сессии) —"
for s in review test migrate security-audit; do
  if ls /tmp/claude-$s-done-* "$tmpd"/claude-$s-done-* >/dev/null 2>&1; then echo "  $s: есть"; else echo "  $s: НЕТ"; fi
done
```

Then reason over it against what the session actually changed (use `git diff --stat` / the committed diff):

- Touched a **migration/schema**? → `/migrate` **and** `/test` sentinels must be present.
- Touched **payments/auth/secrets**? → `/security-audit` must be present.
- Committed a **multi-file** change? → `/review` must be present.
- Added **brand-new source files**? → `/test` must be present.

For any risk signal whose sentinel is missing, add a **`## Самоаудит скиллов`** subsection to the session memory file naming the gap (e.g. "миграция была, /test не вызван — долг") and surface it to the user in one line. Bypasses with a recorded reason are fine — an explicit choice, not a miss; just report how many there were. This audit is advisory: it never blocks `/session-save`. Its value is making a skipped gate impossible to miss at session end — the same gate `hooks/check-dod-before-commit.sh` enforces at commit time.

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


## Rules

1. Все 9 обязательных полей должны присутствовать — пропуск любого поля делает session-save невалидным. Если данных нет (например, нет блокеров), пиши "Нет блокеров", а не пропускай секцию
2. Конкретика, не абстракции — "Реализовал JWT refresh token с ротацией" вместо "работал над авторизацией". "Выбрали Redis потому что уже в стеке" вместо "выбрали кеш"
3. Следующие шаги должны быть actionable — можно начать выполнять немедленно без дополнительного контекста. "Добавить POST /api/auth/reset-password по спеке из PRD §3.2" вместо "продолжить работу над auth"
4. Lockfile `.active-session.lock` обновляется при КАЖДОМ вызове — идемпотентно перезаписывается, никогда не append. Timestamp должен быть свежим (`date +%s`)
5. Неочевидный контекст — записывай устные договорённости, ограничения не из кода, решения принятые в разговоре. Если этого поля нет или оно пустое, следующая сессия потеряет контекст, который невозможно восстановить из git


## Self-validation

Before confirming session save, verify:
- [ ] All 9 required fields present (date, project, summary, decisions, files, blockers, next steps, non-obvious context)
- [ ] Summary is specific (not "worked on project")
- [ ] Next steps are actionable (can start immediately without guessing)
- [ ] MEMORY.md index updated with new entry
- [ ] .active-session.lock written with fresh timestamp

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
