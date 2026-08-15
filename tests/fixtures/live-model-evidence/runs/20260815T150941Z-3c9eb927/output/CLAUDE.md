# nginx-insight Project Instructions

## Context

Build a local, open-source Python 3.11 CLI for DevOps and SRE engineers that streams nginx common/combined access logs and reports top IPs, top error URLs, hourly request distribution, and exact User-Agent share. The MVP budget is $0 and the delivery boundary is one weekend.

The current repository state is blueprint-only. Do not treat planned files or commands as implemented behavior.

## Sources of Truth

1. `PRD.md` defines user-visible requirements and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` defines technical, CLI, metric, output, and exit contracts.
3. `IMPLEMENTATION_PLAN.md` defines dependency-ordered work units and checks.
4. `STRATEGIC_PLAN.md` defines priorities, success measures, risks, and scope.
5. `.itd/` and `.itd-memory/` define execution and verification state when implementation begins.

If the documents disagree, stop implementation, reconcile the spec, and update downstream documents before code.

## Non-Negotiable Product Rules

- Python 3.11, Click, Rich, standard-library dataclasses, and pip distribution.
- Local single-process streaming analysis; never buffer the whole raw log.
- No authentication, database, HTTP API, server, telemetry, cloud, or Kubernetes.
- Default colored terminal output, with deterministic `--json` and `--csv` pipeline formats.
- Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`.
- Exit codes are complete and fixed: `0` success, `1` operational failure, `2` usage failure, `3` input-data failure, `4` unique-cardinality exhaustion.
- Code 4 must never be omitted or remapped, and failure paths emit no partial report.
- Log fields are untrusted data: never execute them, pass them through a shell, or render them as Rich markup.
- The target is a representative 1 GB log in under 30 seconds on a documented reference laptop.

## Engineering Rules

- Preserve WIP=1: one active `IMPLEMENTATION_PLAN.md` step at a time.
- Start with the step's tests and contracts; keep changes within `.itd/SCOPE_LOCK.md`.
- Use one parsed record model and one final report model across every renderer.
- Make all ranking ties and output ordering deterministic.
- Write diagnostics to stderr and report data to stdout.
- Run the exact verification commands named by the active step and record actual results.
- Accept completion only from the current exact-candidate verification/adjudication evidence required by `.itd/VERIFICATION_CONTRACT.json`; narration is not evidence.
- Do not add P1/P2 work before all P0 behavior is green.
- At the end of every session or significant block of work, save context through `/session-save`.
- Required continuity rule: «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Planned Structure

```text
src/nginx_insight/
  cli.py
  models.py
  input.py
  parser.py
  aggregate.py
  render/{terminal,json,csv}.py
tests/
  fixtures/
  golden/
  test_models.py
  test_input.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_performance.py
```

## Implementation Status

| Step | Deliverable | Status | Required evidence before completion |
|---:|---|---|---|
| 1 | Package and domain contracts | Not started | Help/version and model/CLI tests |
| 2 | Streaming input and parser | Not started | Input/parser tests and parser coverage |
| 3 | IP, error URL, hourly metrics | Not started | Aggregation tests and coverage |
| 4 | User-Agent cardinality guard | Not started | Boundary/exhaustion tests |
| 5 | Rich terminal renderer | Not started | Golden and renderer coverage tests |
| 6 | JSON and CSV renderers | Not started | Parsed golden and equivalence tests |
| 7 | End-to-end CLI/exit mapping | Not started | Subprocess matrix for `0/1/2/3/4` |
| 8 | Performance and release readiness | Not started | Full suite, build, clean install, 1 GB benchmark, exact-candidate receipt |

## Current Next Action

Begin Step 1 only after creating the active `.itd-memory` unit state and reconciling `.itd/SCOPE_LOCK.md` for implementation. Follow Prompt 1 in `CLAUDE_CODE_GUIDE.md`; do not skip directly to product features.

