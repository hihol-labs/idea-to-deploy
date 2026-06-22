# Manual verification — fixture 21 (/mcp-docs)

`/mcp-docs` is a **read-only** lookup of fresh library/framework documentation
via MCP providers (Context7). It resolves a library ID, asks a narrow question,
records the source + decision, and prints a structured summary. It MUST NOT
modify project files. This fixture regressionally fixes the read-only contract,
the no-secrets guard, the MCP-unavailable fallback, and repo-convention precedence.

## Fixture status

`pending` — **deferred**, same bucket as `fixture-15-advisor` (read-only,
external MCP tool + stdout). For now: manual checklist below. The stub satisfies
`check-skill-completeness.sh`.

## /mcp-docs — Scenario A: fresh SDK docs before integration (happy path)

User pastes the prompt from `idea.md`: how is the client initialized in the new
major version? Needs fresh docs, not a guessed API.

### Critical contract: no files written
- [ ] `ls -la output/` shows NO files after `/mcp-docs` completes (only `.`/`..`)
- [ ] If any project file is created/modified — **contract violation**

### Lookup behavior
- [ ] Resolves a library ID for the package/framework
- [ ] Asks a NARROW question scoped to the task (not a broad doc dump)
- [ ] Records source library ID + decision in notes / plan / review

### Output shape (stdout)
- [ ] Contains DOC SOURCE, VERSION OR LIBRARY ID, DECISION,
      IMPLEMENTATION IMPACT, FOLLOW-UP RISK

### Guard rails
- [ ] NO secrets / proprietary source / credentials sent to documentation tools
- [ ] Prefers official / high-reputation sources

## /mcp-docs — Scenario B: MCP unavailable (fallback)

Context7 / MCP docs not reachable.

- [ ] Falls back to official project documentation
- [ ] Explicitly states the MCP source was unavailable

## /mcp-docs — Scenario C: docs conflict with repo convention

Fetched docs recommend pattern X; the repo consistently uses pattern Y.

- [ ] Skill explains the conflict
- [ ] Prefers the repository convention UNLESS it is broken or deprecated

## /mcp-docs — Scenario D: tiny local fix, behavior already proven

- [ ] Does NOT block a tiny local fix when the relevant API behavior is already
      proven by tests or existing code

## Cross-reference with `check-skill-completeness.sh`

1. ✅ `skills/mcp-docs/references/` exists (mcp-docs-checklist.md)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/mcp-docs`
3. ✅ `tests/fixtures/fixture-21-mcp-docs/` exists with `idea.md`, `notes.md`,
   `expected-files.txt`, `expected-snapshot.json`

## Run manually

1. `cd tests/fixtures/fixture-21-mcp-docs/`
2. `mkdir -p output && cd output`
3. Start Claude Code, paste `idea.md` content, invoke `/mcp-docs`
4. Verify `ls -la` shows NO new files; check the Scenario A checklist
5. `cd .. && python3 ../../verify_snapshot.py .` — expected: `⏸️ fixture-21-mcp-docs: PENDING`

## Failures (fill in if any)

(empty unless the fixture fails — especially any file written by /mcp-docs or any
secret leaked into an external documentation query)
