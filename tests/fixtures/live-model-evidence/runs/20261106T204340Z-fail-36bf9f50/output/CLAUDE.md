# Nginx Lens Project Context

## Purpose and Source of Truth
Local nginx combined-log analysis for DevOps/SRE. Planning documents are the durable source; product code is not implemented. Read [PRD](PRD.md) for acceptance criteria, [PROJECT_ARCHITECTURE](PROJECT_ARCHITECTURE.md) for precise interfaces, [STRATEGIC_PLAN](STRATEGIC_PLAN.md) for priorities, [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md) for sequencing and [CLAUDE_CODE_GUIDE](CLAUDE_CODE_GUIDE.md) for prompts. [README](README.md) labels future commands explicitly.

## Rules and Stack
Python 3.11, Click, Rich, dataclasses, pip. One process, one pass, transient exact aggregates; no database, auth, HTTP API, server, cloud or Kubernetes. WIP=1. Change specifications before behavior. Test all new code and run the suite before commits; never report unrun checks as passing. External actions require explicit human approval. Do not emit secrets or raw logs in diagnostics.

Exit codes: 0 success; 1 I/O/runtime error; 2 usage error; 3 nonempty all-invalid input; 4 unique-cardinality exhaustion. Hourly percentage: `100 × hourly_request_count / total_valid_requests`. Respect distinct-entry and line-size limits.

At the end of every session or significant block of work, save context through /session-save.
В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure
`src/nginx_lens/`: CLI, bounded reader, parser, models, aggregate, renderer and errors. `tests/`: golden, unit and integration fixtures. `scripts/`: deterministic benchmarks. `docs/`: measured benchmark report and optional troubleshooting. These are planned paths, not existing product modules.

## Status
| Step | Work | Status |
|---|---|---|
| 1 | Packaging/help | Not started |
| 2 | Reader/parser | Not started |
| 3 | Rankings/limits | Not started |
| 4 | Hourly/UA | Not started |
| 5 | Renderers | Not started |
| 6 | Integration | Not started |
| 7 | Performance/wheel | Not started |
| 8 | Release qualification | Not started |

Blueprint documents have been authored; adversarial review belongs to the external harness after this session. No in-session independent verdict, product tests, performance results or release approval are asserted. Next implementation action after planning review: step 1.
