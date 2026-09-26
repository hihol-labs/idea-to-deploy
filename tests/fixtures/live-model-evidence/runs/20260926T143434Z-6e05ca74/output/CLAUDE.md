# Project Instructions: nginx-stream-report

## Project Context

This repository specifies a local, open-source Python 3.11 CLI for streaming nginx combined access logs. It reports top 10 IPs, top 10 request URLs with 4xx/5xx statuses, hourly request percentages, and the share of unique nonempty User-Agent values. Default output is colored terminal text; JSON and CSV support pipelines.

The blueprint documents are the durable source of truth. No product code was created during blueprint generation.

## Source-of-Truth Order

1. `PRD.md` — behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — component, CLI, schema, error, and ADR contracts.
3. `IMPLEMENTATION_PLAN.md` — delivery order and verification commands.
4. `STRATEGIC_PLAN.md` — priorities, KPIs, risks, budget, and Definition of Done.
5. `CLAUDE_CODE_GUIDE.md` — bounded prompts for later execution.

When documents conflict, pause implementation, reconcile the PRD and architecture, and only then update plans or code.

## Non-Negotiable Rules

- Use Python 3.11, Click, Rich, dataclasses, and standard pip packaging.
- Preserve one synchronous, single-process, line-streaming architecture unless profiling evidence and an approved spec change require otherwise.
- Do not add authentication, a database, an HTTP API, a server, cloud infrastructure, Docker as a runtime requirement, or Kubernetes.
- Never buffer the complete log or retain parsed records after their aggregate update.
- Keep metrics exact. Never silently approximate top values or cardinality.
- Calculate hourly percentage as `100 × hourly_request_count / total_valid_requests`.
- Keep public exits exact: `0` success, `1` I/O/unexpected runtime, `2` CLI usage, `3` input data/format, `4` unique-cardinality exhaustion.
- Write report data to stdout and diagnostics to stderr. Expected errors must not show tracebacks.
- Treat log content as untrusted and potentially sensitive. Make no network calls and do not echo complete malformed lines.
- Update specifications and acceptance tests before intentional behavior changes.
- Do not claim the 1 GB / 30 s target without current recorded measurement.
- At the end of every session or meaningful block of work, save context through `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Planned Project Structure

```text
src/nginx_stream_report/
  __init__.py
  cli.py
  analyzer.py
  parser.py
  aggregate.py
  models.py
  errors.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
scripts/
  generate_benchmark_log.py
```

Create paths only in the implementation step that owns them. Do not prebuild later-step behavior.

## Standard Verification

Once implementation exists, the baseline commands are:

```bash
.venv/bin/pytest -q --cov=nginx_stream_report --cov-fail-under=90
.venv/bin/ruff check src tests scripts
.venv/bin/mypy src
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
```

The performance gate additionally requires the documented 1 GB fixture procedure and at least three timed runs. Preserve command output as evidence; narration alone does not establish completion.

## Implementation Status

| Step | Scope | Status | Completion evidence required |
|---:|---|---|---|
| 1 | Package skeleton and CLI baseline | Not started | Install, help, tests, Ruff, mypy |
| 2 | Models, errors, fixtures | Not started | Contract tests and static checks |
| 3 | Combined-log parser | Not started | Parser boundary tests |
| 4 | Streaming aggregation | Not started | Metrics, streaming, and exhaustion tests |
| 5 | Terminal renderer | Not started | Renderer tests and no-color smoke run |
| 6 | JSON and CSV renderers | Not started | Standard-parser and schema tests |
| 7 | End-to-end exit contract | Not started | Codes 0/1/2/3/4, coverage, static checks |
| 8 | Performance and packaging | Not started | Package checks and recorded benchmark |

Only one row may be in progress at a time. Update the row after actual verification, not when code is merely written.

## Session Handoff

At the end of work, record the active step, changed files, commands actually run with outcomes, blockers, and the next exact action. Keep generated benchmark logs outside the repository and never commit sensitive access logs.

