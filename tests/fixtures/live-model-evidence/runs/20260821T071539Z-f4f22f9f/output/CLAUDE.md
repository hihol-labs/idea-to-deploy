# Nginx Stream Analyzer Project Memory

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx access logs and reports top 10 IPs, top 10 URLs by 4xx/5xx errors, 24-hour request distribution, and unique User-Agent share. Default output is colored terminal text; `--json` and `--csv` serve pipelines. Cash budget is $0 and MVP delivery is one weekend.

The durable product truth is `PRD.md`; architecture and interfaces are owned by `PROJECT_ARCHITECTURE.md`; execution order and checks are owned by `IMPLEMENTATION_PLAN.md`. Update specifications before changing behavior.

## Non-Negotiable Decisions

- Single local process with stateless streaming aggregation.
- No database, HTTP API, authentication, server, network calls, cloud, Docker, or Kubernetes.
- Python 3.11, Click, Rich, dataclasses, pip installation.
- Representative 1 GB input must complete under 30 seconds on a documented laptop.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`.
- Exit codes are 0 success, 1 I/O/decoding error, 2 usage error, 3 no valid records, and 4 unique-cardinality exhaustion.
- Do not silently approximate exact metrics or emit partial stdout on failure.

## Planned Repository Structure

```text
src/nginx_stream_analyzer/
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
    json_output.py
    csv_output.py
tests/
  fixtures/
  test_*.py
benchmarks/
  generate_log.py
  run.sh
pyproject.toml
```

This tree is planned, not implemented by the blueprint.

## Engineering Rules

1. Keep WIP=1 and follow `IMPLEMENTATION_PLAN.md` in order.
2. Read and discard one record at a time; retaining counters/sets is allowed, retaining records is not.
3. Keep parsing, aggregation, and presentation isolated and testable.
4. Escape untrusted log fields in terminal output and never echo complete malformed records.
5. Keep JSON/CSV deterministic, schema-stable, undecorated, and stdout-only on success.
6. Write or update acceptance tests with each behavior change.
7. Record benchmark environment with every performance claim.
8. Do not mark work complete from narration; run the relevant verification commands and retain evidence required by `.itd/VERIFICATION_CONTRACT.json` when implementation begins.
9. At the end of every session or meaningful block of work, save context via `/session-save`. Required workflow wording: «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Status

| Step | Scope | Status | Evidence |
|---:|---|---|---|
| Blueprint | Six required planning documents | Complete | Document presence/structure checks only |
| 1 | Package skeleton and CLI | Not started | — |
| 2 | Parser and models | Not started | — |
| 3 | Streaming input and aggregation | Not started | — |
| 4 | Terminal renderer | Not started | — |
| 5 | JSON and CSV renderers | Not started | — |
| 6 | Failure semantics | Not started | — |
| 7 | Performance and robustness | Not started | — |
| 8 | Packaging and release | Not started | — |

## Session Handoff Template

- Active step:
- Files changed:
- Commands run and outcomes:
- Contract changes:
- Risks/blockers:
- Next exact action:

Do not change a Not started status until the corresponding implementation and verification actually exist.
