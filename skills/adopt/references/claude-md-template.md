<!--
Canonical CLAUDE.md block for projects adopted into the idea-to-deploy methodology.

/adopt skill appends everything between the BEGIN and END markers to the
project's CLAUDE.md (or writes the whole file if CLAUDE.md is absent).
Re-running /adopt detects the marker and does nothing — idempotent.

To re-adopt after a methodology version bump, delete the block between the
markers manually and re-run /adopt.
-->

<!-- idea-to-deploy:begin v{{VERSION}} -->

# Idea-to-Deploy methodology rules

> Adopted into this project on {{ADOPTED_AT}} via `/adopt`.
> These rules route Claude Code to the right skill automatically and keep
> commits, tests, and documentation honest. Full methodology:
> https://github.com/hihol-labs/idea-to-deploy

## ⚠️ Hard rule (violation = bug)

### Step 0 — Pre-flight check (before any tool call)

Before the first action, check repo state and context so you do not duplicate
work done in parallel Claude sessions:

1. `git log --oneline -10` + `git status --short` — recent commits? uncommitted WIP?
2. `MEMORY.md` in the project memory dir (usually auto-loaded by `pre-flight-check.sh`;
   if not, read it explicitly).
3. `.active-session.lock` in memory dir — a fresh lockfile means a parallel
   Claude session is running: stop and read `session_*.md` before acting.

**If a recent commit already contains keywords from your task → the task is
done. Read the commit instead of redoing the work.**

### Step 1 — Choose a task-level skill (before any tool call)

Evaluate the task **once**, not before every Bash/Edit/Write. If a skill fits,
**invoke it via the Skill tool FIRST**, before Read/Edit/Bash/Write.

**Creating a new project** — `/project` (router → `/kickstart` · `/blueprint` · `/guide`).

**Working on existing code** — `/task` (daily-work router):
- «close tech debt X / refactor Y» → `/task` → `/refactor`
- «stack trace, fix the bug in Z» → `/task` → `/bugfix` (or `/bugfix` directly if the hook matched)
- «update README / document API» → `/task` → `/doc`
- «add tests / no coverage» → `/task` → `/test`
- «endpoint is slow / find bottleneck» → `/task` → `/perf`
- «check security / OWASP» → `/task` → `/security-audit`
- «check dependencies / CVE» → `/task` → `/deps-audit`
- «apply migration / schema change» → `/task` → `/migrate`
- «prepare for prod / rate limit / runbook» → `/task` → `/harden`
- «set up Terraform / Helm / K8s» → `/task` → `/infra`
- «explain this code» → `/task` → `/explain`
- «review this PR» → `/task` → `/review`

**Deploying to production** — `/deploy`.

**Strategic replanning** — `/strategy`. **Advisory-only analysis** — `/advisor`.

**Always after any code** — `/review` and `/test`:
- Committing more than 2 files without a prior `/review` is **forbidden**.
- Writing new code without a follow-up `/test` is **forbidden**.

**End of any significant work block** — `/session-save`:
- After a feature, bug-fix, architectural decision, or `/kickstart` phase.
- After a `/review` of 9+/10 that led to merge/PR.
- After a long session (5+ significant actions without a save).

### Step 2 — Do not reflexively dismiss skill hints

The hook `check-tool-skill.sh` reminds you before every Bash/Edit/Write (rate-limited).
If the reminder appears — **re-evaluate task-level once**, then keep working.
A formal dismissal ("skills don't match") is a methodology bypass = a bug.

### Exceptions (no skill needed)

- One-line fixes (typo, rename, trivial change)
- Pure research queries («show where X is», «explain what Y does»)
- When the user explicitly said «without a skill» / «just do it»

## 4 принципа аккуратного кода

> Адаптировано из [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills)
> (Forrest Chang, ~54K stars), систематизировавшего [пост Andrej Karpathy](https://x.com/karpathy)
> о типичных ошибках LLM-агентов. Применяется поверх скилл-роутинга выше.

1. **Думай перед кодом.** Если задача допускает несколько интерпретаций — озвучь их и спроси. Если что-то неясно — остановись и уточни, не строй молчаливых допущений. Указывай на противоречия в требованиях, предлагай альтернативы, возражай там, где стоило бы.
2. **Простота прежде всего.** Минимум кода под задачу. Никаких абстракций ради однократного использования, никаких фич «на будущее», никаких обработок сценариев, которые не могут произойти. Если решение получается на 1000 строк там, где хватило бы 100 — это сигнал переделать.
3. **Хирургические правки.** Меняй только то, что просили. Не рефакторь соседний код, не удаляй чужой dead code без запроса, не меняй форматирование в незатронутых строках, сохраняй существующий стиль. Каждая изменённая строка должна трассироваться к запросу пользователя.
4. **Целеориентированное выполнение.** Превращай размытую задачу в verifiable goal. Для багов: сначала напиши failing test, который воспроизводит проблему, потом делай так, чтобы он прошёл. LLM сильны в итерациях до конкретной цели — дай её явно.

## Project-specific context

Add anything here that Claude Code should know permanently about this project:
tech stack, deploy target, conventions, non-obvious constraints, runbook URLs,
important contacts. Everything above this section is methodology-canonical and
updated by future `/adopt` re-runs; everything below is yours to edit freely.

<!-- idea-to-deploy:end -->
