# Project Memory: Nginx Stream Insights

## Project Context

Nginx Stream Insights is an open-source, local Python 3.11 CLI for DevOps and SRE engineers. It streams nginx combined access logs from files or stdin and produces:

1. top 10 client IPs by request count;
2. top 10 request URLs by combined 4xx/5xx count;
3. all 24 hourly request counts and percentages;
4. unique User-Agent count and share of total valid requests.

Default output is colored Rich text when appropriate. `--json` and `--csv` provide stable pipeline output. The target is a representative 1 GB log in under 30 seconds on a documented laptop, with a $0 budget and one-weekend MVP.

## Source-of-Truth Order

1. `AGENTS.md` and `.itd/` project/verification contracts.
2. `PROJECT_ARCHITECTURE.md` for technical and CLI decisions.
3. `PRD.md` for user-visible behavior and acceptance criteria.
4. `IMPLEMENTATION_PLAN.md` for sequencing and verification.
5. `STRATEGIC_PLAN.md` for priorities, constraints, risks, and Definition of Done.
6. `CLAUDE_CODE_GUIDE.md` for reusable step prompts.

When behavior changes, update the specification first and then the implementation. Do not let generated code silently become the source of truth.

## Non-Negotiable Decisions

- Use Python 3.11, Click, Rich, dataclasses, and pip packaging.
- Use one process and one streaming pass. Retain counts/distinct keys, never raw records.
- **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- No authentication, server, cloud, Docker requirement, Kubernetes, telemetry, or network calls.
- Top-list size is exactly 10; ties use count descending then key ascending.
- Error URLs include status 400–599 and preserve targets exactly as logged, including queries.
- Hour buckets use the wall-clock hour as logged, without offset normalization.
- Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share is `100 × unique_user_agent_count / total_valid_requests`.
- JSON/CSV never contain ANSI; stdout is report data and stderr is diagnostics.
- `--max-unique` defaults to 1,000,000 per distinct dimension and never silently approximates or truncates.

## Complete Exit-Code Contract

| Code | Meaning |
|---:|---|
| `0` | Successful report, help, or version |
| `1` | Unexpected runtime or output failure |
| `2` | CLI usage/configuration error |
| `3` | Input/read/decode/data failure, including zero valid records |
| `4` | Unique-cardinality exhaustion in IP, error-URL, or User-Agent state |

Never omit or remap code 4. Tests, wrappers, docs, and future implementation must preserve the complete `0/1/2/3/4` contract.

## Intended Repository Structure

```text
pyproject.toml
src/nginx_insight/
  __init__.py
  cli.py
  models.py
  errors.py
  input.py
  parser.py
  aggregate.py
  render_text.py
  render_json.py
  render_csv.py
tests/
  fixtures/
  test_cli_contract.py
  test_input.py
  test_parser.py
  test_aggregate.py
  test_render_text.py
  test_render_json.py
  test_render_csv.py
  test_cli_integration.py
  test_end_to_end.py
benchmarks/
  generate_log.py
  README.md
```

This is the planned structure, not evidence that implementation files exist.

## Engineering Rules

- Preserve Idea to Deploy WIP=1 and reconcile the active unit before editing.
- Keep each change inside `.itd/SCOPE_LOCK.md`; update scope explicitly before expanding it.
- Treat log fields as hostile data. Never evaluate them, invoke a shell, follow a URL, or render raw Rich markup/control characters.
- Keep parsing, aggregation, and rendering separate. Renderers receive the finalized report and do no business calculations.
- Use buffered iteration; never load the whole input or retain raw lines.
- Prefer standard JSON and CSV encoders and deterministic golden fixtures.
- Do not hide performance or cardinality failure with sampling or approximation.
- Do not claim completion from prose or a standalone passing message. Freeze the exact candidate, run the contracted machine oracle, apply the risk-tier checker, and require a current revalidated adjudication receipt.
- End every session handoff-ready with tests recorded, state reconciled, and one explicit next action.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Verification Expectations

- Unit tests cover parser grammar, exact aggregations, percentage calculations, tie ordering, encoding, output escaping, and boundary behavior.
- CLI integration tests exercise file/stdin paths, JSON/CSV exclusion, stdout/stderr separation, and every exit code `0/1/2/3/4`.
- Overall line coverage is at least 90%; parser, aggregation, and renderers meet the tighter thresholds in the plan.
- A clean Python 3.11 environment installs and invokes the built wheel.
- Performance evidence declares fixture, cardinality, interpreter, hardware, command, elapsed time, and peak RSS.
- Acceptance follows `.itd/VERIFICATION_CONTRACT.json`, not narration.

## Implementation Status

| Step | Scope | Status | Acceptance evidence | Next action |
|---:|---|---|---|---|
| 1 | Package skeleton and gates | Not started | None | Adopt Step 1 as the sole active unit |
| 2 | Models, errors, fixtures | Blocked by Step 1 | None | Wait for Step 1 acceptance |
| 3 | Streaming input and parser | Blocked by Step 2 | None | Wait for Step 2 acceptance |
| 4 | Aggregation/cardinality | Blocked by Step 3 | None | Wait for Step 3 acceptance |
| 5 | Rich text renderer | Blocked by Step 4 | None | Wait for Step 4 acceptance |
| 6 | JSON/CSV renderers | Blocked by Step 4 | None | Wait for Step 4 acceptance |
| 7 | CLI integration | Blocked by Steps 5–6 | None | Wait for renderer acceptance |
| 8 | Quality/performance/release | Blocked by Step 7 | None | Wait for integration acceptance |

## Current Handoff

Blueprint documentation is the only completed work. No product code has been implemented. The next authorized implementation action, when requested, is to adopt only Step 1 from `IMPLEMENTATION_PLAN.md`, align `.itd/SCOPE_LOCK.md` and `.itd-memory` state, and establish verification evidence before moving to Step 2.
