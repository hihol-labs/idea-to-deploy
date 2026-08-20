# Repository Instructions: nginx Stream Analytics CLI

## Project Context

This repository is the specification-first plan for `nginx-stream-report`, a local pip-installable Python 3.11 CLI for DevOps/SRE users. It streams nginx combined-format access logs and reports top 10 IPs, top 10 4xx/5xx request targets, hourly request distribution, and unique User-Agent share. Terminal text is the default; JSON and CSV support pipelines.

Read `AGENTS.md` and the applicable repository-local `.itd-plugin` skill before lifecycle work. Treat `.itd/` as the project/verification contract and `.itd-memory/` as canonical execution state.

## Source of Truth

Documents have this authority:

1. `PRD.md` defines product behavior and acceptance.
2. `PROJECT_ARCHITECTURE.md` defines technical, metric, CLI, output, and failure contracts.
3. `IMPLEMENTATION_PLAN.md` defines sequencing and checks.
4. `STRATEGIC_PLAN.md` defines scope, priorities, constraints, and success measures.
5. `CLAUDE_CODE_GUIDE.md` supplies step prompts but cannot override the specifications.

When behavior must change, update and approve the specification first, then implementation. Never alter the spec merely to make a failing implementation appear correct.

## Non-negotiable Rules

- Product code targets Python 3.11 with Click, Rich, dataclasses, and pip packaging.
- Maintain one stateless local process and line-by-line input.
- Add no authentication, database, HTTP API, server/daemon, cloud, paid service, or Kubernetes.
- Do not load an entire input file, persist reports, or silently approximate metrics.
- Hourly percentages use exactly `100 × hourly_request_count / total_valid_requests`; never emit an unscaled fraction.
- Rankings use count descending and exact key ascending for ties.
- Treat log-derived strings as untrusted text; do not interpret them as markup, terminal instructions, paths, or code.
- Keep stdout exclusively for the selected report and stderr for diagnostics.
- Preserve WIP=1 and do not mark work complete without the evidence required by `.itd/VERIFICATION_CONTRACT.json`.
- Product source code does not exist yet; follow the implementation plan and do not skip ahead.
- At the end of every session or significant block of work, save context through `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Exit-code Contract

Every implementation and guide must retain the full mapping:

| Code | Meaning |
|---:|---|
| `0` | Successful complete report, including mixed valid/malformed input |
| `1` | Unexpected internal error |
| `2` | CLI usage or input I/O error |
| `3` | Zero valid nginx records |
| `4` | Unique-cardinality exhaustion: the configured exact User-Agent limit would be exceeded |

Code `4` must not be omitted, remapped, or replaced with approximation. Expected failure paths produce no partial report or traceback.

## Planned Stack and Structure

```text
pyproject.toml
src/nginx_stream_report/
  cli.py
  input.py
  parser.py
  models.py
  aggregate.py
  renderers/{terminal,json,csv}.py
tests/
scripts/
docs/
```

Runtime dependencies are Click and Rich. Prefer the Python standard library otherwise. Planned development checks are pytest with coverage, Ruff, and mypy.

## Implementation Status

| Step | Scope | Status |
|---:|---|---|
| 1 | Package skeleton and executable contract | Not started |
| 2 | Combined-format parser and input lifecycle | Not started |
| 3 | IP and error-URL rankings | Not started |
| 4 | Hourly and exact User-Agent metrics | Not started |
| 5 | Rich terminal renderer | Not started |
| 6 | JSON and CSV renderers | Not started |
| 7 | Failure matrix and distribution | Not started |
| 8 | Correctness and 1 GB performance acceptance | Not started |

Update only the active row when evidence supports a state change. Keep the next action singular and explicit in `.itd-memory/` handoff state.

## Standard Quality Commands (once implemented)

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/python -m pytest -q --cov=nginx_stream_report --cov-report=term-missing --cov-fail-under=90
.venv/bin/python -m build
```

The 1 GB benchmark is a separate measured acceptance gate described in `PROJECT_ARCHITECTURE.md` and `IMPLEMENTATION_PLAN.md`; never claim its target from a smoke test or estimate.

## Session Handoff

Record the active step, files changed, exact verification commands/results, exit paths tested (explicitly including code `4`), spec deviations, blockers, and one next action. Reconcile Idea to Deploy state and save context through `/session-save`.
