# Project Memory: nginx-stream-report

## Context

This repository defines and will implement a local Python 3.11 CLI for streaming nginx access-log analysis. The durable specifications are `PRD.md`, `PROJECT_ARCHITECTURE.md`, `STRATEGIC_PLAN.md`, and `IMPLEMENTATION_PLAN.md`. Generated code is subordinate to those specifications.

## Product Rules

- Produce top 10 client IPs, top 10 request targets with 4xx/5xx responses, 24 hourly percentages, and exact unique User-Agent share.
- Calculate hours with `100 × hourly_request_count / total_valid_requests`.
- Keep the process local, stateless, single-process, and streaming.
- Do not add authentication, a database, an HTTP API, a server, cloud services, Docker, or Kubernetes.
- Do not silently approximate, sample, normalize targets, or skip supported valid records.
- Render only after successful aggregation so failed runs do not emit partial reports.

## Stack

- CPython 3.11
- Click for CLI behavior
- Rich for terminal output
- Python dataclasses for domain records
- Standard-library JSON/CSV serialization
- pytest, coverage, Ruff, and mypy for development verification
- PEP 517 `pyproject.toml` and pip distribution

## Interface Invariants

- Command: `nginx-stream-report [OPTIONS] [INPUT]`; missing `INPUT` or `-` means stdin.
- `--json` and `--csv` are mutually exclusive; structured output contains no ANSI escapes.
- Exit codes are always `0/1/2/3/4`: success, I/O runtime failure, usage error, no valid records, and unique-cardinality exhaustion respectively.
- Code 4 must not be mapped to code 1 or 3.
- Diagnostics go to stderr; successful reports go to stdout.

## Planned Structure

```text
src/nginx_stream_report/{cli,models,parser,aggregate,errors}.py
src/nginx_stream_report/render/{text,json,csv}.py
tests/{fixtures,unit,integration,performance}/
docs/PERFORMANCE.md
```

## Working Rules

1. Preserve WIP=1 and follow `IMPLEMENTATION_PLAN.md` in order.
2. Use `CLAUDE_CODE_GUIDE.md` for the bounded prompt corresponding to the active step.
3. Add or update tests with every behavior change; never weaken a gate to obtain a pass.
4. Treat logs as sensitive local data: no network calls, telemetry, persistence, or full malformed-line echo.
5. Record performance claims only with hardware, Python version, input size, record counts, cardinalities, wall time, and memory evidence.
6. At the end of every session or meaningful work block, save context via `/session-save`.
7. В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Status

| Step | Scope | Status |
|---:|---|---|
| 1 | Package and CLI skeleton | Not started |
| 2 | Domain models and failure mapping | Not started |
| 3 | Supported-format parser | Not started |
| 4 | Bounded streaming aggregator | Not started |
| 5 | JSON and CSV renderers | Not started |
| 6 | Rich text renderer | Not started |
| 7 | End-to-end CLI and exit codes | Not started |
| 8 | Full quality gate | Not started |
| 9 | Reproducible performance gate | Not started |
| 10 | Documentation and release candidate | Not started |

No product code has been implemented by the blueprint workflow.

