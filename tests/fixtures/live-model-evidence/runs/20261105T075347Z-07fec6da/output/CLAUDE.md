# Nginx Lens — Project Instructions

## Context and Source of Truth
Local, open-source, $0, weekend nginx access-log CLI for DevOps/SRE. This repository currently contains planning documents only. The spec is the durable source of truth; change requirements before changing delivered behavior. Keep project agent instructions in this file; existing harness AGENTS.md remains authoritative for methodology.

Read [PRD.md](PRD.md) for requirements, [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for parsing/output/CLI contracts, [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for priorities, [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for steps, [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) for prompts and [README.md](README.md) for intended usage.

## Stack and Boundaries
Python 3.11, Click, Rich, dataclasses; pip packaging; one synchronous streaming process. No authentication, database, HTTP API, server, cloud, Kubernetes, telemetry, persistent state or live tail. Exact aggregation bounded by --max-unique; default global entry budget 1000000. No implementation code was authorized in this blueprint session.

## Behavior Rules
- Preserve full exit codes **0/1/2/3/4**: 0 success/help/version, 1 I/O/interruption/runtime failure, 2 usage, 3 no valid requests, 4 unique-cardinality exhaustion including MemoryError.
- Valid requests alone drive denominators. Hourly percentage is `100 × hourly_request_count / total_valid_requests`, using logged local hours across dates.
- Unique UA share is distinct nonmissing User-Agents divided by all valid requests, multiplied by 100.
- Top-10 sorting is count descending then key ascending. Error paths combine 400–599 and strip query/fragment.
- Do not approximate, emit partial aggregates on failure, print raw log lines, or interpret terminal control sequences from input.
- Use one work item at a time. Update spec and scope before expanding work. Add meaningful tests and run the suite before any commit.
- Separate planned tests and performance targets from observed results. Request separate authorization before publishing, push, PR, deployment or deletion.
- At the end of every session or significant block of work, save context through /session-save.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure
`src/nginx_lens/`: __init__.py, cli.py, reader.py, parser.py, models.py, aggregate.py, render.py.

`tests/`: parser/reader, rankings/metrics/capacity, render/CLI, end-to-end/install tests and hand-counted fixtures. `benchmarks/`: synthetic generator, runner and measured results. `pyproject.toml`: packaging/dependencies/entry point.

## Implementation Status
| Step | Work | Status |
|---|---|---|
| 1 | Packaging, models, fixtures | Not started |
| 2 | Bounded reader/parser | Not started |
| 3 | IP/error rankings | Not started |
| 4 | Hourly/UA metrics, capacity | Not started |
| 5 | Terminal/JSON/CSV | Not started |
| 6 | CLI options/exit mapping | Not started |
| 7 | End-to-end/wheel verification | Not started |
| 8 | Performance and handoff | Not started |

## Verification and Next Action
No product tests or performance measurements exist yet. Blueprint structural checks are recorded in `.itd-memory/continuity/nginx-lens-blueprint.md`. Adversarial architecture review is external and has not run inside this session. Next product action, after external review and implementation authorization, is step 1; the guide contains the exact prompt and verification commands.
