# nginx-top Project Memory

## Context

Build a local, pip-installable Python 3.11 CLI for DevOps/SRE engineers. It streams conventional nginx combined access logs and reports top 10 IPs, top 10 URLs by 4xx/5xx count, 24 hourly request percentages, and exact unique User-Agent share. Default output is Rich terminal text; JSON and CSV are stable pipeline formats.

The architecture decision is fixed for the MVP: **no database — stateless streaming processing; no HTTP API — CLI-only tool**. There is no authentication, server, cloud service, Docker requirement, or Kubernetes. Cash budget is $0 and delivery is one weekend.

## Source of Truth

1. `PRD.md` defines behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` defines component, input/output, and exit contracts.
3. `IMPLEMENTATION_PLAN.md` defines dependency order and verification commands.
4. `STRATEGIC_PLAN.md` defines product priorities and Definition of Done.
5. `CLAUDE_CODE_GUIDE.md` supplies bounded execution prompts but does not override the specifications.

When behavior changes, update the specification first and then implementation/tests. Do not infer successful verification from prose.

## Required Stack and Structure

- CPython 3.11, Click, Rich, and standard-library dataclasses.
- `src/nginx_top/` package layout with typed modules for CLI, input, parser, models, aggregation, errors, and renderers.
- pytest, Ruff, mypy, at least 90% line coverage, and pip wheel/sdist packaging.
- No product code is present at blueprint completion; create it only during an explicitly authorized implementation step.

## Invariants

- Process input in one pass and never retain raw logs.
- Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`, with `0.0` on empty valid input.
- Exact User-Agent share is `100 × unique_user_agent_count / total_valid_requests`, guarded by the configured cardinality ceiling.
- Ranking order is count descending, key ascending.
- Results go to stdout; diagnostics go to stderr.
- Preserve exit codes `0/1/2/3/4`: success, I/O, usage, strict malformed input, and unique-cardinality exhaustion.
- Never emit partial JSON/CSV on a fatal path.
- Treat log fields as untrusted data in terminal and CSV renderers.
- Do not add database, API, service, authentication, cloud, or Kubernetes scope.

## Working Rules

- Keep WIP at one implementation-plan step.
- Add or update tests with every behavioral change and actually run the relevant suite.
- Report failures faithfully; red checks block completion.
- Measure the 1 GB/<30 s target on a named machine; do not promote estimates to results.
- Do not commit generated 1 GB fixtures, virtual environments, build output, caches, or reports containing real logs.
- Preserve user changes and keep unrelated discoveries out of the current diff.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Implementation Status

| Step | Scope | Status | Completion evidence |
|---:|---|---|---|
| 1 | Package skeleton and CLI | Not started | Required commands in `IMPLEMENTATION_PLAN.md` STEP 1 |
| 2 | Models and parser | Not started | STEP 2 pytest + mypy |
| 3 | Input and core metrics | Not started | STEP 3 unit/integration + coverage |
| 4 | User-Agent cardinality | Not started | STEP 4 boundary/exit tests |
| 5 | Rich renderer | Not started | STEP 5 renderer/integration tests |
| 6 | JSON and CSV renderers | Not started | STEP 6 parser/CLI tests |
| 7 | Error semantics and quality | Not started | Ruff + mypy + full ≥90% test gate |
| 8 | Benchmark and packaging | Not started | Build/install smoke test + measured benchmark |

## Next Action

Begin only STEP 1 using the matching prompt in `CLAUDE_CODE_GUIDE.md`. Do not implement later-step behavior until STEP 1 verification is green.

