# Nginx Stream Analyzer — Project Memory

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams a supported nginx combined access log and reports top 10 IPs, top 10 URLs by 4xx/5xx errors, 24-hour request distribution, and unique User-Agent share. Default output is colored Rich text; `--json` and `--csv` serve pipelines. The target is 1 GB in under 30 seconds on a recorded laptop, with $0 infrastructure and a one-weekend P0 scope.

The durable specifications are `PRD.md`, `PROJECT_ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, and `STRATEGIC_PLAN.md`. When behavior changes, update the specification first. Use `CLAUDE_CODE_GUIDE.md` for step prompts.

## Non-Negotiable Decisions

- Use Python 3.11, Click, Rich, dataclasses, src layout, and pip-compatible packaging.
- Use one local process and one streaming pass; retain aggregates, never raw records.
- No authentication, database, HTTP API, server, telemetry, cloud, Docker runtime requirement, or Kubernetes.
- Inputs are one local path or stdin. Logs are untrusted data and never commands.
- Default top count is 10. Error URLs count statuses 400–599 inclusive.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`; it is not an unscaled fraction.
- Unique User-Agent share is exact distinct nonempty User-Agents divided by all valid requests, multiplied by 100.
- Exact User-Agent tracking is bounded. The full exit contract is: `0` success, `1` operational I/O failure, `2` usage/configuration error, `3` data failure or no valid requests, `4` unique-cardinality exhaustion.
- JSON/CSV stdout contains only the report; diagnostics go to stderr.
- Do not implement P1/P2 until all P0 gates and the performance target pass.

## Intended Repository Structure

```text
pyproject.toml
src/nginx_stream_analyzer/
  __init__.py
  cli.py
  errors.py
  models.py
  parser.py
  aggregate.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
  test_cli.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_terminal_renderer.py
  test_integration.py
  test_security_boundaries.py
scripts/generate_benchmark_log.py
benchmarks/README.md
```

This is the planned layout, not evidence that these implementation files exist.

## Engineering Rules

1. Preserve WIP=1: implement one numbered step from `IMPLEMENTATION_PLAN.md` at a time.
2. Read the active scope and acceptance criteria before editing. Do not silently broaden behavior.
3. Prefer typed small functions and immutable dataclasses. Keep Rich out of parsing/aggregation.
4. Own and close file resources at the CLI boundary; do not close caller-owned stdin.
5. Make rankings deterministic and round percentages only at rendering.
6. Escape terminal control sequences and avoid raw malformed-line diagnostics.
7. Profile before optimizing. Record fixture checksum and environment for performance claims.
8. Add/adjust tests with every behavior change; run the active step’s full verification set.
9. Never call a failed or unrun check successful. Record recovery until green.
10. Freeze and verify the exact staged candidate under `.itd/VERIFICATION_CONTRACT.json` before acceptance.
11. At the end of every session or meaningful block of work, save context through `/session-save`.

## Standard Verification

Use the exact commands specified by the active implementation step. The final gate is expected to include:

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest --cov=nginx_stream_analyzer --cov-fail-under=90
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
```

In addition, install the built wheel in a fresh Python 3.11 environment, smoke-test file/stdin with terminal/JSON/CSV, observe exits 0/1/2/3/4, and record the 1 GB benchmark. These commands are future implementation guidance; the Blueprint session creates no product code.

## Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 0 | Full Blueprint documents | Complete when all six required root documents exist | Document structure/content checks |
| 1 | Package and CLI skeleton | Not started | install/help/CLI tests |
| 2 | Models and parser | Not started | parser tests, Ruff, mypy |
| 3 | Streaming aggregation | Not started | metric/exhaustion tests and coverage |
| 4 | JSON and CSV | Not started | golden and parse smoke tests |
| 5 | Rich terminal output | Not started | renderer tests and no-color smoke |
| 6 | I/O and exit integration | Not started | subprocess exits 0/1/2/3/4 |
| 7 | Performance and hardening | Not started | security tests, wall time, peak RSS |
| 8 | Release readiness | Not started | all quality/build/fresh-wheel checks and current adjudication receipt |

## Next Action

Begin Step 1 only when implementation is explicitly authorized. Until then, preserve these planning documents as the source of truth and leave product code absent.
