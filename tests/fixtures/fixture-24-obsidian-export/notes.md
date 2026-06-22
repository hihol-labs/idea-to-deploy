# Manual verification — fixture 24 (/obsidian-export)

`/obsidian-export` generates a **derived, regenerable** Obsidian knowledge layer
from canonical idea-to-deploy artifacts. This fixture regressionally fixes the
derived-output contract (canon untouched), the no-secrets guard, and the
regenerability rule.

## Fixture status

`pending` — **deferred**, same bucket as `fixture-15-advisor` (generated output +
stdout). For now: manual checklist below. The stub satisfies
`check-skill-completeness.sh`.

## /obsidian-export — Scenario A: generate knowledge graph (happy path)

User pastes the prompt from `idea.md`: build an Obsidian knowledge graph from
planning docs + memory; don't touch canon; output must be regenerable.

### Adoption + source
- [ ] Adoption confirmed (`CLAUDE.md`, memory dir with `STATE.json`)
- [ ] Source artifacts read (LAUNCH_PLAN.md, BACKLOG.md, STATE.json, HANDOFF.md, ...)

### Generated note set (under `.itd-integrations/obsidian/`)
- [ ] `PROJECT_INDEX.md` (entrypoint)
- [ ] `KNOWLEDGE_GRAPH.md`
- [ ] `STATE.md`, `DECISIONS.md`, `GATES.md`
- [ ] Copied planning + memory notes for existing source artifacts

### Obsidian markdown
- [ ] `[[wikilinks]]` between generated notes
- [ ] `![[KNOWLEDGE_GRAPH]]` embedded in `PROJECT_INDEX.md`
- [ ] Callouts for next action / blockers / risks
- [ ] Frontmatter tags `itd/project`, `itd/planning`, `itd/memory`, `itd/graph`

### Guard rails
- [ ] Canonical source docs NOT modified
- [ ] NO secrets / credentials / private data / prod dumps in the export
- [ ] If a real external vault path is given — asks before writing outside project

### Output shape (stdout)
- [ ] OBSIDIAN EXPORT / ENTRYPOINT / NOTES / SOURCE ARTIFACTS /
      REGENERATE COMMAND / NEXT ACTION

## /obsidian-export — Scenario B: regenerate after canon edit

User edits `LAUNCH_PLAN.md`, then re-runs `/obsidian-export`.

- [ ] Export regenerated from updated source (no hand-edits to generated notes)
- [ ] Generated notes reflect the canon change

## Cross-reference with `check-skill-completeness.sh`

1. ✅ `skills/obsidian-export/references/` exists (obsidian-export-checklist.md)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/obsidian-export`
3. ✅ `tests/fixtures/fixture-24-obsidian-export/` exists with `idea.md`,
   `notes.md`, `expected-files.txt`, `expected-snapshot.json`

## Run manually

1. `cd tests/fixtures/fixture-24-obsidian-export/`
2. `mkdir -p output && cd output`
3. Start Claude Code, paste `idea.md` content, invoke `/obsidian-export`
4. Verify the checklist above; confirm canon docs untouched
5. `cd .. && python3 ../../verify_snapshot.py .` — expected: `⏸️ fixture-24-obsidian-export: PENDING`

## Failures (fill in if any)

(empty unless the fixture fails — especially any canonical doc modified or a
secret written into the export)
