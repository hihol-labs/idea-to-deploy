# nginx-report Project Instructions

## Project Context

Build a local, pip-installable Python 3.11 CLI for DevOps/SRE engineers. It streams nginx combined access logs and reports top client IPs, top 4xx/5xx request targets, UTC hourly request percentages, and unique User-Agent share. Default output is TTY-aware Rich text; `--json` and `--csv` are stable pipeline formats.

The governing architecture decision is **no database — stateless streaming processing; no HTTP API — CLI-only tool**. Do not add authentication, persistence, a daemon/server, cloud services, Docker as a runtime dependency, or Kubernetes. Cash budget is $0 and the MVP delivery window is one weekend.

## Specification Order

1. `PRD.md` defines user-visible behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` defines technical interfaces, schemas, metrics, and module boundaries.
3. `IMPLEMENTATION_PLAN.md` defines dependency order and verification per step.
4. `CLAUDE_CODE_GUIDE.md` provides executable prompts; it does not override the specifications.
5. `STRATEGIC_PLAN.md` defines scope, priority, success, risks, and Definition of Done.

When behavior changes, change and reconcile the specification first. Do not let generated code become the only source of truth.

## Stack and Planned Structure

- Python 3.11, Click, Rich, dataclasses, standard-library aggregation and serialization.
- `src/nginx_report/cli.py`: interface, stream ownership, renderer choice, exit mapping.
- `src/nginx_report/parser.py`: combined-log grammar only.
- `src/nginx_report/aggregate.py`: exact one-pass metrics and cardinality guard.
- `src/nginx_report/models.py`: immutable cross-module dataclasses.
- `src/nginx_report/renderers/`: text, JSON, and CSV presentation only.
- `tests/`: parser, aggregator, renderer, CLI, package, and opt-in performance evidence.

## Non-negotiable Product Contracts

- Stream input once; do not retain raw records or read the whole file.
- Hourly distribution is a percentage using exactly `100 × hourly_request_count / total_valid_requests` after UTC normalization.
- Unique User-Agent share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`.
- Rank by count descending, then key ascending. Request targets remain verbatim, including query strings.
- stdout contains only the selected report; diagnostics go to stderr. JSON/CSV never contain ANSI escapes.
- Complete exit codes are `0` success (including empty input), `1` I/O or unexpected runtime failure, `2` usage error, `3` non-empty input with zero valid requests, and `4` unique-cardinality exhaustion. Never omit or remap code `4`, and never silently approximate exact results.
- Treat input as untrusted data: cap line length, escape Rich markup, and use standard JSON/CSV serializers.
- Target a representative 1 GB log in under 30 seconds and under 512 MiB peak RSS on the documented laptop baseline.

## Engineering Rules

- Preserve WIP=1 and complete steps in `IMPLEMENTATION_PLAN.md` order unless an evidence-backed dependency requires reconciliation.
- Add tests in the same step as behavior; never remove or weaken a gate to make a run pass.
- Use real command output from the current candidate as evidence. A narrated pass is not acceptance.
- Keep synthetic fixtures and benchmark data explicitly labeled; never present them as production data.
- Do not commit secrets, user logs, benchmark logs, virtual environments, build output, or caches.
- Before accepting a release candidate, run unit/CLI/golden tests, coverage, lint, types, wheel checks, fresh-install smoke, and the documented performance/RSS benchmark.
- At the end of every session or meaningful block of work, save context through `/session-save` (required continuity rule: «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save»).

## Step Status

| Step | Scope | Status | Required evidence before Done |
|---:|---|---|---|
| 1 | Packaging and CLI contracts | Not started | Install, help, CLI tests |
| 2 | Models and combined parser | Not started | Parser tests, compile check |
| 3 | Streaming aggregation | Not started | Aggregation tests, coverage |
| 4 | JSON and CSV | Not started | Renderer tests, golden validation |
| 5 | Rich text | Not started | Text tests, ANSI redirection check |
| 6 | Integration and exits | Not started | Full CLI tests including `0/1/2/3/4` |
| 7 | Performance and memory | Not started | 1 GB timing/RSS record and code `4` case |
| 8 | Quality and packaging | Not started | Lint, types, wheel, clean install |
| 9 | Release reconciliation | Not started | Complete current-candidate gate |

Blueprinting creates documentation only. Do not mark implementation steps started or done until product code work is explicitly requested.
