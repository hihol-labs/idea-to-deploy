---
name: adopt
description: 'Adopt legacy project into idea-to-deploy methodology — add CLAUDE.md, register project-level hooks in .claude/settings.json, bootstrap memory dir. Detects product type and suggests a matching starter/golden-path for the /blueprint chain. Idempotent. No reverse-engineering of plan docs. Voice-chain to /strategy or /blueprint for plan generation.'
argument-hint: optional — "skip-chain" to disable the final /strategy · /blueprint voice-chain
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash(git:*) Bash(ls:*) Bash(cat:*) Bash(mkdir:*) Bash(python3:*) Bash(node:*) Bash(go:*) Bash(cargo:*) Bash(make:*) Skill
metadata:
  effort: medium
  side_effect: local-write
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.22.0
  category: methodology
  tags: [adopt, legacy, onboarding, methodology, bootstrap, initialization]
---

# Adopt

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- адоптируй, адоптируй проект, адоптируй методологию
- подключи методологию, подключи idea-to-deploy, подключи к idea-to-deploy
- включи методологию, примени методологию, bootstrap methodology
- добавь CLAUDE.md, добавь хуки в проект, настрой проект под методологию
- этот проект без методологии, в проекте нет CLAUDE.md
- onboard this project, onboard existing project, adopt methodology
- enable methodology, legacy project, adopt legacy

## Recommended model

**sonnet** — `/adopt` is bounded, declarative writing (template + merge) plus a short voice-chain. No architectural reasoning. Sonnet is plenty.

Set via `/model sonnet` before invoking this skill if Opus is active.

## Instructions

You are the adoption operator for `idea-to-deploy`. Your job is to **minimally** onboard an existing legacy project into the methodology — without rewriting the user's code, without hallucinating plan documents, and without modifying `~/.claude/settings.json` (user-level).

You produce exactly **three writes**, plus up to three **optional recommended** ones the user may decline — the `.itd/` contract scaffold (Step 3.5), an example test when the project has none (Step 3.6), a runnability check via the init validator (Step 3.7) — plus one voice-chain question. Nothing more.

### Step 0: Safety & discovery

Before writing anything:

1. **Resolve `$PROJECT_ROOT`.** Must be a git repo. Run `git rev-parse --show-toplevel`. If it fails (not a git repo) → tell the user «`/adopt` работает в git-репозиториях. Создай репо (`git init`) или перейди в существующий.» and exit.

2. **Self-reference guard.** If `$PROJECT_ROOT/.claude-plugin/plugin.json` exists AND contains `"name": "idea-to-deploy"` → **refuse**. Tell the user «Ты внутри самой методологии `idea-to-deploy`. `/adopt` адоптирует ДРУГИЕ проекты в методологию, не саму методологию. Выход.» and exit.

3. **Detect existing state** (for idempotent reporting):
   - `CLAUDE.md` in root → present / absent.
   - If present → contains marker `<!-- idea-to-deploy:begin v1.20 -->` → **already adopted**.
   - `.claude/settings.json` → present / absent; if present, parse JSON and check whether our hook scripts already appear by `command` path.
   - Memory dir for current project (see `hooks/pre-flight-check.sh` lines 89-127 for resolution logic — `~/.claude/projects/-<dashed-cwd>/memory/`).

4. **Detect plugin dir** (where our hooks live). Try in order:
   - `$CLAUDE_PLUGIN_DIR` env var, if set.
   - `~/.claude/plugins/idea-to-deploy/hooks/` (default install path).
   - Grep `~/.claude/plugins/*/plugin.json` for `"name": "idea-to-deploy"` and resolve sibling `hooks/`.
   - Fallback: `~/.claude/hooks/` (legacy install via `sync-to-active.sh`). Tell the user the resolved path so they can correct it if wrong.

5. **Detect tech stack** (best-effort, only for the sentinel session-save — NOT for writing into CLAUDE.md). Glob manifest files: `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `composer.json`, `Gemfile`, `pom.xml`, `build.gradle`, `Dockerfile`, `docker-compose*.yml`, `.github/workflows/*.yml`. Report to user as «detected stack, проверь вручную».

6. **Detect product type → starter / golden-path** (read-only analysis, for the
   `/blueprint` chain only — NOT written into `CLAUDE.md`). From the manifests
   and structure detected in 0.5, classify the project into one product type and
   map it to a reference starter (`starters/<id>/STARTER.json`) and golden-path
   (`golden-paths/<id>.json`). Heuristics (first match wins):

   | Signal | productType | starter | golden-path |
   |---|---|---|---|
   | `aiogram` in deps | `messaging_bot` | `bot-aiogram` | `messaging-bot-sales` |
   | Telegram Mini App SDK / `@twa-dev` + frontend | `mini_app` | `mini-app-vue` | `mini-app-loyalty` |
   | FastAPI backend **and** Vue/Vite frontend | `saas` | `saas-fastapi-vue` | `saas-subscriptions` |
   | FastAPI/backend manifest, no frontend | `api_service` | `api-fastapi` | `api-service-booking` |
   | Vite/static frontend only, no backend | `landing_page` | `landing-vite` | `landing-leadgen` |
   | none of the above | `unknown` | — | — |

   This is a **hint**, not a rewrite: report it and pass it into the `/blueprint`
   chain (Step 6) so the plan references a known starter instead of inventing a
   scaffold. If `unknown`, skip the hint silently. Always state «определено
   эвристически по манифестам, проверь вручную».

7. **Show plan to user** before any write:

   ```
   /adopt plan:
     - CLAUDE.md:              [create | append methodology block | skip (already adopted)]
     - .claude/settings.json:  [create | merge hooks | skip (already registered)]
     - memory dir:             [create + sentinel /session-save | skip (already bootstrapped)]
     - .itd/ + .itd-memory/:   [scaffold (recommended) | skip (already present)] — опционально, скажи «без .itd» чтобы пропустить
     - example test:           [create + run (recommended — тестов не найдено) | skip (тесты уже есть)] — «без example test» чтобы пропустить
     - runnability check:      [run init validator (recommended) | skip] — «без проверки запускаемости» чтобы пропустить
     - Plugin hooks dir:       <resolved path>
     - Detected stack:         <stack or "none">
     - Detected product type:  <type → starter `<id>`, golden-path `<id>` | "unknown">
   Proceed? [yes/no]
   ```

   If everything is already adopted (all three skips) → say so and jump to Step 5 (voice-chain question, user may still want plan docs).

### Step 1: Write / merge CLAUDE.md

Read the canonical template from `references/claude-md-template.md`. Fill in two placeholders:
- `{{VERSION}}` → `1.20` (major.minor of the methodology at adoption time).
- `{{ADOPTED_AT}}` → today's date in `YYYY-MM-DD`.

Branch on existing state:

- **File absent** → `Write` the template as the entire file.
- **File present without marker** → `Edit` and **append** the methodology block (wrapped in `<!-- idea-to-deploy:begin v1.20 -->` … `<!-- idea-to-deploy:end -->`) to the end of the file. Add a blank line before the marker. Do NOT modify any existing content above.
- **File present with marker** → skip. Report «CLAUDE.md уже содержит idea-to-deploy блок, не трогаю».

**Never** rewrite or remove the user's existing content. The marker is the source of truth for future updates — a user who wants to re-adopt can delete the block manually.

> **Consolidation (Day-5 SDD).** Prefer a **single** `CLAUDE.md` as the agent's
> operational manifest (the `AGENTS.md` equivalent). If the project scatters agent
> instructions across many files (READMEs, ad-hoc prompt docs, multiple `*.cursorrules`
> / `*.md`), flag it as *instructional fragmentation* in the Step 4 report and suggest
> consolidating into `CLAUDE.md` — do not auto-merge their content here.

### Step 2: Write / merge .claude/settings.json

**Step 2.0 — user-level installation detect (v1.42.0).** Before writing any
project-level hooks, check `~/.claude/settings.json`: if the ITD hooks are
already registered **user-level** (command paths reference our hook script
names — on Windows via the python.exe wrapper form), do NOT duplicate them at
project level: every hook would fire twice per event, and bare `.sh` commands
do not execute on Windows anyway (live case: OneOfS adoption 2026-07-02).
In that case write/merge ONLY the `permissions` key from the template and
report: «hooks уже зарегистрированы user-level — project-дубли пропущены».
Project-level hook registration remains the right path for machines where the
plugin is installed without `sync-to-active.sh` (no user-level registration).

Read the template from `references/project-settings-template.json`. It encodes the same hook layout that `scripts/sync-to-active.sh` installs at user-level, but pointed at the plugin's hooks (via `~/.claude/plugins/idea-to-deploy/hooks/` by default — use the plugin hooks dir resolved in Step 0.4). Substitute `{{PLUGIN_HOOKS_DIR}}` in every `command` value. The template carries two keys: `hooks` (enforcement) and `permissions.ask` (recommended ASK guardrails for dangerous OS tool-classes — native Claude Code permissions, no custom DSL). Strip the `_comment_*` keys before writing.

Branch (apply the same logic independently to `hooks` and to `permissions`):

- **`.claude/settings.json` absent** → `mkdir -p .claude/` and `Write` the template (hooks + permissions) with plugin-dir paths substituted, comments stripped.
- **Exists, no `hooks` key** → `Edit` to add the `hooks` key from the template. Preserve every other key (`env`, `statusLine`, `model`, …).
- **Exists with `hooks` key** → merge. For each event (`UserPromptSubmit`, `PreToolUse`, `PostToolUse`), add any of our hook entries that are missing, matched by `command` path. **Never** remove the user's existing hooks. If all our hooks are already present → skip.
- **`permissions` merge** → add our `permissions.ask` rules that are missing, matched by exact rule string (e.g. `Bash(rm:*)`). **Never** remove or reorder the user's existing `permissions.allow` / `permissions.deny` / other `permissions.ask` rules. If the user has no `permissions` key, create it with our `ask` list. If all our rules are already present → skip. This guardrail set is a recommended default — if the user declines, omit it; do not force it.

**Never** touch `~/.claude/settings.json` (user-level). Project-level settings apply in this directory only.

### Step 3: Bootstrap memory dir

1. Compute memory dir path using the same logic as `hooks/pre-flight-check.sh` lines 89-127:
   - `expected = "-" + cwd_resolved.lstrip("/").replace("/", "-")`
   - `candidate = ~/.claude/projects/<expected>/memory/`
   - Fallback: suffix-matching against existing `~/.claude/projects/*` dirs.

2. `mkdir -p` the memory dir if missing. (Claude Code normally creates the outer `projects/<hash>/` dir itself; we only ensure `/memory/` exists inside it.)

3. **Invoke `/session-save` via the Skill tool** with a synthesized sentinel context. Pass these 9 fields:

   - **Date:** today (`YYYY-MM-DD`).
   - **Project + branch:** `$PROJECT_ROOT` and `git branch --show-current`.
   - **Summary:** «Проект адоптирован в методологию idea-to-deploy v1.20 через `/adopt`. Установлены: `CLAUDE.md` в корень, `.claude/settings.json` с hooks-регистрацией (project-level), memory dir инициализирован.»
   - **Key decisions:** «Выбрана минимальная адоптация без reverse-engineering plan-документов (по ROADMAP_v1.20 §Scope). Plan-документы будут сгенерированы отдельно через `/strategy` или `/blueprint` по запросу пользователя.»
   - **Changed files:** `CLAUDE.md`, `.claude/settings.json`, `MEMORY.md` (newly indexed), plus any that were append-merged.
   - **Blockers:** «Нет.»
   - **Next steps:** «Опционально запустить `/strategy` (live reassessment) или `/blueprint` (plan с нуля), если нужны LAUNCH_PLAN.md / STRATEGIC_PLAN.md.»
   - **Non-obvious context:** detected stack (Step 0.5), current branch, count of root-level files, presence of `README.md`. Mark explicitly: «Стек детектирован по манифестам, проверь вручную.»
   - **Memory type:** `project` (this is a project-level bootstrap, not user feedback).

   `/session-save` will also (a) append a line to `MEMORY.md` index, (b) write `.active-session.lock` in the memory dir, (c) name the sentinel file `session_YYYY-MM-DD.md` (auto-numbered if a file for today already exists).

### Step 3.5: Scaffold `.itd/` contracts + structured state (optional 4th write, recommended)

Closes the "templates without a creator" gap (v1.40.0): the gates that consume `.itd/` artifacts (`/review` Stage A, `/task` tiers, `/grill-me`, `/handoff`) silently degrade to no-ops when no one ever scaffolds the files. Contracts stay **opt-in by design** (v1.39.0 tradeoff) — this step is offered in the Step 0.7 plan as recommended, and skipped entirely if the user said «без .itd».

If the user accepted:

1. **Resolve templates dir** — try in order: (a) sibling of the plugin hooks dir resolved in Step 0.4: `<plugin>/docs/templates/itd/` (e.g. `~/.claude/plugins/idea-to-deploy/docs/templates/itd/`); (b) `~/.claude/templates/itd/` — `sync-to-active.sh` mirrors the templates there since v1.68.0 (Step 4/6), so sync-based installs carry them too; (c) `docs/templates/itd/` in a methodology repo checkout if one is known. If none exists, warn («шаблоны .itd/ не найдены — обнови установку: `bash scripts/sync-to-active.sh` из репо методологии») and skip to Step 4.
2. **Skip if present** — if `$PROJECT_ROOT/.itd/` already exists, report «.itd/ уже существует, не трогаю» (idempotent) and continue.
3. **Copy all 13 contract templates plus the `.py` utilities** (`check_contract_drift.py`, `itd_init_validate.py`) into `$PROJECT_ROOT/.itd/`, filling only the obvious placeholders (project name, detected stack from Step 0.5, verify commands if a test runner was detected). Do NOT invent invariants, golden flows, or forbidden changes — leave template prose where real knowledge is missing; the user or a later `/blueprint`/`/task` fills them.
4. **Create `.itd-memory/`** with `STATE.json` from `<plugin>/docs/templates/itd-memory/STATE.example.json` reset to this project (`sessionState: "ACTIVE"`, `currentStage: "ADOPTED"`, `intent`: «adoption», empty logs/history, `existingProject.detectedStack` from Step 0.5) and an empty `events.jsonl`.

### Step 3.6: Example test — «столб держит вес» for brownfield (optional 5th write, recommended; v1.67.0)

Closes init-audit gap #2 (2026-07-08): `/adopt` never proved the test harness works, so the completion gate's L2 layer had nothing to stand on in legacy projects. Offered in the Step 0.7 plan; skipped if the user said «без example test».

1. **Detect existing tests** — glob `tests/`, `test/`, `**/*_test.*`, `**/*.test.*`, `**/test_*.py`, `src/**/__tests__/`. If ANY test file exists → skip (report «тесты уже есть — example test не нужен») and go to Step 3.7.
2. **Pick a ZERO-DEPENDENCY built-in runner** for the detected stack — `/adopt` must not install anything (non-scope):
   - Python (`pyproject.toml`/`requirements*.txt`) → `tests/test_smoke.py` on stdlib `unittest`; run: `python3 -m unittest discover -s tests -v`. (If `pytest` is ALREADY a declared dependency, prefer `python3 -m pytest tests/ -q`.)
   - Node ≥ 18 (`package.json`) → `tests/smoke.test.mjs` on built-in `node:test`; run: `node --test tests/`.
   - Go (`go.mod`) → `smoke_test.go` in the main package; run: `go test ./...`.
   - Rust (`Cargo.toml`) → `#[test] fn smoke()` in `tests/smoke.rs`; run: `cargo test`.
   - Anything else (PHP without PHPUnit, etc.) → report «встроенного runner'а нет — example test пропущен, добавь через /test когда выберешь фреймворк» and skip.
3. **Write ONE trivial smoke test** — imports the project's top-level package/module (or just asserts `1 + 1 == 2` when even importing needs env) with a comment explaining it proves the harness, not the product. Zero business logic, zero new dependencies, zero edits outside the tests dir.
4. **Run it** and show the real output. A red example test means the harness itself is broken — report the WHY and leave the test in place as the fix target; do not delete it to make adoption look green.
5. Record the working test command as the project's baseline L2 evidence: mention it in the Step 3 sentinel `/session-save` and, if `.itd/VERIFICATION_CONTRACT.json` was scaffolded, note it there as a candidate verify command.

### Step 3.7: Runnability check — init validator on the legacy project (optional, recommended; v1.67.0)

Closes init-audit gap #1: `/adopt` only detected the stack by manifests and never proved the project actually comes up from a clean clone. Offered in the Step 0.7 plan; skipped if the user said «без проверки запускаемости». Requires Step 3.5 (the validator is copied as `.itd/itd_init_validate.py`; when `.itd/` was declined, run it straight from the plugin templates dir).

1. **Detect commands** (best-effort, confirm with the user when ambiguous):
   - bootstrap: `make setup` (Makefile target exists) / `npm ci` / `pnpm install --frozen-lockfile` / `pip install -e .[dev]` / `poetry install` / `go mod download` / `cargo fetch`.
   - test: `make test` / `package.json scripts.test` / `python3 -m pytest` (or the Step 3.6 built-in-runner command) / `go test ./...` / `cargo test`.
2. **Run**: `python3 .itd/itd_init_validate.py --bootstrap "<cmd>" --test "<cmd>"` — it clones the repo into an isolated temp dir and executes both commands there.
3. **Advisory for brownfield** — a red result does NOT roll back the adoption. Report the WHY+FIX mark verbatim; a legacy project that cannot bootstrap from a clean clone is exactly what the user needs to see on day one (the validator keeps the failed clone for inspection). Record PASS/FAIL in the sentinel `/session-save`.
4. Skip silently when the project has no commits yet (validator prints SKIP) or when secrets/external services make an isolated bootstrap impossible — say so explicitly instead of faking green.

### Step 4: Report to user

Summarize, with exact absolute paths:

```
Adoption complete. Wrote / updated:
  - <ABS>/CLAUDE.md                          (created | appended | unchanged)
  - <ABS>/.claude/settings.json              (created | merged | unchanged)
  - <ABS>/.itd/ + .itd-memory/STATE.json     (scaffolded | skipped — declined | skipped — already present)
  - <ABS>/tests/<example test>               (created + run: PASS/FAIL | skipped — tests exist | skipped — declined | skipped — no built-in runner)
  - runnability check (init validator)       (PASS | FAIL: <why> | skipped — declined | skipped — no commits)
  - <MEMORY>/MEMORY.md                       (indexed)
  - <MEMORY>/session_<DATE>.md               (sentinel)
  - <MEMORY>/.active-session.lock            (written)

Next Claude Code session in this project will:
  - Auto-run pre-flight-check.sh on every user prompt
  - Auto-run session-open-diagnostic.sh on the first prompt
  - Auto-run check-skills.sh → skill hints per trigger phrase
  - Auto-run check-tool-skill.sh → rate-limited skill reminder on Bash/Edit/Write
```

Even if all three operations were skips (idempotent re-run), still print the summary so the user sees the adopted state confirmed.

### Step 5: Voice-chain — ask about plan documents

If the argument `skip-chain` was passed → skip this step and exit.

Otherwise, ask the user **in text** (not as an interactive prompt — so it works in headless and pipe mode):

> «Адоптация завершена (CLAUDE.md + .claude/settings.json + memory dir).
>
> Хочешь сгенерировать plan-документы для этого проекта сейчас?
>
> — **да** → я оценю состояние проекта и запущу нужное:
>    • есть `README.md` + история коммитов → `/strategy` (live reassessment)
>    • пустой репо или нет `README.md` → `/blueprint` (plan с нуля)
> — **нет** → завершаю. Сгенерируешь позже через `/strategy` или `/blueprint` вручную.»

Wait for the user's reply.

### Step 6: Chain to /strategy | /blueprint | exit

Based on the user's answer:

**Decision tree:**

```
user says "да" / "yes" / "ok" / equivalent:
├── README.md exists AND  git log --oneline | wc -l  ≥ 3  → Skill(/strategy, "$PROJECT_ROOT")
├── README.md exists AND  empty/initial git log            → Skill(/blueprint, "retroactive plan for existing code at $PROJECT_ROOT $STARTER_HINT")
├── README.md absent AND  any src/app/lib or manifest file → Skill(/blueprint, "retroactive plan for existing code at $PROJECT_ROOT $STARTER_HINT")
└── README.md absent AND  no code (fresh repo)             → Skill(/blueprint, "fresh project plan at $PROJECT_ROOT $STARTER_HINT")

Where `$STARTER_HINT` is, when the product type from Step 0.6 is **not** `unknown`:
`— product type: <type>, reference starter: starters/<id>/, golden-path: golden-paths/<id>.json`
(empty string when `unknown`). This lets `/blueprint` align the plan to a known
starter scaffold + required artifacts instead of inventing one. `/strategy` does
not take the hint — live reassessment reads the real project state directly.

user says "нет" / "no" / "later" / equivalent:
└── exit, print final summary

user says something ambiguous:
└── re-ask once with clearer phrasing; if still unclear, default to exit (user can invoke /strategy or /blueprint manually later)
```

Tell the user which skill you're invoking and why in one sentence, e.g. «Запускаю `/strategy` — вижу README.md и 127 коммитов, это live reassessment кейс.»

## Idempotency

Every write is guarded:

- `CLAUDE.md` — marker `<!-- idea-to-deploy:begin v1.20 -->` makes re-runs no-ops.
- `.claude/settings.json` — hook entries are matched by `command` path; duplicates are not added.
- Memory dir — `/session-save` appends to `MEMORY.md`; sentinel session file is auto-numbered.
- `.itd/` — scaffold is skipped when the directory already exists (never overwrites filled-in contracts).

Re-running `/adopt` twice in a row is safe and produces no extra output beyond a confirmation that the project is already adopted.

## What `/adopt` does NOT do (explicit non-scope)

- **Does NOT** reverse-engineer plan documents (`STRATEGIC_PLAN.md`, `PROJECT_ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `PRD.md`) from code. Hallucination risk is too high: a plausible-sounding plan that the user trusts, but that misrepresents KPIs, competitors, or scope, poisons trust in the methodology. Plan generation is delegated to `/strategy` (live reassessment with user input) or `/blueprint` (clarify-first mode) via the voice-chain in Step 5-6.
- **Does NOT** treat the product-type detection (Step 0.6) as authoritative. It is a heuristic **hint** from manifests/structure, reported to the user and passed to `/blueprint` as a reference starter — never written into `CLAUDE.md` and never a substitute for `/blueprint`'s own clarification.
- **Does NOT** modify `~/.claude/settings.json` (user-level). Other projects on the same machine stay untouched.
- **Does NOT** modify project source code. Zero edits in `src/`, `app/`, `lib/`. No new dependencies installed. The single carve-out is the **opt-in** Step 3.6 example test — one new file in the tests dir, on a built-in zero-dependency runner only; if creating it would require installing anything, it is skipped.
- **Does NOT** perform `git commit` or any git write operation. The user decides when and how to commit the new `CLAUDE.md` and `.claude/settings.json`.
- **Does NOT** rewrite an existing `CLAUDE.md` that already contains the idea-to-deploy block. Use idempotent append-with-marker pattern only.

## Rules

1. **Never rewrite user content** — `CLAUDE.md` is append-only (guarded by marker); `settings.json` is merge-only (guarded by command-path match).
2. **Never touch user-level `~/.claude/settings.json`** — adoption is project-scoped.
3. **Never commit** — the user decides when to commit the new files.
4. **Never reverse-engineer plan docs** — delegate to `/strategy` or `/blueprint` via voice-chain.
5. **Never run on the methodology repo itself** — Step 0.2 self-reference guard is mandatory.
6. **Always show the plan before writing** — three write operations, user approves before anything happens.
7. **Always print the final summary** — even if all three operations were no-ops.
8. **Always offer the voice-chain question** — unless `skip-chain` was explicitly passed.

## Self-validation

Before reporting adoption as complete, verify:

- [ ] `$PROJECT_ROOT/CLAUDE.md` exists and contains `<!-- idea-to-deploy:begin v1.20 -->` marker
- [ ] `$PROJECT_ROOT/.claude/settings.json` exists and references all 3 project-level hook commands in `hooks.UserPromptSubmit` (pre-flight-check, session-open-diagnostic, check-skills), all 7 in `hooks.PreToolUse` (check-tool-skill, check-commit-completeness, check-review-before-commit, check-dod-before-commit, cross-review-precommit, check-skill-completeness, pii-egress-guard), all 3 in `hooks.PostToolUse` (record-agent-skill on `Task|Agent`; cost-tracker + risk-score on `*`), and handoff-readiness in `hooks.Stop`
- [ ] `$PROJECT_ROOT/.claude/settings.json` carries the recommended `permissions.ask` OS-tool-class guardrails (rm/sudo/chown/dd/mkfs/kill/…) merged without clobbering the user's existing `permissions` (or the user explicitly declined them)
- [ ] `.itd/` + `.itd-memory/STATE.json` scaffolded — or the skip reason recorded (user declined / already present / templates dir absent)
- [ ] Example test created **and actually run** with real output shown (or skip reason recorded: tests exist / declined / no built-in runner) — a red run is reported, never hidden
- [ ] Runnability check ran via `itd_init_validate.py` with its PASS/FAIL recorded in the sentinel session-save (or skip reason recorded: declined / no commits / isolated bootstrap impossible)
- [ ] Memory dir exists with `MEMORY.md` indexing at least the sentinel session
- [ ] `.active-session.lock` written in memory dir
- [ ] Sentinel `session_YYYY-MM-DD.md` exists in memory dir
- [ ] Voice-chain question was either asked (Step 5) or skipped on `skip-chain` flag
- [ ] Product type detected and reported (or explicitly `unknown`); when not `unknown` and chaining to `/blueprint`, the starter/golden-path hint was passed in
- [ ] Next-skill invocation happened correctly (or user explicitly opted out)

## Examples

### Example 1 — Fresh adoption on a legacy FastAPI project

```
User: адоптируй этот проект в методологию

Claude: [/adopt]
  Step 0 — discovery:
    Git repo:            /home/user/work/shop-api
    Existing CLAUDE.md:  not found
    Existing settings:   .claude/settings.json not found
    Memory dir:          ~/.claude/projects/-home-user-work-shop-api/memory/ (absent)
    Plugin hooks dir:    ~/.claude/plugins/idea-to-deploy/hooks/
    Detected stack:      Python + FastAPI (pyproject.toml), PostgreSQL (docker-compose.yml)
    Detected product type: api_service → starter `api-fastapi`, golden-path `api-service-booking`
                           (эвристически по манифестам, проверь вручную)

  /adopt plan:
    - CLAUDE.md:                  create
    - .claude/settings.json:      create
    - memory dir:                 create + sentinel /session-save
    - .itd/ + .itd-memory/:       scaffold (recommended)
    - Detected product type:      api_service → starter api-fastapi
  Proceed? [yes/no]
User: yes
  Step 1/4 — CLAUDE.md ............. written (2.1 KB, marker v1.20)
  Step 2/4 — .claude/settings.json . written (hooks: 3 UserPromptSubmit, 4 PreToolUse, 1 Stop)
  Step 3/4 — memory bootstrap ...... OK (sentinel session_2026-04-17.md created)
  Step 4/4 — .itd/ scaffold ........ OK (13 contracts + .itd-memory/STATE.json)

  Adoption complete. Next session will auto-run pre-flight + session-open-diagnostic + check-skills.

  Хочешь сгенерировать plan-документы сейчас?
  — да → запущу /strategy (вижу README.md + 84 коммита = live reassessment)
  — нет → закончу, сгенерируешь позже вручную
User: да
  Запускаю /strategy. [/strategy $PROJECT_ROOT]
```

### Example 2 — Idempotent re-run (already adopted)

```
User: адоптируй проект ещё раз

Claude: [/adopt]
  Step 0 — discovery:
    Git repo:            /home/user/work/shop-api
    Existing CLAUDE.md:  present, marker v1.20 found
    Existing settings:   .claude/settings.json present, all hooks registered
    Memory dir:          exists, MEMORY.md has 12 sessions

  Project is already adopted. Nothing to write.

  Хочешь сгенерировать plan-документы для этого проекта?
  — да → я оценю состояние и запущу /strategy или /blueprint
  — нет → закончу
User: нет
  Готово. Если понадобятся plan-документы — вызови /strategy или /blueprint.
```

## Troubleshooting

### Plugin hooks dir not found

If `~/.claude/plugins/idea-to-deploy/hooks/` does not exist AND `$CLAUDE_PLUGIN_DIR` is unset, the plugin may have been installed via `git clone + bash scripts/sync-to-active.sh` (legacy path). In that case hooks live at `~/.claude/hooks/` directly — fall back to that path when writing `.claude/settings.json`. If that also fails, ask the user for the correct path.

### CLAUDE.md is very large (> 20 KB)

Append still works — the marker block is ~60 lines, cost is negligible. If the user prefers, they can move the marker block into a separate file (`docs/claude-methodology.md`) and link from CLAUDE.md; that is a manual refactor, not in `/adopt` scope.

### Hooks in .claude/settings.json don't fire

Claude Code uses project-level `.claude/settings.json` automatically when you open the directory — no reload needed. If hooks still don't fire, check:
1. `command` paths point to executable files (`chmod +x` if not).
2. `~/.claude/plugins/idea-to-deploy/hooks/*.sh` actually exists — re-run `bash scripts/sync-to-active.sh` from the methodology repo to re-populate.
3. Claude Code version supports project-level hooks (≥ 2.0 with plugin support).

### User wants to re-adopt after a version bump

Current `/adopt` uses marker `v1.20`. When a future version changes the canonical `CLAUDE.md` or settings template, re-run is a no-op because the marker matches. Workaround: the user deletes the block between markers manually, then re-invokes `/adopt`. A future `/adopt --refresh` flag can automate this; out of scope for v1.20.

### Ctrl+C mid-adoption

All three writes are idempotent. If adoption was interrupted after Step 1 (CLAUDE.md written) but before Step 2 (settings.json missing) — a re-run picks up from Step 2 cleanly. No partial-state recovery needed.
