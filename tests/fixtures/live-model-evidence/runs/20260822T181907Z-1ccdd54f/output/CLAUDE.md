# CLAUDE.md — nginx-stream-report Project Memory

## Project Context

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams one nginx combined access log and reports:

1. top 10 client IPs;
2. top 10 request targets with 4xx/5xx statuses;
3. 24-hour request distribution as percentages;
4. exact unique User-Agent share.

Default output is colored Rich terminal text. `--json` and `--csv` are stable pipeline formats. The performance target is a 1 GB input in under 30 seconds on the documented reference laptop. The cash budget is $0 and the delivery timebox is one weekend.

## Sources of Truth

Read these before product work, in precedence order:

1. `AGENTS.md` and `.itd/` contracts — repository workflow and verification rules.
2. `PRD.md` — user-visible behavior, priorities, and acceptance criteria.
3. `PROJECT_ARCHITECTURE.md` — CLI, metric, dataflow, and failure contracts.
4. `IMPLEMENTATION_PLAN.md` — the one-at-a-time delivery sequence.
5. `CLAUDE_CODE_GUIDE.md` — bounded prompt for the active step.
6. `STRATEGIC_PLAN.md` — goals, roadmap, constraints, and release criteria.

When behavior must change, update the PRD and architecture first, then reconcile the plan and implementation. Do not let generated code silently become the specification.

## Non-Negotiable Rules

- Use Python 3.11, Click, Rich, dataclasses, src layout, and pip packaging.
- Remain a single-process, stateless, local CLI.
- Do not add authentication, a database, HTTP API, server, cloud service, Docker, or Kubernetes.
- Process input line by line; never read the entire log or retain parsed request rows.
- Keep exact meanings shared by terminal, JSON, and CSV renderers.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`.
- Exact unique User-Agent share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`.
- Send the selected report only to stdout and diagnostics only to stderr.
- Escape terminal markup in all user-derived values; never echo an entire sensitive log line in normal errors.
- Preserve WIP=1. A unit is not complete without evidence required by `.itd/VERIFICATION_CONTRACT.json` and a current revalidated adjudication receipt.
- Do not create `DEVILS_ADVOCATE_REVIEW.md`; the external harness owns that independent review.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## CLI and Exit Codes

Command: `nginx-stream-report [OPTIONS] [INPUT]`. Omitted `INPUT` or `-` means stdin. `--json` and `--csv` are mutually exclusive; `--no-color`, `--strict`, and `--max-unique-user-agents` behave as specified in `PROJECT_ARCHITECTURE.md`.

| Code | Meaning |
|---:|---|
| `0` | Successful complete report |
| `1` | Input I/O failure |
| `2` | CLI usage error |
| `3` | Parse/data failure or zero valid requests |
| `4` | Exact unique User-Agent cardinality exhaustion; no partial report |

Never omit, remap, or collapse these codes.

## Planned Source Structure

```text
pyproject.toml
src/nginx_stream_report/
  __init__.py
  __main__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  errors.py
  renderers/{__init__,terminal,json,csv}.py
tests/
  fixtures/
  perf/
  test_parser.py
  test_aggregate.py
  test_cli.py
  test_renderers.py
  test_integration.py
```

Create these files only in their corresponding active implementation step. Planning documents existing today do not authorize product code in the blueprint session.

## Working and Verification Protocol

1. Identify exactly one active step from `IMPLEMENTATION_PLAN.md` and reconcile it with `.itd/SCOPE_LOCK.md` and `.itd-memory/` state.
2. Freeze its acceptance criteria and verification command before editing product code.
3. Implement only the bounded files and behavior.
4. Run focused tests, then the applicable broader suite.
5. Freeze the exact candidate, run its declared machine oracle, and apply the repository risk-tier checker.
6. Accept completion only from a current revalidated adjudication receipt; otherwise record recovery and an explicit next action.
7. Save session context through `/session-save`.

Ignored or untracked overlays are excluded from the oracle unless explicitly declared with a bound content hash.

## Implementation Status

| Step | Scope | Status | Required evidence before completion |
|---:|---|---|---|
| 0 | Full blueprint documents | Complete for planning handoff | Six root documents present and structurally validated |
| 1 | Package and CLI skeleton | Not started | Install, CLI, and focused pytest output |
| 2 | Models and typed failures | Not started | Model and mapping tests |
| 3 | Combined-log parser | Not started | Parser tests and coverage |
| 4 | Streaming aggregation | Not started | Formula, ranking, and exhaustion tests |
| 5 | Rich terminal renderer | Not started | Terminal golden tests |
| 6 | JSON and CSV renderers | Not started | Machine-output parse/golden tests |
| 7 | End-to-end CLI | Not started | Full exit-code and integration tests |
| 8 | Performance and packaging | Not started | Suite, wheel install, benchmark, adjudication receipt |

## Current Handoff

Planning is complete; product implementation has not begun. The next authorized implementation action, when separately requested, is Step 1 only. The external harness may run the independent Devil's Advocate architecture review before implementation.
