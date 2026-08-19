# Project Memory: nginx-log-insights

## Context

This repository is planning a local Python 3.11 CLI for DevOps/SRE engineers.
It streams standard nginx combined access logs and reports top 10 client IPs,
top 10 URLs by combined 4xx/5xx count, 24 hourly request percentages, and exact
unique User-Agent share. Terminal output is default; JSON and CSV are pipeline
contracts. The cash budget is $0 and delivery is timeboxed to one weekend.

Read `AGENTS.md` first. Product truth lives in `PRD.md`; technical truth lives
in `PROJECT_ARCHITECTURE.md`; work order and checks live in
`IMPLEMENTATION_PLAN.md`; ready-to-run prompts live in
`CLAUDE_CODE_GUIDE.md`.

## Non-Negotiable Rules

- Use Python 3.11, Click, Rich, dataclasses, a `src/` package, and pip packaging.
- Keep a single local process with no authentication, database, HTTP API,
  server, cloud, Docker, or Kubernetes.
- Process input line-by-line. Do not load the complete log into memory.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- Keep exact deterministic rankings: count descending, key ascending.
- Keep output contracts stable and diagnostics on stderr.
- Preserve exit codes `0/1/2/3/4`; code 4 always means unique-cardinality
  exhaustion and produces no partial report.
- Never emit full source log lines in diagnostics or interpret log fields as
  Rich markup, shell syntax, or URLs to fetch.
- Preserve WIP=1 and attach real verification evidence before changing status.
- Do not claim the 1 GB/<30-second target until the named benchmark has run.
- Before changing behavior, update the spec first; generated code follows it.
- At the end of every session or meaningful work block, save context via
  `/session-save`.
- Mandatory methodology wording: «В конце каждой сессии или значимого блока
  работы — сохранить контекст через /session-save».

## Planned Structure

```text
src/nginx_log_insights/
  __init__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  renderers/{__init__,terminal,json_output,csv_output}.py
tests/
  fixtures/
  performance/
  test_package.py
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_terminal_output.py
  test_output_contracts.py
  test_security.py
  test_integration.py
  test_performance.py
```

This structure is planned, not implemented by the blueprint workflow.

## Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 0 | Full blueprint documents | Complete | Required documents exist and structural checks pass |
| 1 | Package and test skeleton | Not started | Install, package test, help |
| 2 | Parser and domain models | Not started | Parser suite and coverage |
| 3 | Streaming aggregation | Not started | Aggregation suite and coverage |
| 4 | CLI and exit codes | Not started | CLI suite with 0/1/2/3/4 matrix |
| 5 | Rich terminal output | Not started | Terminal semantic/safety tests |
| 6 | JSON and CSV | Not started | Parsed schema and parity tests |
| 7 | Hardening | Not started | Full suite, coverage, compile check |
| 8 | Performance | Not started | Recorded 1 GB benchmark and smoke test |
| 9 | Release candidate | Not started | Build/install checks and current verification receipt |

## Current Scope and Next Action

Blueprint planning is complete; product code has not been created. The next
authorized implementation action, when requested, is Step 1 only. Before that
work, update `.itd/SCOPE_LOCK.md` and canonical `.itd-memory` state for the new
unit. Do not create `DEVILS_ADVOCATE_REVIEW.md` in the blueprint session; the
benchmark harness owns that separate review.

