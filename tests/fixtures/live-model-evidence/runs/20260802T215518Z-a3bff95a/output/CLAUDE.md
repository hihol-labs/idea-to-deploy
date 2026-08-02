# nginx-streamtop Project Memory

## Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams
nginx combined access logs and reports top 10 IPs, top 10 URLs by 4xx/5xx
count, hourly request distribution, and unique User-Agent share. Default output
is Rich terminal text; `--json` and `--csv` are public pipeline formats.

Current phase: blueprint complete, product implementation not started.

## Source of Truth

1. `PRD.md` defines behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` defines architecture and the exact CLI contract.
3. `IMPLEMENTATION_PLAN.md` defines dependency order and verification commands.
4. `STRATEGIC_PLAN.md` defines priorities, scope, KPIs, risks, and budget.
5. `.itd/` and `.itd-memory/` define active execution and verification policy.

When behavior changes, update the specification and acceptance criteria before
changing generated/implementation code.

## Non-Negotiable Decisions

- Local, stateless, single-process streaming pipeline.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.
- Python 3.11, Click, Rich, dataclasses; pip-installable.
- Exact default metrics with deterministic ordering.
- 1 GB under 30 seconds only when proven on documented reference hardware and
  fixture; never infer this from file size or code inspection.
- Raw input is never retained as a whole and no telemetry/cache/network call is
  allowed.
- JSON/CSV stdout contains report data only; diagnostics use stderr.
- WIP=1: only one implementation-plan step may be active.

## Engineering Rules

- Read project `AGENTS.md` and the smallest applicable Idea to Deploy skill
  before non-trivial work.
- Preserve scope in `.itd/SCOPE_LOCK.md` and reconcile the active unit before
  broadening it.
- Use Python 3.11-compatible syntax and typed dataclass boundaries.
- Treat log lines, URLs, IPs, and User-Agents as untrusted data.
- Keep parser, aggregation, and rendering separate; renderers consume `Report`,
  never raw lines.
- Add tests before or with behavior; include malformed, boundary, injection,
  tie, empty, and machine-format cases.
- Profile before performance optimization. Never trade metric correctness for a
  benchmark without a spec change.
- Freeze and verify the exact candidate using the current machine oracle and
  risk-tier adjudication receipt before accepting a step.
- Do not publish packages, create external resources, or send data without
  explicit authorization.
- В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save

## Target Structure

```text
src/nginx_streamtop/
  cli.py
  models.py
  parser.py
  aggregate.py
  inputs.py
  renderers/{terminal,json,csv}.py
tests/
scripts/generate_benchmark_log.py
docs/PERFORMANCE.md
```

## Step Status

| Step | Deliverable | Status |
|---:|---|---|
| 1 | Package and CLI contract | Not started |
| 2 | Models and fixtures | Not started |
| 3 | Streaming inputs | Not started |
| 4 | Combined-format parser | Not started |
| 5 | Aggregation and early performance gate | Not started |
| 6 | Rich terminal output | Not started |
| 7 | JSON output | Not started |
| 8 | CSV output | Not started |
| 9 | 1 GB performance/resource evidence | Not started |
| 10 | Release verification | Not started |

## Current Handoff

- Active implementation step: none.
- Last completed lifecycle work: `$idea-to-deploy:blueprint --full` planning.
- Product code: intentionally absent.
- Next action: establish an authorized implementation unit for Step 1 and its
  executable verification contract.

