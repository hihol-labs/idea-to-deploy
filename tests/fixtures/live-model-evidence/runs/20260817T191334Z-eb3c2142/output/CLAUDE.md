# nginx-stream-stats Project Instructions

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams
nginx combined access logs and reports top 10 IPs, top 10 4xx/5xx URL paths,
24 hourly request percentages, and exact unique User-Agent share. Default output
is colored Rich text; `--json` and `--csv` are stable pipeline formats. The
release target is a representative 1 GB log in under 30 seconds on a documented
laptop. Cash and infrastructure budget is $0; delivery is one weekend.

The current repository phase is blueprint complete, product implementation not
started. Read `PRD.md`, `PROJECT_ARCHITECTURE.md`, and
`IMPLEMENTATION_PLAN.md` before product changes.

## Source-of-Truth Order

1. User instructions and `.itd/` project contracts.
2. `PRD.md` for observable behavior and acceptance criteria.
3. `PROJECT_ARCHITECTURE.md` for interfaces, data semantics, and boundaries.
4. `IMPLEMENTATION_PLAN.md` for sequence and verification commands.
5. `CLAUDE_CODE_GUIDE.md` for bounded per-step execution prompts.
6. `STRATEGIC_PLAN.md` for priorities, KPIs, budget, and scope control.

If documents conflict, stop implementation, reconcile the durable specs, then
resume. Do not let generated code silently become the source of truth.

## Mandatory Rules

- Preserve WIP=1 and implement one numbered plan step at a time.
- Use Python 3.11, Click, Rich, dataclasses, a `src/` layout, and pip packaging.
- Maintain one local stateless process. Do not add authentication, database,
  HTTP API, server, network service, cloud, Docker, or Kubernetes.
- Consume input incrementally; never retain raw-log collections or persist logs.
- Treat log values as untrusted data. Never execute them, use them as Rich
  markup, echo malformed raw lines, or send them over a network.
- Hourly percentages always use
  `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share is exact. Cardinality exhaustion must fail explicitly;
  it must never switch silently to approximation.
- Preserve the full exit contract everywhere: `0` success, `1` unexpected
  runtime/non-pipe output failure, `2` usage/configuration error, `3`
  input/log-data error, `4` unique-cardinality exhaustion.
- Keep JSON/CSV stdout free of ANSI sequences and diagnostics.
- Never claim the 1 GB/<30 s goal without current measured evidence naming the
  machine and representative fixture.
- Run the verification commands for the active step and reconcile Idea to
  Deploy state before marking it complete.
- **В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save**.

## Approved Stack

| Concern | Choice |
|---|---|
| Runtime | Python 3.11 |
| CLI | Click |
| Terminal | Rich |
| Models | Standard-library dataclasses and type annotations |
| Parsing/aggregation | Python standard library, single-process streaming |
| Packaging | `pyproject.toml`, pip, console entry point, sdist and wheel |
| Verification | pytest, coverage, Ruff, mypy, representative benchmark |

Dependency additions require a concrete need, license compatibility, and a
spec update. Prefer the standard library in the hot path.

## Planned Repository Structure

```text
src/nginx_stream_stats/
  __init__.py
  cli.py
  models.py
  parser.py
  aggregator.py
  inputs.py
  errors.py
  renderers/{__init__,text,json,csv}.py
tests/
  fixtures/
  unit/
  integration/
  performance/
docs/PERFORMANCE_BASELINE.md
pyproject.toml
```

Do not create these paths ahead of their numbered implementation step.

## Architecture Boundaries

- `cli.py` owns Click, orchestration, stderr, and exit translation.
- `inputs.py` owns file/stdin stream lifecycle.
- `parser.py` converts one untrusted line into one validated `LogRecord`.
- `aggregator.py` owns exact bounded counters and report finalization.
- Renderers consume only `AnalysisReport`; they do not parse or aggregate.
- Models and errors import no Click or Rich concerns.

There are no database tables and no HTTP endpoints. OS read/execute permissions
are the only authorization boundary.

## Status

| Step | Deliverable | State |
|---:|---|---|
| Blueprint | Strategy, architecture, PRD, implementation plan, README, guides | Complete |
| 1 | Package and domain contracts | Not started |
| 2 | Combined-log parser | Not started |
| 3 | Core aggregations | Not started |
| 4 | Percentages and cardinality guardrails | Not started |
| 5 | Text/JSON/CSV renderers | Not started |
| 6 | CLI and exit-code integration | Not started |
| 7 | Correctness/security/performance evidence | Not started |
| 8 | Distribution, docs, optional gzip | Not started |

Update only the active row when evidence satisfies its plan checks. “Code
written” is not a completed state.

## Common Commands After Step 1

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src
.venv/bin/python -m pytest --cov=nginx_stream_stats --cov-fail-under=90
```

Run the 1 GB benchmark only through the command defined in Step 7; record rather
than infer its result.
