# Project Memory: Nginx Insights CLI

## Context

Build a local, open-source Python 3.11 CLI for DevOps and SRE engineers. It streams a finite nginx combined access-log input and reports top-10 IPs, top-10 URLs across 4xx/5xx, hourly request percentages, and exact unique User-Agent share. Default output is Rich terminal text; JSON and CSV support pipelines. Cash budget is $0 and delivery is one weekend.

The specification is the durable source of truth. Read `PRD.md`, then `PROJECT_ARCHITECTURE.md`, then the active step in `IMPLEMENTATION_PLAN.md` before changing product code. If behavior changes, update the specification first.

## Non-Negotiable Decisions

- One local process and one-pass processing; no persistent runtime state.
- No authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.
- Python 3.11, Click, Rich, dataclasses, `pyproject.toml`, and pip installation.
- The release target is 1 GB under 30 seconds on a documented reference laptop; this requires measured evidence.
- Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`.
- Exit codes are exactly: 0 success; 1 unexpected runtime/processing/output failure; 2 invalid usage; 3 unreadable input or no valid records; 4 unique-cardinality exhaustion. Never omit or remap code 4, and never emit a partial report for it.
- Machine output goes to stdout; diagnostics go to stderr.
- Untrusted log values are data, never shell input or Rich markup.

## Planned Stack

| Area | Choice |
|---|---|
| Runtime | CPython 3.11 |
| CLI | Click |
| Terminal output | Rich |
| Domain types | Standard-library dataclasses |
| JSON/CSV | Standard library |
| Packaging | `pyproject.toml`, pip console script |
| Quality | pytest, coverage, Ruff, mypy, build/twine |

## Planned Structure

```text
src/nginx_insights/{cli,parser,models,aggregator,errors}.py
src/nginx_insights/renderers/{rich,json,csv}.py
tests/{unit,integration,fixtures,performance}/
```

## Working Rules

1. Preserve WIP=1 and implement only the active numbered step.
2. Keep parsing, aggregation, orchestration, and rendering separate.
3. Retain no raw input lines; avoid per-record output and per-line regex compilation.
4. Add focused tests for every behavior and failure path before accepting it.
5. Do not claim performance from estimates; record a real benchmark environment and result.
6. Preserve user work and do not broaden scope without updating `.itd/SCOPE_LOCK.md` and canonical state.
7. Completion requires current evidence under `.itd/VERIFICATION_CONTRACT.json` and the exact-candidate Verification Loop route.
8. В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Implementation Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI contract | Not started | Install, help, CLI contract tests |
| 2 | Models and exit semantics | Not started | Unit tests and mypy |
| 3 | Combined-log parser | Not started | Parser fixtures, tests, lint |
| 4 | Streaming aggregations | Not started | Metric and cardinality tests |
| 5 | Rich renderer | Not started | TTY, color, escaping tests |
| 6 | JSON and CSV | Not started | Schema and golden tests |
| 7 | End-to-end execution | Not started | File/stdin and all exit-code tests |
| 8 | Acceptance and release | Not started | Full quality suite, package smoke test, benchmark, verification receipt |

## Session Handoff

At session end, record the active step, changed files, exact commands and outcomes, unresolved risks, current verification receipt status, and the next bounded action. Do not mark a step complete based on narrative status alone.
