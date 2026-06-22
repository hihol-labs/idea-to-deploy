# Manual verification — fixture 18 (/handoff)

`/handoff` writes a **compact context packet** (`HANDOFF.md`) to transfer work
from one session/agent to the next when there is no return path. This fixture
regressionally fixes the 9-field contract and the `/handoff` vs `/session-save`
distinction.

## Fixture status

`pending` — **deferred**, same bucket as `fixture-15-advisor`. Phase 1
`verify_snapshot.py` is file-presence-shaped; field-level validation of
`HANDOFF.md` needs the Phase 2 artifact-snapshot scheme. For now: manual
checklist below. The stub satisfies `check-skill-completeness.sh`.

## /handoff — Scenario A: planning → implementation, pre-compaction (happy path)

User pastes the prompt from `idea.md`: session is compacting, transfer auth
context to the next session.

### Critical contract: HANDOFF.md produced with 9 fields
- [ ] `HANDOFF.md` exists in project root after the run
- [ ] Field 1 — **From → To** roles present (e.g. `planner → implementer`)
- [ ] Field 2 — **Reason** present (compaction)
- [ ] Field 3 — **Current state** (node/unit, done, in-progress) present
- [ ] Field 4 — **Final decisions only** (no chat-history retelling)
- [ ] Field 5 — **Required inputs** present (links to [[STATE]], [[BUILD_PLAN]], etc.)
- [ ] Field 6 — **Write areas + forbidden changes** present
- [ ] Field 7 — **Verification commands** present (runnable)
- [ ] Field 8 — **Blockers and risks** present
- [ ] Field 9 — **First action** is ONE concrete command/step in a `> [!todo]` callout

### Obsidian compatibility
- [ ] Frontmatter with project/stage/roles
- [ ] Wikilinks to artifacts (`[[STATE]]`, `[[BUILD_PLAN]]`)
- [ ] Risks/blockers in `> [!warning]` callout

### Guard rails
- [ ] NO secrets / keys / tokens written into HANDOFF.md
- [ ] Does NOT modify source code (it transfers context, not work)
- [ ] Compact enough to be the first thing a fresh session reads

## /handoff — Scenario B: confused with /session-save (edge case)

User says: «сохрани сессию» (milestone done, no next actor).

- [ ] Skill recognizes this is a **milestone save**, not a transfer
- [ ] Redirects: «Похоже на завершение вехи — используй `/session-save`.
      `/handoff` нужен для передачи перед стартом следующего актора.»

## /handoff — Scenario C: delegation to another agent/AFK run

User says: «передай контекст агенту, он продолжит ночью».

- [ ] HANDOFF.md is self-contained — no reliance on this chat
- [ ] First action is unambiguous (a fresh agent can act cold)
- [ ] Required inputs list every artifact the receiver must read

## Cross-reference with `check-skill-completeness.sh`

`/handoff` satisfies the three Quality Gate 2 requirements:

1. ✅ `skills/handoff/references/` exists (handoff-checklist.md)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/handoff`
3. ✅ `tests/fixtures/fixture-18-handoff/` exists with `idea.md`, `notes.md`,
   `expected-files.txt`, `expected-snapshot.json`

## Run manually

1. `cd tests/fixtures/fixture-18-handoff/`
2. `mkdir -p output && cd output`
3. Start Claude Code, paste `idea.md` content, invoke `/handoff`
4. Verify `HANDOFF.md` appears with all 9 fields (checklist above)
5. `cd .. && python3 ../../verify_snapshot.py .` — expected: `⏸️ fixture-18-handoff: PENDING`

## Failures (fill in if any)

(empty unless the fixture fails — especially any secret leaked into HANDOFF.md
or any source-code modification in violation of the transfer-only contract)
