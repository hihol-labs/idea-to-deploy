# Manual verification — fixture 17 (/adopt)

`/adopt` onboards a legacy project into the idea-to-deploy methodology. By default (minimal path, ITD-PLAN-S9) it
performs **one write** - the pointer block in `CLAUDE.md` (Codex: `AGENTS.md`) with the project commands found in the
manifests. Contracts, state, the first unit, project hooks and the merge gate come only on the strict route
(`/adopt strict`). No reverse-engineering of plan documents, no hallucinated architecture, no code changes.

The mechanical part is `skills/adopt/scripts/itd_adopt.py`; `tests/verify_task_adopt_route.py` runs it on fixtures
(empty repo, existing file, idempotent re-run, strict full set, refusals). This checklist covers the skill's dialogue.

## /adopt — Scenario A: minimal adoption of a legacy repo with an existing CLAUDE.md

Prerequisites: `output/` contains a seeded legacy project - `.git/` initialised, `CLAUDE.md` with user content (no
idea-to-deploy marker), `.claude/settings.json` with a custom hook, `pyproject.toml` with pytest and ruff, a
`justfile` with a `test` recipe.

- [ ] Step 0 prints `minimal` (no `itd-route: strict` marker in the project, no `strict` argument)
- [ ] Step 1 runs the helper with `--host claude --plan`; the `ADOPT PLAN` shows `"CLAUDE.md": "append-guarded-block"`
      and `commands` = `{"test": "just test", "lint": "ruff check ."}`
- [ ] The plan says nothing else is written (`.itd/`, `.itd-memory/`, hooks, merge gate - only `/adopt strict`) and asks
      for confirmation before writing
- [ ] On «да» the helper runs with `--apply --approved`; `ADOPTION: PASS` reports `"CLAUDE.md": "appended"`
- [ ] `CLAUDE.md` keeps the user content byte-for-byte above one `<!-- idea-to-deploy:begin v... -->` block; the block
      lists the two commands, one per line
- [ ] `.claude/settings.json` is byte-identical; no `.itd/`, no `.itd-memory/` appear
- [ ] `/session-save` is NOT invoked; `/strategy` / `/blueprint` are only mentioned in the report

## /adopt — Scenario B: second run (idempotency)

- [ ] The plan shows `"CLAUDE.md": "skip-marker-present"`; nothing is written, `CLAUDE.md` is byte-identical
- [ ] The report still prints, confirming the adopted state

## /adopt — Scenario C: strict route

`/adopt strict` on the same project (it needs a tracked verifier, e.g. `tests/test_smoke.py`, committed first).

- [ ] Step 0 takes the strict route because of the argument; `references/strict.md` is read
- [ ] S1: the first-unit values (baseline, verification command, trusted verifier, criterion, allowed areas) are agreed
      with the user, never invented; the helper `--strict --plan` is shown before any write
- [ ] The block gains the strict paragraph with the line `itd-route: strict` inside the existing block (one marker);
      Step 0 of `/bugfix` now prints `strict`
- [ ] `.itd/` holds every contract template and no `.py` tool; `.itd-memory/` holds `STATE.json`, `events.jsonl`,
      `session-artifacts.json`, `GOAL.json`, `contracts/U-001.md`; `BASELINE: PASS` is reported
- [ ] S2-S8 are offered (example test, runnability, router split, context index, GitHub profile, plan documents,
      project hooks last with `itd_project_hooks.py apply --yes` only on «да»)
- [ ] S9: one `/session-save` with the topic `adopt` writes `.itd-memory/continuity/adopt.md`

## /adopt — Scenario D: refusals

- [ ] Inside the `idea-to-deploy` repository the helper refuses (self-reference guard) and nothing is written
- [ ] Outside a git repository: «`/adopt` работает в git-репозиториях. Создай репо (`git init`) или перейди в существующий.»
- [ ] `--unit-id` or other strict-only options without `--strict` are refused with WHY/FIX
- [ ] A strict run on a `CLAUDE.md` larger than 8 KB refuses (`refuse-marker-beyond-8kb`) and writes nothing

## /adopt — Scenario E: guard rails (what /adopt MUST NOT do)

- [ ] Does NOT generate plan documents (LAUNCH_PLAN.md / STRATEGIC_PLAN.md / PRD.md / PROJECT_ARCHITECTURE.md /
      IMPLEMENTATION_PLAN.md / DISCOVERY.md) - those come from /strategy or /blueprint on request
- [ ] Does NOT reverse-engineer architecture from source code
- [ ] Does NOT modify `~/.claude/settings.json` (user-level) - project-level only
- [ ] Does NOT overwrite pre-existing CLAUDE.md content above the marker
- [ ] Does NOT copy repository text (script bodies, recipe text) into the block - only fixed command strings
- [ ] Does NOT write OUTSIDE `$PROJECT_ROOT`

## Cross-reference with `check-skill-completeness.sh`

`/adopt` satisfies the three Quality Gate 2 requirements:

1. ✅ `skills/adopt/references/` exists (claude-md-template.md, agents-md-template.md, strict.md, codex-adoption.md)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/adopt`
3. ✅ `tests/fixtures/fixture-17-adopt/` exists with `idea.md`, `notes.md`, `expected-files.txt`, `expected-snapshot.json`

## Run manually

1. `cd tests/fixtures/fixture-17-adopt/`
2. `rm -rf output && mkdir output && cd output`
3. Seed a minimal legacy repo:
   ```bash
   git init
   printf "# Legacy project\n\nUser's own notes go here.\n" > CLAUDE.md
   mkdir .claude
   echo '{"permissions": {}, "hooks": {"UserPromptSubmit": [{"matcher": "", "hooks": [{"type": "command", "command": "echo lint-check"}]}]}}' > .claude/settings.json
   printf "[project]\nname = 'legacy'\n[project.optional-dependencies]\ndev = ['pytest', 'ruff']\n" > pyproject.toml
   printf "test:\n\tpytest\n" > justfile
   echo "print('hello')" > main.py
   git add -A && git commit -m "legacy baseline"
   ```
4. Start Claude Code, paste `idea.md` content, invoke `/adopt`
5. Answer «да» at the plan preview
6. Verify outputs per the Scenario A checklist
7. Invoke `/adopt` a second time - verify Scenario B idempotency
8. `cd .. && python3 ../../verify_snapshot.py .`

Expected: `✅ fixture-17-adopt: PASSED`.

## Failures (fill in if any)

(empty unless the fixture fails - leave space for documenting regressions, especially any plan doc written by /adopt
in violation of the "no reverse-engineering" contract, or any write beyond the pointer on the minimal path)
