# Project Memory: nginx-stream-insights

## Context

This repository defines a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams one nginx access log from a path or stdin and reports top client IPs, top error URLs, hourly request percentages, and unique User-Agent share. Default presentation is Rich terminal text, with JSON and CSV for pipelines. Budget is $0 and the MVP delivery window is one weekend.

## Source of Truth

Read in this order before implementation:

1. `PRD.md` for product behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` for components, CLI schemas, and process boundaries.
3. `IMPLEMENTATION_PLAN.md` for dependency order and verification per step.
4. `STRATEGIC_PLAN.md` for priorities, success measures, and risks.
5. `CLAUDE_CODE_GUIDE.md` for bounded implementation prompts.

When behavior changes, update the specification first and then adjust code. Do not let generated code become the only description of behavior.

## Non-Negotiable Rules

- Python 3.11; Click; Rich; dataclasses; pip-installable `src/` package.
- One local synchronous process and line-by-line input processing.
- No authentication, database, HTTP API, server, cloud, Kubernetes, telemetry, or retained input.
- Default top-N is 10 for IPs and error URLs.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`.
- Structured stdout is deterministic and contains no ANSI; diagnostics use stderr.
- Exit codes stay `0/1/2/3/4`, where 4 is exact User-Agent cardinality exhaustion.
- Treat all log fields as untrusted data and never evaluate them or pass them to a shell.
- Preserve WIP=1 and attach actual verification evidence before advancing a step.
- End every implementation cycle with exact-candidate verification according to `.itd/VERIFICATION_CONTRACT.json`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure

```text
src/nginx_stream_insights/
  __init__.py
  cli.py
  models.py
  parser.py
  aggregator.py
  renderers/{__init__,text,json,csv}.py
tests/{fixtures,test_parser,test_aggregator,test_cli,test_renderers,test_performance}.py
benchmarks/{generate_log,run_benchmark}.py
```

Do not create product code during blueprint work. During implementation, create only the files assigned to the active step.

## Active Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 0 | Blueprint documents | Complete | Required root documents exist and content checks pass |
| 1 | Package and CLI contract | Not started | Install/help/version and focused tests |
| 2 | Models and fixtures | Not started | Compile and model tests |
| 3 | Parser | Not started | Parser tests and lint |
| 4 | Aggregator | Not started | Formula/cardinality tests and coverage |
| 5 | Renderers | Not started | JSON/CSV parse and text snapshots |
| 6 | End-to-end CLI | Not started | Integration tests for exit codes `0/1/2/3/4` |
| 7 | Performance | Not started | Three-run 1 GB benchmark and peak RSS |
| 8 | Packaging/docs | Not started | Build, distribution validation, clean install |
| 9 | Release candidate | Not started | Current revalidated adjudication receipt |

## Current Next Action

Begin Step 1 only after the blueprint and any externally run architecture review are accepted. Do not infer that an adversarial review occurred in this blueprint session.

