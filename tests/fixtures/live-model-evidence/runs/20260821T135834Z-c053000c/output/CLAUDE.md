# Project Memory: Nginx Stream Analyzer

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams nginx combined access logs and reports top 10 IPs, top 10 URLs with 4xx/5xx responses, hourly request percentages, and exact unique User-Agent share. Default output is colored Rich text; `--json` and `--csv` support pipelines. Target: 1 GB under 30 seconds on a declared laptop, $0 budget, one-weekend MVP.

The durable specification is `PRD.md`; architectural details live in `PROJECT_ARCHITECTURE.md`; work order and verification commands live in `IMPLEMENTATION_PLAN.md`. When behavior changes, update the specification before product code.

## Non-Negotiable Rules

1. Use Python 3.11, Click, Rich, and dataclasses; keep runtime dependencies minimal.
2. Preserve a single-process, stateless, one-pass architecture.
3. Do not introduce authentication, a database, an HTTP API, a server, cloud resources, Docker, or Kubernetes.
4. Do not retain raw log lines or read the complete input into memory.
5. Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
6. Machine output is deterministic and ANSI-free; diagnostics go to stderr.
7. Preserve exits `0/1/2/3/4`: `0` success (including empty input), `1` operational/internal failure, `2` invalid usage, `3` non-empty all-invalid input, `4` unique-cardinality exhaustion.
8. Cardinality exhaustion must not silently produce a partial success report.
9. Keep WIP=1 and attach actual test/benchmark evidence before marking a step complete.
10. В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure

```text
pyproject.toml
src/nginx_stream_analyzer/
  __init__.py
  cli.py
  errors.py
  models.py
  parser.py
  aggregate.py
  report.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
  test_cli_contract.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli_integration.py
  test_invariants.py
  test_performance_smoke.py
scripts/
  generate_benchmark_log.py
  benchmark.py
```

## Metric Semantics

- Valid records alone contribute to metrics and denominators.
- Error URL means status 400–599 and the exact logged request target, including query string.
- Hour is 00–23 as recorded in the parsed log timestamp.
- Unique User-Agent equality is exact and case-sensitive.
- Ranking order is count descending and key ascending; at most 10 rows.
- Empty input is a valid empty report; a non-empty all-invalid input is exit `3`.

## Implementation Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and contracts | Not started | Install/help/contract tests |
| 2 | Parser and fixtures | Not started | Parser tests and branch coverage |
| 3 | Streaming aggregation | Not started | Metric/cardinality tests and coverage |
| 4 | Text/JSON/CSV renderers | Not started | Golden/schema/no-ANSI tests |
| 5 | CLI integration | Not started | File/stdin and `0/1/2/3/4` tests |
| 6 | Correctness hardening | Not started | Full suite and core coverage |
| 7 | Performance acceptance | Not started | Smoke test and declared 1 GB benchmark |
| 8 | Packaging/release | Not started | Build, clean install, suite, benchmark |

## Working Protocol

Before a step:

1. Read the corresponding implementation-plan section and linked PRD criteria.
2. Lock scope to one step in `.itd/SCOPE_LOCK.md` and reconcile `.itd-memory/STATE.json`.
3. Write a failing behavior test when product code is being changed.

Before handoff:

1. Run the exact verification commands for the current step.
2. Record actual evidence and unresolved failures.
3. Reconcile the status table and Idea to Deploy state.
4. State the next single action explicitly.

## Current State

Blueprint documentation is complete; product implementation has not begun. The next authorized implementation action, when requested, is Step 1 only. The separate adversarial architecture review is outside this blueprint session and must not be represented as already completed.
