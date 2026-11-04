# nginx-scan: project context

## Product and scope

Local Python 3.11 CLI for DevOps/SRE engineers reading nginx combined access logs. Deliver exact top-10 IPs, top-10 error URLs, hourly UTC request percentages and unique User-Agent share. Terminal text defaults to TTY-aware color; --json and --csv support pipelines. One weekend, approximately 16 developer hours, $0 cash, open source. No product code has been implemented by the blueprint.

## Source of truth and working rules

Read [PRD.md](PRD.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) and [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) before implementation. PRD acceptance criteria are durable behavioral specifications; architecture resolves interface details. If they conflict, reconcile documents before changing code. Keep agent instructions here; retain and follow the existing AGENTS.md harness rules.

- WIP=1: execute one approved step at a time; change the spec before changing behavior.
- No database, auth, HTTP API, server, cloud, Kubernetes or network telemetry.
- Use Python 3.11, Click, Rich, dataclasses and pip packaging; no whole-log reads.
- Exact counts require bounded cardinality. Never silently approximate, evict keys or drop exit code 4.
- Preserve 0/1/2/3/4: success, internal/interruption, usage, I/O, unique-cardinality exhaustion respectively.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`; use UTC and zero-safe percentages.
- Add meaningful tests with implementation and run the relevant suite; never claim a future command as completed evidence.
- Keep secrets and raw sensitive logs out of diagnostics, commits and external tools.
- Commits, pushes, publishing and production changes require their applicable human authorization; blueprint approval covers local documentation only.
- At the end of each session or significant block of work, save context via /session-save.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned structure and commands

`src/nginx_scan/{cli,reader,parser,models,aggregate,render}.py`, `tests/`, `benchmarks/`, `pyproject.toml`. These paths are planned, not implemented. Future checks: `python -m pytest`, `python -m ruff check src tests benchmarks`, `python -m build`. Benchmark commands are in implementation step 7; record measurements rather than assume the 1 GB/<30-second goal is achieved.

## Step status

| Step | Work | Status |
|---|---|---|
| 1 | Packaging and models | Pending |
| 2 | Reader and parser | Pending |
| 3 | Aggregation and caps | Pending |
| 4 | Terminal output | Pending |
| 5 | JSON/CSV | Pending |
| 6 | CLI/error integration | Pending |
| 7 | Performance evidence | Pending |
| 8 | Local wheel and documentation | Pending |

Blueprint artifacts are distinct from product readiness. No product tests, performance run or independent review occurred in this documentation session. The external harness runs the real adversarial review separately; do not create its review artifact or imply it has passed. Next implementation action after reviewing that artifact: step 1. [README.md](README.md) documents the planned user experience.
