# Meta-Review Checklist (for the methodology repo itself)

> Used when `/review --self` runs on a repository whose `.claude-plugin/plugin.json` declares `name: idea-to-deploy` (or a fork with the same structure). This is a **different** rubric from `review-checklist.md` — that one audits user projects, this one audits the methodology that audits user projects.
>
> Same tier semantics: Critical failure → `BLOCKED`, Important → `PASSED_WITH_WARNINGS`, Nice-to-have → `PASSED`.

## Tier 1: Critical (every failure blocks the release)

### M-C1. Every skill has a SKILL.md with required frontmatter
**Criterion:** for each subdirectory of `skills/`, a `SKILL.md` file exists with at least the following frontmatter fields: `name`, `description`, `license`, `metadata.version`, `metadata.category`. No frontmatter OR missing required field → fail.

### M-C2. Every skill that references `references/` has a non-empty `references/` folder
**Criterion:** for each `skills/<name>/SKILL.md` whose body contains the string `references/`, the `skills/<name>/references/` folder exists AND contains at least one file.
**Rationale:** this is the exact failure mode from v1.4.0. The release hook and this check are two layers of defense against it happening again.

### M-C3. Every model-invocable skill has trigger phrases in `hooks/check-skills.sh`
**Criterion:** for each `skills/<name>/SKILL.md` whose frontmatter does NOT set `disable-model-invocation: true`, the file `hooks/check-skills.sh` contains the literal string `/<name>` somewhere in the hint text. Skills with `disable-model-invocation: true` are exempt.

### M-C4. Every skill has at least one regression fixture
**Criterion:** for each `skills/<name>/`, at least one `tests/fixtures/fixture-*-<name>*/` directory exists. Skills may legitimately share fixtures (e.g., `/kickstart` shares with `/blueprint`), but **every skill name must be mentioned in at least one fixture directory name OR inside at least one fixture's `notes.md`**.

### M-C5. Version consistency across all declaration sites
**Criterion:** `plugin.json` version matches all of:
1. `README.md` version badge (`Version: X.Y.Z`)
2. `README.ru.md` version badge
3. The most recent `[X.Y.Z]` header in `CHANGELOG.md`
4. (Informational) Optionally, individual skill `metadata.version` fields — these may lag the plugin version legitimately (skill versioning is per-skill).
If any of 1–3 disagree → fail.

### M-C6. CHANGELOG has an entry for the current plugin version
**Criterion:** `CHANGELOG.md` contains a `## [X.Y.Z]` header where `X.Y.Z` equals `plugin.json#version`. No entry → fail.

### M-C7. README badges match reality
**Criterion:** `Skills: N` badge in both READMEs matches `ls skills/ | wc -l`. `Agents: N` badge matches `ls agents/ | wc -l`. Mismatch → fail.

### M-C8. Every skill has a Troubleshooting section
**Criterion:** every `skills/*/SKILL.md` body contains a `## Troubleshooting` heading. This was enforced in v1.3.1 for the 13 skills that existed at that time, extended to all 16 skills in v1.4.0+, and should hold for all future additions.

### M-C9. No skill file has been Write'n in the current working state without its supporting artifacts on disk
**Criterion:** git-staged `skills/*/SKILL.md` → matching `references/` (if referenced in body), trigger in hook, fixture in tests/fixtures — all staged OR already committed. This mirrors the `check-commit-completeness.sh` hook logic; the meta-review runs the same check so the state can be audited without committing.

### M-C10. Every hook uses the JSON schema and exit code semantics matching its declared event type
**Added in v1.6.0 — closes the v1.5.0 blind spot.**

**Criterion (binary, static analysis):** for each file under `hooks/*.sh` (all four hooks are Python despite the `.sh` extension), read the file and verify:

1. **Declared event type** — the file contains exactly one `"hookEventName"` string literal (in an emit function or JSON dict). That literal is the declared event.
2. **Field location matches event** — the JSON output structure matches Anthropic's hook-event-specific schema per [the hooks reference](https://code.claude.com/docs/en/hooks.md):

| Event | Blocking exit code | Decision field location | Allowed decision values | Reason field |
|---|---|---|---|---|
| `PreToolUse` | 2 (blocks tool) | `hookSpecificOutput.permissionDecision` | `allow`, `deny`, `ask`, `defer` | `hookSpecificOutput.permissionDecisionReason` |
| `PostToolUse` | **Non-blocking** — tool already ran | root `decision` (feedback only) | `block` | root `reason` |
| `UserPromptSubmit` | 2 (rejects prompt) | root `decision` (optional) | `block` | root `reason`, plus `hookSpecificOutput.additionalContext` allowed |
| `Stop` / `SubagentStop` | 2 (prevents stop) | root `decision` (optional) | `block` | root `reason` |
| `Notification` | — | — | — | `hookSpecificOutput.additionalContext` |
| `PreCompact` / `SessionStart` | — | — | — | `hookSpecificOutput.additionalContext` |

3. **Anti-patterns that MUST fail M-C10:**
   - A `PostToolUse` hook whose **docstring or comments claim to "prevent", "block the tool call", or "stop the write from landing on disk"**. Per spec, PostToolUse runs AFTER the tool result is produced — its `decision: "block"` only feeds the reason back to Claude, it cannot undo the effect. If that's the desired behavior, the hook belongs in `PreToolUse`.
   - A `PreToolUse` hook that emits a **root-level `decision` field** instead of `hookSpecificOutput.permissionDecision`. The root-level field belongs to `PostToolUse` schema; in `PreToolUse` it is silently dropped by the schema validator.
   - A `PreToolUse` hook that emits `permissionDecision` with a value outside `{allow, deny, ask, defer}`.
   - Any hook that declares one `hookEventName` literal but uses field names from a different event's schema.

4. **Verification procedure** (runnable as a Python script inside the meta-review):
   ```python
   import re
   from pathlib import Path

   EVENTS = {
       "PreToolUse": {
           "decision_path": "hookSpecificOutput.permissionDecision",
           "root_decision_forbidden": True,
           "may_block": True,
       },
       "PostToolUse": {
           "decision_path": "root.decision",
           "root_decision_forbidden": False,
           "may_block": False,  # tool already ran
       },
       "UserPromptSubmit": {
           "decision_path": "root.decision",
           "root_decision_forbidden": False,
           "may_block": True,  # blocks prompt
       },
       "Stop": {"decision_path": "root.decision", "root_decision_forbidden": False, "may_block": True},
       "SubagentStop": {"decision_path": "root.decision", "root_decision_forbidden": False, "may_block": True},
       "Notification": {"decision_path": None, "root_decision_forbidden": True, "may_block": False},
       "PreCompact": {"decision_path": None, "root_decision_forbidden": True, "may_block": False},
       "SessionStart": {"decision_path": None, "root_decision_forbidden": True, "may_block": False},
   }

   def check_hook(path: Path) -> list[str]:
       text = path.read_text()
       errors = []
       events = re.findall(r'"hookEventName"\s*:\s*"([A-Za-z]+)"', text)
       events = list(set(events))
       if len(events) != 1:
           errors.append(f"{path.name}: declares {len(events)} event types, expected exactly 1")
           return errors
       event = events[0]
       if event not in EVENTS:
           errors.append(f"{path.name}: unknown event '{event}'")
           return errors
       spec = EVENTS[event]
       has_perm_decision = "permissionDecision" in text
       # Root-level decision: line starts with "decision" inside a dict literal, NOT inside hookSpecificOutput
       # Heuristic: find every `"decision"` string that is NOT preceded by permissionDecision in the same block.
       root_dec = bool(re.search(r'(?<!permission)[\'"]decision[\'"]\s*:', text))
       if event == "PreToolUse":
           if not has_perm_decision and ("decision" in text):
               errors.append(
                   f"{path.name} ({event}): uses top-level 'decision' — should be "
                   f"hookSpecificOutput.permissionDecision per Anthropic spec"
               )
       if event == "PostToolUse":
           # Spec anti-pattern: PostToolUse claiming to block the tool
           if re.search(r"block(s)?\s+(the\s+)?(tool|write|call|edit)", text, re.IGNORECASE):
               # Check if there's a disclaimer acknowledging non-blocking behavior
               if not re.search(r"non-?blocking|already\s+ran|cannot\s+undo", text, re.IGNORECASE):
                   errors.append(
                       f"{path.name} ({event}): docstring claims to block the tool, "
                       f"but PostToolUse exit 2 is non-blocking per spec"
                   )
       return errors
   ```

**Action on fail:** move the hook to the correct event (usually `PostToolUse` → `PreToolUse` if the goal is prevention) AND fix the JSON field path. Both fixes together — one without the other is still broken. See v1.5.1 commit for a worked example.

**Why this check exists:** v1.5.0 shipped two hooks — `check-skill-completeness.sh` (PostToolUse with `decision: "block"`, advertised as hard-blocking) and `check-commit-completeness.sh` (PreToolUse with root-level `decision: "deny"`). Both were wrong per Anthropic's spec. Neither was caught by the v1.5.0 meta-review because the rubric checked structural completeness (hook exists, references correct event name), not spec compliance (field paths, exit code semantics per event). v1.6.0 adds M-C10 so the next hook-related mistake cannot repeat the same blind spot.

### M-C12. Skill and agent counts in user-facing prose must match reality
**Added in v1.9.0 — closes the v1.4.0 → v1.8.1 "stale narrative count" drift class.**

**Criterion (binary, static analysis):** for each user-facing documentation file, scan narrative prose for hardcoded skill-count or agent-count numbers and verify they match `ls skills/ | wc -l` and `ls agents/*.md | wc -l` respectively.

**Scope — scanned files:**
- `README.md`
- `README.ru.md`
- `CONTRIBUTING.md`
- `hooks/README.md`
- `docs/**/*.md`

**Scope — deliberately NOT scanned:**
- `CHANGELOG.md` — historical entries legitimately reference past counts.
- `skills/*/SKILL.md` — skill bodies mention small numbers in examples that would produce many false positives.
- `skills/review/references/*.md` — rubric documentation may legitimately reference historical counts for context.

**Skipped lines (even within scanned files):**
- Markdown table rows (start with `|`) — tables are the authoritative per-row count, not prose.
- Markdown headings (start with `#`) — headings legitimately list category subtotals like `### Project Creation (3 skills)`.
- Lines with version markers (`v\d+\.\d+`) or historical phrases (`at that time`, `existed at`, `era`, `legacy`, `initially`, `was enforced`, `изначально`, `тогда существовал`, `на момент`).

**Patterns caught:**
1. **Direct count:** `\d+ skills?`, `\d+ skill directories`, `\d+ скиллов` — with a hyphen guard `(?<!\S)` to avoid false positives on qualifiers like `depth-3 skills`.
2. **Contextual count:** `existing N` / `current N` / `существующих N` — only fires when the same line also mentions `skill` / `скилл`. This catches phrases like "the existing 13" that escape pattern 1.
3. **Direct agent count:** `\d+ agents?`, `\d+ subagents?`, `\d+ агентов`, `\d+ субагентов` — same hyphen guard.

**Failure mode:** every finding is Critical. A prose sentence saying "registers 13 skills" when there are 16 is user-visible wrongness that hurts trust.

**Verification:** implemented inline in `tests/meta_review.py` under the `--- M-C12 ---` block.

**Action on fail:** update the prose to the correct count. Do not work around the check by adding `v\d+\.\d+` version markers to hide drift — that defeats the purpose.

**Why this check exists:** the v1.4.0 → v1.5.0 → v1.6.0 → v1.7.0 → v1.8.0 sequence bumped the skill count from 13 to 16 in badges, tables, the call graph, and the Skill Contracts section — but left 5 narrative sentences saying "13 skills". The user caught the first 3 in v1.8.1 by direct inspection. The remaining 2 (the `existing 13` phrasing in Contributing) escaped because the initial ad-hoc grep pattern only matched `\d+\s+(skill|скилл)`, not `existing \d+`. M-C12 generalizes the check so no future count bump silently drifts narrative prose. Catches the class of bug structurally instead of reactively.

### M-C11. Every canonical trigger phrase in a `SKILL.md` body routes to the right skill via `hooks/check-skills.sh`
**Added in v1.7.0 — closes the v1.4.0 drift-class of bug.**

**Criterion (binary):** for each `skills/<name>/SKILL.md` whose frontmatter does NOT set `disable-model-invocation: true`:

1. Extract the list of trigger phrases from the `## Trigger phrases` section (bullet lines, comma-separated). Filter out:
   - Meta-descriptions (lines starting with `любой`, `любая`, `автоматически`, `перед любым`, `есть документация`, `нужны`, `multi-file`, `see`, `full list`, etc.)
   - Lines with more than 6 words (descriptions, not literal phrases)
   - Backtick code spans and URLs
2. For each remaining canonical phrase, scan the `TRIGGERS` list in `hooks/check-skills.sh` and verify that at least one regex matches the phrase AND the matched hint text mentions `/<skill-name>`.

**Failure modes:**
- `unmatched` — the phrase exists in the SKILL.md body but no regex in the hook matches it. Drift.
- `wrong-route` — the phrase matches a regex, but the hint routes to a different skill. Cross-wired.
- `no-trigger-section` — the SKILL.md has no `## Trigger phrases` section at all (Important warning, not Critical — some legacy skills may still be missing it).

**Verification script:** `tests/verify_triggers.py` (added in v1.7.0). Runs as part of the meta-review via subprocess. Invoke standalone with `python3 tests/verify_triggers.py` — exits 0 on no drift, 1 on drift, 2 on internal error. Output can be JSON (`--json`) or human-readable.

**Action on fail:** either (a) add the missing phrase to the corresponding regex in `hooks/check-skills.sh`, OR (b) remove the phrase from the SKILL.md body if it's not actually a literal user input. The SKILL.md body is treated as the canonical source of truth — if it's listed there as a trigger, the hook must route it correctly.

**Why this check exists:** throughout v1.2.0–v1.6.1 the SKILL.md `## Trigger phrases` sections drifted from `hooks/check-skills.sh`. Phrases listed in bodies were never matched by hook regex (or matched the wrong one), and nothing caught it until users reported missing hints or a smoke-test caught one by accident (the v1.4.0 "provision ec2 instance" miss). v1.7.0 runs the verifier on every meta-review; the initial run against v1.6.1 found 111 drift findings that had accumulated silently over 5 minor releases. v1.7.0 closes all 111 as part of the release — see the CHANGELOG [1.7.0] entry for the fix breakdown.

---

## Tier 2: Important (warn but pass)

### M-I1. Every skill has a `## Recommended model` section in its body
**Criterion:** the body contains a `## Recommended model` heading explaining which Claude model is recommended and why.

### M-I2. Every skill has an `## Examples` section with at least 2 examples
**Criterion:** `## Examples` heading AND at least 2 `### Example N:` subheadings.

### M-I3. Every skill declares `allowed-tools` in frontmatter (least-privilege)
**Criterion:** frontmatter `allowed-tools` field is present and non-empty. Skills that need the full tool set can declare it explicitly, but the field must exist.

### M-I4. README Skill Contracts table covers every skill
**Criterion:** for each `skills/<name>/`, the Skill Contracts table in `README.md` has a row starting with `` `/<name>` ``. Missing row → warn.

### M-I5. README Recommended Models table covers every skill
**Criterion:** for each `skills/<name>/`, the Recommended Models table has a row.

### M-I6. Call Graph mentions every skill
**Criterion:** the Call Graph code block in README mentions every `/<name>` at least once. Leaf skills like `/debug` may be listed as "leaf skills".

### M-I7. `hooks/check-skills.sh` triggers pass a smoke test
**Criterion:** for each skill with triggers, at least one representative Russian and English phrase actually matches via the hook's regex. The meta-review runs a synthetic smoke test by constructing `{"prompt":"<phrase>"}`, feeding it to the hook, and checking the skill name appears in `additionalContext`.

### M-I8. CHANGELOG entries use Keep-a-Changelog sections
**Criterion:** the most recent CHANGELOG entry has at least one of: `### Added`, `### Changed`, `### Fixed`, `### Removed`, `### Security`.

---

## Tier 3: Nice-to-have (informational)

### M-N1. Every skill body mentions its version in a comment or metadata
**Criterion:** informational.

### M-N2. README Russian and English versions have the same line count ±10%
**Criterion:** rough sync check — drift is normal but a 30% divergence suggests one language is falling behind.

### M-N3. `tests/run-fixtures.sh` mentions every fixture name
**Criterion:** informational.

### M-N4. No skill is longer than 1000 lines of markdown
**Criterion:** informational — past 1000 lines a skill should probably split into sub-skills.

---

## Reporting format

Same as the standard `/review` rubric — tier-by-tier list with ✅/❌/⚠️/ℹ️, summary table, final status, and (for self-review) a "Suggested fixes" section that is specifically tied to the self-hosted enforcement:

```markdown
## /review --self report

### Tier 1: Critical
- ✅ M-C1: every skill has SKILL.md frontmatter
- ❌ M-C2: skill /foo references `references/` but the folder is empty
       → write skills/foo/references/foo-checklist.md before next commit
- ...

### Summary
| Tier | Pass | Total | Status |
|---|---|---|---|
| Critical | 11 | 12 | ❌ BLOCKED |
| Important | 6 | 8 | ⚠️ |
| Nice-to-have | 3 | 4 | ℹ️ |

**Final status:** BLOCKED
**Must fix before commit:**
1. [M-C2] skills/foo/references/foo-checklist.md
```

> **v1.6.0 note:** the Critical tier grew from 9 to 10 checks with the addition of M-C10 (hook schema compliance). All 4 hooks in the v1.6.0 methodology repo pass M-C10; the check was validated on the v1.5.1 post-fix state before being merged into the rubric.
>
> **v1.7.0 note:** the Critical tier grew from 10 to 11 with the addition of M-C11 (trigger drift). The initial run against v1.6.1 caught 111 drift findings — all fixed as part of the v1.7.0 release before the check was merged into the rubric. v1.7.0 is the first release to pass M-C11 cleanly.
>
> **v1.9.0 note:** the Critical tier grew from 11 to 12 with the addition of M-C12 (prose count drift). The initial run against v1.8.1 caught 2 remaining `existing 13` references that had survived the v1.8.1 spot-fix because the user's ad-hoc grep pattern was narrower than M-C12's. Also caught 12 false-positive category-subtotal matches in headings (e.g., `### Project Creation (3 skills)`) and 2 false positives on hyphenated qualifiers (`depth-3 skills`) — both false-positive classes were closed by adding heading-skip and hyphen-guard to the check before merging it into the rubric. v1.9.0 is the first release to pass M-C12 cleanly.

When `check-commit-completeness.sh` is active (recommended in the methodology repo), any Critical failure here will also block the next `git commit` — there is no path to shipping a broken release short of the documented override file.
