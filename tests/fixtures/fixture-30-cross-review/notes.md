# Fixture 30 — /cross-review — manual verification notes

`/cross-review` is a read-only orchestrator skill (omnigent "one vendor reviews
another vendor's code" outcome port). It writes NO project files; it shells out to
an external review CLI and summarizes findings in the conversation.

Validation deferred (status: pending) — same read-only detect/advise stdout bucket
as fixture-15-advisor, fixture-21-mcp-docs, fixture-26-caveman,
fixture-27-context-mode-setup, fixture-28-seo-setup, fixture-29-security-guidance-setup.
`verify_snapshot.py`'s Phase 1 schema is file-shaped and cannot assert a
shell-out/stdout flow, so structural validation is manual via this file.

## Contract to verify manually

`/cross-review` MUST:
- Resolve the diff (argument range/path, else working tree + staged); if empty, say
  "nothing to cross-review" and stop without calling any external CLI.
- **Scrub secrets/PII from the diff BEFORE sending it to a third-party CLI**
  (egress). If a live credential cannot be scrubbed, skip the external send and
  degrade to native review.
- Honor the degradation chain **codex → gemini → native Claude red-team review**.
  Treat any non-zero exit / auth error / quota or rate-limit message as
  "engine unavailable" and move to the next link. Never block the workflow.
- **Name the engine that actually produced the findings** (codex / gemini / native).
- Be **additive to `/review`**: it must NOT be a commit gate and MUST NOT write the
  `/tmp/claude-review-done-*` marker (that belongs to `/review`).
- Remind the user that the mandatory `/review` is still required.

`/cross-review` MUST NOT:
- Replace `/review` or satisfy its gate.
- Send an unscrubbed diff (with live secrets/PII) to an external CLI.
- Fail the session when the external CLI is missing or out of quota (fail-open).
- Hide or weaken any idea-to-deploy gate, verification result, or the
  skill-decision line.

## Why no expected-files
See `expected-files.txt` — a read-only skill; any file written to the output dir is
a contract violation.
