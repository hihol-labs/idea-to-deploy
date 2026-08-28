# Project Instructions: nginx-insight

## Context

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams standard nginx combined access logs and reports top-10 IPs, top-10 URLs by 4xx/5xx count, 24 hourly request percentages, and unique User-Agent count/share. Default output is colored terminal text; `--json` and `--csv` support pipelines.

## Source of Truth

Read in this order before implementation:

1. `PRD.md` for behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` for interfaces, schemas, metric semantics, and architecture.
3. `IMPLEMENTATION_PLAN.md` for WIP=1 delivery order.
4. `.itd/` contracts and `.itd-memory/` state for execution and verification.

When behavior changes, update the specifications first and then change code. Do not fragment durable agent instructions into new instruction files.

## Non-Negotiable Rules

- Use Python 3.11, Click, Rich, dataclasses, and pip-compatible packaging.
- Keep a single local process with stateless streaming; no database, HTTP API, server, auth, cloud, or Kubernetes.
- Never load the whole input into memory or make a network request.
- Preserve deterministic ordering and machine-output schemas.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`.
- Preserve exit codes `0/1/2/3/4`: success, input/I/O, usage, log-data, and unique-cardinality exhaustion.
- Code 4 must remain unique-cardinality exhaustion and must not emit a partial report.
- Keep report output on stdout and diagnostics on stderr.
- Add or update tests with every behavior change; performance work requires before/after measurement.
- Preserve WIP=1. Freeze and verify the exact staged candidate under the Idea to Deploy contracts before accepting implementation work.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure

```text
src/nginx_insight/        package, parser, aggregator, CLI, renderers
tests/                    unit, CLI, renderer, and acceptance tests
tests/fixtures/           small deterministic nginx fixtures
benchmarks/               representative generator and timed runner
pyproject.toml            package and tool configuration
```

## Implementation Status

| Step | Scope | Status |
|---:|---|---|
| 1 | Package and CLI contract | Not started |
| 2 | Models and parser | Not started |
| 3 | Streaming input | Not started |
| 4 | Aggregates and cardinality guard | Not started |
| 5 | Rich terminal renderer | Not started |
| 6 | JSON and CSV renderers | Not started |
| 7 | End-to-end acceptance | Not started |
| 8 | Performance, packaging, handoff | Not started |

## Verification Expectations

Each step must identify concrete changed files and run its focused checks. Final acceptance requires the complete suite, clean-wheel installation, output-mode smoke tests, the representative 1 GB benchmark, and a current exact-candidate adjudication receipt. A narrative `PASSED` statement is not evidence.

## Current Next Action

Begin Step 1 only after the blueprint has passed the separately orchestrated external architectural review. Do not create `DEVILS_ADVOCATE_REVIEW.md` from the implementation session.
