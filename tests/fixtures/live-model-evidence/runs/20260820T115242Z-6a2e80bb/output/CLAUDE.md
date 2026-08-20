# Project Memory: nginx-insight

## Context

This repository is planned as a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams supported nginx combined access logs and reports top 10 IPs, top 10 4xx/5xx URLs, hourly request percentages, and exact unique User-Agent share. Default output is Rich terminal text; JSON and CSV serve pipelines. Budget is $0 and MVP delivery is one weekend.

## Durable Rules

- Specifications are source: observable changes begin in `PRD.md`; technical changes begin in `PROJECT_ARCHITECTURE.md`.
- Keep WIP=1 and implement `IMPLEMENTATION_PLAN.md` one verified step at a time.
- Use Python 3.11, Click, Rich, dataclasses, pip packaging, and a `src/` layout.
- Keep one local process and stream raw lines. Do not add authentication, a database, an HTTP API, a server, cloud infrastructure, Docker requirements, or Kubernetes.
- Hourly distribution always means percentage via `100 × hourly_request_count / total_valid_requests`, never an unscaled fraction.
- User-Agent share is `100 × unique_user_agent_count / total_valid_requests` and remains exact up to the configured limit.
- Exit contract: `0` success; `1` processing/data failure; `2` CLI usage failure; `3` input I/O or UTF-8 decoding failure; `4` unique-cardinality exhaustion. Never omit or remap code 4.
- stdout contains the report; stderr contains diagnostics. Never contaminate JSON/CSV stdout or emit a partial structured document on failure.
- Do not claim the performance target without a current reproducible benchmark on documented hardware.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure

```text
src/nginx_insight/
  __init__.py
  __main__.py
  cli.py
  input.py
  parser.py
  models.py
  aggregate.py
  errors.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  test_cli.py
  test_input.py
  test_parser.py
  test_models.py
  test_aggregate.py
  test_renderers.py
  test_exit_codes.py
  test_security.py
benchmarks/
  generate_log.py
  run.sh
  RESULTS.md
```

This structure is planned, not currently implemented by the blueprint.

## Document Map

| File | Purpose |
|---|---|
| `STRATEGIC_PLAN.md` | Audience, alternatives, priorities, budget, risks, and Definition of Done |
| `PROJECT_ARCHITECTURE.md` | Components, models, streaming rules, CLI, formats, status codes, and capacity |
| `PRD.md` | User stories and testable P0/P1/P2 requirements |
| `IMPLEMENTATION_PLAN.md` | Eight dependency-ordered steps with commands |
| `CLAUDE_CODE_GUIDE.md` | Replayable prompts for future implementation sessions |
| `README.md` | User-facing overview and intended quick start |

## Implementation Status

| Step | Status | Required evidence before completion |
|---:|---|---|
| 1. Package and CLI skeleton | Not started | Editable install, help/version, usage tests |
| 2. Models and exits | Not started | Invariant tests and `0/1/2/3/4` mapping tests |
| 3. Input and parser | Not started | File/stdin/parser/decode test results |
| 4. Aggregation | Not started | Metric, tie, formula, empty, and cardinality tests |
| 5. Renderers | Not started | Terminal safety and JSON/CSV reconciliation |
| 6. CLI integration | Not started | End-to-end CLI and all exit statuses |
| 7. Quality/performance | Not started | Static checks, ≥90% core coverage, benchmark record |
| 8. Release readiness | Not started | Build, metadata, clean install, full suite |

## Current State and Next Action

Blueprint documentation is the only completed work. No product code exists. The next authorized implementation action, when requested, is STEP 1 from `IMPLEMENTATION_PLAN.md`; do not start later steps or publish anything first.

