# Project Memory: nginx-log-report

## Context

This repository will contain a local Python 3.11 CLI for DevOps/SRE engineers. It streams nginx combined access logs and reports top-10 IPs, top-10 URLs with 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. Default output is colored terminal text; JSON and CSV are supported for pipelines.

The blueprint documents are the current source of truth. Product implementation has not started.

## Required Reading Order

1. `PRD.md` for behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` for module, CLI, schema, and failure contracts.
3. `IMPLEMENTATION_PLAN.md` for ordered steps and verification commands.
4. `CLAUDE_CODE_GUIDE.md` for bounded implementation prompts.
5. `STRATEGIC_PLAN.md` for priorities, constraints, risks, and release criteria.

## Non-Negotiable Rules

- Python 3.11, Click, Rich, dataclasses, src-layout package, and pip installation.
- One local process, streaming input, no retained raw lines, and no persistent state.
- No authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.
- The hour calculation is `100 × hourly_request_count / total_valid_requests`.
- The full exit contract is `0` success, `1` internal/runtime failure, `2` usage/configuration error, `3` input/read/decode/parse failure or no valid requests, `4` unique-cardinality exhaustion.
- Exact results within the configured limit; never silently approximate. Code 4 emits no partial report.
- Machine formats stay deterministic and ANSI-free; diagnostics use stderr.
- New code requires tests and the relevant suite must run before commit.
- Do not publish, deploy, push/open a PR, delete, or perform another external/irreversible action without human confirmation.
- In the event of a conflict, `PROJECT_ARCHITECTURE.md` controls technical design and `PRD.md` controls public acceptance behavior; reconcile the documents before code changes.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Planned Structure

```text
src/nginx_log_report/
  __init__.py
  __main__.py
  cli.py
  model.py
  errors.py
  stream.py
  parser.py
  aggregate.py
  render/
tests/
  fixtures/
  golden/
bench/
pyproject.toml
```

## Implementation Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package skeleton and CLI | Not started | CLI contract tests |
| 2 | Models and exit semantics | Not started | `0/1/2/3/4` tests |
| 3 | Streaming parser | Not started | Parser/stream tests and branch coverage |
| 4 | Exact aggregations | Not started | Aggregation tests |
| 5 | Cardinality and strict mode | Not started | Boundary and failure tests |
| 6 | Terminal/JSON/CSV renderers | Not started | Golden and ANSI-safety tests |
| 7 | Integration and package quality | Not started | Full suite, lint, typing, build/install |
| 8 | Performance and handoff | Not started | Recorded 1 GB timing and peak RSS |

## Current Decision Log

- Architecture Variant A, a single-process streaming CLI, is selected and pre-approved.
- Combined nginx log format is the only P0 input grammar.
- Percentages round to two decimal places only during serialization.
- `--max-unique` defaults to 1,000,000 per tracked dimension.
- Gzip is P1 and configurable top-N is P2.
- No adversarial review was performed in the blueprint session; review is handled separately.

## Session Handoff Template

At the end of each implementation block, record:

- current step and status;
- files changed;
- exact verification commands and outcomes;
- unresolved failures/risks;
- next single action.
