# StreamSift Project Instructions

## Project Context

StreamSift is a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams one nginx access log from a file or stdin and reports top 10 IPs, top 10 request targets returning 4xx/5xx, 24 hourly request-distribution percentages, and the share/count of unique nonempty User-Agent values. Default output is colored terminal text; `--json` and `--csv` are stable pipeline modes.

The approved boundary is a one-weekend, $0, pip-installable, single-process tool. There is no authentication, database, HTTP API, server, cloud, Docker, Kubernetes, telemetry, or persistence.

## Source-of-Truth Order

1. `PRD.md` — user-visible behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — CLI, schemas, components, state, and decisions.
3. `IMPLEMENTATION_PLAN.md` — WIP=1 delivery order and verification.
4. `CLAUDE_CODE_GUIDE.md` — bounded prompts for each future implementation step.
5. `STRATEGIC_PLAN.md` — goals, priorities, risks, budget, release gates.

If behavior must change, update the PRD and architecture first, then revise the plan and implementation. Do not let generated code silently become the specification.

## Non-Negotiable Product Contracts

- Python 3.11, Click, Rich, and dataclasses; install through pip.
- One local process and one traversal of input; never retain raw log lines or a full parsed-record list.
- Top IP count includes every valid request.
- Error target count includes statuses 400–599 only; query strings remain part of the target.
- Emit all 24 hour buckets. Percentage is exactly `100 × hourly_request_count / total_valid_requests`, rounded only when serialized.
- Unique User-Agent share uses distinct nonempty values over total valid requests; `-` is missing.
- Rankings are count descending and key ascending for deterministic ties, with at most 10 rows.
- Default Rich output may use color only on a TTY unless explicitly overridden. JSON/CSV never contain ANSI.
- Results go to stdout; warnings/errors go to stderr. No failed pipeline invocation may masquerade as complete success.
- Treat log fields as untrusted data: never evaluate or shell-interpolate them; escape display controls; use standard JSON/CSV serializers.
- Enforce cardinality before inserting a new distinct aggregate key.

## Complete Exit-Code Contract

Every implementation and test must preserve all five codes:

| Code | Meaning |
|---:|---|
| `0` | Successful analysis with complete output |
| `1` | Input/output runtime failure |
| `2` | CLI usage or option-validation error |
| `3` | Log-data failure: strict malformed record or no valid requests |
| `4` | Unique-cardinality exhaustion |

Code `4` is reserved for unique-cardinality exhaustion and must never be omitted or remapped.

## Planned Stack

| Concern | Technology |
|---|---|
| Runtime | CPython 3.11 |
| Command interface | Click |
| Terminal presentation | Rich |
| Models | Standard-library dataclasses and type hints |
| Aggregation | `collections.Counter`, fixed hour list, bounded set/maps |
| JSON/CSV | Standard library serializers |
| Packaging | `pyproject.toml`, wheel/sdist, pip |
| Tests | pytest, Click test runner, coverage, subprocess release checks |

Do not introduce a database, web framework, task queue, remote service, or approximate cardinality algorithm without an approved spec/architecture change.

## Planned Repository Structure

```text
pyproject.toml
src/streamsift/
  __init__.py
  __main__.py
  aggregate.py
  cli.py
  errors.py
  model.py
  parser.py
  render.py
tests/
  fixtures/
  test_aggregate.py
  test_cli.py
  test_parser.py
  test_performance.py
STRATEGIC_PLAN.md
PROJECT_ARCHITECTURE.md
PRD.md
IMPLEMENTATION_PLAN.md
CLAUDE_CODE_GUIDE.md
CLAUDE.md
```

This is a planned structure, not authorization to create all files in one step.

## Working Rules

- Preserve WIP=1: select exactly one step from `IMPLEMENTATION_PLAN.md`.
- Before editing, state scope, read relevant specs/tests, and inspect existing work.
- Add acceptance tests with the behavior and run the step's commands against the exact candidate.
- Do not weaken tests, alter exit meanings, or introduce mock output to make a gate pass.
- Keep ignored/untracked inputs out of verification unless explicitly declared and content-bound.
- On a failing gate, record recovery and next action; never label it passed.
- Keep user documentation and schemas synchronized with intentional behavior changes.
- At the end of each session or meaningful block of work, save context with `/session-save`.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Implementation Status

| Step | Deliverable | Status | Required evidence |
|---:|---|---|---|
| 1 | Package, contracts, CLI shell | Not started | Install/help and focused CLI tests |
| 2 | Parser and input adapters | Not started | Parser and strict/input tests |
| 3 | Aggregation and cardinality guard | Not started | Metric, formula, invariant, exit `4` tests |
| 4 | Rich terminal renderer | Not started | Golden, escaping, and TTY tests |
| 5 | JSON/CSV renderers | Not started | Schema/golden and stream-separation tests |
| 6 | End-to-end contract matrix | Not started | Full suite, coverage, all `0/1/2/3/4` subprocess paths |
| 7 | Performance/memory gate | Not started | Recorded 1 GB timing and peak-memory evidence |
| 8 | Packaging/release rehearsal | Not started | Build/install/smoke evidence from clean Python 3.11 |

Only change a status after its current verification evidence exists. The next action is Step 1; product code has not been implemented by the blueprint workflow.

## Session Handoff

Record the active step, exact files changed, commands and results, unresolved failures/risks, contract changes, and next action. A prose `PASSED` without current evidence is not completion.

