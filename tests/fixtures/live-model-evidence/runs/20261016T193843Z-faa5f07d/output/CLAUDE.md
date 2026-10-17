# CLAUDE.md — nginx-log-top

## Project Context

Build a local Python 3.11 CLI for DevOps/SRE users that streams nginx access logs and reports top-10 IPs, top-10 4xx/5xx URLs, 24-hour request percentages, and the share of unique User-Agents. Default output is colored terminal text; JSON and CSV are stable pipeline formats. Delivery is time-boxed to one weekend with a `$0` budget.

The specifications are the source of truth:

1. `PRD.md` defines behavior and acceptance.
2. `PROJECT_ARCHITECTURE.md` defines structure and CLI contracts.
3. `IMPLEMENTATION_PLAN.md` defines delivery order and verification.
4. `CLAUDE_CODE_GUIDE.md` provides bounded prompts.

## Non-Negotiable Rules

- Do not add authentication, a database, HTTP API, server, cloud resources, or Kubernetes.
- Process incrementally; never load the whole input or retain raw records.
- Use Python 3.11, Click, Rich, dataclasses, and standard pip packaging.
- Keep JSON/CSV free of ANSI styling and diagnostics; stderr is for diagnostics.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`.
- Preserve `0/1/2/3/4`: success, internal error, usage/I/O, no valid records, unique-cardinality exhaustion.
- Code 4 always means unique-cardinality exhaustion; do not remap it or silently approximate.
- Add tests with new code and run the targeted set before committing.
- Do not publish, push, deploy, delete data, or make external changes without human approval.
- At the end of every session or meaningful block of work, save context through `/session-save`.

## Stack

| Area | Choice |
|---|---|
| Runtime | Python 3.11 |
| CLI | Click |
| Terminal output | Rich |
| Models | dataclasses |
| Machine serialization | standard `json` and `csv` |
| Tests | pytest and pytest-cov |
| Packaging | `pyproject.toml`, PEP 517, pip |

## Intended Structure

```text
src/nginx_log_top/
  __init__.py
  __main__.py
  cli.py
  inputs.py
  parser.py
  models.py
  aggregate.py
  errors.py
  renderers/{text,json,csv}.py
tests/
  fixtures/
  golden/
benchmarks/
```

## Working Method

Read the relevant specification section before editing. Implement only the current step, preserve earlier acceptance tests, and record commands actually run. Prefer simple typed functions and dependency injection of streams/consoles over global state. Treat logs as untrusted and potentially sensitive. A passing unit test is not evidence of the 1 GB target; performance requires the benchmark record.

## Status

| Step | Scope | Status |
|---:|---|---|
| 1 | Package and CLI skeleton | Not started |
| 2 | Domain models and exit semantics | Not started |
| 3 | Streaming input and parser | Not started |
| 4 | One-pass aggregation | Not started |
| 5 | Rich terminal renderer | Not started |
| 6 | JSON and CSV renderers | Not started |
| 7 | Follow mode | Not started |
| 8 | Performance benchmark | Not started |
| 9 | Release readiness | Not started |

## Session Handoff

Before stopping, update the status table, record tests and benchmark evidence, state the next incomplete step, and run `/session-save`. Never mark a step complete from narration alone.

