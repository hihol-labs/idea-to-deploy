# Nginx Stream Analyzer — Project Memory

## Context

Build a pip-installable local Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports top 10 IPs, top 10 4xx/5xx URLs, 24 hourly request buckets, and the share of distinct User-Agents. Default output is colored terminal text; `--json` and `--csv` are stable pipeline formats. Target a representative 1 GB file in under 30 seconds on a documented laptop.

The durable product source of truth is [PRD.md](PRD.md); architecture decisions are in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md); execution is governed by [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) and `.itd/` contracts.

## Non-Negotiable Rules

- Preserve WIP=1: implement one numbered plan step at a time.
- Use Python 3.11, Click, Rich, and dataclasses; package for pip installation.
- Preserve the architecture statement: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- Do not add authentication, a server, cloud resources, Docker requirements, or Kubernetes.
- Never materialize the whole input; parse and aggregate in one pass.
- stdout contains the selected report only; diagnostics go to stderr.
- JSON and CSV never contain ANSI escapes. Treat every log field as untrusted data.
- Change PRD/architecture first when changing behavior or scope.
- Do not claim the 1 GB / 30 second goal without recorded benchmark evidence.
- At the end of every session or meaningful block of work, save context through `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Stack

| Area | Choice |
|---|---|
| Runtime | CPython 3.11 |
| CLI | Click |
| Terminal | Rich |
| Models | dataclasses |
| Machine formats | standard-library `json` and `csv` |
| Tests/quality | pytest, coverage, ruff |
| Packaging | `pyproject.toml`, console script, pip/pipx |

## Planned Structure

```text
src/nginx_stream_analyzer/{cli,models,parser,aggregate,service}.py
src/nginx_stream_analyzer/renderers/{terminal,json,csv}.py
tests/{test_parser,test_aggregate,test_renderers,test_cli,test_performance}.py
scripts/generate_benchmark_log.py
```

## Step Status

| Step | Deliverable | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Not started | editable install, help, CLI tests |
| 2 | Models and contract fixtures | Not started | test collection, JSON validation |
| 3 | Combined-log parser | Not started | parser tests, lint |
| 4 | One-pass aggregation | Not started | aggregation tests, coverage |
| 5 | JSON renderer | Not started | renderer tests, `json.tool` parse |
| 6 | CSV renderer | Not started | round-trip tests, CLI smoke |
| 7 | Rich UX and failures | Not started | CLI/renderer tests, no-color smoke |
| 8 | Quality, benchmark, release | Not started | lint, ≥90% coverage, build, clean install, measured benchmark |

## Current State

- Blueprint documentation: complete; required files, content checks, and the architecture review were verified on 2026-07-19.
- Product implementation: not started by design.
- Next action after blueprint acceptance: execute Implementation Step 1 using [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md).

## Session Handoff

Before stopping, record changed files, exact verification output, unresolved risks, current step status, and the single next action. Never translate an unrun check into a pass.
