# Project Memory: Nginx Stream Analytics CLI

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams conventional nginx combined access logs from a path or stdin and reports top 10 IPs, top 10 URLs across 4xx/5xx responses, 24 hourly percentage buckets, and exact unique User-Agent share. Default output is colored Rich terminal text; JSON and CSV serve pipelines. Cash budget is $0 and the planned delivery window is one weekend.

This file is implementation guidance, not evidence that product code exists. The repository is currently at blueprint completion only.

## Source-of-Truth Order

1. User request and project `AGENTS.md`.
2. `.itd/` contracts and `.itd-memory/` active state.
3. `PRD.md` for observable behavior and acceptance criteria.
4. `PROJECT_ARCHITECTURE.md` for technical and CLI contracts.
5. `IMPLEMENTATION_PLAN.md` for dependency order and verification commands.
6. `CLAUDE_CODE_GUIDE.md` for bounded execution prompts.
7. `STRATEGIC_PLAN.md` for scope, priorities, KPIs, budget, and risks.

When behavior changes, update the specification before changing code.

## Non-Negotiable Product Rules

- Python 3.11, Click, Rich, dataclasses, pip-installable package.
- Single local process and one-pass streaming.
- No authentication, database, HTTP API, server, cloud, Docker runtime, or Kubernetes.
- No full-file materialization and no remote telemetry or upload.
- All three formats consume the same immutable `Summary`.
- Deterministic top-10 ties: count descending, key ascending.
- Hourly distribution uses `100 × hourly_request_count / total_valid_requests`; zero valid requests produces 24 zero percentages.
- Exact User-Agent cardinality has a hard limit; never silently substitute an approximation.
- The complete exit-code contract is `0` success, `1` input/runtime I/O failure, `2` CLI usage error, `3` strict parse failure, and `4` unique-cardinality exhaustion. Codes 1–4 emit no partial report; code 4 is never omitted or remapped.
- Treat input fields as untrusted; never interpret them as shell, code, paths, or Rich markup.
- The performance claim requires a current 1 GiB run under 30 seconds on a documented laptop profile.

## Engineering Rules

- Preserve WIP=1: execute one `IMPLEMENTATION_PLAN.md` step at a time.
- Before changing scope, update `.itd/SCOPE_LOCK.md` and reconcile the active `.itd-memory/` unit.
- Use specific tests for parser edge cases, cross-renderer agreement, failure outputs, exact cardinality, and deterministic ordering.
- Keep the parser/aggregator independent of Click and Rich; renderers never compute metrics.
- Do not weaken or delete tests and quality gates to obtain a pass.
- Preserve unrelated worktree changes and avoid destructive Git commands.
- Freeze the exact candidate and use the repository Verification Loop before accepting implementation work.
- The external Devil's Advocate review is a separate session. Do not fabricate it, run an inline substitute, or create `DEVILS_ADVOCATE_REVIEW.md` under this blueprint task.
- At the end of every session or significant block of work, save context through `/session-save`. Required workflow wording: «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Planned Structure

```text
src/nginx_stream_report/
  __init__.py
  cli.py
  models.py
  errors.py
  parser.py
  aggregate.py
  render_text.py
  render_json.py
  render_csv.py
tests/
  fixtures/
  performance/
  test_models.py
  test_parser.py
  test_aggregate.py
  test_renderers.py
  test_cli.py
  test_integration.py
  test_performance.py
docs/PERFORMANCE.md
pyproject.toml
```

These paths are planned by the blueprint and do not yet authorize or imply implementation.

## Step Status

| Step | Deliverable | Status |
|---:|---|---|
| Blueprint | Strategy, architecture, PRD, plan, README, guides | Complete in documentation scope |
| 1 | Package and CLI skeleton | Not started |
| 2 | Domain models and error taxonomy | Not started |
| 3 | Combined-log parser and fixtures | Not started |
| 4 | Streaming aggregations and cardinality guard | Not started |
| 5 | JSON and CSV renderers | Not started |
| 6 | Rich terminal renderer | Not started |
| 7 | End-to-end failures and pipe semantics | Not started |
| 8 | Performance and quality gate | Not started |
| 9 | Packaging and release candidate | Not started |

## Next Action

Begin Step 1 only after the active implementation unit is scoped in Idea to Deploy. Use Prompt 1 in `CLAUDE_CODE_GUIDE.md`; do not begin Step 2 until Step 1 has current verification evidence and state reconciliation.
