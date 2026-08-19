# Nginx Log Lens Project Memory

## Context

Nginx Log Lens is a local Python 3.11 CLI for DevOps/SRE engineers. It streams
nginx combined access logs and reports top client IPs, top 4xx/5xx URLs, hourly
request percentages, and unique User-Agent share. Default output is Rich text;
JSON and CSV support pipelines. The product is open source, costs $0 to operate,
and targets a one-weekend MVP.

## Source of Truth

Read these documents before implementation:

1. `PRD.md` — behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — module, CLI, data, output, and error contracts.
3. `IMPLEMENTATION_PLAN.md` — ordered work and verification commands.
4. `CLAUDE_CODE_GUIDE.md` — bounded prompt for each step.
5. `STRATEGIC_PLAN.md` — product boundaries, priority, and release gates.

When behavior must change, update the specification first, then reconcile the
architecture and plan before changing code.

## Non-Negotiable Rules

- Python 3.11, Click, Rich, dataclasses, pip-installable `src/` package.
- One local process, one-pass input, no full-file materialization.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Hourly percentage is exactly
  `100 × hourly_request_count / total_valid_requests`, never an unscaled
  fraction.
- Exit codes are exactly: `0` success; `1` input/I/O failure; `2` CLI usage
  error; `3` nonempty input with no valid records; `4` unique-cardinality
  exhaustion. Code 4 is mandatory and must not be remapped.
- The complete exit-code contract is `0/1/2/3/4`. Code `4` means unique-cardinality exhaustion.
- No partial report on exit 1, 2, 3, or 4. Data is stdout; diagnostics are
  stderr.
- All renderers consume the same frozen report model.
- The fixed 1 GB acceptance log must complete below 30 seconds on the declared
  reference laptop and within the documented memory gate.
- Do not create `DEVILS_ADVOCATE_REVIEW.md` during implementation; independent
  review provenance belongs to the designated external review session.
- **В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save**.

## Intended Structure

```text
src/nginx_log_lens/
  __init__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  errors.py
  renderers/
    __init__.py
    text.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
  test_parser.py
  test_aggregate_rankings.py
  test_aggregate_metrics.py
  test_renderers.py
  test_cli.py
  test_exit_codes.py
  test_end_to_end.py
scripts/
  generate_benchmark_log.py
  run_benchmark.sh
```

This is an intended implementation layout, not evidence that these files
already exist.

## Standard Verification

Run step-specific commands from `IMPLEMENTATION_PLAN.md`, then the full gate:

```bash
.venv/bin/python -m pytest --cov=nginx_log_lens --cov-fail-under=90
.venv/bin/ruff check .
.venv/bin/mypy src
```

Performance and clean-wheel installation are additional release gates, not
replacements for the correctness suite.

## Status

WIP limit is one implementation step. Blueprint documentation does not mark any
product implementation step complete.

| Step | Scope | Status | Evidence |
|---:|---|---|---|
| 1 | Package foundation | Not started | None; planning only |
| 2 | Combined parser | Not started | None; planning only |
| 3 | Ranked metrics | Not started | None; planning only |
| 4 | Hourly and User-Agent metrics | Not started | None; planning only |
| 5 | Three renderers | Not started | None; planning only |
| 6 | CLI and exit handling | Not started | None; planning only |
| 7 | Quality closure | Not started | None; planning only |
| 8 | 1 GB performance proof | Not started | None; planning only |
| 9 | Distribution handoff | Not started | None; planning only |

## Current Next Action

Begin only Step 1 from `IMPLEMENTATION_PLAN.md`. Do not implement later steps
in parallel, and do not infer completion from this blueprint.
