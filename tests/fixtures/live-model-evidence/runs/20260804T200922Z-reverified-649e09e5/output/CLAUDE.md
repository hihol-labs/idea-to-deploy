# Project Memory: Nginx Stream Analytics CLI

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports top client IPs, top error URLs, hourly request percentages, and unique User-Agent share. Default output is colored Rich terminal text; JSON and CSV serve pipelines. The cash budget is $0 and MVP delivery is one weekend.

This file guides implementation sessions. Product truth lives in `PRD.md`; public interfaces and algorithms live in `PROJECT_ARCHITECTURE.md`; sequencing and checks live in `IMPLEMENTATION_PLAN.md`; ready-to-run prompts live in `CLAUDE_CODE_GUIDE.md`.

## Hard Scope

- Use Python 3.11, Click, Rich, and dataclasses; package with pip.
- Use one local process and one-pass, invocation-scoped aggregation.
- Do not add authentication, a database, an HTTP API, a server, cloud resources, Docker, or Kubernetes.
- Do not retain or upload input data, open network connections, or add telemetry.
- Do not implement P1/P2 features during a P0 step without changing the specifications and scope first.
- Preserve WIP=1: one implementation-plan step active at a time.
- Do not claim a step complete without its named verification evidence.

## Public Semantics

- Default ranking size is 10; counts descend and string keys break ties ascending.
- Error URLs include statuses 400–599 and preserve the logged request target.
- Emit all 24 recorded-log-time hour buckets. The required percentage formula is `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`; `"-"` is empty.
- Malformed lines are excluded from every metric but counted in summary metadata. Zero valid requests is a data failure.
- stdout contains report data only; stderr contains diagnostics only. JSON/CSV are stable and never colored.

## Complete Exit-Code Contract

| Code | Meaning |
|---:|---|
| `0` | Success, help, or version |
| `1` | Unexpected internal processing/rendering failure |
| `2` | Invalid command usage/options |
| `3` | Input/data failure, including unreadable input or zero valid requests |
| `4` | Unique-cardinality exhaustion; no partial report |

Never omit, remap, or turn exit 4 into a successful approximate report.

## Intended Repository Structure

```text
src/nginx_stream_report/  # package, domain, CLI, renderers
tests/                    # unit/integration fixtures and tests
scripts/                  # deterministic benchmark fixture generator
pyproject.toml            # build, dependencies, tools, console entry point
```

Keep Click and Rich at the boundary. Parser and aggregator use standard-library types and domain dataclasses. Renderers consume the same immutable `Report` so text, JSON, and CSV cannot disagree.

## Working Rules

1. Read the relevant PRD stories and architecture section before editing.
2. Work only on the active row below; update its evidence before advancing.
3. Update specifications before changing externally observable behavior.
4. Treat log fields as untrusted: never evaluate them, invoke a shell, or render them as markup.
5. Run the exact per-step commands plus proportionate regression checks.
6. Record benchmark machine, input recipe, command, cache condition, wall time, and peak RSS.
7. Preserve unrelated workspace changes.
8. At the end of every session or significant block of work, save context through `/session-save`.

## Implementation Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Not started | Install, CLI unit tests, help/version smoke |
| 2 | Domain models and failure taxonomy | Not started | Model tests and mypy |
| 3 | Input stream and combined parser | Not started | Parser/input tests and Ruff |
| 4 | Aggregation and cardinality guard | Not started | Branch-covered aggregation tests and mypy |
| 5 | Rich terminal renderer | Not started | Text renderer tests and no-color smoke |
| 6 | JSON and CSV renderers | Not started | Renderer tests and JSON parse smoke |
| 7 | End-to-end CLI composition | Not started | CLI/full tests proving exits `0/1/2/3/4` |
| 8 | Performance and robustness | Not started | Documented 1 GB time/RSS run |
| 9 | Packaging and release acceptance | Not started | Static checks, suite, build, clean install |

## Current State and Next Action

Blueprint documentation is complete; product code has not been implemented. The next authorized implementation action is Step 1 only, using Prompt 1 in `CLAUDE_CODE_GUIDE.md`. Before implementation, reconcile the active Idea to Deploy unit and its verification contract with the repository methodology.

## Definition of Done

A release is complete only when all P0 acceptance criteria, static checks, tests, clean-install checks, and the measured 1 GB/30-second gate pass on the exact candidate; documentation agrees with observed behavior; no Critical/High issue remains; and project execution state is reconciled.
