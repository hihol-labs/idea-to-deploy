# CLAUDE.md — nginx-insights Project Memory

## Project Context

Build a local Python 3.11 CLI for DevOps/SRE users that streams nginx access logs and reports top-10 IPs, top-10 URL paths by 4xx/5xx count, a 24-hour request percentage distribution, and unique User-Agent share. Default output is Rich terminal text; `--json` and `--csv` support pipelines. The cash budget is $0 and delivery is one weekend.

Planning is complete; product implementation has not started. Read `PRD.md`, `PROJECT_ARCHITECTURE.md`, and `IMPLEMENTATION_PLAN.md` before editing source.

## Rules

1. Preserve WIP=1: only one implementation-plan step may be in progress.
2. Specifications are the durable source of truth. Change the specification before changing an established behavior contract.
3. Implement no authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
4. Keep processing local, single-process, single-pass, and stateless across runs.
5. Keep stdout for report data and stderr for diagnostics.
6. Preserve exact deterministic metrics and the full `0/1/2/3/4` exit-code contract.
7. Never replace exact results with silent approximation or sampling.
8. Run and record the verification commands for the active step before marking it complete.
9. Do not create `DEVILS_ADVOCATE_REVIEW.md`; the external harness owns adversarial review.
10. В конце каждой сессии или значимого блока работы — сохранить контекст через /session-save.

## Stack

| Concern | Choice |
|---|---|
| Runtime | Python 3.11 |
| CLI | Click |
| Terminal rendering | Rich |
| Models | dataclasses |
| Packaging | `pyproject.toml`, PEP 517, pip, `src/` layout |
| Testing | pytest + coverage plugin |
| Architecture | One local process with parser, aggregator, shared report model, and three renderers |

## Planned Structure

```text
src/nginx_insights/
  __init__.py
  __main__.py
  cli.py
  input.py
  parser.py
  models.py
  aggregate.py
  errors.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
benchmarks/
pyproject.toml
```

Do not create this structure merely to satisfy the plan; create each path only in its numbered implementation step.

## Behavioral Anchors

- Hourly percentage: `100 × hourly_request_count / total_valid_requests`.
- Error status range: 400–599 inclusive.
- URL grouping: parsed path only; omit query and fragment.
- Ranking ties: label ascending after count descending.
- User-Agent share: distinct non-null User-Agent count divided by requests with non-null User-Agent, times 100.
- Exit 4: exact cardinality ceiling exceeded; no normal report.
- Performance gate: 1 GB in under 30 seconds on the documented laptop baseline.

## Status

| Step | Description | Status | Evidence |
|---:|---|---|---|
| 1 | Package and CLI contracts | Not started | — |
| 2 | Parser and models | Not started | — |
| 3 | Streaming input | Not started | — |
| 4 | Exact aggregation | Not started | — |
| 5 | Cardinality and exit semantics | Not started | — |
| 6 | Terminal/JSON/CSV renderers | Not started | — |
| 7 | End-to-end CLI | Not started | — |
| 8 | Performance and quality gates | Not started | — |
| 9 | Packaging and release readiness | Not started | — |

## Next Action

Start only Step 1 using the corresponding prompt in `CLAUDE_CODE_GUIDE.md`. Do not claim implementation completion because this blueprint session produced documentation only.
