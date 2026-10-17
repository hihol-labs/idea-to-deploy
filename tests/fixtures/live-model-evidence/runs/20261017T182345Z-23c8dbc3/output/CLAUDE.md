# Project Memory: nginx-stream-report

## Context

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams supported nginx combined access logs and reports top 10 IPs, top 10 4xx/5xx URLs, hourly request percentages, and unique User-Agent share. Default output is Rich terminal text; JSON and CSV support pipelines. Target: 1 GB in under 30 seconds on a documented laptop. Budget: $0. Delivery: one weekend.

The durable specifications are `STRATEGIC_PLAN.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, and `IMPLEMENTATION_PLAN.md`. Change the specification before intentionally changing behavior.

## Non-Negotiable Rules

- Python 3.11, Click, Rich, dataclasses, src layout, pip installation.
- Local, stateless, single-process CLI only: no auth, database, HTTP API, server, cloud, or Kubernetes.
- Preserve lazy streaming and do not retain raw input.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- Keep JSON/CSV stdout machine-parseable; send diagnostics to stderr.
- Preserve exit codes `0/1/2/3/4`, with 4 reserved for unique-cardinality exhaustion.
- Add tests for every new behavior and run the relevant subset before the full suite.
- Never claim the 1 GB target without a recorded benchmark on named hardware.
- No publish, push, deployment, deletion, or other external/irreversible action without human confirmation.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Intended Structure

```text
src/nginx_stream_report/
  __init__.py
  __main__.py
  aggregate.py
  cli.py
  errors.py
  models.py
  parser.py
  renderers/
    __init__.py
    csv.py
    json.py
    text.py
tests/
  fixtures/
  test_aggregate.py
  test_cli.py
  test_csv_renderer.py
  test_json_renderer.py
  test_models.py
  test_parser.py
  test_performance_smoke.py
  test_text_renderer.py
benchmarks/
  generate_fixture.py
  run_benchmark.py
pyproject.toml
```

## Implementation Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Not started | Editable install, help, CLI tests |
| 2 | Models, errors, fixtures | Not started | Model tests, compileall |
| 3 | Streaming parser | Not started | Parser and CLI tests |
| 4 | Core aggregations | Not started | Aggregation tests and coverage |
| 5 | Rich terminal renderer | Not started | Renderer and CLI tests |
| 6 | JSON and CSV | Not started | Parsed renderer tests |
| 7 | Exit codes and diagnostics | Not started | Tests for codes 0–4 |
| 8 | Benchmark and optimization | Not started | Smoke test and recorded 1 GB run |
| 9 | Release quality | Not started | Full tests, build checks, clean install |

## Working Protocol

Work on only the next incomplete step in `IMPLEMENTATION_PLAN.md`. Keep commits step-scoped if commits are requested. Record commands and outcomes, including failures or skipped environment-dependent checks. Do not mark a step complete based on prose alone. `PROJECT_ARCHITECTURE.md` owns technical contracts; `PRD.md` owns product acceptance.

