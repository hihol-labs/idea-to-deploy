# Manual verification — fixture 17 (/adopt)

`/adopt` onboards a legacy project into the idea-to-deploy methodology. It performs **exactly three writes plus one voice-chain question** — no reverse-engineering of plan documents, no hallucinated architecture, no code changes.

This fixture exercises the "pre-existing CLAUDE.md + .claude/settings.json" path (append/merge), which is the hardest case for idempotency.

## /adopt — Scenario A: happy path on a legacy repo with existing CLAUDE.md + settings

Prerequisites:
- `output/` contains a seeded legacy project: `.git/` init'd, `CLAUDE.md` with some user content (no idea-to-deploy marker), `.claude/settings.json` with at least one custom hook, some source files (e.g., `main.py`)

### Step 0 — Safety and discovery
- [ ] Skill resolves `$PROJECT_ROOT` via `git rev-parse --show-toplevel`
- [ ] Skill self-reference guard: if `$PROJECT_ROOT/.claude-plugin/plugin.json` exists with `"name": "idea-to-deploy"` → refuses to adopt itself, exits
- [ ] Skill detects CLAUDE.md (present, no marker → "append" branch)
- [ ] Skill detects .claude/settings.json (present, no methodology hooks → "merge" branch)
- [ ] Skill detects memory dir (absent → "create + sentinel" branch)
- [ ] Skill resolves plugin hooks dir via: `$CLAUDE_PLUGIN_DIR` → `~/.claude/plugins/idea-to-deploy/hooks/` → grep → `~/.claude/hooks/` fallback
- [ ] Skill best-effort detects stack via glob (package.json / pyproject.toml / etc.) — reports to user, does NOT embed in CLAUDE.md (sentinel only)

### Step 0.5 — Plan preview
- [ ] Skill prints a plan before writing:
```
/adopt plan:
  - CLAUDE.md:              append methodology block
  - .claude/settings.json:  merge hooks
  - memory dir:             create + sentinel /session-save
  - Plugin hooks dir:       <resolved path>
  - Detected stack:         <stack>
Proceed? [yes/no]
```
- [ ] Waits for explicit "yes" — does not silently proceed

### Step 1 — CLAUDE.md append
- [ ] User's existing CLAUDE.md content is preserved verbatim above the marker
- [ ] Methodology block is wrapped in `<!-- idea-to-deploy:begin v1.20 -->` ... `<!-- idea-to-deploy:end -->` markers
- [ ] Placeholders replaced: `{{VERSION}}` → "1.20", `{{ADOPTED_AT}}` → today's date YYYY-MM-DD
- [ ] One blank line separates existing content from the begin marker
- [ ] Block references the methodology's core rules (not a rewrite of user's style guide)

### Step 2 — .claude/settings.json merge
- [ ] Pre-existing keys (`permissions`, `env`, `statusLine`, `model`, ...) preserved
- [ ] Pre-existing hooks in `hooks.UserPromptSubmit` / `hooks.PreToolUse` arrays preserved — NOT overwritten
- [ ] Methodology hooks added only if absent (matched by `command` path): `pre-flight-check.sh`, `check-skills.sh`, `check-tool-skill.sh`, `check-skill-completeness.sh`, `check-commit-completeness.sh`, `check-review-before-commit.sh`, `session-open-diagnostic.sh`
- [ ] `{{PLUGIN_HOOKS_DIR}}` placeholder substituted with the resolved plugin hooks dir from Step 0
- [ ] JSON remains valid (parse with `python3 -c "import json; json.load(open('.claude/settings.json'))"` — no syntax errors from merge)

### Step 3 — Memory dir bootstrap
- [ ] Memory dir created at `~/.claude/projects/-<dashed-cwd>/memory/`
- [ ] `session_YYYY-MM-DD.md` sentinel written with: project root path, detected stack, adoption note, "no blockers (just bootstrapped)"
- [ ] `MEMORY.md` created (or updated) with a pointer line to the sentinel session
- [ ] `.active-session.lock` written with fresh timestamp, pid, branch, project path, note

### Step 4 — Voice-chain question
- [ ] Skill asks ONE question at the end: «Сгенерировать план документов? (1) /strategy — обновит существующий план, (2) /blueprint — создаст с нуля, (3) пропустить»
- [ ] If user picks 1 or 2 — skill invokes the corresponding skill via Skill tool; `/adopt` itself exits cleanly
- [ ] If user picks 3 — skill exits with: «OK, план-документы не создаю. /strategy или /blueprint можно запустить позже вручную.»
- [ ] If user passed `skip-chain` argument at invocation — skip Step 4 entirely

## /adopt — Scenario B: second run (idempotency)

User runs `/adopt` again on the same project after Scenario A.

- [ ] Skill detects CLAUDE.md with `<!-- idea-to-deploy:begin v1.20 -->` marker → "skip (already adopted)" decision
- [ ] Skill detects .claude/settings.json with all methodology hooks already present → "skip (already registered)" decision
- [ ] Skill detects existing memory dir with MEMORY.md → "skip (already bootstrapped)" decision
- [ ] Plan preview shows 3 "skip" decisions
- [ ] Skill jumps straight to voice-chain Step 4 — user may still want plan docs they declined on first adoption
- [ ] NO new writes happen to any file

## /adopt — Scenario C: self-reference refusal

User (mistakenly) runs `/adopt` inside the `idea-to-deploy` methodology repo itself.

- [ ] Skill detects `.claude-plugin/plugin.json` exists with `"name": "idea-to-deploy"`
- [ ] Skill refuses: «Ты внутри самой методологии `idea-to-deploy`. `/adopt` адоптирует ДРУГИЕ проекты в методологию, не саму методологию. Выход.»
- [ ] Skill exits without writing anything

## /adopt — Scenario D: not a git repo

User runs `/adopt` in a directory that is not a git repository.

- [ ] Skill's `git rev-parse --show-toplevel` fails
- [ ] Skill tells the user: «`/adopt` работает в git-репозиториях. Создай репо (`git init`) или перейди в существующий.»
- [ ] Skill exits without writing anything

## /adopt — Scenario E: guard rails (what /adopt MUST NOT do)

- [ ] Does NOT generate plan documents (LAUNCH_PLAN.md / STRATEGIC_PLAN.md / PRD.md / PROJECT_ARCHITECTURE.md / IMPLEMENTATION_PLAN.md / DISCOVERY.md) — those are voice-chained to /strategy or /blueprint
- [ ] Does NOT reverse-engineer architecture from source code
- [ ] Does NOT modify `~/.claude/settings.json` (user-level) — project-level only
- [ ] Does NOT overwrite pre-existing CLAUDE.md content above the marker
- [ ] Does NOT remove pre-existing `.claude/settings.json` keys or hooks
- [ ] Does NOT run on Haiku — Sonnet required (bounded declarative templating; Opus is overkill)
- [ ] Does NOT write OUTSIDE `$PROJECT_ROOT` except the single known-safe path (project memory dir)

## Cross-reference with `check-skill-completeness.sh`

`/adopt` satisfies the three Quality Gate 2 requirements:

1. ✅ `skills/adopt/references/` exists (claude-md-template.md, project-settings-template.json)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/adopt`
3. ✅ `tests/fixtures/fixture-17-adopt/` exists with `idea.md`, `notes.md`, `expected-files.txt`, `expected-snapshot.json`

## /review status

- [ ] After adoption, run `/review` on the modified CLAUDE.md + settings.json
- [ ] Expected status: `PASSED` or `PASSED_WITH_WARNINGS`
- [ ] If `BLOCKED`, log the failing checks in Failures below

## Run manually

1. `cd tests/fixtures/fixture-17-adopt/`
2. `rm -rf output && mkdir output && cd output`
3. Seed a minimal legacy repo:
   ```bash
   git init
   echo "# Legacy project\n\nUser's own notes go here." > CLAUDE.md
   mkdir .claude
   echo '{"permissions": {}, "hooks": {"UserPromptSubmit": [{"matcher": "", "hooks": [{"type": "command", "command": "echo lint-check"}]}]}}' > .claude/settings.json
   echo "print('hello')" > main.py
   git add -A && git commit -m "legacy baseline"
   ```
4. Start Claude Code on Sonnet, paste `idea.md` content, invoke `/adopt`
5. Answer "yes" at the plan preview; answer voice-chain with "3" (skip) for the first run
6. Verify outputs per Scenario A checklist
7. Invoke `/adopt` a second time — verify Scenario B idempotency
8. `cd .. && python3 ../../verify_snapshot.py .`

Expected: `✅ fixture-17-adopt: PASSED`.

Note: the memory-dir sentinel file (`session_YYYY-MM-DD.md`, `MEMORY.md`, `.active-session.lock`) lives in `~/.claude/projects/-<dashed-output-path>/memory/` and is validated via `ls -la` of that directory, not through expected-snapshot.json.

## Failures (fill in if any)

(empty unless the fixture fails — leave space for documenting regressions, especially any plan doc written by /adopt in violation of the "no reverse-engineering" contract)
