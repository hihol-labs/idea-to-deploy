# Nginx Lens: project context

## Context and source of truth
Documentation-only blueprint for an open-source local nginx combined access log CLI for DevOps/SRE engineers. Approved scope: top-10 IPs, top-10 error URLs (400–599), hourly request percentages, unique User-Agent share, default colored terminal text and JSON/CSV exports. Budget $0; one-weekend delivery target.

Read [PRD.md](PRD.md) for acceptance, [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for the CLI/schema contract, [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for priorities, [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for tasks, [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) for prompts and [README.md](README.md) for usage. Keep agent instructions centralized here, while respecting the repository's AGENTS.md harness policy. Specifications are durable: update agreed requirements before implementing behavior changes.

## Rules
- Implement only when explicitly requested; this session generates no product code.
- One active task at a time. Keep unrelated discoveries out of the current diff.
- Python 3.11, Click, Rich, dataclasses, pip; single process; no authentication, database, HTTP API, server, cloud or Kubernetes.
- Process finite input incrementally, preserve exact counts, and never quietly approximate. Default shared cardinality limit 250000; oversized line limit 65536 bytes.
- Hourly percentage: `100 × hourly_request_count / total_valid_requests`, using logged hour-of-day. Missing User-Agents are excluded from unique-share numerator and denominator.
- Exit codes **0/1/2/3/4**: 0 success/empty/help/version; 1 I/O, interruption/internal failure; 2 usage; 3 nonempty zero-valid input; 4 unique-cardinality exhaustion. Code 4 must remain distinct.
- Protect stdout export schemas; diagnostics belong on stderr. Never send input records or secrets externally.
- Write and run meaningful tests for new code. Record actual results and performance evidence before claiming completion; blueprint checks do not prove product behavior.
- External actions, publishing, pushing, deletion and deployment need explicit human confirmation. Do not fabricate review evidence.
- At the end of every session or significant block, save context through `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Planned structure
`src/nginx_lens/`: cli.py, reader.py, parser.py, models.py, aggregate.py, render.py, errors.py and __init__.py. `tests/`: synthetic fixtures plus parser, reader, metrics, renderer, CLI and acceptance tests. `benchmarks/`: synthetic corpus generator, benchmark driver and measured results. `pyproject.toml`: dependencies/build/entry point. No implementation files exist yet.

## Implementation status
| Step | Deliverable | Status | Evidence required |
|---|---|---|---|
| 1 | Package skeleton and models | Not started | Install/help/package tests |
| 2 | Reader/parser | Not started | Reader/parser tests |
| 3 | Metrics and key cap | Not started | Exact aggregation/overflow tests |
| 4 | JSON/CSV | Not started | Golden export tests |
| 5 | Terminal tables | Not started | Color/control-character tests |
| 6 | CLI and error mapping | Not started | All exits 0/1/2/3/4 |
| 7 | Acceptance/performance | Not started | Suite, coverage, actual benchmark |
| 8 | Local distribution | Not started | Wheel and clean-env smoke checks |

## Review boundary and next action
The external harness runs the real Devil's Advocate in a fresh session after blueprint generation. No in-session adversarial or independent review is claimed. Do not create DEVILS_ADVOCATE_REVIEW.md in this workflow. Next action: external harness reviews the written architecture; product implementation may start only in a separately requested task. Current handoff is saved under `.itd-memory/continuity/blueprint.md`.
