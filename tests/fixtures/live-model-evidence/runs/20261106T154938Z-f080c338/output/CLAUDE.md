# Nginx Lens Project Instructions

## Context
Planning-only blueprint for a local nginx access-log CLI for DevOps/SRE. The product and MoSCoW decisions are user-approved. No product code exists. Read [PRD](PRD.md) for behavior, [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for contracts, [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for priorities, [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for steps and [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) for prompts. [README](README.md) describes intended usage.

## Rules
- Keep one task active. Change the specification before changing behavior; keep instruction memory in this single file.
- Python 3.11, Click, Rich, dataclasses; local pip installation; one process and stateless streaming.
- No auth, database, HTTP API, server, cloud or Kubernetes. No network or telemetry in product runtime.
- Retain exact metrics and bounded key state. Preserve exit codes 0/1/2/3/4: success, I/O/internal failure, usage, nonempty all-invalid, unique-cardinality exhaustion respectively.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`. Architecture defines denominators, zero cases, UTC conversion, parser and export contracts.
- Add and run meaningful tests for new code. Record actual command results; performance targets remain unverified until measured.
- Human approval precedes push, PR, publication, deployment and destructive/external operations. Never expose secrets or raw sensitive log lines in diagnostics.
- At the end of each session or significant work block, save context through /session-save.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure
`src/nginx_lens/`: cli, reader, parser, models, aggregate, render, errors. `tests/`: fixtures, unit and subprocess acceptance checks. `benchmarks/`: generator, runner, environment/results. These are planned paths, not existing implementation.

## Step Status
| Step | Deliverable | Status |
|---|---|---|
| 1 | Package and verification scaffold | Pending |
| 2 | Bounded parser | Pending |
| 3 | Exact aggregation | Pending |
| 4 | File/stdin CLI | Pending |
| 5 | Terminal output | Pending |
| 6 | JSON/CSV | Pending |
| 7 | Acceptance suite | Pending |
| 8 | Benchmark and local release candidate | Pending |

## Handoff
Blueprint documents are the current artifacts. External harness architecture review is pending; none ran here. Next product action after that review is implementation step 1 in a separately authorized session.
