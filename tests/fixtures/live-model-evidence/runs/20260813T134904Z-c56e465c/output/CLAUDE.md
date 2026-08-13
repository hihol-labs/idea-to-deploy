# Nginx Stream Insights — Project Instructions

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE users that streams nginx combined access logs and reports top client IPs, error-heavy URLs, hourly request distribution, and unique User-Agent share. Default output is Rich terminal text; `--json` and `--csv` serve pipelines. Cash budget is $0 and delivery scope is one weekend.

The project is currently documentation-only. No product implementation or runtime benchmark has occurred.

## Sources of Truth

Read these before implementation:

1. `AGENTS.md` and `.itd/` — methodology and active scope contracts.
2. `PRD.md` — behavior, priorities, user stories, and acceptance criteria.
3. `PROJECT_ARCHITECTURE.md` — modules, CLI, data, schemas, errors, and performance design.
4. `IMPLEMENTATION_PLAN.md` — dependency order and verification commands.
5. `CLAUDE_CODE_GUIDE.md` — bounded prompts for one step at a time.
6. `STRATEGIC_PLAN.md` — product rationale, alternatives, KPIs, and risks.

If documents conflict, stop implementation and reconcile the specification. Architecture controls technical design; PRD controls observable behavior. Do not silently change either in code.

## Non-Negotiable Rules

- Preserve WIP=1 and implement only the active plan step.
- Use Python 3.11, Click, Rich, dataclasses, a `src/` layout, and pip packaging.
- Remain a single-process, stateless streaming CLI. Do not add authentication, a database, HTTP API, server, cloud dependency, or Kubernetes.
- Do not retain the complete input or raw lines; enforce the configured distinct-key ceiling.
- Calculate every hourly percentage as `100 × hourly_request_count / total_valid_requests`.
- Exit codes are `0` success, `1` unexpected internal error, `2` CLI usage/input I/O/encoding error, `3` log-data failure, and `4` unique-cardinality exhaustion. Never omit, reuse, or remap code `4`.
- Write report data to stdout and diagnostics to stderr. JSON/CSV must be deterministic and atomic on domain failure.
- Add or update tests with every behavioral change; use actual results, not predicted outcomes, to update status.
- Do not add secrets, telemetry, or network calls.
- Do not create `DEVILS_ADVOCATE_REVIEW.md` during normal implementation. Independent adversarial review is a separately scoped external workflow.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Planned Stack

| Area | Choice |
|---|---|
| Runtime | Python 3.11 |
| CLI | Click |
| Terminal | Rich |
| Models | standard-library dataclasses |
| Packaging | `pyproject.toml`, pip, wheel, `src/` layout |
| Tests | pytest and branch coverage |
| Storage/API/deployment | None; local process only |

## Planned Structure

```text
src/nginx_stream_insights/
  __init__.py
  cli.py
  parser.py
  models.py
  aggregate.py
  errors.py
  render_text.py
  render_json.py
  render_csv.py
tests/
  fixtures/
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_performance.py
scripts/
  generate_benchmark_log.py
```

Create paths only in their implementation-plan step; this tree is a target, not evidence that files exist.

## Implementation Status

| Step | Scope | Status | Evidence required |
|---:|---|---|---|
| 1 | Installable CLI scaffold | Not started | Editable install, help, focused tests |
| 2 | Models, errors, fixtures | Not started | Model/error tests and explicit `4` assertion |
| 3 | Combined-log parser | Not started | Parser tests and branch coverage |
| 4 | Bounded aggregation | Not started | Metric, tie, formula, and cardinality tests |
| 5 | Text/JSON/CSV renderers | Not started | Parsed/golden renderer tests |
| 6 | CLI integration and failures | Not started | File/stdin tests and `0/1/2/3/4` matrix |
| 7 | Correctness/performance evidence | Not started | Full suite, coverage, three benchmark runs |
| 8 | Wheel and clean acceptance | Not started | Built wheel and fresh-environment smoke tests |

## Session Handoff

At the end of work, record the active step, files changed, commands actually run with outcomes, unresolved risks, and one next action. A step remains Not started or In progress unless its own evidence is current. Documentation planning is not product runtime evidence.
