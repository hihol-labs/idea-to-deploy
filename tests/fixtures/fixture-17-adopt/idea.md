# Fixture 17 — /adopt

Onboarding an existing legacy project into the idea-to-deploy methodology.

## Context

The user has an existing Python project (FastAPI backend + Vue frontend + PostgreSQL) that predates `idea-to-deploy`. It has its own `CLAUDE.md` with project-specific instructions (not methodology-aware), a `.claude/settings.json` with custom hooks, a `pyproject.toml` with pytest and ruff, and a `justfile` with a `test` recipe. The user wants to **adopt** the methodology without overwriting what's already there and **without** reverse-engineering plan documents.

`/adopt` is a **minimal-write** skill (ITD-PLAN-S9): by default one write - the pointer block in `CLAUDE.md` with the discovered project commands. Contracts, state, project hooks and the merge gate come only on the strict route (`/adopt strict`).

## Input prompt

У меня есть существующий проект на FastAPI + Vue, его писал другой разработчик. Там уже есть свой CLAUDE.md с инструкциями по стилю и .claude/settings.json с хуками линтера. Подключи `idea-to-deploy` к нему так, чтобы ничего не сломать - добавь блок методологии в CLAUDE.md, не трогая существующее. Потом можно будет запустить `/strategy` или `/blueprint`, но пока только adopt.

## Expected behavior

- Refuses inside the `idea-to-deploy` methodology repo itself (self-reference guard)
- Requires a git repo; exits gracefully if not
- Shows the `ADOPT PLAN` (create / append / skip, the discovered commands) and asks for confirmation before writing
- Writes exactly one target: the pointer block appended to `CLAUDE.md` with the marker, listing `just test` and `ruff check .`
- Preserves the user's pre-existing `CLAUDE.md` content above the marker; `.claude/settings.json` is not touched
- Does not invoke `/session-save` and does not chain to `/strategy` or `/blueprint` unless asked
- Second run on the same project: "skip-marker-present", no write

## Fixture status

`active` — primary artefact (`CLAUDE.md` in output dir) is file-structured and fits verify_snapshot.py. Strict-route writes (`.itd/`, `.itd-memory/`, `.claude/settings.json`) are exercised by `tests/verify_task_adopt_route.py` and the notes.md checklist, not via `expected-snapshot.json`.
