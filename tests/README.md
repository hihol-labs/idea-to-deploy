# Tests — methodology regression fixtures

These fixtures protect the methodology from accidental regression. They are NOT unit tests of the skills' code (skills are markdown, not code). They are **golden examples**: known inputs paired with expected output structure.

## What's here

```
tests/
  fixtures/
    fixture-01-saas-clinic/
      idea.md              # the user's project description
      expected-files.txt   # files that /kickstart should create
      notes.md             # what to verify manually
    fixture-02-tg-bot/
      ...
    fixture-03-cli-tool/
      ...
  run-fixtures.sh          # smoke runner (manual)
```

## Why these specific fixtures

| # | Project type | Why included |
|---|---|---|
| 01 | SaaS — clinic management | Heavy: ARCHITECTURE has 5+ tables, auth flow, multi-role. Tests Full mode. |
| 02 | Telegram bot — appointment booking | Light: minimal API, single bot service. Tests Lite mode and bot-specific scaffolding. |
| 03 | CLI utility — log analyzer | Edge case: no API, no DB. Verifies that rubric correctly handles "no database" / "no API" justifications. |

## What is automated vs. manual

The methodology has **three tiers** of testing (as of v1.15.0):

1. **Structural gate (automated, CI-blocking).** `tests/meta_review.py` runs on every PR via [.github/workflows/meta-review.yml](../.github/workflows/meta-review.yml). It verifies version badges, skill count, SKILL.md frontmatter, trigger-phrase drift between `skills/` and `hooks/check-skills.sh`, marketplace.json consistency, subagent contract disclaimers (M-I8), caller-skill tool superset (M-I9), fixture snapshot schemas (M-I10), and ~20 other invariants. A PR with any Critical drift is blocked. See [docs/CI.md](../docs/CI.md) for the full list of checks.

2. **Snapshot validation (Phase 1 automated, v1.15.0).** After a maintainer runs a fixture manually, `tests/verify_snapshot.py` deterministically validates the output against a machine-readable contract in `expected-snapshot.json`. Catches regressions that a human skimming the output would miss (section renamed, endpoint count dropped, required multi-tenant column missing). Deterministic, zero API cost, zero model-version flakiness. Runs locally on demand, not in CI. **3 fixtures (01, 02, 03) have active snapshots; 7 are `status: pending` stubs deferred to Phase 2.**

3. **Behavioural execution (manual now, v1.16.0 candidate).** The fixtures themselves still need a Claude Code run to produce the output that Phase 1 validates. That run is done by the maintainer on each release. Phase 2 automation (`claude -p --output-format json --input-format stream-json`) is the next target — see [Phase 2: non-interactive execution](#phase-2-non-interactive-execution-v1160-candidate) below.

## Phase 1 workflow: snapshot validation

### Running a fixture (maintainer)

```bash
# 1. Spin up Claude Code in a clean working directory
mkdir -p tests/fixtures/fixture-01-saas-clinic/output
cd tests/fixtures/fixture-01-saas-clinic/output

# 2. Run the fixture manually (copy the idea into Claude Code)
#    Inside Claude Code:  /kickstart < paste contents of ../idea.md
#    Answer clarifying questions as documented in ../notes.md

# 3. After /kickstart finishes, record the rubric status
echo "PASSED_WITH_WARNINGS" > .rubric-status   # or whatever /review returned

# 4. Validate the output against the deterministic snapshot
cd ../../../..
python3 tests/verify_snapshot.py tests/fixtures/fixture-01-saas-clinic
```

Output:

```
✅ fixture-01-saas-clinic: PASSED
  Snapshot: .../expected-snapshot.json
  Output:   .../output
  Checks:   23 run, 0 failed
```

A fixture passes if:
1. All `files.required` exist in `output/`
2. All `content_contracts` (required sections, must-contain literals, count constraints) validate
3. The recorded `.rubric-status` is in `rubric_status.expected` and not in `rubric_status.forbidden`

### Snapshot schema

See the docstring at the top of [`tests/verify_snapshot.py`](verify_snapshot.py) for the full schema. Minimal `expected-snapshot.json`:

```json
{
  "$schema_version": "1.0",
  "fixture_type": "kickstart-full",
  "skill_under_test": "/kickstart",
  "status": "active",
  "description": "Why this fixture exists",
  "files": { "required": ["STRATEGIC_PLAN.md"], "min_count": 7 },
  "content_contracts": {
    "STRATEGIC_PLAN.md": {
      "required_sections": ["Competitors|Конкуренты", "Budget|Бюджет"],
      "min_length_chars": 800,
      "must_contain_any_of": {
        "competitors_named": ["MEDODS", "IDENT"]
      }
    }
  },
  "rubric_status": {
    "expected": ["PASSED", "PASSED_WITH_WARNINGS"],
    "forbidden": ["BLOCKED"]
  }
}
```

All fields except `$schema_version`, `fixture_type`, `skill_under_test`, `status`, and `description` are optional.

### Pending snapshots

A snapshot with `status: pending` auto-passes without validation — useful when the schema for a given fixture type isn't fully bootstrapped yet. The `M-I10` meta-review gate requires every fixture to have at least a pending stub so the schema coverage is explicit. See [CHANGELOG 1.15.0](../CHANGELOG.md) for the Phase 2 work that will flip pending stubs to active.

## Legacy fixture workflow (pre-v1.15.0, deprecated)

Before Phase 1 snapshots, fixtures were validated by manually diffing `ls -1` against `expected-files.txt` and eyeballing `notes.md`. The old files are retained for reference but the snapshot schema is the authoritative contract going forward.

```bash
# OLD WORKFLOW (retained for reference only)
cd tests/fixtures/fixture-01-saas-clinic
mkdir output && cd output
cat ../idea.md
# /kickstart {paste idea}
diff <(ls -1) ../expected-files.txt
cat ../notes.md
```

## When fixtures should fail

Fixtures should fail when:
- A skill's behavior changes in a backwards-incompatible way (e.g., `/blueprint` stops generating PROJECT_ARCHITECTURE.md)
- The rubric changes and previously-passing fixtures now fail Critical checks
- A new rubric check is added that the fixtures don't satisfy (this is OK — update the fixtures)

When a fixture fails, the maintainer must decide:
1. **Skill bug** → fix the skill, fixture passes again
2. **Intentional change** → update the fixture
3. **Rubric tightening** → either update fixture to satisfy new check, or document the exception

## Adding new fixtures

When adding a fixture:
1. Pick a project type that exposes a real edge case (not just "another SaaS")
2. Write `idea.md` as a real user would write it — vague is OK, that's part of the test
3. Run `/kickstart` once on a known-good methodology version
4. Capture the output file list as `expected-files.txt`
5. Write `notes.md` with manual checks that are too qualitative for diff

## Phase 2: non-interactive execution (v1.16.0 candidate)

Phase 1 (v1.15.0) validates *already-generated* output deterministically. Phase 2 will automate the *generation* step so the full pipeline — idea → run → validate — can be kicked off from a single command or a scheduled workflow.

### What Phase 2 will use

Claude Code supports non-interactive mode as of the current CLI:

- `claude -p, --print` — print response and exit (headless)
- `--output-format json` — single structured JSON result
- `--output-format stream-json` — incremental streaming output
- `--input-format stream-json` — supply multiple user messages (needed to answer `/kickstart`'s clarifying questions from a file)
- `--plugin-dir <path>` — load idea-to-deploy without installing it globally
- `--tools "Read Write Edit Glob Grep Bash"` — explicit tool whitelist for the sandbox
- `--max-budget-usd <amount>` — hard budget cap per run
- `--dangerously-skip-permissions` — required for a non-interactive sandbox run
- `--no-session-persistence` — throwaway session
- `--model opus` / `--model sonnet` — model override (cost knob)

The headless invocation looks roughly like:

```bash
claude -p \
  --plugin-dir . \
  --tools "Read Write Edit Glob Grep Bash" \
  --input-format stream-json \
  --output-format json \
  --max-budget-usd 5.00 \
  --no-session-persistence \
  --dangerously-skip-permissions \
  --model sonnet \
  < fixture-01-stream.jsonl
```

`fixture-01-stream.jsonl` contains the idea and pre-seeded answers to clarifying questions as a stream of user messages. The final JSON result is parsed, the generated files are written to `output/`, and `verify_snapshot.py` runs against the result.

### Why it is deferred to v1.16.0 rather than bundled into v1.15.0

1. **POC required before rollout.** The SDK exists, but the exact protocol for pre-seeded clarifying-question answers (`stream-json` input format) needs hands-on testing. Bundling POC work with a release risks a half-working release.
2. **Cost estimate required.** A single `/kickstart` Opus run costs several dollars in tokens. Running all 10 fixtures on every PR would be $20–50/month. Running only on release tags is the likely answer, but that decision needs a benchmarked run first.
3. **CI secrets management.** The non-interactive run needs an API key injected as a GitHub Actions secret. That's infrastructure work that doesn't overlap with Phase 1 schema validation.
4. **Snapshot bootstrap debt.** 7 of 10 fixtures currently have `status: pending` stubs. Turning them active requires one successful headless run each to record the ground truth. Doing that in the same PR as the SDK plumbing would mix research and cleanup.

### v1.16.0 target workflow

1. POC: headless `/kickstart` on fixture-01 → capture JSON result → diff output against current live snapshot.
2. If POC succeeds, write `tests/run-fixture-headless.sh` wrapper.
3. Add GitHub Actions workflow `.github/workflows/fixture-smoke.yml` that runs on `release/*` branches (not every PR) with a 25-USD budget cap.
4. Flip all 7 pending snapshots to active by running the wrapper on each fixture.
5. Document observed cost per fixture in `docs/CI.md`.

If the POC shows Phase 2 is infeasible (unknown SDK limitation, prohibitive cost), document it honestly in this file and close the "automate behavioural tier" goal. The fallback is Phase 1 forever, which is already a large improvement over the pre-v1.15.0 status quo.
