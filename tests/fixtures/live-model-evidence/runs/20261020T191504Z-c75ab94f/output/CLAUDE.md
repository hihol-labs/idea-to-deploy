# Project Memory: nginx-log-top

## Context

`nginx-log-top` is a local open-source Python 3.11 CLI for DevOps/SRE incident triage. It streams nginx Combined Log Format logs and reports top-10 client IPs, top-10 4xx/5xx URLs, hourly request percentages, and exact unique User-Agent share. It emits Rich terminal text by default and supports JSON and CSV for pipelines.

The project is documentation-only at blueprint completion. Product code must be implemented in the order and boundaries defined by `IMPLEMENTATION_PLAN.md`.

## Source of Truth

1. `PRD.md` defines observable product behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` defines the CLI, data, module, algorithm, output, and exit contracts.
3. `IMPLEMENTATION_PLAN.md` defines file-level delivery order and verification.
4. `STRATEGIC_PLAN.md` defines scope, priorities, success measures, and reassessment criteria.
5. `CLAUDE_CODE_GUIDE.md` supplies bounded implementation prompts; it does not override the specifications above.

When behavior changes, update the specifications first and keep all documents consistent.

## Non-Negotiable Decisions

- Python 3.11, Click, Rich, standard-library dataclasses, and pip-compatible packaging.
- One synchronous local process; stream line by line and retain no raw requests.
- No authentication, database, HTTP API, server, cloud service, Docker runtime, or Kubernetes.
- Default Rich text plus mutually exclusive `--json` and `--csv` modes.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`, with zero for empty input.
- Exact User-Agent cardinality has a configurable hard ceiling.
- Complete exit-code contract: `0/1/2/3/4`; code `4` means unique-cardinality exhaustion and must never be omitted or remapped.
- The release performance gate is a recorded representative 1 GB run under 30 seconds on a documented laptop.
- Never print full malformed log lines in diagnostics; they may contain sensitive data.

## Expected Structure

```text
pyproject.toml
src/nginx_log_top/
  __init__.py
  __main__.py
  cli.py
  errors.py
  models.py
  parser.py
  aggregate.py
  renderers/{__init__,text,json,csv}.py
scripts/generate_benchmark_log.py
tests/
  fixtures/
  test_models.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_performance.py
```

## Engineering Rules

- Work on one numbered implementation step at a time and do not mix deferred P1/P2 features into P0 work.
- Add tests with new behavior and run the step checks before changing its status.
- Preserve deterministic ties: count descending, then key lexicographically ascending.
- Keep Click and stream ownership at the CLI boundary; parsers, aggregation, and renderers remain independently testable.
- Machine output must be ANSI-free and stable; diagnostics go only to stderr.
- Do not silently approximate an exact metric or increase a safety ceiling to make a test pass.
- Generated 1 GB benchmark data belongs outside the repository.
- Do not claim external, adversarial, or independent review unless its artifact exists and identifies the actual reviewer.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Verification Baseline

```text
ruff format --check .
ruff check .
mypy src
pytest --cov=nginx_log_top --cov-report=term-missing --cov-fail-under=90
python3.11 -m build
python3.11 -m twine check dist/*
```

Performance acceptance additionally requires the exact generator and `/usr/bin/time -v` command from Step 8 of `IMPLEMENTATION_PLAN.md`.

## Implementation Status

| Step | Deliverable | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Not started | Install, help/version, CLI tests |
| 2 | Models, errors, fixtures | Not started | Model tests and compileall |
| 3 | Streaming parser | Not started | Parser tests, lint, typing |
| 4 | Aggregation and metrics | Not started | Boundary, formula, cardinality tests |
| 5 | Rich terminal renderer | Not started | Text and ANSI tests |
| 6 | JSON and CSV renderers | Not started | Structural renderer and CLI tests |
| 7 | Error integration | Not started | Full suite and `0/1/2/3/4` tests |
| 8 | Performance and packaging | Not started | Quality gates, wheel smoke, benchmark |

Only set a row to Complete after recording its actual commands and results. The next action is Step 1; no product code exists yet.

