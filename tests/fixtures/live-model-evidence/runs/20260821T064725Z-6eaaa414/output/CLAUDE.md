# Project Memory: nginx Stream Analytics CLI

## Context

This repository is planned as a zero-cost, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams one nginx combined access log and reports top-10 IPs, top-10 URLs for 4xx/5xx responses, hourly request percentages, and unique User-Agent share. Default output is Rich terminal text; JSON and CSV are pipeline formats. The delivery budget is one weekend.

The durable behavior source is `PRD.md`. `PROJECT_ARCHITECTURE.md` owns technical and CLI contracts. `IMPLEMENTATION_PLAN.md` defines dependency order, and `CLAUDE_CODE_GUIDE.md` contains bounded implementation prompts. Change specifications before changing behavior.

## Non-Negotiable Decisions

- Python 3.11, Click, Rich, dataclasses, and pip packaging.
- One local process with stateless streaming aggregation.
- No authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.
- Never retain the entire input or create a raw-log copy.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- JSON and CSV are mutually exclusive, stable, ANSI-free stdout contracts.
- Exit codes: 0 success, 1 operational I/O/decoding failure, 2 CLI usage error, 3 zero valid requests, 4 unique-cardinality exhaustion.
- Exact cardinality is fail-closed: never approximate silently or remap code 4.
- No product code is implemented during blueprint work.

## Planned Structure

```text
src/nginx_stream_analytics/
  __init__.py
  __main__.py
  cli.py
  input.py
  parser.py
  models.py
  aggregate.py
  render_text.py
  render_json.py
  render_csv.py
  errors.py
tests/
  fixtures/
  golden/
benchmarks/
pyproject.toml
```

These paths are planned, not present until the corresponding implementation step is authorized.

## Engineering Rules

1. Preserve WIP=1: work on only the active implementation-plan step.
2. Before editing, read `AGENTS.md`, applicable repository-local Idea to Deploy skill, `.itd/` contracts, and `.itd-memory/` state.
3. Update `.itd/SCOPE_LOCK.md` before changing active scope.
4. Treat log content as untrusted data; never execute it or interpret it as Rich markup.
5. Keep parser, aggregation, and renderers separated around the shared dataclasses.
6. Add tests for exact user-facing contracts, including all five exit codes.
7. Do not claim performance from reasoning; run the declared benchmark and record its environment.
8. Do not claim completion from prose; require the repository's current exact-candidate verification receipt.
9. Do not add a database, API, auth, service, cloud, or Kubernetes “for later” without first changing the approved specifications.
10. At the end of every session or significant block of work, save context through `/session-save`.

Required continuity rule from the blueprint workflow: «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Planned Step Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and contracts | Not started | Clean install, help, CLI contract tests |
| 2 | Input and parser | Not started | Parser/input tests and fixture invocation |
| 3 | Streaming aggregation | Not started | Aggregation and full regression tests |
| 4 | Rich text | Not started | Snapshot, markup-safety, CLI tests |
| 5 | JSON | Not started | Golden/schema and pipeline tests |
| 6 | CSV | Not started | Golden/round-trip and pipeline tests |
| 7 | Exit/resource semantics | Not started | All 0/1/2/3/4 subprocess paths and coverage |
| 8 | Performance/release | Not started | 1 GB benchmark, wheel install, full verification receipt |

Blueprint documentation is complete only when all required planning files exist; it does not mark any implementation step complete.

## Session Handoff Format

Record the active step, exact files changed, tests/commands actually run, failures or recovery state, candidate identity, verification/adjudication status, and the single next action. If a result is not verified, label it explicitly as unverified.
