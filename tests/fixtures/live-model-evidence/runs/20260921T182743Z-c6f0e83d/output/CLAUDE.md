# nginx-stream-report Project Instructions

## Context

This repository builds a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams nginx access logs and reports top-10 client IPs, top-10 URLs with 4xx/5xx statuses, hourly request percentages, and exact unique User-Agent share. Default output is Rich terminal text; JSON and CSV are pipeline formats. The performance target is a representative 1 GB log in under 30 seconds on a documented laptop.

## Sources of Truth

1. `PRD.md` defines product behavior, priorities, and acceptance scenarios.
2. `PROJECT_ARCHITECTURE.md` defines components, schemas, formulas, CLI behavior, and architectural decisions.
3. `IMPLEMENTATION_PLAN.md` defines the nine dependency-ordered delivery units and their verification.
4. `STRATEGIC_PLAN.md` defines scope, success metrics, risks, budget, and Definition of Done.
5. `CLAUDE_CODE_GUIDE.md` provides bounded prompts; it does not override the specifications above.

When behavior changes, update the specification first and then implementation/tests. Do not let implementation become an undocumented source of truth.

## Non-Negotiable Rules

- Preserve a single-process, stateless streaming design: no database, HTTP API, server, authentication, cloud, Docker, or Kubernetes.
- Use Python 3.11, Click, Rich, dataclasses, standard packaging, and pip installation.
- Do not accumulate raw input or parsed records; consume iterators and keep only aggregates.
- Calculate hourly percentage with `100 × hourly_request_count / total_valid_requests`.
- Preserve the complete exit-code contract: `0` success, `1` I/O, `2` usage, `3` log-data, `4` unique-cardinality exhaustion.
- Send report data to stdout and diagnostics to stderr. JSON and CSV must never contain ANSI styling.
- Treat log content as untrusted data: do not evaluate it, invoke a shell with it, or allow Rich markup interpretation.
- Keep WIP at one implementation-plan step and run that step's verification before moving on.
- Do not claim the 1 GB / 30 s target without a current measured benchmark and documented environment.
- At the end of every session or meaningful block of work, save context through `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Approved Stack

| Area | Choice |
|---|---|
| Runtime | CPython 3.11 |
| CLI | Click |
| Terminal rendering | Rich |
| Domain records | frozen dataclasses |
| Aggregation | standard-library counters, fixed buckets, guarded sets, heap selection |
| Structured output | standard-library `json` and `csv` |
| Tests | pytest and Click `CliRunner` |
| Package | `pyproject.toml`, wheel/sdist, pip console script |

New runtime dependencies require a documented need, compatibility check, and update to the architecture before adoption.

## Intended Structure

```text
src/nginx_stream_report/
  __init__.py
  cli.py
  inputs.py
  parser.py
  models.py
  aggregate.py
  errors.py
  renderers/{terminal,json_output,csv_output}.py
tests/{fixtures,test_parser.py,test_aggregate.py,test_renderers.py,test_cli.py,test_performance.py}
scripts/generate_benchmark_log.py
```

Keep dependencies directed toward domain models. Renderers must not parse; the parser must not render; aggregation must not access Click or Rich.

## Working Method

1. Read the active step in `IMPLEMENTATION_PLAN.md` and the cited specification sections.
2. Make the smallest change that completes only that step.
3. Add or update tests for success, boundaries, and expected failures.
4. Run every verification command named by the step.
5. Record evidence, reconcile documents, and only then advance the status table.

Do not mark work complete based on narration, unexecuted commands, or a stale result.

## Implementation Status

| Step | Deliverable | Status |
|---:|---|---|
| 1 | Package and CLI skeleton | Not started |
| 2 | Domain models and exit semantics | Not started |
| 3 | Streaming input and parser | Not started |
| 4 | Core streaming aggregation | Not started |
| 5 | Rich terminal renderer | Not started |
| 6 | JSON and CSV renderers | Not started |
| 7 | End-to-end CLI and follow mode | Not started |
| 8 | Correctness, security, and packaging gate | Not started |
| 9 | Performance acceptance and release documentation | Not started |

Only one row may be “In progress”. A row becomes “Done” only after its current verification evidence is recorded.

## Test and Release Gates

- Focused step tests pass before the full suite.
- Core coverage is at least 90%.
- A built wheel installs and runs in a clean Python 3.11 virtual environment.
- Default text, JSON, and CSV golden contracts pass.
- Every exit code from 0 through 4 has an end-to-end test.
- The representative 1 GB run completes in under 30 seconds with peak RSS and environment recorded.
- No critical/high security issue or silent malformed-data behavior remains.

## Out of Scope

Hosted services, persistent history, dashboards, remote ingestion, custom nginx format configuration, compressed inputs, multiple concurrent sources, approximate analytics, and configurable top-N are excluded from MVP unless the PRD and architecture are explicitly revised first.

