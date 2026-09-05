# Project Instructions: nginx-log-report

## Product Context

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams conventional nginx combined access logs and reports top 10 IPs, top 10 URLs by 4xx/5xx errors, hourly request percentages, and unique User-Agent share. Default output is colored Rich terminal text; JSON and CSV support pipelines. The product is open source, costs $0 to operate, and targets one-weekend delivery plus a measured 1 GB runtime under 30 seconds on a documented laptop.

## Source of Truth

Read in this order before implementation:

1. `.itd/` contracts and `.itd-memory/` active state.
2. `PRD.md` for user-visible requirements and acceptance criteria.
3. `PROJECT_ARCHITECTURE.md` for data, CLI, schema, and failure decisions.
4. `IMPLEMENTATION_PLAN.md` for dependency order and verification commands.
5. `CLAUDE_CODE_GUIDE.md` for bounded prompts.
6. `STRATEGIC_PLAN.md` for outcomes, priorities, risks, and release Definition of Done.

If documents conflict, stop and reconcile the specification before changing code. Behavior changes begin in the spec. Preserve WIP=1 and do not skip the active Idea to Deploy verification contract.

## Non-Negotiable Decisions

- Python 3.11, Click, Rich, dataclasses, standard pip packaging.
- One local process and a single-pass streaming pipeline.
- No authentication, database, HTTP API, server, cloud, Docker dependency, or Kubernetes.
- No network calls or telemetry.
- Exact metrics; never silently substitute approximation.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests` using the hour and offset represented in each log line.
- Machine formats are deterministic, ANSI-free, and diagnostic-free on stdout.
- Full exits are `0` success, `1` unexpected internal error, `2` usage/input I/O, `3` unusable or strict-invalid data, `4` unique-cardinality exhaustion.
- Untrusted log values must be escaped in displays; default errors must not echo whole log lines.

## Intended Structure

```text
pyproject.toml
src/nginx_log_report/
  __init__.py
  cli.py
  input.py
  parser.py
  models.py
  aggregate.py
  renderers.py
  errors.py
tests/
  fixtures/
  golden/
  test_cli.py
  test_input.py
  test_parser.py
  test_aggregate.py
  test_render_terminal.py
  test_render_machine.py
  test_e2e.py
  test_performance_smoke.py
tools/
  generate_benchmark_log.py
docs/
  BENCHMARK.md
```

This is a target structure, not permission to create all files at once. Each active implementation step owns only its listed files.

## Engineering Rules

- Work on one numbered implementation step at a time and keep its scope lock current.
- Add or update tests with behavior; do not weaken checks to obtain green output.
- Keep parsing, aggregation, and rendering independent.
- Never load an entire input or benchmark corpus into memory.
- Produce one immutable `Report` before selecting a renderer.
- Use deterministic tie-breaking: descending count, ascending value.
- Check cardinality before insertion and emit no partial stdout on failure.
- Record commands and actual outcomes. “Should pass” is not evidence.
- Do not commit generated 1 GB logs, virtual environments, build outputs, coverage files, or secrets.
- In the end of every session or meaningful block of work, save context through `/session-save`.
- Workflow rule (kept verbatim from the local skill): «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Step Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI skeleton | Planned | Clean install, help/version, CLI tests |
| 2 | Models and failure mapping | Planned | mypy and all exit-mapping tests |
| 3 | Combined-log parser | Planned | parser fixtures, Ruff, focused tests |
| 4 | Streaming input | Planned | stdin/plain/gzip/order and no-buffer tests |
| 5 | Aggregation and limits | Planned | formula, ties, reconciliation, boundary tests |
| 6 | Rich terminal output | Planned | content and ANSI tests |
| 7 | JSON and CSV | Planned | schema and golden tests |
| 8 | End-to-end hardening | Planned | coverage, Ruff, mypy, dependency checks |
| 9 | Performance and packaging | Planned | measured 1 GB result, peak RSS, clean wheel install |

Only set a row to Complete when the exact candidate has current evidence required by `.itd/VERIFICATION_CONTRACT.json`; prose or an isolated `PASSED` verdict is insufficient.

## Session Handoff

At handoff, state the active step, files changed, commands actually run, unresolved failures, current scope lock, and the single next action. Do not claim an adversarial or independent review unless that reviewer actually ran and produced its expected artifact.
