# Nginx Log Lens — project memory

## Context
Blueprint-only project for a local DevOps/SRE nginx combined-access-log CLI. Product code has not been implemented. Python 3.11, Click, Rich, dataclasses, pip installation; one-weekend, $0, open source. Approved single-process streaming design; no authentication, database, HTTP API, server, cloud or Kubernetes.

## Source of truth
Read [PRD.md](PRD.md) and [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) before implementation. [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) records MoSCoW/RICE and release gates. Follow [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) in order using [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md). [README.md](README.md) describes intended user commands. Change specifications before behavior. Keep agent instructions here rather than distributing new instruction files.

## Rules
- WIP=1. Implement only the active approved step and add meaningful tests; run applicable tests before a commit. Do not claim measured performance or completed tests without session evidence.
- Keep exact bounded counters, deterministic ranking and schemas. Hourly distribution is `100 × hourly_request_count / total_valid_requests`; UA share is a percentage against all valid requests.
- Preserve exit codes **0/1/2/3/4**: 0 success/help/version, 1 I/O/runtime failure, 2 usage error, 3 no valid requests, 4 unique-cardinality exhaustion. Never omit or remap 4.
- Treat logs as untrusted data. No executing log fields, raw-record diagnostics, telemetry, secrets or uploads. Text rendering must escape markup/control characters.
- No persistent processing state; cap each unique dimension and stop before exceeding it. No silent approximation or truncation of the report.
- External publishing, push, deployment, deletion or irreversible actions require explicit human authorization. No such action is part of this blueprint.
- The external harness runs adversarial review separately; do not invent a review verdict or write its artifact in this session.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Planned structure
`src/nginx_log_lens/{cli,reader,parser,models,aggregate,render}.py`; `pyproject.toml`; `tests/`; `benchmarks/`. These are future paths. No application modules exist yet.

## Step status
| Step | Work | Status |
|---|---|---|
| 1 | Package and CLI skeleton | Pending |
| 2 | Bounded reader/parser | Pending |
| 3 | Exact IP/error rankings | Pending |
| 4 | Hours and UAs | Pending |
| 5 | Text/JSON/CSV | Pending |
| 6 | End-to-end exit contract | Pending |
| 7 | Performance qualification | Pending |
| 8 | Local package/release candidate | Pending |

## Handoff
Blueprint documents are the present deliverable. Runtime tests, throughput measurement, implementation review and publication have not occurred. Next product action after the externally managed architecture review is implementation step 1, in a separately started implementation phase. Session continuity lives in `.itd-memory/continuity/nginx-blueprint.md`.
