# Nginx Pulse — Project Instructions

## Context and Source of Truth
Documentation-only blueprint for a local nginx combined-log analytics CLI for DevOps/SRE. The project brief pre-approves Python 3.11, Click, Rich, dataclasses, pip delivery, a $0 cash budget and one weekend. No product implementation has occurred.

Read [PRD.md](PRD.md) for acceptance, [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for the interface and parsing contract, [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for priorities, [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for work order, and [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) for step prompts. Follow repository `AGENTS.md` and applicable `.itd/` contracts. Change specifications before implementing changed behavior; reconcile conflicts explicitly.

## Rules
- One process, finite streaming, exact in-memory aggregates. No auth, DB, HTTP API, server, cloud, Kubernetes or persisted state.
- Top-ten IPs across valid requests; top-ten query-free paths by combined 4xx/5xx count; 24 local-hour buckets; exact unique-UA share. Tie-break by key ascending.
- Hourly percentage: `100 × hourly_request_count / total_valid_requests`. Unique-UA percentage: 100 × distinct nonmissing UAs / valid requests. Missing UA remains in denominator.
- Preserve exit codes **0/1/2/3/4**: success/help/version; I/O failure; usage error; no valid records/interruption/processing failure; unique-cardinality exhaustion. Resource failure gives no final report.
- Retained-key budgets are exact and preflighted per record. Never silently sample, evict, approximate or bypass the byte cap.
- Treat log content as data, keep diagnostics on stderr, use synthetic fixtures, and make no runtime network calls.
- Work one plan step at a time. Run focused checks and the full suite; record actual output. Do not claim unmeasured performance or review completion.
- Before irreversible/external actions obtain human confirmation under AGENTS.md. This blueprint does not authorize publication, push or deployment.
- In the end of every session or significant block of work, save context through `/session-save`.
- «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Planned Structure
`src/nginx_pulse/`: CLI, bounded reader, parser, dataclasses, aggregation, renderers. `tests/`: unit/integration/installed-wheel checks and synthetic fixtures. `benchmarks/`: corpus generator, runner, measured results. These are future paths; root Markdown files are the current product deliverables.

## Step Status
| Step | Scope | Status |
|---|---|---|
| 1 | Package scaffold | Not started |
| 2 | Bounded reader/parser | Not started |
| 3 | Metrics/resource budgets | Not started |
| 4 | CLI and errors | Not started |
| 5 | Terminal presentation | Not started |
| 6 | JSON/CSV | Not started |
| 7 | Benchmark/tuning | Not started |
| 8 | Wheel/handoff | Not started |

## Current Handoff
Blueprint documents are the planning deliverable. Adversarial review is reserved for the external harness's fresh session, with no in-session independent verdict. Product tests, performance targets and local installation remain unverified until implementation. The continuation record is `.itd-memory/continuity/nginx-pulse-blueprint.md`; next engineering action after external review is plan step 1.
