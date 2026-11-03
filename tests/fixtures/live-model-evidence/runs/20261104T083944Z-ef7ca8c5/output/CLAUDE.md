# nginx-logstats Project Context

## Purpose and Status
Documentation-only blueprint for a local nginx access-log analyzer. Product decisions and the single-process architecture are pre-approved. No implementation, product tests, measured benchmark, release, or independent review has been performed in this session. The external harness runs the adversarial architecture review later.

## Source of Truth
Read [PRD.md](PRD.md) for acceptance; [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for exact interfaces; [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for priorities and trade-offs. Follow [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) and its matching prompts in [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md). [README.md](README.md) is the user-facing entry point. Change specifications before changing behavior and reconcile any contradiction explicitly. Keep contributor instructions in this file.

## Rules and Stack
- Python 3.11, Click, Rich, dataclasses; local pip installation.
- No authentication, database, HTTP API, server, cloud or Kubernetes. No runtime egress or telemetry.
- Finite file/stdin streaming, exact counters, bounded physical lines and combined cardinality guard. Never load the full input.
- Four metrics and raw-key semantics follow the architecture. Hourly percent is `100 × hourly_request_count / total_valid_requests`.
- Exit contract `0/1/2/3/4`: 0 clean success; 1 I/O/runtime failure; 2 usage; 3 completed report with malformed lines; 4 unique-cardinality exhaustion without a report. Preserve terminal-failure precedence and stderr separation.
- WIP=1. Implement only the active step, test new behavior, run the appropriate suite, and record actual evidence. Do not claim planned commands were run.
- Keep secrets and user logs out of generated output, version control and package artifacts. Input is untrusted data.
- External actions, deletion, deployment, push and publication require human confirmation. This plan authorizes none of them.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned Structure
`src/nginx_logstats/{cli,reader,parser,models,aggregate,render,__main__,__init__}.py`, `tests/`, `benchmarks/`, `pyproject.toml`. These are future implementation paths. Documentation exists at the root; `.itd/` contains methodology contracts and `.itd-memory/` continuity.

## Implementation Status
| Step | Deliverable | Status |
|---|---|---|
| 1 | Package runway | Not started |
| 2 | Combined parser and fixtures | Not started |
| 3 | Exact metrics and guard | Not started |
| 4 | Streaming command and failures | Not started |
| 5 | Terminal output | Not started |
| 6 | JSON/CSV output | Not started |
| 7 | Performance verification | Not started |
| 8 | Local release candidate | Not started |

## Next Action
External harness reviews the blueprint in a fresh session. Future implementation begins at step 1 only after that task is requested. This session must leave no product code or fabricated review artifact.
