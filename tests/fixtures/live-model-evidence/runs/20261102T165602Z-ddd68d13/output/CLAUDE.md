# Project Instructions: nginx-stream-report

## Context

Build a local, open-source Python 3.11 CLI that streams standard nginx combined access logs and reports top 10 IPs, top 10 4xx/5xx URLs, hourly request percentages, and exact unique User-Agent share. Default output is Rich terminal text; JSON and CSV are stable pipeline formats. The one-weekend MVP has a $0 budget and a 1 GB-under-30-seconds target.

## Source of Truth

Read documents in this order:

1. `PRD.md` — behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — technical and public CLI contracts.
3. `IMPLEMENTATION_PLAN.md` — dependency-ordered work units and checks.
4. `STRATEGIC_PLAN.md` — priorities, risks, KPIs, and release criteria.
5. `CLAUDE_CODE_GUIDE.md` — prompts for executing one unit safely.

If documents conflict, stop and reconcile the specification before changing code; architecture controls technical ambiguity and PRD controls product behavior.

## Non-Negotiable Rules

- Preserve WIP=1: execute only the active implementation step.
- Do not add authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Stream input; never load a complete log into memory.
- Use Python 3.11, Click, Rich, dataclasses, a `src/` layout, and pip-compatible packaging.
- Keep the complete exit contract `0/1/2/3/4`; code `4` is unique-cardinality exhaustion.
- Compute hourly percentages as `100 × hourly_request_count / total_valid_requests`.
- Add tests with every behavior change and run the relevant suite before claiming completion.
- Treat JSON fields, CSV columns, formulas, ranking rules, and exit codes as versioned public contracts.
- Never print secrets or upload log data. Do not push, publish, deploy, delete, or perform another external/irreversible action without explicit human confirmation.
- Ground progress reports in command output from the current session; state failed or skipped checks exactly.
- At the end of every session or meaningful block of work, save context through `/session-save`.

## Planned Structure

```text
src/nginx_stream_report/
  __init__.py
  __main__.py
  cli.py
  input.py
  parser.py
  models.py
  aggregator.py
  report.py
  renderers/
    __init__.py
    rich_text.py
    json_output.py
    csv_output.py
tests/
  fixtures/
  test_models.py
  test_input.py
  test_parser.py
  test_aggregator.py
  test_report.py
  test_renderers.py
  test_cli.py
  test_cli_integration.py
  test_performance_smoke.py
benchmarks/
  generate_fixture.py
  run.sh
```

## Engineering Conventions

- Type all public functions and use immutable/frozen dataclasses where practical.
- Parse into domain values; keep Click and Rich objects out of parser/aggregation modules.
- Send only complete reports to stdout and all diagnostics to stderr.
- Sort top lists by count descending, then key ascending.
- Use timezone-aware timestamps and the hour encoded in each nginx record.
- Escape terminal values and use the standard `csv` module.
- Prefer small pure functions and fixture-driven tests over mocks.
- Large generated benchmark inputs belong outside Git.

## Step Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and contracts | Not started | install + model/CLI tests |
| 2 | Input and parser | Not started | parser/input tests + lint/types |
| 3 | Aggregation and cap | Not started | aggregation + coverage tests |
| 4 | Report formulas | Not started | report and integration tests |
| 5 | Renderers | Not started | golden/cross-format tests |
| 6 | CLI and exit codes | Not started | subprocess coverage for `0/1/2/3/4` |
| 7 | Performance | Not started | recorded 1 GB time and RSS |
| 8 | Release candidate | Not started | full suite, build, clean install |

No product code exists as part of the blueprint. Begin only when implementation is explicitly requested.

