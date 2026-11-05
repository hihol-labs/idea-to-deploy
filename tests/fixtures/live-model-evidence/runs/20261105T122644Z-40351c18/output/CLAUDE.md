# Nginx Lens Project Memory

## Context and Sources

Build a local nginx combined-log analytics CLI for DevOps/SRE engineers. This checkout currently contains the blueprint, not product implementation. Product decisions and priorities were pre-approved for a non-interactive blueprint run.

Read [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md), [PRD.md](PRD.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) and [README.md](README.md). The PRD and acceptance criteria are durable specifications; architecture defines detailed technical behavior. Resolve contradictions in the documents before coding.

## Rules

- WIP=1. Work through the numbered plan and attach real verification evidence to status changes.
- Python 3.11, Click, Rich, dataclasses and pip packaging; one process, no auth, database, HTTP API, server, cloud or Kubernetes.
- Read bounded lines, aggregate in memory and discard state at exit. No raw-record retention, telemetry or network calls.
- Exact unique keys are quota-limited. Defaults are 250000 shared entries and 67108864 UTF-8 key bytes. Exceeding either is code 4 with no report; never approximate silently.
- Preserve exit codes 0/1/2/3/4: 0 success/empty/help/version, 1 malformed-line partial report, 2 usage, 3 I/O/resource/interruption, 4 unique-cardinality exhaustion. Fatal 3/4 override pending 1.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`, with 24 UTC hours across dates. UA diversity is 100 times distinct nonmissing agents over all valid requests.
- Tests accompany new code. Run the relevant suite before a commit and record failures faithfully. Planned commands in the blueprint are not evidence of execution.
- All irreversible or external actions, including publishing/push/PR/deploy, need explicit human confirmation. Keep secrets and raw log records out of outputs and external systems.
- Keep project instructions centralized here; preserve existing AGENTS.md harness contracts.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Planned Structure

`src/nginx_lens/{cli,reader,parser,models,aggregate,render}.py`, `tests/`, `benchmarks/`, `pyproject.toml`, `LICENSE`. These are planned files, not claims of implementation. No database tables, API routes, Docker or environment secrets are required.

## Step Status

| Step | Work | Status |
|---|---|---|
| 1 | Package, dataclasses and test contracts | Not started |
| 2 | Bounded reader and combined parser | Not started |
| 3 | Exact rankings and quotas | Not started |
| 4 | Percentages and component probe | Not started |
| 5 | CLI and terminal rendering | Not started |
| 6 | JSON and CSV | Not started |
| 7 | End-to-end validation and performance | Not started |
| 8 | Wheel and local handoff | Not started |

## Current Handoff

Scope is documentation only. No product tests, benchmarks, independent review or release have run. The external harness owns adversarial architecture review after this session; do not fabricate its artifact or verdict. Next action is external blueprint review; implementation starts at Step 1 in a later authorized task. Canonical continuity is `.itd-memory/continuity/nginx-lens-blueprint.md`. No verified/adjudicated transition is implied by the presence of these documents.
