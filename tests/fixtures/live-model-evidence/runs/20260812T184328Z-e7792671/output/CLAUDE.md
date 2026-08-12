# Project Memory: nginx-insights

## Product Context

`nginx-insights` is a local Python 3.11 CLI for DevOps/SRE engineers. It streams a finite nginx combined access log from one file or stdin in a single pass and reports top-10 IPs, top-10 4xx/5xx URLs, hourly request distribution, and unique User-Agent share. Default output is Rich terminal text; `--json` and `--csv` are stable pipeline formats. The performance target is a representative 1 GB input in under 30 seconds on a documented laptop.

This repository is currently in blueprint state. No product code has been implemented.

## Durable Sources of Truth

Read in this order before implementation:

1. [PRD.md](PRD.md) — user-visible behavior, priorities, acceptance, and kill criteria.
2. [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) — structure, data semantics, CLI schemas, and ADRs.
3. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — dependency-ordered WIP=1 steps and verification.
4. [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) — bounded prompt and evidence contract for each step.
5. [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) — audience, alternatives, roadmap, KPIs, budget, risks, and Definition of Done.

Specifications are the durable asset. Change behavior in PRD first, reconcile architecture and plans, then modify code.

## Fixed Product Decisions

- Architecture: one local process with stateless streaming aggregation.
- **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- No authentication, server, daemon, cloud, Docker requirement, or Kubernetes.
- Stack: Python 3.11, Click, Rich, dataclasses, standard library, pip packaging.
- Budget: $0; delivery: one weekend; license/distribution intent: open source.
- Combined nginx format only for MVP; arbitrary `log_format` and indefinite follow mode are out of scope.
- Exact aggregation only. If a distinct tracker exceeds `--max-unique`, stop with code 4; never approximate silently.

## Metric Definitions

- Top IPs count all valid records and return at most 10.
- Top error URLs count request targets only for status 400–599 and return at most 10.
- Ranking order is count descending, then raw value ascending.
- Each hourly percentage is `100 × hourly_request_count / total_valid_requests`, or `0.0` when there are no valid requests. Use the timestamp's written local hour; do not convert through host timezone.
- Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`, or `0.0` when there are no valid requests.
- Default malformed-line behavior counts and skips; `--fail-on-invalid` stops at the first malformed line.

## CLI and Exit Rules

Command: `nginx-insights [OPTIONS] [PATH]`. Missing `PATH` or `-` reads stdin. `--json` and `--csv` are mutually exclusive. JSON/CSV stdout contains data only, diagnostics use stderr, and ANSI is forbidden in structured output.

The complete exit contract is mandatory in every implementation:

| Code | Meaning |
|---:|---|
| `0` | Success |
| `1` | Operational/internal or stdout-write failure |
| `2` | Usage/options failure |
| `3` | Input/read/decode/strict-parse failure |
| `4` | Unique-cardinality exhaustion |

Never omit or remap code 4. Do not emit a normal report on exits 1, 3, or 4.

## Planned Repository Structure

```text
pyproject.toml
src/nginx_insights/
  __init__.py
  cli.py
  errors.py
  models.py
  parser.py
  aggregate.py
  pipeline.py
  renderers/
    __init__.py
    rich_text.py
    json_output.py
    csv_output.py
tests/
  fixtures/
  unit/
  integration/
  performance/
```

Keep Click and Rich at the adapters. Parser, aggregation, and domain models must not depend on either. Every renderer consumes the same immutable report.

## Engineering Rules

- Preserve WIP=1: only one implementation-plan step may be active.
- Do not read the full file or retain raw lines/records; use buffered iteration.
- Add tests with behavior and run the current step's actual verification commands.
- Maintain at least 90% coverage, plus Ruff and mypy gates.
- Freeze and benchmark the exact candidate before accepting the 1 GB / 30 s target.
- Generated benchmark fixtures must be labeled test data, never real production evidence.
- Treat log content as untrusted data: no Rich markup interpretation, raw-line diagnostics, telemetry, or network transmission.
- Do not weaken tests, input size, exactness, or the cardinality guard to pass a gate.
- Do not create Docker, database, API, auth, cloud, or Kubernetes assets without a PRD/scope revision.
- At the end of every session or meaningful work block, save context with `/session-save`.
- Required continuity rule: «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Implementation Status

| Step | Scope | Status | Evidence / next action |
|---:|---|---|---|
| 1 | Package, CLI, and test contracts | Not started | Begin with Prompt 1 in CLAUDE_CODE_GUIDE.md |
| 2 | Models and failure taxonomy | Blocked by Step 1 | — |
| 3 | Combined-log parser | Blocked by Step 2 | — |
| 4 | Streaming aggregation | Blocked by Step 3 | — |
| 5 | Rich renderer | Blocked by Step 4 | — |
| 6 | JSON and CSV renderers | Blocked by Step 5 | — |
| 7 | I/O and exit integration | Blocked by Step 6 | — |
| 8 | Benchmark, packaging, release check | Blocked by Step 7 | — |

Do not change a status to Done from narration. Record the relevant commands and evidence for the exact candidate.

## Session Handoff Template

At a meaningful boundary, record:

- Active implementation step and its allowed files.
- Behavior completed and acceptance criteria affected.
- Commands actually run and their outcomes.
- Known failures, risks, or deviations.
- Exact next action.
- Any specification decision requiring reconciliation.

Current next action: implement only Step 1 using [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) when product-code work is explicitly authorized.
