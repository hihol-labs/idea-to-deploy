# Project Memory: nginx-logtop

## Context

`nginx-logtop` is a planned open-source Python 3.11 CLI for DevOps/SRE engineers. It streams nginx Combined Log Format from local files or stdin and reports top-ten client IPs, top-ten URL paths by combined 4xx/5xx count, a 24-bucket hourly percentage distribution, and exact unique User-Agent share. Default output is colored Rich terminal text; `--json` and `--csv` are deterministic pipeline formats.

Current phase: blueprint complete; no product code exists yet. The durable specifications are `STRATEGIC_PLAN.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, and `IMPLEMENTATION_PLAN.md`. Implement one numbered plan step at a time only after explicit authorization.

## Rules

1. Read `AGENTS.md`, applicable `.itd/` contracts, and the relevant repository-local Idea to Deploy skill before lifecycle work.
2. Preserve WIP=1 and freeze scope before edits. Never begin the next implementation step while the current unit is unverified or in recovery.
3. Specifications are source: change `PRD.md`/`PROJECT_ARCHITECTURE.md` before changing an intentional behavioral contract.
4. No authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.
5. Use one synchronous, stateless, streaming process; never load the complete log into memory.
6. Use exactly `100 × hourly_request_count / total_valid_requests` for every hourly percentage.
7. Unique User-Agent share is exact. Enforce the configured ceiling; never silently approximate.
8. Preserve the full exit-code contract: `0` success/help/version, `1` operational I/O/output/internal failure, `2` usage failure, `3` input/data-format/empty/no-valid-record failure, `4` unique-cardinality exhaustion. Do not omit or remap `4`.
9. stdout is report-only and stderr is diagnostic-only. Never echo complete malformed log lines or allow Rich markup injection.
10. Deterministic ordering is descending count then ascending key. Text, JSON, and CSV must render the same report.
11. Performance claims require a current exact-candidate 1 GB benchmark record with hardware and peak-memory context.
12. Do not publish packages or create external releases without explicit authorization.
13. В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Stack

| Area | Choice |
|---|---|
| Runtime | Python 3.11+ |
| CLI | Click |
| Terminal | Rich |
| Models | dataclasses |
| Core storage | `Counter`, `set`, fixed 24-element list; memory only |
| Serialization | standard-library `json` and `csv` |
| Packaging | `pyproject.toml`, `src/` layout, pip/pipx |
| Verification | pytest, coverage, Ruff, mypy, deterministic performance fixture |

## Planned Structure

```text
pyproject.toml
src/nginx_logtop/
  __init__.py
  cli.py
  input.py
  parser.py
  models.py
  aggregate.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  tools/generate_benchmark_log.py
  test_package.py
  test_parser.py
  test_aggregate.py
  test_input.py
  test_renderers.py
  test_cli.py
  test_performance.py
docs/BENCHMARK.md
```

Do not create absent structure speculatively outside the active implementation step.

## Implementation Status

| Step | Deliverable | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and verification skeleton | Not started | clean install, import/help tests |
| 2 | Domain models and parser | Not started | parser fixtures and coverage |
| 3 | Streaming aggregation | Not started | all metric/cardinality unit tests |
| 4 | Streaming input | Not started | file/stdin and incremental-read tests |
| 5 | Text/JSON/CSV renderers | Not started | deterministic golden outputs |
| 6 | CLI integration | Not started | all options and exit codes `0/1/2/3/4` |
| 7 | Quality and performance | Not started | checks plus documented 1 GB result |
| 8 | Packaging handoff | Not started | clean wheel install and complete verification receipt |

## Session Handoff Protocol

At the start, inspect current Git status and `.itd-memory/` state before trusting this table. At the end, record tests actually run, unresolved failures, the exact active unit status, and one explicit next action. A prose success statement is not a substitute for the repository's current verification/adjudication receipt.
