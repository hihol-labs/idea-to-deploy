# Project Memory: nginx Log Top

## Context

nginx Log Top is a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams an nginx access log and reports top 10 client IPs, top 10 URLs producing 4xx/5xx responses, all 24 hourly request buckets, and unique User-Agent share. Default output is colored terminal text; `--json` and `--csv` are pipeline contracts.

The governing architecture decision is: **no database — stateless streaming processing; no HTTP API — CLI-only tool**. There is also no authentication, daemon, server, cloud, Docker, or Kubernetes.

## Source of Truth

Read in this order:

1. `AGENTS.md` and `.itd/` for methodology and active execution contracts.
2. `PRD.md` for behavior, priority, and acceptance.
3. `PROJECT_ARCHITECTURE.md` for grammar, components, CLI/schema/exit, security, and performance contracts.
4. `IMPLEMENTATION_PLAN.md` for the only approved step sequence.
5. `STRATEGIC_PLAN.md` for goals, RICE/MoSCoW, risks, and kill criteria.
6. `CLAUDE_CODE_GUIDE.md` for bounded step prompts.

When behavior changes, update the specs before code. Do not scatter agent instructions into new instruction files.

## Stack

- Python 3.11
- Click
- Rich
- dataclasses and Python standard-library streaming/serialization utilities
- pip-compatible wheel and source distribution
- pytest, Ruff, mypy, and coverage during implementation

## Planned Structure

```text
src/nginx_log_top/
  cli.py input.py parser.py models.py aggregate.py reports.py
  renderers/terminal.py renderers/json.py renderers/csv.py
tests/
  fixtures/ and correctness, contract, safety, package, performance tests
benchmarks/
  deterministic fixture generator and benchmark protocol
```

## Non-Negotiable Rules

- Preserve WIP=1 and the active `.itd/SCOPE_LOCK.md`.
- Never add product code during a planning-only unit.
- Parse input once; never materialize request records or persist log data.
- Exact aggregation memory is cardinality-dependent, not constant or inherently bounded.
- Keep data stdout clean; send diagnostics and errors to stderr.
- Treat every log value as untrusted. Enforce terminal control/bidi sanitization, Rich escaping, standard JSON/CSV serialization, and CSV formula-cell protection.
- Do not add a database, HTTP API, auth, server, network call, telemetry, cloud, Docker, or Kubernetes without a new approved scope.
- Record actual test and benchmark output. A standalone `PASSED` or narrative claim is not acceptance.
- Freeze the exact staged candidate, run its declared machine oracle, and require the current risk-tier adjudication receipt before marking an implementation unit complete.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Delivery Status

| Step | Deliverable | Status | Evidence / next action |
|---:|---|---|---|
| Blueprint | Six required planning files plus README and `.gitignore` | Complete | File/heading/decision/story/step/placeholder checks passed on 2026-07-30 |
| 1 | Packaging and CLI shell | Not started | Start only in a new implementation unit |
| 2 | Domain contracts and fixtures | Not started | Blocked by Step 1 |
| 3 | Streaming parser | Not started | Blocked by Step 2 |
| 4 | Input and error boundary | Not started | Blocked by Step 3 |
| 5 | Exact aggregations | Not started | Blocked by Steps 2–4 |
| 6 | JSON renderer | Not started | Blocked by Step 5 |
| 7 | Terminal renderer | Not started | Blocked by Step 5 |
| 8 | CSV renderer | Not started | Blocked by Step 5 |
| 9 | Integrated quality/package | Not started | Blocked by Steps 1–8 |
| 10 | Benchmarks and exact candidate | Not started | Blocked by Step 9 |

## Current Handoff

The blueprint is validated. The next action is to open a new scoped unit for Step 1 of `IMPLEMENTATION_PLAN.md`; do not implement later steps concurrently.
