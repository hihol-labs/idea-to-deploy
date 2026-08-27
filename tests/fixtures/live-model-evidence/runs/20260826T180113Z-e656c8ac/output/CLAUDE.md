# Project Instructions: Nginx Log Insights CLI

## Project Context

This repository is for a local Python 3.11 CLI that streams nginx combined access logs and reports top-10 IPs, top-10 URLs by 4xx/5xx count, hourly request distribution percentages, and exact unique User-Agent share. Default output is colored terminal text; JSON and CSV are stable pipeline formats. The target is a representative 1 GB log in under 30 seconds on a documented laptop.

Planning sources, in precedence order for product behavior:

1. `PRD.md` — behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — technical and CLI contracts.
3. `IMPLEMENTATION_PLAN.md` — dependency-ordered execution.
4. `STRATEGIC_PLAN.md` — product boundaries and success measures.
5. `CLAUDE_CODE_GUIDE.md` — bounded prompts for implementation sessions.

## Non-Negotiable Scope

- Local, stateless, single-process streaming CLI only.
- Python 3.11, Click, Rich, dataclasses, pip-installable package.
- No authentication, database, HTTP API, daemon/server, cloud, Docker runtime requirement, or Kubernetes.
- Budget is $0 and MVP delivery is one weekend.
- Do not implement approximate distinct counting unless the specifications are explicitly revised.
- Do not silently skip cardinality exhaustion, malformed strict input, or zero-valid-record input.

## Engineering Rules

- Preserve WIP=1: finish and verify the active implementation-plan step before starting another.
- Inspect the worktree before edits and preserve unrelated user changes.
- Use a `src/nginx_insights/` package layout and keep parsing, aggregation, rendering, and CLI boundaries separate.
- Stream file/stdin input; never use whole-file loading and never persist raw log records.
- Ensure deterministic ties: count descending, then key ascending.
- Calculate hourly percentages exactly as specified in the PRD and retain counts alongside rounded serialized percentages.
- Keep stdout exclusively for report data and stderr for concise privacy-safe diagnostics.
- Escape untrusted log-derived strings in terminal, JSON, and CSV renderers.
- Preserve the complete exit contract: `0` success; `1` runtime/input I/O failure; `2` usage/configuration error; `3` input data or strict parse failure; `4` unique-cardinality exhaustion.
- Change the specification first when externally visible behavior changes.
- Do not claim verification from expected behavior; run the relevant commands and report observed evidence.
- At the end of each session or meaningful work block, preserve context through `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Planned Repository Structure

```text
pyproject.toml
src/nginx_insights/
  __init__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  errors.py
  renderers/
    __init__.py
    terminal.py
    json_output.py
    csv_output.py
tests/
  fixtures/
  test_package.py
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
  test_end_to_end.py
  test_performance.py
  test_distribution.py
scripts/
  generate_benchmark_log.py
docs/
  BENCHMARK.md
```

This is a planned structure, not permission to generate all files at once. Follow the active step.

## Verification Baseline

Use the commands named by the active step in `IMPLEMENTATION_PLAN.md`. The eventual baseline includes:

```text
python3.11 -m pytest --cov=nginx_insights --cov-fail-under=90 -q
python3.11 -m ruff check src tests
python3.11 -m mypy src/nginx_insights
python3.11 -m build
python3.11 -m twine check dist/*
```

The 1 GB release benchmark is a separate mandatory gate and must bind results to the exact release candidate and declared reference hardware.

## Step Status

| Step | Description | Status |
|---:|---|---|
| 1 | Package and contract scaffold | Not started |
| 2 | Dataclasses and combined-log parser | Not started |
| 3 | Streaming aggregation core | Not started |
| 4 | Input and failure semantics | Not started |
| 5 | Terminal renderer | Not started |
| 6 | JSON and CSV renderers | Not started |
| 7 | Correctness, security, compatibility hardening | Not started |
| 8 | Performance gate | Not started |
| 9 | Packaging and release documentation | Not started |

Update only the active row after attaching the verification evidence required by the implementation plan. Product code has not been implemented during the blueprint phase.
