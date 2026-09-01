# Project Memory: nginx-stream-insights

## Context

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports:

1. Top 10 client IPs by valid-request count.
2. Top 10 request targets by 4xx/5xx count.
3. All 24 hourly request percentages, each calculated as `100 × hourly_request_count / total_valid_requests`.
4. Exact unique User-Agent count and share, subject to a hard cardinality ceiling.

Default output is colored Rich terminal text. `--json` and `--csv` provide stable pipeline formats. The target is a representative 1 GB log in under 30 seconds on a documented laptop. The project is open source, costs $0, and is scoped to one weekend.

## Source-of-Truth Order

1. `PRD.md` — observable behavior, metric definitions, priorities, and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — components, boundaries, schemas, and CLI contract.
3. `IMPLEMENTATION_PLAN.md` — dependency-ordered implementation units and verification commands.
4. `CLAUDE_CODE_GUIDE.md` — bounded prompts for executing one plan step at a time.
5. `STRATEGIC_PLAN.md` — goals, competitive context, roadmap, risks, and Definition of Done.

When behavior changes, update the specification first and then reconcile code and tests. Do not let implementation silently redefine the product.

## Hard Rules

- Use Python 3.11, Click, Rich, dataclasses, and standard pip packaging.
- Keep a single local process and consume input in one streaming pass.
- Do not add authentication, a database, an HTTP API, a server/daemon, cloud resources, or Kubernetes.
- Do not persist log records or results and do not make network calls.
- Keep calculations outside renderers and keep I/O orchestration outside parser/aggregator modules.
- Preserve deterministic tie ordering and stable JSON/CSV schemas.
- Treat log content as untrusted; enforce maximum line length and safe CSV cells.
- Preserve exit codes: `0` success, `1` input/read/runtime failure, `2` usage error, `3` no valid requests, `4` unique-cardinality exhaustion.
- Never silently approximate exact User-Agent cardinality; fail with code 4 at the configured ceiling.
- Preserve WIP=1 and verify the active step before moving to the next.
- Do not claim completion from prose; record the commands and results required by the current `.itd/VERIFICATION_CONTRACT.json`.
- Do not publish packages, push branches, tag releases, or contact external systems without explicit authorization.
- At the end of every session or meaningful work block, save context through `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Approved Stack

| Concern | Choice |
|---|---|
| Runtime | Python 3.11 |
| CLI | Click |
| Terminal UI | Rich |
| Records | Standard-library dataclasses |
| Aggregation | Standard-library `Counter`, fixed list, bounded set |
| Packaging | `pyproject.toml`, wheel/sdist, pip console script |
| Testing | pytest, pytest-cov, golden fixtures |
| Static quality | Ruff and mypy |

## Planned Structure

```text
pyproject.toml
src/nginx_stream_insights/
  __init__.py
  cli.py
  parser.py
  models.py
  aggregator.py
  errors.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  perf/
  test_cli.py
  test_parser.py
  test_models.py
  test_aggregator.py
  test_renderers.py
  test_performance.py
scripts/benchmark.sh
```

This is a planned layout, not evidence that product code exists.

## Metric Invariants

- Every physical line is classified exactly once.
- `total_lines == total_valid_requests + malformed_lines`.
- `sum(hourly_counts) == total_valid_requests`.
- Only status 400–599 contributes to error URL counts.
- Rankings use count descending, then key ascending.
- Percentages round only during rendering.
- Machine-readable stdout contains no diagnostics or ANSI codes.

## Implementation Status

| Step | Unit | Status | Required evidence |
|---:|---|---|---|
| 0 | Blueprint documents | Complete | Six required root documents exist and content checks pass |
| 1 | Package and verification skeleton | Not started | Editable install, CLI test, help invocation |
| 2 | Domain models and errors | Not started | Model tests and mypy |
| 3 | Streaming parser | Not started | Parser tests and Ruff |
| 4 | One-pass aggregation | Not started | Aggregator tests and focused coverage |
| 5 | Rich terminal renderer | Not started | Terminal golden test and Ruff |
| 6 | JSON and CSV renderers | Not started | Golden/schema tests and coverage |
| 7 | CLI orchestration | Not started | File/stdin and all-exit-code integration tests |
| 8 | Performance gate | Not started | Three 1 GB timings and peak RSS plus full tests |
| 9 | Package and release check | Not started | Full QA, clean wheel install, benchmark |

Only one row may be In progress. A row becomes Complete only after its verification evidence is current.

## Current Handoff

The blueprint is complete; product implementation has not started. The next authorized implementation action is Step 1 in `IMPLEMENTATION_PLAN.md`, using Prompt 1 in `CLAUDE_CODE_GUIDE.md`. Before implementation, confirm the active Idea to Deploy scope/state contracts describe that unit.
