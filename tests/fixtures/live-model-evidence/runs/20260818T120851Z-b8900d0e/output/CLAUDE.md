# Nginx Insights CLI — Project Instructions

## Project Context

Build a local, open-source Python 3.11 CLI that streams finite nginx Combined
Log Format input and reports top 10 IPs, top 10 4xx/5xx URLs, hourly request
percentages, and exact unique User-Agent share. Default output is colored Rich
terminal text; JSON and CSV are pipeline formats. The performance acceptance is
1 GB in under 30 seconds on a documented reference laptop.

This file is the single project instruction entry point. Normative product
behavior lives in `PRD.md`, architecture in `PROJECT_ARCHITECTURE.md`, and
sequenced work/evidence in `IMPLEMENTATION_PLAN.md`.

## Binding Rules

- Preserve WIP=1: implement only the single active plan step.
- Change the spec before changing specified behavior.
- Use Python 3.11, Click, Rich, and dataclasses; add no other runtime dependency
  without an approved architecture change.
- Preserve a single-process, one-pass design. Never retain raw lines or parsed
  record collections.
- Add no authentication, database, HTTP API, server, telemetry, cloud,
  Kubernetes, or Docker runtime.
- Keep stdout data separate from stderr diagnostics; keep JSON/CSV free of ANSI.
- Use deterministic sorting: count descending, then key ascending.
- Use `100 × hourly_request_count / total_valid_requests` for hourly percentages.
- Do not disclose log lines or User-Agent values in exhaustion diagnostics.
- Run the current step's focused checks and cumulative tests before status changes.
- Never publish a package, push a branch, or create external resources without
  explicit authorization.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Stack and Intended Structure

| Area | Choice / path |
|---|---|
| Runtime | CPython 3.11 |
| CLI | Click in `src/nginx_insights/cli.py` |
| Terminal | Rich in `src/nginx_insights/render/terminal.py` |
| Models | dataclasses in `src/nginx_insights/models.py` |
| Core | `input.py`, `parser.py`, `aggregate.py`, `errors.py` |
| Structured output | `render/json_output.py`, `render/csv_output.py` |
| Tests | `tests/` with fixtures and golden outputs |
| Benchmark | `benchmarks/` with fixed-seed generator and runner |
| Packaging | pip-compatible `pyproject.toml` and console script |

## Complete CLI Exit Contract

| Code | Meaning |
|---:|---|
| `0` | Success/help/version/graceful downstream broken pipe |
| `1` | Runtime or I/O/output failure |
| `2` | CLI usage/configuration failure |
| `3` | Strict malformed input, empty input, or no valid requests |
| `4` | Unique-cardinality exhaustion |

The required contract is `0/1/2/3/4`; code 4 is reserved and must never be
omitted, remapped, or treated as a generic runtime failure.

## Implementation Status

Blueprint creation is complete when the six required planning files exist, but
product implementation has not started. Status must advance from verification
evidence rather than narration.

| Step | Deliverable | Status | Evidence |
|---:|---|---|---|
| 1 | Package, contracts, fixtures | Not started | None; blueprint only |
| 2 | Parser and input adapter | Not started | None; blueprint only |
| 3 | Ranked aggregation | Not started | None; blueprint only |
| 4 | Distribution and cardinality | Not started | None; blueprint only |
| 5 | Terminal renderer | Not started | None; blueprint only |
| 6 | JSON/CSV and exit behavior | Not started | None; blueprint only |
| 7 | Integration and packaging | Not started | None; blueprint only |
| 8 | Performance acceptance | Not started | None; blueprint only |

## Working Protocol

1. Read the active step and its referenced PRD/architecture sections.
2. Freeze its scope and expected evidence before editing.
3. Implement the smallest coherent change and tests.
4. Run the exact focused checks, then the cumulative suite.
5. Update this status table only with observed evidence.
6. Save session context and leave one explicit next action.

Do not create `DEVILS_ADVOCATE_REVIEW.md` from these instructions. Any future
adversarial review must run as its own explicitly authorized workflow and must
identify its real provenance.

