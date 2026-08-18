# Project Memory: nginx-insights

## Product Context

`nginx-insights` is a local, pip-installable Python 3.11 command-line tool for DevOps/SRE engineers. It streams standard nginx common/combined access logs and reports:

1. Top 10 client IPs by valid request count.
2. Top 10 request targets by 4xx/5xx count.
3. All 24 hourly request percentages using `100 × hourly_request_count / total_valid_requests`.
4. Exact non-null unique User-Agent share over total valid requests, subject to an explicit cardinality cap.

Default output is colored Rich terminal text. `--json` and `--csv` are stable, undecorated pipeline formats. The performance target is a deterministic 1 GB log in under 30 seconds on a documented laptop. Budget is $0 and MVP delivery is one weekend.

## Source of Truth

Read these documents before product work:

1. `PRD.md` — behavior, priorities, user stories, and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — components, calculations, schemas, CLI, and architecture decisions.
3. `IMPLEMENTATION_PLAN.md` — WIP=1 delivery order and verification commands.
4. `STRATEGIC_PLAN.md` — audience, alternatives, risks, roadmap, and Definition of Done.
5. `CLAUDE_CODE_GUIDE.md` — bounded prompts for future implementation sessions.

The specifications are durable source assets. Change the applicable specification and acceptance criteria before changing contracted behavior. Never treat generated code as more authoritative than an approved spec.

## Non-Negotiable Decisions

- Use Python 3.11, Click, Rich, and standard-library dataclasses; distribute through pip.
- Use one local process, line-by-line input, and no retention of parsed records.
- Do not add authentication, a database, an HTTP API, daemon/server, cloud component, Docker requirement, or Kubernetes.
- Do not perform network requests or telemetry. Open only user-supplied input paths, read-only.
- Support standard nginx `combined` and `common` formats in the MVP; arbitrary `log_format` is P2.
- Malformed lines are counted and skipped; zero valid records is an input/parse failure.
- Sort top lists by descending count and ascending key, then take 10.
- Keep report calculation in the analyzer and make all renderers consume one `AnalysisReport`.
- Keep JSON/CSV stdout machine-parseable; diagnostics belong on stderr.
- Do not silently approximate unique User-Agent cardinality. Enforce the configured exact limit.

## Complete Exit-Code Contract

| Code | Required meaning |
|---:|---|
| `0` | Successful report, help, or version |
| `1` | Unexpected internal/runtime failure |
| `2` | Click usage error |
| `3` | Input/parse failure: unreadable input, stream failure, or zero valid records |
| `4` | Unique-cardinality exhaustion |

Code `4` must remain a distinct public contract and must never be omitted, swallowed, or remapped to `1` or `3`. Every implementation guide, CLI test matrix, and user-facing exit-code section must carry all five codes `0/1/2/3/4`.

## Intended Repository Structure

```text
pyproject.toml
src/nginx_insights/
  __init__.py
  cli.py
  models.py
  parser.py
  analyzer.py
  errors.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  test_models.py
  test_parser.py
  test_analyzer.py
  test_renderers.py
  test_cli.py
  test_performance.py
scripts/generate_benchmark_log.py
docs/BENCHMARK.md
```

This is a planned structure, not evidence that implementation exists.

## Engineering Rules

- Preserve WIP=1: implement only the active step in `IMPLEMENTATION_PLAN.md`.
- Keep dependency direction toward dataclasses/core logic; parser and analyzer must not import Click or Rich.
- Treat log content as untrusted data. Do not evaluate it, interpolate it into shell commands, or emit raw terminal control sequences.
- Use a precompiled parser and primitive aggregate updates on the hot path; do not render per line.
- Add or update tests with behavior. Never claim a check or benchmark that was not actually run against the candidate.
- Benchmark fixture generation is outside timed analysis and generated 1 GB logs are never committed.
- Performance optimization follows profiling. Architecture changes require an updated architecture decision and PRD impact review.
- Do not place secrets in the repository; the product requires no environment variables or credentials.
- «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Verification Baseline

Future implementation is not complete until the exact candidate passes:

```text
python3.11 -m pytest --cov=nginx_insights --cov-fail-under=90
python3.11 -m ruff format --check .
python3.11 -m ruff check .
python3.11 -m mypy src
python3.11 -m build
python3.11 -m twine check dist/*
```

The separately marked 1 GB benchmark must run on the documented reference laptop three times, with each timed analysis below 30 seconds. A clean environment must install the built wheel and structurally parse both JSON and CSV smoke outputs.

## Implementation Status

Blueprint status is complete; product implementation has not started.

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Not started | Install/help/version and CLI tests |
| 2 | Models and failure contract | Not started | Model tests and complete exit matrix |
| 3 | Common/combined parser | Not started | Parser fixtures and hostile-line test |
| 4 | Streaming analysis | Not started | Metric goldens, formula, cap tests |
| 5 | Terminal/JSON/CSV renderers | Not started | Structural renderer and escaping tests |
| 6 | End-to-end CLI | Not started | File/stdin/output/exit subprocess tests |
| 7 | Performance and quality | Not started | 1 GB timings, memory, tests, lint, types |
| 8 | Release readiness | Not started | Built/checked/clean-installed artifacts |

## Session Handoff

At the end of work, update the status row only when its named evidence exists. Record the active step, files changed, exact commands and outcomes, blockers, and one next action. A narrative claim is not verification. Do not claim an adversarial or independent review unless its actual external artifact exists and can be attributed to that separate session.
