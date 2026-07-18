# Project Instructions: nginx-stream-report

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx common/combined access logs and reports top 10 IPs, top 10 4xx/5xx URLs, hourly request distribution, and distinct User-Agent share. Terminal output is colored; JSON and CSV are pipeline contracts. The product is stateless and local: no database, HTTP API, auth, server, cloud, Docker requirement, or Kubernetes.

## Sources of truth

1. `PRD.md` defines required behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` defines metric, output, safety, and component contracts.
3. `IMPLEMENTATION_PLAN.md` defines dependency order and verification commands.
4. `STRATEGIC_PLAN.md` defines scope, priorities, KPIs, and kill criteria.
5. `.itd/` and `.itd-memory/` define active-unit and evidence state.

When documents disagree, stop and reconcile the specifications before code changes. Behavior changes begin in the spec; generated/implemented code follows it.

## Engineering rules

- Preserve WIP=1 and work only on the active implementation-plan step.
- Use Python 3.11, Click, Rich, and dataclasses; add dependencies only with an explicit architectural reason.
- Stream iterators line by line; never materialize the input log.
- Keep parsing, aggregation, source handling, and rendering separated.
- Keep metric results identical across terminal, JSON, and CSV.
- Send data only to stdout and diagnostics only to stderr in machine modes.
- Use deterministic tie ordering and version machine-readable schemas.
- Never silently approximate exact metrics; enforce the cardinality safety stop.
- Treat access logs as sensitive local data: no telemetry/egress and no full-line diagnostics by default.
- Test first or capture red-to-green evidence for behavior changes.
- Run the verification commands named by the active step; unrun checks are not passes.
- Do not introduce a database, HTTP API, auth, server, cloud, Docker, or Kubernetes without a scope/architecture decision approved by the user.
- At the end of each session or meaningful block of work, preserve context through `/session-save`.
- Required methodology rule: «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Planned structure

```text
src/nginx_stream_report/  # CLI, parser, source, aggregator, models, renderers
tests/                    # unit/integration tests and sanitized fixtures
benchmarks/               # deterministic generator, runner, evidence
pyproject.toml            # package/tool configuration
```

## Implementation status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Package and CLI contract | Planned | wheel build + CLI tests |
| 2 | Models, fixtures, benchmark protocol | Planned | model tests + generator smoke |
| 3 | Streaming parser/sources | Planned | parser tests + mypy |
| 4 | Aggregation and limits | Planned | oracle tests + branch coverage |
| 5 | JSON/CSV renderers | Planned | renderer tests + JSON parse smoke |
| 6 | Rich/CLI integration | Planned | CLI suite + manual no-color output |
| 7 | Follow mode | Planned | follow tests + full suite |
| 8 | Release gates | Planned | quality suite + 1 GB benchmark + clean install |

Blueprint status is documentation complete only after static verification. No product-code step is active yet. The next action is Step 1 after explicit implementation authorization.
