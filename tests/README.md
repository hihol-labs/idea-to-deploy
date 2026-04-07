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

## Running fixtures

The fixtures are **manual** for now — no CI integration yet. To run a fixture against the current methodology:

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

## Future: automated runs

To make this CI-friendly, we'd need:
- A way to invoke `/kickstart` non-interactively (Claude Code SDK?)
- A way to feed clarifying-question answers from a file
- A way to capture the rubric output programmatically

These don't exist as of v1.2.0 — this is on the roadmap. For now, fixtures are run manually before each release.
