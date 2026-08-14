# Project Memory: Nginx Stream Analytics CLI

## Context

This repository is planned as a local, open-source Python 3.11 CLI for DevOps and SRE engineers. It streams nginx combined access logs and reports top client IPs, top URLs by 4xx/5xx count, hourly request distribution, and unique User-Agent share. Default output is colored terminal text, with JSON and CSV for pipelines.

Specifications are the durable source of truth. Change `PRD.md` and related architecture/plan documents before changing behavior.

## Non-Negotiable Decisions

- Single local process and stateless, one-pass processing.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Python 3.11, Click, Rich, dataclasses, and pip installation.
- $0 budget and one-weekend MVP.
- Representative 1 GB log must complete in under 30 seconds on a documented laptop.
- Hourly request distribution is the percentage `100 × hourly_request_count / total_valid_requests`.
- Exit contract: `0` success; `1` input/runtime I/O, encoding, or unexpected failure; `2` usage error; `3` strict parse failure or non-empty all-malformed input; `4` unique-cardinality exhaustion.
- Code `4` always means unique-cardinality exhaustion and must never be omitted or remapped.

## Documentation Map

| File | Authority |
|---|---|
| `STRATEGIC_PLAN.md` | Users, alternatives, MoSCoW/RICE, budget, KPIs, risks, Definition of Done |
| `PROJECT_ARCHITECTURE.md` | Modules, data flow, CLI/options/input/output/exit contracts |
| `PRD.md` | User stories, P0/P1/P2 behavior, acceptance and release criteria |
| `IMPLEMENTATION_PLAN.md` | Eight ordered implementation units and verification commands |
| `CLAUDE_CODE_GUIDE.md` | Session prompts and evidence expectations |
| `README.md` | User-facing quick start and contract summary |

## Intended Source Structure

```text
src/nginx_stream_analytics/
  cli.py
  models.py
  parser.py
  aggregate.py
  errors.py
  renderers/{terminal,json,csv}.py
tests/
  fixtures/
  test_cli.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_performance.py
```

## Engineering Rules

1. Keep WIP at one implementation-plan step.
2. Read the relevant PRD acceptance criteria and architecture section before editing.
3. Parse each input line once; never retain all records or silently approximate required metrics.
4. Keep CLI orchestration, parsing, aggregation, and rendering separately testable.
5. Keep stdout machine-clean and send diagnostics to stderr.
6. Use deterministic ordering: count descending, then key ascending.
7. Treat log content as untrusted data and do not echo full sensitive lines in errors.
8. Run the focused step checks plus the accumulated suite before advancing.
9. Do not claim the performance target without measured evidence on the exact candidate.
10. At the end of every session or significant block of work, save context through `/session-save`.

## Implementation Status

| Step | Unit | Status | Required evidence before Done |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Not started | Clean editable install, help, focused CLI tests |
| 2 | Models, errors, fixtures | Not started | Compile check and complete `0/1/2/3/4` tests |
| 3 | Combined-log parser | Not started | Parser tests and >=90% focused coverage |
| 4 | Metrics and cardinality guard | Not started | Aggregate tests, formula checks, exit 4 exhaustion test |
| 5 | Terminal renderer | Not started | TTY/non-TTY/no-color tests |
| 6 | JSON and CSV renderers | Not started | Schema, escaping, ordering, no-ANSI tests |
| 7 | End-to-end CLI | Not started | File/stdin and all failure-path tests |
| 8 | Release and performance | Not started | Full suite, build, clean install, measured 1 GB benchmark |

## Current State and Next Action

Blueprint documentation is complete; product code has not been implemented. The next authorized implementation action is Step 1 from `IMPLEMENTATION_PLAN.md`, using Session 1 in `CLAUDE_CODE_GUIDE.md`.
