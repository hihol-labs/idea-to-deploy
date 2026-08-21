# Nginx Stream Insights Project Memory

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that reads
nginx combined access logs as a stream. It reports top 10 client IPs, top 10
4xx/5xx URL targets, 24 hourly percentage buckets, and exact unique User-Agent
share. Default output is colored terminal text; JSON and CSV are stable
pipeline formats. Budget is $0 and delivery is one weekend.

The current repository state is blueprint-only. No product code was created by
the planning workflow.

## Source-of-Truth Order

1. `PRD.md` owns user-visible requirements and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` owns metric, parser, CLI, schema, and component contracts.
3. `IMPLEMENTATION_PLAN.md` owns dependency order and verification commands.
4. `STRATEGIC_PLAN.md` owns priority, risk, and success framing.
5. `CLAUDE_CODE_GUIDE.md` provides step-bounded implementation prompts.

If documents conflict, pause implementation, reconcile the PRD and
architecture, then adjust plans. Do not let generated code silently redefine
the specification.

## Fixed Decisions

- Python 3.11, Click, Rich, dataclasses, pip, and a `src/` layout.
- One local process with stateless streaming processing.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Hourly percentage is
  `100 × hourly_request_count / total_valid_requests`.
- User-Agent share is exact distinct non-empty values divided by valid requests
  and multiplied by 100; exhaustion fails rather than approximates.
- The exit contract is `0` success, `1` input/output operating error, `2` usage
  error, `3` no valid finite-input records, and `4` unique-cardinality exhaustion.
- JSON/CSV are deterministic, contain no ANSI escapes, and use stdout; all
  diagnostics use stderr.
- Performance target: a representative 1 GB input in under 30 seconds on a
  documented reference laptop.

## Working Rules

- Preserve WIP=1: implement only the active step in `IMPLEMENTATION_PLAN.md`.
- Read the relevant acceptance criteria before editing.
- Do not add deferred P2 work while any P0/P1 acceptance criterion is open.
- Do not echo full raw log lines in diagnostics or invoke a shell with input data.
- Run the current step's verification commands and record actual outcomes.
- Do not claim the performance target without the prescribed benchmark evidence.
- Keep generated 1 GB fixtures, environments, caches, and distributions out of Git.
- At any behavior change, update the specification before or with implementation.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save
  (at the end of every session or meaningful work block, save context with
  `/session-save`).

## Planned Structure

```text
src/nginx_stream_insights/
  __init__.py
  cli.py
  input.py
  parser.py
  models.py
  aggregate.py
  errors.py
  renderers/
tests/
  fixtures/
tools/
docs/
```

## Implementation Status

| Step | Scope | Status |
|---:|---|---|
| 1 | Package and quality foundation | Not started |
| 2 | Models, errors, fixtures | Not started |
| 3 | Streaming input and parser | Not started |
| 4 | Exact aggregation and UA guard | Not started |
| 5 | Terminal, JSON, CSV renderers | Not started |
| 6 | Finite-stream CLI and exit codes | Not started |
| 7 | Follow mode | Not started |
| 8 | Acceptance and performance evidence | Not started |
| 9 | Release packaging and handoff | Not started |

## Session Handoff Template

Record the active step, changed files, commands actually run and outcomes,
open failures or unverified criteria, current scope lock, and exactly one next
action. Never record a planned check as if it passed.

