# nginx-insights Project Instructions

## Project Context

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams nginx common/combined access logs and reports top-10 IPs, top-10 normalized URL paths by combined 4xx/5xx count, hourly request percentages, and unique User-Agent share. Terminal output is the default; JSON and CSV are pipeline contracts. The product is local, stateless, pip-installable, open source, and constrained to a one-weekend/$0 MVP.

Planning is complete; product code has not been implemented by the blueprint workflow.

## Source-of-Truth Order

1. `PRD.md` — behavior, priorities, and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — interfaces, data semantics, boundaries, and decisions.
3. `IMPLEMENTATION_PLAN.md` — dependency-ordered work and checks.
4. `CLAUDE_CODE_GUIDE.md` — reusable implementation prompts.
5. `STRATEGIC_PLAN.md` — product goals, roadmap, risks, and release criteria.

If documents conflict, reconcile them before code changes; do not silently choose an interpretation.

## Non-Negotiable Rules

- Use Python 3.11, Click, Rich, and dataclasses; package through pip.
- Keep a single-process, one-pass streaming architecture and never retain raw log lines.
- Do not add authentication, a database, HTTP API, server, cloud service, or Kubernetes.
- Preserve stdout for the selected report and stderr for diagnostics.
- Hourly distribution is `100 × hourly_request_count / total_valid_requests`.
- Preserve exact deterministic top-10 results; do not introduce approximation without a PRD decision.
- Preserve exit codes: 0 success, 1 I/O/operational failure, 2 usage/configuration, 3 zero valid requests, 4 unique-cardinality exhaustion.
- Add tests with behavior and run them; never claim a pass without command evidence.
- Keep work-in-progress at one implementation-plan step.
- Do not commit generated gigabyte benchmark fixtures.
- At the end of every session or significant block of work, save context through `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Repository Structure

```text
src/nginx_insights/
  __init__.py
  __main__.py
  cli.py
  models.py
  errors.py
  input.py
  parser.py
  normalize.py
  aggregate.py
  report.py
  render_terminal.py
  render_json.py
  render_csv.py
tests/
  fixtures/
  golden/
  test_cli.py
  test_parser.py
  test_normalize.py
  test_aggregate.py
  test_render_terminal.py
  test_render_json.py
  test_render_csv.py
  test_end_to_end.py
  test_exit_codes.py
benchmarks/
  generate_log.py
  run_benchmark.py
```

This is a planned structure, not permission to create all files at once. Follow `IMPLEMENTATION_PLAN.md` step boundaries.

## Verification Baseline

- Fast correctness: `python3.11 -m pytest -q`
- Syntax/import surface: `python3.11 -m compileall -q src tests`
- Coverage: `python3.11 -m pytest -q --cov=nginx_insights --cov-report=term-missing --cov-fail-under=90`
- Release benchmark: the exact commands in Implementation Plan Step 9
- Packaging: the exact commands in Implementation Plan Step 10

Run only relevant checks during a step, then the full required set at the release boundary.

## Status

| Step | Name | Status | Evidence |
|---:|---|---|---|
| 1 | Package skeleton and contracts | Not started | None |
| 2 | Parser and normalization | Not started | None |
| 3 | Streaming aggregation | Not started | None |
| 4 | Input orchestration and failure mapping | Not started | None |
| 5 | JSON renderer | Not started | None |
| 6 | CSV renderer | Not started | None |
| 7 | Rich terminal renderer | Not started | None |
| 8 | End-to-end quality tests | Not started | None |
| 9 | Performance qualification | Not started | None |
| 10 | Packaging and release readiness | Not started | None |

Update a row only from real test or benchmark evidence and keep the next action explicit.
