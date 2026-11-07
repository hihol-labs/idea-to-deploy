# Nginx Lens Project Context

## Purpose and Status

Local nginx combined-log analysis for DevOps/SRE engineers. This repository currently contains a blueprint, not an implemented product. No product tests, performance measurements, deployment, or independent review have run in this blueprint session. The external harness owns the fresh-session Devil's Advocate review.

## Sources of Truth

Read [PRD.md](PRD.md) for product acceptance and [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for technical contracts. [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) contains MoSCoW/RICE priorities and budget. Follow [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) one step at a time using [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md); [README.md](README.md) describes intended operator use. Keep agent instructions here and respect existing AGENTS.md and project methodology contracts.

## Stack and Structure

Python 3.11, Click, Rich, dataclasses, pip; pytest for future tests. Planned modules: `src/nginx_lens/{cli,reader,parser,models,aggregate,renderers}.py`, plus package entry points. Fixtures/tests go in `tests/`; synthetic generation and measurements in `bench/`. These paths are planned, not present product code.

## Rules

- WIP=1. Update the spec before changing behavior and keep all document contracts consistent.
- No auth, DB, HTTP API, server, cloud, Kubernetes, persistent cache, or telemetry.
- Stream once to EOF; exact aggregation is cardinality-bounded, not constant-memory.
- Preserve exit codes 0/1/2/3/4: success; I/O/internal/interruption; usage; strict parse/no valid records; unique-cardinality exhaustion.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`; distinct-UA share uses nonmissing distinct UAs over all valid requests, multiplied by 100.
- Test new code and actually run tests before reporting success. Never equate a written test or prompt with evidence.
- Use synthetic logs; never expose secrets or raw production log lines in diagnostics.
- Human approval is required before publishing, push/PR, deployment, irreversible changes, or external writes.
- At the end of each session or significant work block, save context through `/session-save`.

## Implementation Status

| Step | Deliverable | Status | Evidence |
|---|---|---|---|
| 1 | Package and fixture contracts | Pending | No product code |
| 2 | Bounded reader/parser | Pending | No product tests |
| 3 | Exact aggregation | Pending | No product tests |
| 4 | CLI and failures | Pending | No product tests |
| 5 | JSON/CSV | Pending | No product tests |
| 6 | Terminal report | Pending | No product tests |
| 7 | Capacity evidence | Pending | No measurements |
| 8 | Wheel and handoff | Pending | No built wheel |

Next product action after external blueprint validation: implement step 1 only. Current task authorization is documentation only.
