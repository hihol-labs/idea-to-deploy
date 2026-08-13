# nginx-top Project Memory

## Context

`nginx-top` is a local Python 3.11 CLI for DevOps/SRE engineers. It streams one standard nginx combined-format access log from a file or stdin and reports top-10 IPs, top-10 URLs by combined 4xx/5xx count, 24 hourly request buckets, and exact unique User-Agent share. Default output is Rich terminal text; `--json` and `--csv` are pipeline formats.

This file guides future implementation sessions. The durable product source of truth is `PRD.md`; architecture and interfaces are authoritative in `PROJECT_ARCHITECTURE.md`; work order and verification are authoritative in `IMPLEMENTATION_PLAN.md`.

## Non-Negotiable Rules

- Planning is complete; implement one numbered plan step at a time and keep WIP at one.
- Python 3.11, Click, Rich, and standard-library dataclasses are the approved stack.
- Keep one local process and streaming state; never add a database, HTTP API, server, authentication, cloud service, or Kubernetes.
- Do not retain raw input lines or silently approximate exact metrics.
- Calculate hourly percentage with `100 × hourly_request_count / total_valid_requests`.
- Keep top lists deterministic: count descending, then key ascending.
- Keep report data on stdout and diagnostics on stderr.
- Escape untrusted log-derived text before terminal rendering; use standard encoders for JSON/CSV.
- Change the PRD/architecture before changing documented behavior.
- Do not claim the 1 GB/30 second goal without measured evidence on a named reference laptop.
- At the end of every session or meaningful block of work, save context with `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Exit-Code Contract

Every implementation step, test, and guide must preserve all five codes:

| Code | Meaning |
|---:|---|
| `0` | Successful report, help, or version |
| `1` | Operational input/output failure |
| `2` | Usage or configuration error |
| `3` | Malformed-line threshold exceeded or no valid requests |
| `4` | Unique-cardinality exhaustion |

Code `4` cannot be omitted or remapped. Exits `1`, `2`, `3`, and `4` emit no partial report.

## Stack

| Area | Choice |
|---|---|
| Runtime | CPython 3.11 |
| CLI | Click |
| Terminal UI | Rich |
| Models | `dataclasses` |
| Serialization | standard-library `json` and `csv` |
| Tests | pytest, Click `CliRunner`, coverage |
| Packaging | `pyproject.toml`, wheel, pip |
| Runtime architecture | Single-process stateless streaming pipeline |

## Planned Structure

```text
src/nginx_top/
├── __init__.py
├── cli.py
├── models.py
├── parser.py
├── aggregate.py
├── errors.py
└── renderers/
    ├── __init__.py
    ├── terminal.py
    ├── json.py
    └── csv.py
tests/
├── fixtures/
├── test_parser.py
├── test_aggregate.py
├── test_cli.py
├── test_renderers.py
└── test_performance.py
benchmarks/generate_log.py
```

## Implementation Status

| Step | Deliverable | Status | Required evidence before marking done |
|---:|---|---|---|
| 1 | Package skeleton and CLI contract | Not started | Install, CLI unit tests, help smoke test |
| 2 | Models and parser | Not started | Parser tests and coverage |
| 3 | Streaming aggregation | Not started | Metric, formula, ordering, and code-4 boundary tests |
| 4 | Rich terminal renderer | Not started | Golden, TTY/color, and escaping tests |
| 5 | JSON/CSV renderers | Not started | Schema, quoting, and equivalence tests |
| 6 | End-to-end CLI | Not started | File/stdin tests and table-driven exits `0/1/2/3/4` |
| 7 | Correctness/package gate | Not started | Full tests, coverage, build, pip/security checks |
| 8 | Performance evidence | Not started | Recorded 1 GB wall time and peak RSS |
| 9 | Documentation/release handoff | Not started | Full rerun, distribution checks, reconciled docs |

Update a row only after running its verification in the current candidate. A prose claim is not evidence.

## Working Commands

Use these only after the corresponding files exist:

```bash
python3.11 -m pip install -e '.[test]'
python3.11 -m pytest --cov=nginx_top --cov-report=term-missing --cov-fail-under=90 -q
python3.11 -m build
python3.11 -m pip check
nginx-top --help
```

## Scope Boundaries

P0 is the weekend MVP. Gzip input and `NO_COLOR` are P1. Configurable top-N, multiple parser formats, and merged file inputs are P2. Persistent analytics, live tailing, dashboards, APIs, accounts, log shipping, and hosted infrastructure are out of scope.

## Handoff Protocol

At session start, read this file, the active plan step, its PRD stories, and referenced architecture sections. At session end, record commands and outcomes, reconcile the status row, note the next single action, and run `/session-save`. If requirements conflict, stop implementation and reconcile the specifications first.
