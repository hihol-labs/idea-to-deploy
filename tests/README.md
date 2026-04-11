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

The methodology has **two tiers** of testing:

1. **Structural gate (automated, CI-blocking).** `tests/meta_review.py` runs on every PR via [.github/workflows/meta-review.yml](../.github/workflows/meta-review.yml). It verifies version badges, skill count, SKILL.md frontmatter, trigger-phrase drift between `skills/` and `hooks/check-skills.sh`, marketplace.json consistency, and other invariants. A PR with any Critical drift is blocked. See [docs/CI.md](../docs/CI.md) for the full list of checks.

2. **Behavioural smoke-runs (manual, release-time).** The `fixtures/` below exercise **LLM behaviour** — did `/kickstart` ask the right clarifying questions, did `/review` correctly flag a dud plan, did `/infra` produce a Terraform module that actually deploys. These outputs are non-deterministic by model, so they cannot be diffed against a golden file (would break on every model upgrade). They are run **by the maintainer on each release** before tagging. See [Future: automated behavioural tests](#future-automated-behavioural-tests) below for the options under consideration.

## Running fixtures

To run a fixture against the current methodology:

```bash
cd tests/fixtures/fixture-01-saas-clinic
mkdir output && cd output
# Copy the idea into Claude Code:
cat ../idea.md
# Then in Claude: /project   (and follow the prompts)
# Or: /kickstart {paste idea}

# After completion, verify:
diff <(ls -1) ../expected-files.txt
cat ../notes.md  # manual verification checklist
```

A fixture passes if:
1. All files in `expected-files.txt` exist in `output/`
2. All Critical rubric checks in the generated docs pass (`/review` returns `PASSED` or `PASSED_WITH_WARNINGS`)
3. The notes.md manual checklist items are satisfied

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

## Future: automated behavioural tests

The structural gate (`meta_review.py`) already runs in CI on every PR. What remains manual is the **behavioural** side — did `/kickstart` actually produce the right output on a known idea? Three paths to automation, each with tradeoffs:

1. **LLM-as-judge in a nightly workflow.** A separate GitHub Actions workflow (not blocking PRs) that runs Claude Code non-interactively via the SDK on each fixture, then asks a judge model to score the output against `notes.md`. Costs API credits per run, flaky, but captures real regressions. Candidate for v1.15.0.
2. **Snapshot diffing with tolerance.** Freeze a "good" output per fixture, diff structural markers (file list, section headings, rubric status). Tight enough to catch breakage, loose enough to survive minor model drift. Breaks hard on major model upgrades (Opus 4.6 → 5.0). Candidate for v1.14.0.
3. **Schema-only validation.** Just assert that generated docs match expected schemas (PRD has user stories, ARCHITECTURE has DB section, etc.). No judgement, just presence. Cheap, deterministic, partial coverage. Could be added to `meta_review.py` directly.

Until one of these lands, fixtures are run by the maintainer before each release tag. The structural gate in CI catches the bulk of regressions; the behavioural tier catches the long tail.
