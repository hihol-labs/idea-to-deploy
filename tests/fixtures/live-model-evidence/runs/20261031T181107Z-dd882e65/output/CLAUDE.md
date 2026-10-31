# nginx-log-report Project Memory

## Context

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports top-10 client IPs, top-10 URLs with 4xx/5xx errors, hourly request distribution, and the share of unique User-Agents. Default output is colored Rich terminal text, with JSON and CSV modes for pipelines. Delivery budget is $0 and one weekend.

The durable product contract is `PRD.md`; architecture and interfaces are authoritative in `PROJECT_ARCHITECTURE.md`; delivery order and checks are in `IMPLEMENTATION_PLAN.md`; executable prompts are in `CLAUDE_CODE_GUIDE.md`.

## Non-Negotiable Decisions

- Python 3.11, Click, Rich, dataclasses, pytest, `src` package layout, pip install.
- One local process and one-pass stateless streaming.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.
- No silent approximate cardinality in MVP.
- 1 GB must process in under 30 seconds on the documented reference laptop.
- Exit codes are exactly: `0` success, `1` I/O, `2` usage, `3` no valid records, `4` unique-cardinality exhaustion.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`.
- Product code is not yet implemented; blueprint files are planning artifacts only.

## Working Rules

1. Preserve WIP=1: implement one numbered step at a time.
2. Read the relevant specification before editing; change the specification first when behavior changes.
3. Add tests with new code and run the stated step checks plus the affected suite.
4. Never claim a check passed unless its command ran successfully in the current work session.
5. Keep diagnostics on stderr and selected report output on stdout.
6. Treat log content as untrusted text and never print full malformed records in errors.
7. Do not commit generated 1 GB fixtures, build output, virtual environments, caches, or coverage data.
8. At the end of every session or meaningful block of work, save context through `/session-save`.

## Planned Structure

```text
pyproject.toml
src/nginx_log_report/
  __init__.py
  __main__.py
  cli.py
  model.py
  parser.py
  aggregate.py
  render/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  performance/
docs/PERFORMANCE.md
```

## Status

| Step | Scope | Status | Evidence required |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Not started | Install, basic pytest, help output |
| 2 | Models and parser | Not started | Parser tests and coverage |
| 3 | Aggregation and guard | Not started | Aggregation tests and coverage |
| 4 | Terminal renderer | Not started | Renderer tests and manual fixture output |
| 5 | JSON and CSV | Not started | Schema/parity tests and JSON parse check |
| 6 | End-to-end CLI | Not started | Integration and all exit-code tests |
| 7 | Performance | Not started | CI-sized test and recorded 1 GB timing/RSS |
| 8 | Release readiness | Not started | Full suite, build, clean-wheel smoke test |

## Current Next Action

Begin Step 1 only when implementation is requested. This blueprint task intentionally contains no product code.
