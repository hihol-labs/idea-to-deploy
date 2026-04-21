# Manual verification — fixture 12 (/autopilot)

`/autopilot` chains all five methodology phases (discover → blueprint → kickstart → review → test) with `/session-save` checkpoints between phases. This fixture verifies the **Full mode** path (Opus required; Sonnet auto-falls to Lite).

This is the longest fixture — a full run takes 15–30 min of LLM time. Run manually, rarely, before methodology releases.

## /autopilot — Scenario A: full pipeline, happy path

User pastes the prompt from `idea.md`. Claude Code is on Opus.

### Pre-flight (Step 0)
- [ ] Skill checks the model: Opus → Full mode, Sonnet → Lite mode, Haiku → refuses
- [ ] Skill asks for confirmation (shows 5-phase plan with ~15–30 min estimate) before executing
- [ ] Skill verifies working dir is empty or a clean git repo (no uncommitted changes)
- [ ] Skill collects What / Who / Stack from the prompt — fills automatically from `idea.md` if present

### Phase 1 — /discover
- [ ] `DISCOVERY.md` created in root with Market / TAM / SAM / SOM / Competitor / Persona / MoSCoW sections
- [ ] Includes hairdresser / parikmakher terminology (domain match)
- [ ] `/session-save` runs at end of phase — new `session_YYYY-MM-DD.md` in project memory dir
- [ ] Pipeline proceeds automatically; no user confirmation between phases

### Phase 2 — /blueprint
- [ ] `/blueprint` Step 1.5 auto-detects DISCOVERY.md and **skips** its own MoSCoW re-prioritization
- [ ] Six new files created: `STRATEGIC_PLAN.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, `IMPLEMENTATION_PLAN.md`, `CLAUDE_CODE_GUIDE.md`, `README.md`
- [ ] PROJECT_ARCHITECTURE.md uses `aiogram` + PostgreSQL (matches the prompt's stack pin)
- [ ] `/session-save` checkpoint runs

### Phase 3 — /kickstart
- [ ] `CLAUDE.md` created with project status table
- [ ] Project scaffolded (src/, tests/, Dockerfile / docker-compose.yml as applicable, requirements.txt / pyproject.toml)
- [ ] Each implementation step commits before moving to the next
- [ ] After each sub-phase a `/session-save` checkpoint runs
- [ ] If any step fails 3 times in a row, pipeline STOPS and asks the user (does not auto-retry forever)

### Phase 4 — /review
- [ ] `/review` runs on the generated code + doc set
- [ ] Score must be ≥ 8/10 to proceed; lower score halts the pipeline with a summary
- [ ] Status is `PASSED` or `PASSED_WITH_WARNINGS`; never `BLOCKED` on a successful run

### Phase 5 — /test
- [ ] Tests exist for at least one core module (booking handler, DB model, or command dispatch)
- [ ] `pytest` runs green (or the project's equivalent)
- [ ] Any generated test files live under `tests/`, not alongside source

### Final state
- [ ] 8 documentation files land in the project root (listed in `expected-files.txt`)
- [ ] At least one `.session-save` marker between phases exists in the project memory dir
- [ ] Pipeline prints a summary: "✅ Autopilot finished — N phases done, review passed, M tests green"

## /autopilot — Scenario B: error handling in /kickstart (edge case)

A build step fails (e.g., Python dependency conflict).

- [ ] Skill reports the specific error with traceback snippet, not a generic "failed"
- [ ] Skill asks the user: «Retry? Skip this step? Abort pipeline?»
- [ ] On retry: single retry attempt, then halt on second failure (no infinite loop)
- [ ] On skip: pipeline continues, but status line mentions the skipped step in the summary
- [ ] On abort: `/session-save` runs before exit so state is preserved

## /autopilot — Scenario C: Lite mode on Sonnet

User runs `/autopilot` but Claude Code is on Sonnet (no `--full` override).

- [ ] Skill declares Lite mode at Step 0 confirmation
- [ ] /discover uses `--lite` (MoSCoW only, no RICE; 3 competitors; 2 personas)
- [ ] /blueprint uses Lite mode too (shorter architecture, lighter PRD)
- [ ] Same 8 files produced, just smaller
- [ ] Run time roughly halves (estimate 10–15 min instead of 15–30)

## /autopilot — Scenario D: guard rails (what /autopilot MUST NOT do)

- [ ] Does NOT deploy to a real production host — pipeline stops at `/test`, optional deploy is per-user decision
- [ ] Does NOT invoke `/discover` twice — pipeline is linear, not loop
- [ ] Does NOT skip `/review` even if user says "давай без ревью" — Quality Gate 1 is mandatory
- [ ] Does NOT commit to a public remote (`git push`) — local commits are fine, remote push is explicit user action afterwards
- [ ] Does NOT run on Haiku — refuses with «Этот скилл требует Sonnet (Lite) или Opus (Full).»

## Cross-reference with `check-skill-completeness.sh`

`/autopilot` satisfies the three Quality Gate 2 requirements:

1. ✅ `skills/autopilot/references/` exists (pipeline-steps reference)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/autopilot`
3. ✅ `tests/fixtures/fixture-12-autopilot/` exists with `idea.md`, `notes.md`, `expected-files.txt`, `expected-snapshot.json`

## /review status

- [ ] After pipeline completes, run `/review` manually on the output dir
- [ ] Expected status: `PASSED` or `PASSED_WITH_WARNINGS`
- [ ] If `BLOCKED`, log the failing checks in the Failures section below

## Run manually

1. `cd tests/fixtures/fixture-12-autopilot/`
2. `mkdir -p output && cd output` — empty working dir
3. Start Claude Code on **Opus**, paste `idea.md` content, invoke `/autopilot`
4. Wait 15–30 min; skill will checkpoint via `/session-save` and surface errors interactively
5. Once finished, optionally write `.rubric-status` next to the generated docs with the `/review` verdict
6. `cd .. && python3 ../../verify_snapshot.py .`

Expected: `✅ fixture-12-autopilot: PASSED`.

## Failures (fill in if any)

(empty unless the fixture fails — leave space for documenting regressions)
