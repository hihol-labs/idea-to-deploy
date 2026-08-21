# Project Memory: Nginx Stream Analyzer

## Context

This repository is planned as a local, open-source Python 3.11 CLI for DevOps/SRE engineers. It streams one nginx combined access log from a file or stdin and reports top-10 IPs, top-10 URLs with 4xx/5xx statuses, hourly request percentages, and unique User-Agent share. Default output uses Rich; `--json` and `--csv` are pipeline contracts.

The source-of-truth documents are `PRD.md`, `PROJECT_ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, and `STRATEGIC_PLAN.md`. Change the specification before changing behavior.

## Non-Negotiable Decisions

- Python 3.11, Click, Rich, dataclasses, pip installation.
- One local process and one streaming pass; no complete-file buffering.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.
- $0 cash budget and one-weekend MVP.
- Target: 1 GB in under 30 seconds on a documented reference laptop.
- Hourly percentage formula: `100 × hourly_request_count / total_valid_requests`.
- Exit codes: `0` success; `1` strict malformed-log/invariant failure; `2` usage error; `3` I/O error; `4` unique-cardinality exhaustion.
- Exact results are required within cardinality limits; never silently approximate.

## Planned Structure

```text
pyproject.toml
src/nginx_stream_analyzer/
  __init__.py
  cli.py
  errors.py
  models.py
  parser.py
  aggregator.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  golden/
scripts/
docs/BENCHMARK.md
```

This structure is planned, not currently implemented.

## Engineering Rules

- Preserve WIP=1 and follow the active `.itd/` and `.itd-memory/` contracts.
- Implement one numbered step from `IMPLEMENTATION_PLAN.md` at a time.
- Keep parsing, aggregation, and rendering separate; renderers consume only final report models.
- Treat log content as untrusted data; escape terminal markup and use standard JSON/CSV encoders.
- Keep diagnostics on stderr and machine reports on stdout.
- Add or update acceptance tests with any contract change.
- Profile before performance optimization and record the benchmark environment.
- Do not claim completion from narration or a standalone passing test; use the exact-candidate verification route required by `.itd/VERIFICATION_CONTRACT.json`.
- At the end of every session or meaningful block of work, save context via `/session-save`.

## Status

| Step | Description | Status |
|---:|---|---|
| 0 | Full blueprint documents | Complete |
| 1 | Package and CLI contract | Not started |
| 2 | Models and combined-log parser | Not started |
| 3 | Streaming aggregation | Not started |
| 4 | I/O, diagnostics, exit mapping | Not started |
| 5 | Rich terminal renderer | Not started |
| 6 | JSON and CSV renderers | Not started |
| 7 | QA and packaging | Not started |
| 8 | Performance gate and release handoff | Not started |

## Next Action

Begin Step 1 using the matching prompt in `CLAUDE_CODE_GUIDE.md`. Do not implement later steps concurrently.
