# Project Memory: nginx-log-insights

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams nginx combined access logs and reports top-10 IPs, top-10 URLs by 4xx/5xx count, 24-hour request percentages, and the share of unique non-empty User-Agents. Default output is colored terminal text; JSON and CSV are stable pipeline formats. Target delivery is one weekend at $0, with a 1 GB-under-30-seconds release gate on a documented laptop.

The durable product source of truth is `PRD.md`. `PROJECT_ARCHITECTURE.md` owns technical and CLI contracts. `IMPLEMENTATION_PLAN.md` owns step order and verification. `CLAUDE_CODE_GUIDE.md` provides prompts for future implementation sessions.

## Non-Negotiable Rules

- Use Python 3.11, Click, Rich, dataclasses, standard-library parsing/aggregation, and pip packaging.
- Preserve a single-process, one-pass streaming design.
- Do not add authentication, a database, HTTP API, server, cloud resource, Kubernetes, telemetry, or automatic upload.
- Treat log text as untrusted data. Never execute it or disclose complete malformed lines in diagnostics.
- Do not buffer complete files or retain logs after process exit.
- Keep rankings exact and deterministic. Guard each distinct IP, error-URL, and User-Agent structure before insertion.
- Calculate hourly distribution with `100 × hourly_request_count / total_valid_requests`.
- Preserve process codes everywhere: `0` success, `1` input/data failure, `2` CLI usage failure, `3` unexpected internal failure, `4` unique-cardinality exhaustion.
- Never silently approximate after cardinality exhaustion and never emit a partial report after failure.
- Write reports only to stdout and diagnostics only to stderr.
- Change the specification first when behavior changes; then adjust code and tests.
- Work in WIP=1: finish and verify the active implementation step before starting another.
- At the end of every session or meaningful work block, save context through `/session-save`.

## Planned Repository Structure

```text
pyproject.toml
src/nginx_log_insights/
  __init__.py
  __main__.py
  cli.py
  models.py
  errors.py
  inputs.py
  parser.py
  aggregate.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
  test_cli_contract.py
  test_cli_integration.py
  test_inputs.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_performance_smoke.py
benchmarks/
  generate_log.py
  run_benchmark.sh
  RESULTS.md
```

This is a planned structure, not evidence that product code exists.

## Implementation Status

| Step | Description | Status | Acceptance evidence |
|---:|---|---|---|
| 1 | Package skeleton and executable contract | Not started | None; blueprint only |
| 2 | Domain models, errors, and fixtures | Not started | None; blueprint only |
| 3 | Streaming input and parser | Not started | None; blueprint only |
| 4 | Exact streaming aggregation | Not started | None; blueprint only |
| 5 | Text, JSON, and CSV renderers | Not started | None; blueprint only |
| 6 | End-to-end CLI orchestration | Not started | None; blueprint only |
| 7 | Performance and resource acceptance | Not started | None; blueprint only |
| 8 | Packaging, security, and release gate | Not started | None; blueprint only |

## Current State

Blueprint documentation is prepared. No product source code has been implemented, no performance target has been measured, and no adversarial or independent review is claimed in this session. The next authorized action is Step 1 of `IMPLEMENTATION_PLAN.md`.

## Completion Discipline

For each step, run its listed verification commands and record real results. A statement that code looks correct is not evidence. The product is complete only when all P0 criteria pass, the clean-wheel smoke test passes, coverage meets the specified threshold, the current 1 GB benchmark is under 30 seconds under documented conditions, and all five application exit statuses are exercised.
