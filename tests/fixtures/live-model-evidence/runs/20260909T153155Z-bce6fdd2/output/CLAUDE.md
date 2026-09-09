# nginx-insight Project Instructions

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports top 10 IPs, top 10 URLs by 4xx/5xx errors, hourly request distribution, and unique User-Agent share. Default output is Rich terminal text; JSON and CSV are stable pipeline formats. The target is a representative 1 GB file in under 30 seconds on a documented laptop baseline, for $0 and one-weekend delivery.

The repository is currently in blueprint-only state. No product code exists yet.

## Sources of Truth

1. `PRD.md` owns product behavior, schemas, priorities, and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` owns component boundaries and the complete CLI contract.
3. `IMPLEMENTATION_PLAN.md` owns dependency order, planned files, and verification commands.
4. `.itd/` owns methodology and verification contracts; `.itd-memory/` owns active execution state when present.
5. `STRATEGIC_PLAN.md` owns positioning, roadmap, KPIs, risks, and budget.

When behavior changes, update the specification before implementation. Do not infer broader scope from a convenient library or generic template.

## Fixed Stack

- CPython 3.11
- Click for the command interface
- Rich for human-readable output
- Standard-library dataclasses for domain/report types
- Standard `pyproject.toml` build and pip installation

## Hard Constraints

- Single local process and stateless streaming; do not retain raw records.
- No authentication, database, HTTP API, server, cloud, Kubernetes, telemetry, or network dependency.
- JSON/CSV data only on stdout; diagnostics only on stderr.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- Exit codes are exactly `0/1/2/3/4`: success, operational I/O, usage/configuration, partial-data report, and unique-cardinality exhaustion respectively. Code 4 emits no report.
- Use deterministic ordering: descending count, then ascending text key.
- Preserve input bytes/files; never modify a log.
- Product code must remain under `src/nginx_insight/`; tests under `tests/`; benchmarks under `benchmarks/`.
- WIP=1: finish and verify one implementation step before beginning another.
- Do not claim completion from prose or a bare passing verdict; require the repository’s current exact-candidate adjudication receipt.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Planned Structure

```text
src/nginx_insight/
  cli.py             Click boundary and exit mapping
  input.py           file/stdin streaming
  parser.py          combined-log parsing
  aggregate.py       exact guarded aggregation
  models.py          dataclasses
  errors.py          typed failures
  renderers/         Rich, JSON, CSV
tests/                unit, integration, golden, hostile-input tests
benchmarks/           reproducible generator and performance runner
```

## Working Practices

- Start from a failing acceptance test or fixture oracle.
- Keep parsing, aggregation, and rendering separate.
- Use standard serializers; never hand-concatenate JSON or CSV.
- Test boundary statuses 399/400/499/500/599/600, empty input, missing UAs, ties, invalid bytes, huge lines, cap-at-limit, and cap-plus-one.
- Measure performance before optimization and record the environment.
- Preserve unrelated user changes and do not weaken checks to produce a pass.
- Update this status table only after the step’s listed commands actually run.

## Implementation Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI surface | Not started | CLI tests and install/help commands |
| 2 | Golden fixtures/oracles | Not started | Fixture tests and valid JSON oracle |
| 3 | Parser and input stream | Not started | Parser/input tests and mypy |
| 4 | Exact aggregation | Not started | Aggregation boundary/cardinality tests |
| 5 | JSON and CSV | Not started | Renderer tests and golden match |
| 6 | Rich output | Not started | Fixed-console tests and no-color check |
| 7 | End-to-end failures | Not started | All `0/1/2/3/4` integration cases |
| 8 | Performance gate | Not started | Reproducible 1 GB timing/RSS/oracle record |
| 9 | Quality/security gate | Not started | Ruff, mypy, coverage, dependency evidence |
| 10 | Packaging | Not started | Build, metadata check, clean wheel install, adjudication receipt |

## Current Next Action

Begin Step 1 from `IMPLEMENTATION_PLAN.md` only after an implementation session is authorized and its scope lock/state are reconciled. This blueprint session does not implement product code.

