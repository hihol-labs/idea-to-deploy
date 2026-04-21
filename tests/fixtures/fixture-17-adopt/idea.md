# Fixture 17 — /adopt

Onboarding an existing legacy project into the idea-to-deploy methodology.

## Context

The user has an existing Python project (FastAPI backend + Vue frontend + PostgreSQL) that predates `idea-to-deploy`. It has its own `CLAUDE.md` with project-specific instructions (not methodology-aware), a `.claude/settings.json` with custom hooks, and no `MEMORY.md`. The user wants to **adopt** the methodology — register its hooks, append the methodology block to `CLAUDE.md` preserving existing content, bootstrap the project memory dir — **without** overwriting what's already there and **without** reverse-engineering plan documents.

`/adopt` is a **minimal-write** skill: exactly three writes (CLAUDE.md append, .claude/settings.json merge, memory dir bootstrap sentinel) plus one voice-chain question at the end.

## Input prompt

У меня есть существующий проект на FastAPI + Vue, его писал другой разработчик. Там уже есть свой CLAUDE.md с инструкциями по стилю и .claude/settings.json с хуками линтера. Подключи `idea-to-deploy` к нему так, чтобы ничего не сломать — добавь наши хуки, добавь блок методологии в CLAUDE.md (не трогая существующее), подними memory dir. Потом можно будет запустить `/strategy` или `/blueprint`, но пока только adopt.

## Expected behavior

- Refuses inside the `idea-to-deploy` methodology repo itself (self-reference guard)
- Requires a git repo; exits gracefully if not
- Shows an idempotent plan (create / append / skip per artefact) and asks for confirmation before writing
- Writes exactly three targets: `CLAUDE.md` (append with marker), `.claude/settings.json` (merge hooks array), memory dir bootstrap (sentinel `session_YYYY-MM-DD.md` + `MEMORY.md` + `.active-session.lock`)
- Preserves the user's pre-existing `CLAUDE.md` content above the marker and all existing `.claude/settings.json` keys and hooks
- After the writes: voice-chains a single question — «Сгенерировать план документов? (/strategy для существующего — обновит план-документы / /blueprint с нуля / пропустить)»
- Second run on the same project: all three writes become "skip" (idempotent), re-prompts only the voice-chain question

## Fixture status

`active` — primary artefact (`CLAUDE.md` in output dir) is file-structured and fits verify_snapshot.py. Memory-dir writes land outside the output dir (`~/.claude/projects/...`) and are validated via notes.md manual checklist, not via `expected-snapshot.json`.
