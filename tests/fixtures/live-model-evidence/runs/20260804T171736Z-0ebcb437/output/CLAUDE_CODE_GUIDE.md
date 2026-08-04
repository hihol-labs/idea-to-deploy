# Claude Code Guide: Nginx Stream Analyzer

Use one prompt at a time, in order, and keep WIP at one. Before editing, read `AGENTS.md`, `.itd/SCOPE_LOCK.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, and the matching step in `IMPLEMENTATION_PLAN.md`. Do not implement from this guide when a source specification disagrees; fix the specification first.

Every step must preserve and test the complete exit-code contract: `0` success, `1` unexpected runtime/output failure, `2` usage/validation error, `3` input failure, `4` unique-cardinality exhaustion for an exact IP, error-URL, or User-Agent limit. Never omit or remap code 4. Do not add authentication, a database, HTTP API, server, cloud, Docker, or Kubernetes.

## Prompt 1 — Package and contracts

> Execute Step 1 of `IMPLEMENTATION_PLAN.md`. Create only the listed package scaffold, dataclasses, error types, Click entry point, and contract tests. Keep the CLI installable on Python 3.11. Run both verification commands and report exact evidence; stop on failures.

## Prompt 2 — Streaming parser

> Execute Step 2 of `IMPLEMENTATION_PLAN.md`. Implement the documented nginx combined-log grammar with binary LF framing, strict per-line decoding, bounded oversized-line draining, and explicit malformed accounting. Add all named fixtures and parser tests. Do not retain raw lines or add format auto-detection. Run the step's pytest and Ruff commands.

## Prompt 3 — Aggregation and cardinality

> Execute Step 3 of `IMPLEMENTATION_PLAN.md`. Implement deterministic top-10 counters, 24 percentage buckets using `100 × hourly_request_count / total_valid_requests`, and exact key tracking with hard IP, error-URL, and User-Agent limits. Prove exhaustion of each dimension exits 4 with no partial successful report. Run the listed tests and mypy.

## Prompt 4 — Rich output

> Execute Step 4 of `IMPLEMENTATION_PLAN.md`. Add default Rich tables, deterministic formatting, TTY-aware color, `--no-color`, and control-character-safe display. Create the golden text fixture and run the prescribed verification without altering machine schemas.

## Prompt 5 — JSON and CSV

> Execute Step 5 of `IMPLEMENTATION_PLAN.md`. Implement the exact schemas in `PROJECT_ARCHITECTURE.md` with standard serializers. Ensure JSON/CSV are mutually exclusive, UTF-8, ANSI-free, deterministic, and semantically equivalent. Run golden tests and JSON parsing verification.

## Prompt 6 — Input and failures

> Execute Step 6 of `IMPLEMENTATION_PLAN.md`, completing P0 plain-file ownership first. Add stdin and gzip only after P0 is green. Test missing/unreadable/corrupt inputs and stream ownership. Prove exit 3 for input failure and exit 4 for unique-cardinality exhaustion.

## Prompt 7 — Performance

> Execute Step 7 of `IMPLEMENTATION_PLAN.md`. Use the exact seed, byte count, traffic mix, warm-up, three-run median oracle, and evidence fields specified by the architecture. Generate data outside the repository, require median time under 30 seconds, and enforce the accepted RSS ceiling. Profile before changing code; any optimization must preserve the full test suite and exact metrics.

## Prompt 8 — Quality gate

> Execute Step 8 of `IMPLEMENTATION_PLAN.md`. Add end-to-end coverage of text, JSON, CSV and exits `0/1/2/3/4`. Run Ruff, mypy, and pytest with branch coverage at least 90% for parser/aggregation. Record actual output and do not accept narration as evidence.

## Prompt 9 — Packaging and handoff

> Execute Step 9 of `IMPLEMENTATION_PLAN.md`. Replace planned README examples only with verified commands, record benchmark evidence, build wheel/sdist, inspect them, and install the wheel in a clean temporary Python 3.11 environment. Do not publish. Preserve code 4 as unique-cardinality exhaustion in every user-facing guide.

## Session Rule

At the end of every session or meaningful block of work, save context via `/session-save`, including active step, verification evidence, unresolved failures, and the exact next action.
