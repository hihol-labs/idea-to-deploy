# Project Memory: Nginx Stream Analytics CLI

## Context

This project is a local Python 3.11 CLI for DevOps/SRE engineers. It streams one nginx access-log source and reports top-10 IPs, top-10 request targets with 4xx/5xx responses, hourly request percentages, and unique User-Agent share. Default output is colored terminal text; JSON and CSV serve pipelines. Budget is $0 and delivery is one weekend.

The approved architecture is one stateless process. Never add authentication, a database, HTTP API, server, cloud, Kubernetes, telemetry, or persistent product state.

## Sources of Truth

Read in this order before implementation:

1. `AGENTS.md` and `.itd/` contracts.
2. `.itd-memory/STATE.json` for the one active unit.
3. `PRD.md` for behavior and acceptance criteria.
4. `PROJECT_ARCHITECTURE.md` for schemas and boundaries.
5. `IMPLEMENTATION_PLAN.md` and `CLAUDE_CODE_GUIDE.md` for the current step.
6. `STRATEGIC_PLAN.md` for priorities and kill criteria.

When behavior changes, update the specification first, then implementation and tests. Preserve WIP=1.

## Stack and Structure

- Python 3.11, Click, Rich, standard-library dataclasses/JSON/CSV, pytest, Ruff, and mypy.
- `src/nginx_stream_analytics/`: CLI, input, parser, models, aggregation, renderers.
- `tests/`: unit, CLI, golden, end-to-end, and install tests.
- `benchmarks/`: generated-fixture performance tooling; never commit the 1 GB fixture.

## Product Invariants

- Stream once and retain no raw log records.
- Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share uses distinct non-empty strings over total valid requests.
- Rankings break equal counts by key ascending.
- JSON/CSV are deterministic, ANSI-free, stdout-only; diagnostics use stderr.
- Full exit contract: `0` success, `1` input/I/O or unexpected runtime failure, `2` usage error, `3` no valid records, `4` unique-cardinality exhaustion.
- Code 4 is mandatory; never omit/remap it or silently approximate after exhaustion.
- No partial report on nonzero exit.
- Escape/disable interpretation of untrusted log text in terminal output.

## Engineering Rules

- Use the smallest applicable repository-local Idea to Deploy skill.
- Implement exactly one numbered step at a time and touch only its declared files unless scope is reconciled first.
- Add or update tests with behavior; run actual commands and retain evidence.
- Freeze the exact staged candidate, run its machine oracle, and apply the risk-tier checker before acceptance.
- Exclude undeclared ignored/untracked overlays; bind the content hash of any declared non-Git input.
- Accept completion only from a current revalidated adjudication receipt.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package baseline | Not started | install/help tests |
| 2 | Domain contracts | Not started | model tests + mypy |
| 3 | Input/parser | Not started | parser/input tests + lint |
| 4 | Aggregations | Not started | metric tests + coverage |
| 5 | JSON/CSV | Not started | machine golden tests |
| 6 | Terminal | Not started | terminal golden/security tests |
| 7 | CLI integration | Not started | CLI tests for 0/1/2/3/4 |
| 8 | Release evidence | Not started | full suite, build, 1 GB benchmark, current receipt |

## Next Action

Begin only Step 1 through the applicable Idea to Deploy implementation workflow. The external benchmark, not this blueprint session, performs Devil's Advocate review.
