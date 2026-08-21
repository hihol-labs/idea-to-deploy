# Project Instructions: Nginx Stream Analytics CLI

## Product Context

This repository is for a local, open-source Python 3.11 CLI that streams nginx combined-format access logs and reports top-10 IPs, top-10 URLs by 4xx/5xx errors, hourly request distribution, and exact unique User-Agent share. Default output is Rich terminal text; `--json` and `--csv` serve pipelines. Delivery budget is $0 and the MVP window is one weekend.

The durable product source of truth is, in precedence order for behavior: `PRD.md`, `PROJECT_ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, and `STRATEGIC_PLAN.md`. Change the specification before intentionally changing behavior.

## Non-Negotiable Architecture

- One local Python process; one incremental pass over a file or stdin.
- Python 3.11, Click, Rich, dataclasses, pip installation.
- No authentication, database, HTTP API, server, network dependency, cloud service, Docker, or Kubernetes.
- Never read the entire log into memory or persist log-derived application state.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent share is exact. If exact-cardinality capacity is exceeded, abort without a partial report.
- Complete exit contract: `0` success, `1` unexpected internal error, `2` usage/options/unreadable input, `3` no valid records, `4` unique-cardinality exhaustion. Never omit or remap code `4`.

## Planned Structure

```text
src/nginx_stream_analytics/  # CLI, models, parser, aggregation, renderers
tests/                       # unit, CLI, golden, and opt-in performance tests
scripts/                     # reproducible benchmark command
pyproject.toml               # packaging, dependencies, console entry point
```

Do not create product code until implementation is explicitly requested. During implementation, create only files required by the active step in `IMPLEMENTATION_PLAN.md`.

## Engineering Rules

1. Keep WIP at one implementation step.
2. Preserve deterministic ordering: count descending, key ascending for ties.
3. Keep machine output clean: result on stdout; diagnostics on stderr; no ANSI in JSON/CSV.
4. Treat log bytes and decoded fields as untrusted data. Never invoke a shell with them.
5. Write tests with behavior, including malformed/empty inputs and exact cardinality boundaries.
6. Profile before optimizing. The performance claim requires the complete 1 GB benchmark on a documented reference laptop and exact candidate.
7. Do not silently broaden supported nginx formats or redefine metrics.
8. Do not start P1/P2 features before P0 release gates pass.

## Implementation Status

| Step | Deliverable | Status |
|---:|---|---|
| 1 | Package and test foundation | Not started |
| 2 | Domain, errors, and fixtures | Not started |
| 3 | Combined-log parser | Not started |
| 4 | Streaming aggregation | Not started |
| 5 | JSON and CSV renderers | Not started |
| 6 | Rich terminal renderer | Not started |
| 7 | CLI integration and exit contract | Not started |
| 8 | Performance and release gate | Not started |

Update only the active row when runtime/static evidence named by the project verification contract exists. Narration alone is not completion evidence.

## Session Continuity

At the end of every session or meaningful block of work, save context through `/session-save`.

Record the active step, files changed, commands actually run and outcomes, current blockers/risks, and the next action. Leave the repository handoff-ready.

