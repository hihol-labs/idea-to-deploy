# Nginx Insight Project Memory

## Product Context

Nginx Insight is a local Python 3.11 command-line tool for DevOps/SRE engineers. It streams conventional nginx combined access logs and reports:

1. Top 10 client IPs by valid-request count.
2. Top 10 request URLs by 4xx/5xx count.
3. All 24 hourly request counts and percentages, using `100 × hourly_request_count / total_valid_requests`.
4. Exact unique User-Agent count and share percentage.

Default output is colored Rich terminal text; `--json` and `--csv` are deterministic pipeline formats. The target is a representative 1 GB log in under 30 seconds on a documented laptop. Delivery budget is $0 and one weekend.

## Source of Truth

Read these before product work:

1. `PRD.md` — user-visible requirements and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — module, metric, CLI, format, and error contracts.
3. `IMPLEMENTATION_PLAN.md` — WIP=1 delivery order and verification commands.
4. `STRATEGIC_PLAN.md` — scope, priority, risk, KPI, and Definition of Done.
5. `CLAUDE_CODE_GUIDE.md` — bounded prompt for each implementation step.

When behavior changes, update the applicable specification first, then implementation and tests. Do not allow code to become the only specification.

## Non-Negotiable Architecture

Use the literal decision **no database — stateless streaming processing; no HTTP API — CLI-only tool**.

- One local process reads files/stdin sequentially, parses once, updates bounded exact state, and renders after EOF.
- Do not add authentication, database, cache, HTTP API, network listener, server, cloud, Docker, Kubernetes, telemetry, or background service.
- Do not retain raw lines or all parsed records.
- Exact IP/error-URL/User-Agent collections obey `--max-unique`; never silently approximate.
- Combined nginx format is the MVP grammar. Custom formats are deferred.

## Stack and Quality

- CPython 3.11.
- Click for CLI parsing/help.
- Rich for human terminal output only.
- Standard-library dataclasses for domain records.
- `pyproject.toml`/pip with a `src/` package layout.
- pytest, Ruff, and mypy for verification.

Expected implementation layout:

```text
src/nginx_insight/{cli,model,parser,aggregate}.py
src/nginx_insight/render/{terminal,json_output,csv_output}.py
tests/{fixtures,test_parser,test_aggregate,test_cli,test_outputs,test_performance}.py
benchmarks/generate_log.py
```

## Public Interface Rules

The exact interface is under `## CLI Interface` in `PROJECT_ARCHITECTURE.md`. Preserve these public exits everywhere:

| Code | Meaning |
|---:|---|
| `0` | Success |
| `1` | Processing/data error |
| `2` | CLI usage error |
| `3` | Input/output error |
| `4` | Unique-cardinality exhaustion |

Code 4 is part of the complete `0/1/2/3/4` contract and may not be omitted or remapped. Diagnostics belong on stderr. JSON/CSV stdout must contain one complete deterministic report or nothing and must never include ANSI/progress output.

## Engineering Rules

- Preserve WIP=1: execute only the active step from `IMPLEMENTATION_PLAN.md`.
- Inspect before editing; do not overwrite unrelated user work.
- Keep parsing, aggregation, rendering, and CLI exception mapping separate.
- Treat every log field as untrusted; escape Rich markup and neutralize CSV formula prefixes.
- Do not echo complete malformed lines because logs may contain sensitive data.
- Sort tied top results lexically for reproducibility.
- Render all 24 hourly buckets. Display percentages to two decimals without changing calculation semantics.
- Benchmark before optimizing and record the data generator, environment, wall time, and peak RSS. Never claim the 1 GB target without a real run.
- Add focused tests for every changed behavior and run prior regression tests.
- Do not publish packages, push, deploy, or create remote resources without separate authorization.
- The Devil's Advocate review is external to the blueprint session. Never fabricate its artifact or verdict.

## Verification Discipline

A step is complete only with current evidence from its commands in `IMPLEMENTATION_PLAN.md`. Expected results, narration, or a standalone “passed” statement are not evidence. If a required command cannot run, label the step unverified and state the blocker.

At minimum, implementation acceptance includes:

- Parser and aggregation boundary tests with core coverage at least 90%.
- Parameterized subprocess proof for `0/1/2/3/4`.
- Reviewed golden terminal, JSON, and CSV outputs.
- Ruff and mypy success.
- Clean wheel installation in a fresh Python 3.11 virtual environment.
- A recorded representative 1 GB benchmark with median under 30 seconds on the reference laptop.

## Session Continuity Rule

«В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

Record the active step, status, changed files, real verification evidence, blockers, and exactly one next action. Reconcile `.itd-memory/STATE.json` or `.itd-memory/GOAL.json` when present; never mark work verified from narration alone.

## Implementation Status

Blueprint completion does not mean product implementation has started.

| Step | Scope | Status | Required evidence before completion |
|---:|---|---|---|
| 1 | Package and public contracts | Not started | Install/help, CLI tests, Ruff, mypy |
| 2 | Combined-log parser/input | Not started | Parser fixtures, coverage, CLI I/O tests |
| 3 | Streaming metrics/cardinality | Not started | Metric oracle and exhaustion tests |
| 4 | CLI orchestration/exits | Not started | Subprocess `0/1/2/3/4` matrix |
| 5 | Rich renderer | Not started | Terminal goldens and ANSI checks |
| 6 | JSON/CSV renderers | Not started | Schema parse and machine-output goldens |
| 7 | Performance/robustness | Not started | Profile, hostile fixtures, 1 GB measurements |
| 8 | Packaging/release acceptance | Not started | Full suite, build checks, fresh-wheel install |

## Current Next Action

Start STEP 1 only when implementation is authorized. Until then, preserve this planning-only state and do not create product code.
