# Three-Tier Testing for LLM Methodologies: How We Test a Claude Code Plugin

- **Platform:** Dev.to
- **Target length:** ~2000 words
- **Tags:** #ai, #testing, #claudecode, #opensource, #devtools
- **Hook:** How do you test a methodology that runs inside an LLM? We built three tiers of automated testing -- and each tier catches bugs the others miss.
- **CTA:** The full test suite and plugin are MIT-licensed at https://github.com/HiH-DimaN/idea-to-deploy. PRs and feedback welcome.

---

## Three-Tier Testing for LLM Methodologies: How We Test a Claude Code Plugin

How do you test a methodology that runs inside an LLM? We built three tiers of automated testing -- and each tier catches bugs the others miss.

### The problem

idea-to-deploy is a Claude Code plugin with 20 skills and 7 subagents. It provides structured workflows for the full project lifecycle: from initial idea through architecture, coding, testing, review, and deployment.

The challenge: the "code" is mostly markdown. Skills are prompt templates with structured sections. Subagents are markdown files describing agent roles. There are no functions to unit-test in the traditional sense.

But there is plenty to break:
- Version badges can drift from `plugin.json`
- Skill counts in README headings can diverge from actual skill directories
- Trigger phrases in hooks can miss newly added skills
- Table rows can silently lose entries across 20+ PRs
- Generated output from skills can silently regress in structure

We needed testing that catches all of these. We ended up with three tiers.

### Tier 1: Structural meta-review (CI-blocking)

`tests/meta_review.py` is a Python script that runs 25+ checks against the repository's working tree. It runs on every PR via GitHub Actions and blocks merging on any Critical failure.

Here is what it checks:

**Version consistency (M-C1, M-C2, M-C3):**
```python
# Simplified from actual implementation
plugin_version = json.load(open("plugin.json"))["version"]
readme_badge = re.search(r'Version-(.+?)-purple', readme_text).group(1)
assert plugin_version == readme_badge, f"Badge drift: {readme_badge} != {plugin_version}"
```

**Skill count integrity (M-C7):**
```python
skill_dirs = [p for p in Path("skills/").iterdir()
              if p.is_dir() and not p.name.startswith("_")]
badge_count = int(re.search(r'Skills-(\d+)-green', readme_text).group(1))
assert len(skill_dirs) == badge_count
```

**Trigger phrase coverage (M-I7):**

Each skill has trigger phrases (both Russian and English) that should fire the routing hook. The check verifies that every skill has at least one trigger phrase registered, and that the hook script references all skills.

```python
SMOKE_TRIGGERS = [
    ("new project", "project"),
    ("fix bug", "bugfix"),
    ("write tests", "test"),
    ("refactor this", "refactor"),
    # ... 20 skills, 2+ phrases each
]
for phrase, expected_skill in SMOKE_TRIGGERS:
    assert expected_skill in hook_script, f"Missing trigger for {expected_skill}"
```

**Table integrity (M-C16):**

This is the newest gate, added after a user counted skills in category headings and found "Operations (4 skills)" with only 3 table rows. It has two modes:

Mode A: Parse `### Category (N skills)` headings, count table rows below, verify N equals row count.

Mode B: For each comprehensive table (Skill Contracts, Recommended Models, and their Russian equivalents), verify the set of `/skill-name` entries equals the set of skill directories.

```python
# Mode A: category subtotals
for heading_match in re.finditer(r'### .+ \((\d+) skills?\)', readme_text):
    declared = int(heading_match.group(1))
    table_rows = count_table_rows_after(heading_match.end())
    assert declared == table_rows, f"Subtotal drift: {declared} declared, {table_rows} rows"
```

**What Tier 1 catches:** metadata drift, count mismatches, missing entries, version desync, structural inconsistencies.

**What Tier 1 misses:** whether the skills actually produce correct output when run.

### Tier 2: Snapshot validation (deterministic, local)

`tests/verify_snapshot.py` validates generated output against a machine-readable contract. Each fixture has an `expected-snapshot.json` that declares:

```json
{
  "$schema_version": "1.0",
  "fixture_type": "kickstart-full",
  "skill_under_test": "/kickstart",
  "status": "active",
  "files": {
    "required": ["STRATEGIC_PLAN.md", "PROJECT_ARCHITECTURE.md", "PRD.md"],
    "min_count": 7
  },
  "content_contracts": {
    "STRATEGIC_PLAN.md": {
      "required_sections": ["Competitors|Competitors"],
      "min_length_chars": 800,
      "must_contain_any_of": {
        "competitors_named": ["MEDODS", "IDENT"]
      }
    },
    "PROJECT_ARCHITECTURE.md": {
      "min_api_endpoints": 15,
      "min_user_story_count": 8
    }
  }
}
```

The validator checks:

1. **Required files exist** -- catches "forgot to generate CLAUDE.md" regressions
2. **Required sections present** -- catches "renamed ## Budget to ## Finances" regressions (uses pipe-separated bilingual patterns like `"Budget|Budget"`)
3. **Content markers** -- catches "generated generic text ignoring the user's domain" (a common LLM failure mode)
4. **Count constraints** -- catches "generated 3 API endpoints for a 6-table SaaS"

```python
# Section matching with bilingual support
def section_matches(sections: list[str], pattern: str) -> bool:
    alternatives = [alt.strip().lower() for alt in pattern.split("|")]
    return any(
        any(alt in heading.lower() for alt in alternatives)
        for heading in sections
    )
```

The contracts are deliberately loose -- pattern matching instead of exact strings, minimums instead of exact counts. This accommodates LLM non-determinism while still catching structural regressions.

**What Tier 2 catches:** output structure regressions, missing files, dropped sections, content that ignores the user's domain, count regressions.

**What Tier 2 misses:** it requires someone to produce the output first. The snapshot validates structure, not generation.

### Tier 3: Behavioural execution (headless Claude Code)

This is the tier that closes the loop. `tests/run-fixture-headless.sh` runs Claude Code non-interactively:

```bash
claude -p \
  --input-format stream-json \
  --output-format stream-json \
  --verbose \
  --no-session-persistence \
  --model sonnet \
  --dangerously-skip-permissions \
  --add-dir ./output \
  --max-budget-usd 10.00 \
  < fixture.jsonl
```

Each fixture has a `stream.jsonl` file with the full prompt and pre-seeded answers to clarifying questions:

```json
{"type":"user","message":{"role":"user","content":"/blueprint Build a Telegram bot for clinic appointments\n\nPre-emptive clarifications:\n1. Users: patients and staff\n2. Auth: Telegram built-in\n...\n\nIMPORTANT: do NOT ask further clarifying questions."}}
```

The runner:
1. Creates a clean output directory
2. Pipes the JSONL into `claude -p`
3. Waits for completion (10-20 minutes per fixture)
4. Runs `verify_snapshot.py` on the generated output
5. Reports pass/fail, cleans up on pass

**Observed costs (Sonnet equivalent pricing):**

| Fixture | Skill | Duration | Cost |
|---|---|---|---|
| Telegram bot | `/blueprint` Lite | ~10 min | $1.73 |
| SaaS clinic | `/kickstart` Full | ~20 min | $5-8 |
| CLI tool | `/blueprint` no-DB | ~8 min | $1.50 |

**What Tier 3 catches:** actual generation regressions, model behaviour changes, prompt template bugs, skill interaction issues.

**What Tier 3 misses:** non-deterministic failures (the same fixture can pass or fail depending on model randomness). We handle this by running on release branches only, not every PR, and accepting that some runs need manual triage.

### How the tiers interact

The three tiers form a pyramid:

```
        /\
       /  \   Tier 3: Behavioural (expensive, slow, catches generation bugs)
      /    \  Runs on release branches. $2-8 per fixture, 10-20 min each.
     /------\
    /        \ Tier 2: Snapshot (free, fast, catches structure regressions)
   /          \ Runs locally on demand. 0 API cost, <1 second.
  /------------\
 /              \ Tier 1: Structural (free, fast, catches metadata drift)
/________________\ Runs on every PR in CI. 0 API cost, ~5 seconds.
```

Each tier assumes the ones below it pass. Tier 3 is pointless if Tier 1 is failing (your badges are wrong, fix that first). Tier 2 is pointless without output to validate.

The self-improvement loop operates primarily at Tier 1: a human notices a drift, we add a meta-review gate, and that drift class is permanently covered. In the v1.13.2 to v1.17.0 series, 4 human observations produced 5 new Critical gates.

### Lessons learned

**1. Loose contracts beat exact matches for LLM output.**

Early snapshot contracts tried exact section heading matches. They broke every time the model rephrased a heading. Pattern matching with alternatives (`"Budget|Finances|Cost"`) and minimum counts (`min_api_endpoints: 15`) are far more stable.

**2. Structural testing finds more bugs per dollar than behavioural testing.**

Our 25+ meta-review gates have caught dozens of drifts at $0 cost. Behavioural testing costs $2-8 per run and often passes even when there are real issues (because the contracts are loose). Invest in structural testing first.

**3. The self-improvement loop is the real product.**

The individual gates are not that impressive. What is impressive is the pattern: human spots drift, we trace why existing gates missed it, we add a gate, the class is permanently covered. After 4 cycles, the marginal cost of adding a gate is ~100 lines of Python and the marginal benefit is permanent coverage.

**4. Headless LLM testing is possible but immature.**

The `claude -p` flags work but the documentation is sparse. We discovered most gotchas through experimentation (stream-json requires --verbose, --dangerously-skip-permissions causes hangs without it, rate limits do not terminate runs). Expect to spend time on tooling before you spend time on tests.

### Try it

The full test suite and plugin are MIT-licensed at https://github.com/HiH-DimaN/idea-to-deploy.

Key files:
- `tests/meta_review.py` -- Tier 1 structural gates (25+ checks)
- `tests/verify_snapshot.py` -- Tier 2 snapshot validator
- `tests/run-fixture-headless.sh` -- Tier 3 headless runner
- `tests/README.md` -- full documentation of the testing approach

PRs and feedback welcome -- especially if you have found better patterns for testing LLM-based tooling.
