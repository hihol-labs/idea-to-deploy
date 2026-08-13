# Nginx Insights CLI — Project Memory

## Project Context

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams standard nginx combined access logs and reports top 10 IPs, top 10 request targets by 4xx/5xx count, 24 hourly request percentages, and unique User-Agent share. Default output is Rich colored terminal text; JSON and CSV serve pipelines. The target is a representative 1 GB log in under 30 seconds on a documented laptop.

This file guides implementation sessions. `PRD.md` owns behavior, `PROJECT_ARCHITECTURE.md` owns public and component contracts, and `IMPLEMENTATION_PLAN.md` owns step order.

## Fixed Decisions

- Stack: Python 3.11, Click, Rich, dataclasses, pytest; pip-installable package.
- Architecture: one stateless streaming process. No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Budget and schedule: $0, open source, one weekend.
- Hourly percentages must use `100 × hourly_request_count / total_valid_requests`, not an unscaled fraction.
- Exit codes are `0/1/2/3/4`: 0 success, 1 input I/O or decoding, 2 CLI usage, 3 log-data failure, and 4 unique-cardinality exhaustion. Do not omit or remap code 4.
- Product changes begin in the specification and acceptance criteria, then flow to code.

## Working Rules

1. Read `AGENTS.md`, `.itd/` contracts, this file, and the current implementation-plan step before editing.
2. Preserve WIP=1. Implement and verify only the active step.
3. Stream input line-by-line; never retain raw lines or the full input.
4. Keep parser and aggregation logic independent from Click and Rich.
5. Keep log-derived values out of shell evaluation and escape/disable Rich markup.
6. Send report data to stdout and diagnostics to stderr; nonzero outcomes produce no partial report.
7. Add a failing test for behavior before implementing it, then run the named step verification.
8. Do not claim performance from estimates; record the benchmark environment and measured evidence.
9. В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Intended Structure

```text
pyproject.toml
src/nginx_insights/
  __init__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  errors.py
  renderers/{__init__,terminal,json,csv}.py
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
  test_performance.py
```

The structure is planned, not yet implemented. Do not create product code during blueprint work.

## Session Start Checklist

- Confirm the active `.itd/SCOPE_LOCK.md` and persistent state agree with the requested step.
- Inspect the worktree and preserve unrelated user changes.
- Restate the one step's acceptance commands.
- Confirm no prerequisite step is incomplete.

## Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Installable CLI scaffold | Not started | Clean editable install, help, focused tests |
| 2 | Dataclasses and failure mapping | Not started | Compile and exact exit-contract tests |
| 3 | Combined-log parser | Not started | Parser and CLI tests |
| 4 | Four aggregations | Not started | Focused metric and formula tests |
| 5 | Cardinality guard | Not started | Boundary tests and exit 4/no-output proof |
| 6 | Terminal/JSON/CSV renderers | Not started | Golden outputs and JSON validation |
| 7 | Pipeline and privacy hardening | Not started | End-to-end error and redaction tests |
| 8 | Benchmark and package release | Not started | Full suite, clean wheel, measured 1 GB run |

Blueprint documents are prepared. No product implementation or adversarial review has run in this session.

## Definition of Session Handoff

- The active step's changed files and tests are named.
- Commands and outcomes are recorded without inventing evidence.
- Specification and implementation contradictions are reconciled.
- Idea to Deploy state is current and the next action is explicit.
- Any failed acceptance stays open as recovery work; narration alone never marks a step complete.

