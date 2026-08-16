# nginx-stream-stats Project Memory

## Context

Build a local, pip-installable Python 3.11 CLI for DevOps/SRE engineers that streams nginx combined access logs and reports top IPs, top 4xx/5xx URLs, hourly request percentages, and exact unique User-Agent share. Default output is colored terminal text; JSON and CSV support pipelines. Cash budget is $0 and delivery is one weekend.

Current phase: blueprint documentation complete; product code not started.

## Sources of Truth

1. `PRD.md` — behavior, priorities, acceptance, kill criteria.
2. `PROJECT_ARCHITECTURE.md` — CLI schemas, dataclasses, boundaries, technical decisions.
3. `IMPLEMENTATION_PLAN.md` — WIP=1 sequence and verification commands.
4. `STRATEGIC_PLAN.md` — users, alternatives, budget, roadmap, risks.
5. `.itd/` and `.itd-memory/` — Idea to Deploy execution and verification contracts.

If documents conflict, reconcile them before code. Architecture controls technical shape; PRD controls user-visible behavior.

## Non-negotiable Rules

- Python 3.11, Click, Rich, dataclasses, and pip-compatible packaging.
- One stateless streaming process; never retain complete input or raw record lists.
- No authentication, database, HTTP API, server, network dependency, cloud, Docker requirement, or Kubernetes.
- Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`.
- User-Agent share is exact; exceeding its configured cardinality cap exits 4 instead of approximating.
- Complete exit contract: 0 success, 1 operational/internal, 2 invocation, 3 data/format, 4 unique-cardinality exhaustion.
- Default rankings contain 10 entries; ties use count descending then key ascending.
- Stdout contains only the report; stderr contains warnings/errors; machine modes contain no ANSI.
- Log-derived text is untrusted data and must be escaped/encoded, never executed or treated as Rich markup.
- Update specifications before deliberately changing behavior.
- Preserve WIP=1 and attach the verification evidence required by `.itd/VERIFICATION_CONTRACT.json` before claiming implementation completion.
- Do not publish, deploy, or mutate external systems without separate authorization.
- «В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save».

## Planned Structure

```text
src/nginx_stream_stats/
  __init__.py
  cli.py
  parser.py
  aggregator.py
  models.py
  errors.py
  renderers/
tests/{fixtures,unit,integration,performance}/
```

## Step Status

| Step | Deliverable | Status |
|---:|---|---|
| 1 | Package and verification skeleton | Not started |
| 2 | Domain and error contracts | Not started |
| 3 | Streaming combined-log parser | Not started |
| 4 | IP, error URL, hourly aggregates | Not started |
| 5 | Exact User-Agent guard/share | Not started |
| 6 | Terminal, JSON, CSV renderers | Not started |
| 7 | Complete CLI and exit mapping | Not started |
| 8 | 1 GB performance/memory evidence | Not started |
| 9 | Release documentation and artifact check | Not started |

## Session Workflow

1. Confirm `.itd/SCOPE_LOCK.md` and the active unit allow the intended files.
2. Read the active step in `IMPLEMENTATION_PLAN.md` and its matching prompt in `CLAUDE_CODE_GUIDE.md`.
3. Implement only that step.
4. Run its verification commands and record evidence through Idea to Deploy state.
5. Reconcile docs/state and name the next action.
6. Save session context through `/session-save`.

## Blueprint Review Boundary

This blueprint session did not run an adversarial or independent reviewer and does not create `DEVILS_ADVOCATE_REVIEW.md`. Any later review must be recorded by the actual external review workflow.

