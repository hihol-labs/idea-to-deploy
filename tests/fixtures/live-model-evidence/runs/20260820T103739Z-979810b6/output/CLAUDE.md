# nginx-report Project Memory

## Context

This repository is planned as `nginx-report`, a local, open-source Python 3.11
CLI for DevOps/SRE engineers. It streams finite standard nginx combined access
logs from files or stdin and reports top-ten IPs, top-ten 4xx/5xx URLs, hourly
request percentages, and exact unique User-Agent share. It is installable with
pip and must process a representative 1 GB log in under 30 seconds on a
documented laptop.

The blueprint is the current state. Product code has not yet been implemented.

## Product Boundaries

- Single local process; streaming aggregation; no whole-file buffering.
- No authentication, database, HTTP API, server, cloud, Kubernetes, or telemetry.
- No live tail/follow mode and no arbitrary log-format support in the MVP.
- Default Rich terminal report; stable `--json` and `--csv` pipeline formats.
- $0 cash budget, open source, one-weekend delivery target.

## Source of Truth

Read in this order before implementation:

1. `PRD.md` — behavior, priorities, acceptance and kill criteria.
2. `PROJECT_ARCHITECTURE.md` — parsing, metrics, schemas, CLI, errors.
3. `IMPLEMENTATION_PLAN.md` — eight WIP=1 steps and verification commands.
4. `CLAUDE_CODE_GUIDE.md` — bounded prompts for executing each step.
5. `STRATEGIC_PLAN.md` — audience, competitors, roadmap, risks and Definition of Done.

Change the specification before changing public behavior. Never infer a
database or API from generic framework conventions.

## Stack and Planned Structure

- CPython 3.11, Click, Rich, standard library, frozen dataclasses.
- `src/nginx_report/`: CLI, sources, parser, aggregation, errors, presenters.
- `tests/`: parser, aggregate, presenter, CLI, end-to-end and performance evidence.
- `benchmarks/`: deterministic 1 GB fixture generator and measured runner.
- pip packaging through `pyproject.toml` and `nginx-report` console entry point.

## Public Contract

- Top IPs: valid-request count descending, IP ascending, at most ten.
- Error URLs: combined 4xx/5xx descending, URL ascending, at most ten, with
  separate client/server counts.
- Hourly distribution contains all 24 hours and uses
  `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share is exact and uses total valid requests as denominator.
- User-Agent cap defaults to 1,000,000; exceeding it emits no report and exits 4.
- stdout is report-only; stderr is diagnostic-only; failures emit no partial report.

Complete exit codes, never omit or remap:

| Code | Meaning |
|---:|---|
| `0` | Successful report, help, or version |
| `1` | Operational input/output/decode/gzip/unexpected failure |
| `2` | Click usage error |
| `3` | No valid records after finite input |
| `4` | Unique-cardinality exhaustion |

## Engineering Rules

- Preserve WIP=1: implement and verify one `IMPLEMENTATION_PLAN.md` step at a time.
- Inspect existing files and user changes before editing; do not overwrite unrelated work.
- Keep parsing/aggregation independent of Click and Rich.
- Treat every log field as untrusted data; never evaluate it, shell-expand it,
  or pass it as Rich markup.
- Add direct tests for every P0 acceptance criterion and every failure code.
- Do not claim the 1 GB target without recorded hardware, fixture, time, and RSS evidence.
- Do not publish a package or mutate external systems without explicit authorization.
- Do not write `DEVILS_ADVOCATE_REVIEW.md`; external harness work is separate.
- At the end of every session or meaningful work block, save context with `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Verification Commands

After implementation, the complete local gate is planned as:

```bash
python3.11 -m pytest --cov=nginx_report --cov-report=term-missing --cov-fail-under=90
python3.11 -m ruff check src tests benchmarks
python3.11 -m mypy src
python3.11 -m build
python3.11 -m twine check dist/*
```

The performance command and clean-wheel smoke test are specified in Steps 7
and 8 of `IMPLEMENTATION_PLAN.md`. Record actual evidence; never describe
planned commands as passing.

## Status

| Step | Scope | Status | Required evidence before completion |
|---:|---|---|---|
| Blueprint | Six required project documents plus workflow README | Complete | Root-file and content checks |
| 1 | Package skeleton/contracts | Not started | Step 1 commands |
| 2 | Sources/parser | Not started | Step 2 commands |
| 3 | Streaming aggregation | Not started | Step 3 commands |
| 4 | Presenters | Not started | Step 4 commands |
| 5 | CLI/error mapping | Not started | Step 5 commands |
| 6 | End-to-end matrix | Not started | Step 6 commands |
| 7 | Gzip/performance | Not started | Step 7 commands and benchmark record |
| 8 | Packaging/release readiness | Not started | Step 8 commands and Definition of Done |

## Next Action

Begin only Step 1 using Prompt 1 from `CLAUDE_CODE_GUIDE.md`. Do not begin
implementation during the blueprint workflow itself.
