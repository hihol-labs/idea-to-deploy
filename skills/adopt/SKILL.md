---
name: adopt
description: 'Adopts an existing project into the idea-to-deploy methodology with one pointer block - CLAUDE.md on Claude Code, AGENTS.md on Codex - that names the installed methodology and the test, lint and build commands of the project; the strict route adds the itd-route marker, .itd/ contracts, state, a first unit and the merge-gate profile. Use when a repository should start using the methodology, when a project has no idea-to-deploy block, or to re-check an adopted one. Idempotent; never rewrites user content or reverse-engineers plan documents.'
argument-hint: optional - "strict" for the strict route (contracts, state, first unit, merge gate, project hooks)
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash Skill
metadata:
  effort: low
  side_effect: local-write
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.110.0
  category: methodology
  tags: [adopt, legacy, onboarding, methodology, bootstrap, initialization]
---

# Adopt

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. The hook `hooks/check-skills.sh`
also uses this list - keep them in sync.

- адоптируй, адоптируй проект, адоптируй методологию
- подключи методологию, подключи idea-to-deploy, подключи к idea-to-deploy
- включи методологию, примени методологию, bootstrap methodology
- добавь CLAUDE.md, добавь хуки в проект, настрой проект под методологию
- этот проект без методологии, в проекте нет CLAUDE.md
- onboard this project, onboard existing project, adopt methodology
- enable methodology, legacy project, adopt legacy

## Recommended model

**sonnet** - `/adopt` is bounded, declarative writing through one helper. No architectural reasoning.

## Instructions

You onboard an existing project into `idea-to-deploy` **minimally**: the rules, hooks, skills and tools live in the
installation, the project gets a pointer to them and its own commands. Never rewrite the user's code or content, never
invent plan documents, never touch user-level host configuration.

### Step 0: Route - minimal or strict

From the project root, check whether the project already declares the strict route - a line `itd-route: strict` or
`itd-domain: data-sensitive` by itself, or the comment `<!-- itd:strict -->` / `<!-- itd:data-sensitive -->`:

```bash
( cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" && for f in CLAUDE.md .claude/CLAUDE.md AGENTS.md; do head -c 8192 "$f" 2>/dev/null; echo; done ) | grep -Eiq '^[[:space:]]*(itd-route:[[:space:]]*strict|itd-domain:[[:space:]]*data-sensitive)[[:space:]]*$|<!--[[:space:]]*itd:(strict|data-sensitive)[[:space:]]*-->' && echo strict || echo minimal
```

Take the **strict route** only by an explicit choice: the arguments contain `strict` / `--strict`, the user asked for
contracts, a first unit, the merge gate or project hooks, or the command above prints `strict` (the owner chose it
earlier). Then read `references/strict.md` now and follow it instead of Steps 2-3 below. Otherwise this is the
**minimal path**: Steps 1-4, one write at most - the pointer block. The marker is described in the methodology's
`docs/project-profiles.md`.

### Step 1: Discover

1. **Git root.** `git rev-parse --show-toplevel`. Not a git repository -> tell the user «`/adopt` работает в
   git-репозиториях. Создай репо (`git init`) или перейди в существующий.» and stop.
2. **Host.** Claude Code -> `HOST=claude` (entry file `CLAUDE.md`). Codex (`CODEX_HOME` or `PLUGIN_ROOT` set, or the
   skill was invoked from Codex) -> `HOST=codex` (entry file `AGENTS.md`); read `references/codex-adoption.md` for the
   Codex specifics. Never create both entry files for symmetry. Below, `<entry>` is the entry file of the host.
3. **Existing state** (for the report): the entry file present / absent; any marker `<!-- idea-to-deploy:begin `
   (any version, including the old `v1.20` rules block) means **already adopted**. An old `v1.20` block is a heavy
   rules copy: offer (do not force) to replace it with the current pointer by deleting the old block and re-running.
4. **Helper plan** (read-only; the helper refuses the methodology repository itself, outside a git root, and prints
   WHY/FIX on every refusal):

   ```bash
   HOST=claude  # codex on Codex
   PROJECT_ROOT="$(git rev-parse --show-toplevel)" || exit 1
   AD="skills/adopt/scripts"; [ -f "$AD/itd_adopt.py" ] || AD="$HOME/.claude/skills/adopt/scripts"
   SHD="skills/_shared"; [ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/skills/_shared"
   sh "$SHD/itd_py.sh" "$AD/itd_adopt.py" --project "$PROJECT_ROOT" --host "$HOST" --plan
   ```

   Each shell call starts fresh: repeat these lines in every later helper call (Step 3, `references/strict.md`).
   The helper also refuses an entry file that is a symlink or not a regular file.

   The `ADOPT PLAN` line names the entry file action (`create | append-guarded-block | skip-marker-present`) and
   `commands` - the test, lint and build commands found in `justfile`, `Makefile`, `package.json`, `pyproject.toml`
   / `requirements*.txt`, `go.mod` and `Cargo.toml` (first source per kind wins). The helper writes only fixed command
   strings (`just test`, `npm run lint`, `pytest`, ...), never text copied from the repository.

### Step 2: Show the plan and ask

```
/adopt plan (минимальный путь):
  - <ABS>/<entry>: [create | append pointer block | skip (already adopted)]
  - команды проекта: тесты `<cmd>`, линт `<cmd>`, сборка `<cmd>` | не найдены
  - больше ничего: .itd/, .itd-memory/, хуки проекта и merge-гейт - только строгий маршрут (`/adopt strict`)
Записать? [да/нет]
```

When everything is a skip (already adopted), say so and go to Step 4.

### Step 3: Apply on yes

Only after an explicit yes, rerun the same helper command with `--apply --approved` instead of `--plan`. It writes the
pointer block from `references/claude-md-template.md` (Codex: `agents-md-pointer.md`) with the discovered commands:
a new file, or the block appended after a blank line - never a change to the content above it. Report its
`ADOPTION: PASS` line. A non-zero exit prints WHY/FIX and writes nothing - show it, do not hand-edit around it.

On «нет» or anything ambiguous - write nothing and report «адоптация не выполнена по решению пользователя».

### Step 4: Report

```
Adoption (minimal):
  - <ABS>/<entry>   (created | appended | unchanged)
  - команды проекта   (<list> | не найдены - добавь их в блок вручную)
Методология работает из установки; строгий маршрут (контракты, состояние, первый юнит, merge-гейт, хуки проекта) -
`/adopt strict`. Plan-документы - `/strategy` (есть код и история) или `/blueprint` (с нуля), по запросу.
```

Do not invoke `/session-save` on the minimal path - one pointer block is not a milestone. Do not chain to
`/strategy` or `/blueprint` unless the user asks.

## Idempotency

- The entry file: any `<!-- idea-to-deploy:begin ` marker makes a minimal re-run a no-op - the file stays
  byte-identical, the commands in an existing block are not refreshed (delete the block and re-run to refresh).
- A strict run on a minimally adopted project adds only the strict paragraph inside the existing block, once.

## What `/adopt` does NOT do

- **Does NOT** reverse-engineer plan documents (`STRATEGIC_PLAN.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`) from code:
  a plausible but wrong plan poisons trust. Plans come from `/strategy` or `/blueprint`.
- **Does NOT** modify user-level configuration (`~/.claude/settings.json`, `~/.codex/`), product source, or install
  dependencies.
- **Does NOT** commit or perform any git write - the user decides when to commit the new block.
- **Does NOT** rewrite an existing entry file that already contains the idea-to-deploy block.
- **Does NOT** call `/session-save` unconditionally - only the strict route saves continuity, at its end.

## Rules

1. Never rewrite user content - the entry file is append-only, guarded by the marker.
2. Never touch user-level configuration; adoption is project-scoped.
3. Never commit.
4. Never run on the methodology repository itself (the helper's self-reference guard).
5. Always show the plan before writing; `--apply --approved` only after an explicit yes.
6. Always print the final report, even when everything was a no-op.
7. Strict steps only by an explicit strict choice (Step 0).

## Self-validation

- [ ] Step 0 printed the route; the strict route was taken only by an explicit choice
- [ ] The `ADOPT PLAN` was shown before any write, and `--apply --approved` ran only after a yes
- [ ] `$PROJECT_ROOT/CLAUDE.md` (Codex: `AGENTS.md`) contains exactly one `<!-- idea-to-deploy:begin ` pointer marker,
      no copied rules
- [ ] On the minimal path nothing else was written: no `.itd/`, no `.itd-memory/`, no `.claude/settings.json`
- [ ] The discovered commands in the report match the `ADOPT PLAN` line; none were invented
- [ ] `/session-save` was not invoked on the minimal path

## Examples

### Example 1 - Minimal adoption of a FastAPI project

```
User: адоптируй этот проект
Claude: [/adopt] Step 0: minimal
  ADOPT PLAN {"CLAUDE.md": "create", "commands": {"lint": "ruff check .", "test": "pytest"}, "mode": "minimal", ...}
  /adopt plan (минимальный путь):
    - /home/user/work/shop-api/CLAUDE.md: create
    - команды проекта: тесты `pytest`, линт `ruff check .`
    - больше ничего: .itd/, .itd-memory/, хуки и merge-гейт - только `/adopt strict`
  Записать? [да/нет]
User: да
  ADOPTION: PASS {"CLAUDE.md": "created", "commands": {...}, "mode": "minimal", ...}
  Готово: блок-указатель записан. Строгий маршрут - `/adopt strict`.
```

### Example 2 - Re-run on an adopted project

```
User: адоптируй проект ещё раз
Claude: [/adopt] Step 0: minimal
  ADOPT PLAN {"CLAUDE.md": "skip-marker-present", ...}
  Проект уже адоптирован, писать нечего. CLAUDE.md не изменен.
```

## Troubleshooting

### CLAUDE.md is very large

Append still works - the block is about 15 lines. But a file that size enters context on every turn: offer the
router split from `references/strict.md` (S4) on request; it moves content only after explicit approval.

### Strict marker beyond the first 8 KB

A strict run refuses (`refuse-marker-beyond-8kb`, nothing written) when the strict paragraph would land past the
first 8 KB of the entry file - Step 0 of `/bugfix`, `/test` and `/refactor` reads only that window. Put the line
`itd-route: strict` by itself near the top of the file (or split it), then rerun.

### User wants to re-adopt after a version bump

The block is a pointer, not a copy of the rules (INSTALL-OWNED-1): a methodology update reaches every project by
updating the installation (`/plugin update` or `scripts/sync-to-active.sh`, Codex plugin refresh). An old `v1.20`
rules block or copied `.itd/*.py` tools are reported by `skills/_shared/itd_projects_doctor.py`; replacing the block is
offered, never forced.
