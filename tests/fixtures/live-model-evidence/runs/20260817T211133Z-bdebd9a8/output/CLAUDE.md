# Nginx Stream Analyzer — Project Memory

## Context

This repository specifies a local Python 3.11 CLI for DevOps/SRE engineers. It
streams nginx access logs from files or stdin and reports top-10 IPs, top-10
URLs by combined 4xx/5xx count, 24-hour request percentages, and distinct
User-Agent share. The default is Rich terminal output; `--json` and `--csv`
are stable pipeline modes.

Current phase: blueprint complete; product implementation has not started.

## Source-of-Truth Order

1. `AGENTS.md` and `.itd/` project/verification contracts.
2. `PRD.md` for behavior, priorities, and acceptance criteria.
3. `PROJECT_ARCHITECTURE.md` for CLI schemas, component boundaries, and algorithms.
4. `IMPLEMENTATION_PLAN.md` for sequencing and verification.
5. `CLAUDE_CODE_GUIDE.md` for bounded future implementation prompts.
6. `STRATEGIC_PLAN.md` for product context, KPIs, risks, and release gates.

When documents conflict, stop and reconcile the higher-priority source before
changing implementation.

## Non-Negotiable Rules

- Use Python 3.11, Click, Rich, dataclasses, a `src` layout, and pip packaging.
- Keep one local OS process and a lazy single-pass input pipeline.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.
- Do not persist input or reports; do not make network calls.
- Treat logs as untrusted and potentially personal data; never print a full
  malformed record in diagnostics.
- One finalized report model feeds terminal, JSON, and CSV renderers.
- Preserve deterministic count-descending/key-ascending ranking.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`.
- Preserve the complete `0/1/2/3/4` exit contract: `0` success, `1`
  operational/I/O, `2` usage, `3` log data/strict parse, and `4`
  unique-cardinality exhaustion. Never remap code 4.
- Exits 1–4 emit no partial report on stdout.
- Do not mark the 1 GB / 30 s gate passed without an actual recorded benchmark.
- Keep WIP=1 and update specs before changing observable behavior.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure

```text
pyproject.toml
src/nginx_stream_analyzer/
  __init__.py
  cli.py
  models.py
  errors.py
  parser.py
  sources.py
  aggregate.py
  renderers/{__init__,terminal,json,csv}.py
tests/
  fixtures/
  test_cli.py
  test_models.py
  test_sources.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_integration.py
  test_performance.py
docs/BENCHMARK.md
```

This tree is planned, not evidence that files currently exist.

## Implementation Status

| Step | Deliverable | Status | Evidence | Next action |
|---:|---|---|---|---|
| 1 | Package and CLI contract | Not started | None | Execute Prompt 1 in `CLAUDE_CODE_GUIDE.md` |
| 2 | Domain and error models | Not started | None | Wait for Step 1 evidence |
| 3 | Sources and parser | Not started | None | Wait for Step 2 evidence |
| 4 | Streaming aggregation | Not started | None | Wait for Step 3 evidence |
| 5 | Three renderers | Not started | None | Wait for Step 4 evidence |
| 6 | CLI integration/exit codes | Not started | None | Wait for Step 5 evidence |
| 7 | Quality/performance proof | Not started | None | Wait for Step 6 evidence |
| 8 | Release artifact/handoff | Not started | None | Wait for Step 7 evidence |

## Session Protocol

1. Read the source-of-truth documents and current `.itd-memory/` state if present.
2. Select only the first unblocked step; update the scope lock before edits.
3. Implement the smallest acceptance slice and run the named checks.
4. Record real evidence and reconcile this table; failures remain In Progress.
5. State the exact next action and run `/session-save`.

Deferred P2 work is gzip input and custom nginx formats. It must not begin
inside the MVP until release criteria are met and the PRD is intentionally
updated.
