# Manual verification — fixture 26 (/caveman)

`/caveman` is a **read-only** communication-style control ported from the public
[Caveman plugin](https://github.com/JuliusBrussee/caveman) (MIT). It compresses
output style (~75% fewer output tokens) while keeping full technical accuracy. It
MUST NOT modify project files. This fixture regressionally fixes the compression
rules, the Auto-Clarity safety carve-outs, the idea-to-deploy gate-status
preservation, and the no-unapproved-install contract.

## Fixture status

`pending` — **deferred**, same bucket as `fixture-15-advisor` and
`fixture-21-mcp-docs` (read-only, stdout/style flow). For now: manual checklist
below. The stub satisfies `check-skill-completeness.sh`.

## /caveman — Scenario A: enable caveman mode (happy path)

User pastes the prompt from `idea.md`: enable caveman mode, reply shorter.

### Critical contract: no files written

After the run, `output/` must contain no skill-authored files. `/caveman` only
changes response style.

### Expected output shape

- Mode **full** persists for the session.
- Replies drop articles/filler/pleasantries; fragments OK; short synonyms.
- Code, paths, commands, API names, error strings: verbatim.
- The style is NOT announced; no "Caveman:" recap alongside a normal answer.
- The user's dominant language is preserved (Russian in → Russian caveman).

## /caveman — Scenario B: Auto-Clarity on a destructive op

User (caveman active) asks to drop and recreate a table.

### Expected

- The destructive warning is written in **normal prose**, not compressed:
  a clear "this permanently deletes ... cannot be undone, verify backup first".
- Caveman resumes for the non-risky remainder.
- Brevity never hides the destructive nature.

## /caveman — Scenario C: idea-to-deploy gate preservation

While caveman is active during methodology work:

- The skill-decision line (`Скилл: /X` / `Скилл: не нужен — …`) stays explicit.
- Route, blockers, and gate status (`/review`, `/test`, DoD, security) stay visible.
- Verification evidence (test counts, command output, pass/fail) stays exact.
- Commit / push / PR status stays explicit and truthful.

## /caveman — Scenario D: switch intensity / turn off

- `/caveman ultra` → ultra mode (abbreviate prose words, causal arrows; never
  abbreviate code symbols / function names / API names / error strings).
- `normal mode` / `stop caveman` → revert to normal style immediately.

## Why pending (not active)

Phase 1 snapshot validation is file-shaped (`verify_snapshot.py` checks written
files against `expected-files.txt`). `/caveman` writes nothing and only affects
stdout style, so structural automation is deferred to the Phase 2 stdout-snapshot
scheme. This stub anchors the contract for manual regression until then.
