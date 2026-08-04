# Project Instructions: nginx-stream-report

## Context

Build a local, pip-installable Python 3.11 CLI for DevOps/SRE nginx access-log triage. The durable specifications are `PRD.md` and `PROJECT_ARCHITECTURE.md`; change them before changing behavior. `IMPLEMENTATION_PLAN.md` defines the one-weekend sequence.

## Non-Negotiable Rules

- Preserve WIP=1 and work one implementation step at a time.
- Do not add authentication, a database, HTTP API, server, cloud, Kubernetes, or hidden persistence.
- Keep processing single-pass and bounded by declared cardinality ceilings.
- Preserve CLI exit codes: 0 success, 1 runtime/I/O, 2 usage, 3 strict format, 4 unique-cardinality exhaustion.
- Never emit partial stdout reports for nonzero exits.
- Treat log contents as untrusted data and keep them local.
- Run and record each step's verification commands before marking it complete.
- In the end of every session or significant block of work — save context through `/session-save`.

## Stack

- Python 3.11
- Click
- Rich
- standard-library `dataclasses`, `collections`, `json`, `csv`, `gzip`
- pytest, Ruff, mypy, coverage, standard Python build tooling

## Planned Structure

```text
src/nginx_stream_report/
  __init__.py  cli.py  errors.py  input.py  parser.py  models.py
  aggregate.py render.py
tests/
  fixtures/ golden/ test_*.py
bench/
  generate_log.py README.md
```

## Implementation Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI contract | Not started | install/help/CLI tests |
| 2 | Combined-log parser | Not started | parser tests + Ruff |
| 3 | Streaming aggregation | Not started | aggregation tests + mypy |
| 4 | Input pipeline | Not started | path/stdin/exit integration tests |
| 5 | Text/JSON/CSV | Not started | golden and ANSI tests |
| 6 | gzip P1 | Not started | equivalence/corruption tests |
| 7 | Quality/performance | Not started | lint/type/coverage + 1 GiB timing/RSS |
| 8 | Packaging/release | Not started | build/twine/clean-install smoke test |

No product code exists at blueprint completion. A status may change only when current evidence satisfies `.itd/VERIFICATION_CONTRACT.json` and the applicable risk check.

## Working Sequence

Read `AGENTS.md`, `.itd/SCOPE_LOCK.md`, and the active `.itd-memory/` state before edits. Use the prompts in `CLAUDE_CODE_GUIDE.md`, reconcile state after each unit, and keep the next action explicit.
