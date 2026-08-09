# Nginx Log Lens Project Memory

## Project Context

Nginx Log Lens is a planned local Python 3.11 CLI for DevOps/SRE engineers. It
streams standard nginx common/combined access logs and reports top-10 IPs,
top-10 4xx/5xx URLs, hourly request percentages, and distinct User-Agent share.
Default output is Rich terminal text; JSON and CSV are stable pipeline modes.

The cash budget is $0 and delivery is one weekend. This file summarizes the
blueprint; normative product behavior lives in `PRD.md`, architecture decisions
in `PROJECT_ARCHITECTURE.md`, and sequence/evidence in
`IMPLEMENTATION_PLAN.md`.

## Non-Negotiable Decisions

- Use one stateless streaming Python process.
- Use Python 3.11, Click, Rich, dataclasses, standard packaging, and pip.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.
- Do not retain all lines or parsed records.
- Target a reproducible 1 GB run under 30 seconds on a declared laptop.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- User-Agent share uses distinct non-missing values over total valid requests.
- JSON/CSV stdout must remain parseable and diagnostic-free.

## Exit-Code Contract

| Code | Meaning |
|---:|---|
| `0` | Success, help, or version |
| `1` | Operational input/output/internal failure |
| `2` | CLI usage error |
| `3` | Strict parsing failure or no valid records |
| `4` | Unique-cardinality exhaustion |

The complete contract is `0/1/2/3/4`. Code `4` is reserved for exact
unique-cardinality exhaustion and must not be omitted or remapped in code,
tests, documentation, or implementation prompts.

## Planned Structure

```text
src/nginx_log_lens/
  __init__.py
  cli.py
  errors.py
  models.py
  parser.py
  aggregate.py
  renderers/
    __init__.py
    rich.py
    json.py
    csv.py
tests/
  fixtures/
  schemas/
benchmarks/
docs/
pyproject.toml
```

## Engineering Rules

1. Work on exactly one `IMPLEMENTATION_PLAN.md` step at a time.
2. Read the relevant PRD acceptance criteria before editing implementation files.
3. Keep parsing, aggregation, and rendering separated; all renderers consume one immutable summary.
4. Make tie ordering and machine serialization deterministic.
5. Preserve stdin ownership and close only files opened by the application.
6. Sanitize diagnostics; never reproduce a complete malformed log line.
7. Add or change behavior in the specifications before changing implementation.
8. Mark status Done only from current command evidence, never narration.
9. Do not publish, push, or create external resources without separate authorization.
10. At the end of each session or meaningful work block, save context through `/session-save`.

Required methodology rule: «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Quality Gates

- Python 3.11 wheel installs into a clean virtual environment.
- Pytest passes with at least 90% line coverage.
- Ruff and mypy pass.
- Golden results agree across Rich, JSON, and CSV.
- Process-level tests observe exit codes `0`, `1`, `2`, `3`, and `4`.
- Benchmark evidence includes environment, fixture cardinalities, wall time, and peak RSS.
- No database, API, auth, server, cloud, or Kubernetes artifact is introduced.

## Implementation Status

| Step | Scope | Status | Evidence required to mark Done |
|---:|---|---|---|
| 1 | Package skeleton and CLI contract | Planned | Install, help/version, CLI contract tests |
| 2 | Models and parser | Planned | Parser tests, Ruff, mypy |
| 3 | Core aggregations | Planned | Aggregation tests including one-pass proof |
| 4 | User-Agent exactness boundary | Planned | Limit tests and observed exit `4` |
| 5 | Rich renderer | Planned | Snapshot and no-color tests |
| 6 | JSON/CSV renderers | Planned | Schema, read-back, and equivalence tests |
| 7 | Input diagnostics and exit matrix | Planned | Process tests for `0/1/2/3/4` |
| 8 | Quality, package, performance | Planned | Full gates, clean-wheel smoke, benchmark record |
| 9 | Documentation and release readiness | Planned | Release checklist against exact wheel |

No implementation step is complete at blueprint time; product code was
intentionally not created.

## Session Handoff Format

At a handoff, record the active step, files changed, exact commands and results,
unresolved failures, benchmark environment if applicable, and the single next
action. Do not convert a failure into Planned/Done prose; keep it visible until
the evidence changes.
