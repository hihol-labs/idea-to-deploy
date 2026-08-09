# Project Memory: nginx-stream-report

## Context

This repository specifies a local open-source Python 3.11 CLI for DevOps/SRE engineers. It streams standard nginx combined access logs and reports top-10 IPs, top-10 4xx/5xx URLs, 24 hourly request percentages, and exact unique User-Agent share. Default output is colored terminal text; JSON and CSV support pipelines. Cash budget is $0 and MVP delivery is one weekend.

## Source of Truth

1. `PRD.md` defines observable behavior and acceptance.
2. `PROJECT_ARCHITECTURE.md` defines interfaces, schemas, module boundaries, and decisions.
3. `IMPLEMENTATION_PLAN.md` defines dependency order and verification.
4. `STRATEGIC_PLAN.md` defines scope, priority, risks, and release goals.
5. `CLAUDE_CODE_GUIDE.md` supplies bounded execution prompts but cannot override the specs.

Change the specification before changing behavior. Never represent unimplemented P1/P2 work as shipped.

## Non-Negotiable Rules

- Python 3.11, Click, Rich, dataclasses, src layout, and pip installation.
- Single-process, stateless, one-pass processing; do not store raw lines or parsed record history.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Keep stdout machine-clean; send diagnostics to stderr.
- Hourly percentages use exactly `100 × hourly_request_count / total_valid_requests`.
- Preserve deterministic count-descending/key-ascending rankings.
- Preserve the complete exit mapping: `0` success, `1` internal/output failure, `2` usage failure, `3` input failure, `4` unique-cardinality exhaustion.
- Never omit/remap exit 4 or silently approximate exact User-Agent cardinality.
- Treat log strings as untrusted and escape them for Rich, JSON, and CSV contexts.
- Do not claim the 1 GB/30-second target without recorded benchmark evidence.
- In the final part of every session or meaningful block of work, save context via `/session-save`.

## Intended Structure

```text
src/nginx_stream_report/
  __init__.py
  cli.py
  errors.py
  models.py
  parser.py
  aggregate.py
  renderers/{__init__,text,json,csv}.py
tests/
  fixtures/
  golden/
  test_{parser,aggregate,text_renderer,json_renderer,csv_renderer,cli_contract,cli_integration,package}.py
bench/
  generate_log.py
  README.md
pyproject.toml
```

Do not create this product structure during blueprint work; it is the future implementation layout.

## Working Method

- Keep work-in-progress to one implementation-plan step.
- Read the named context sections before editing.
- Add or update tests with each behavior.
- Run the step-specific verification command; record actual evidence and failures.
- Preserve domain/rendering separation and convert domain exceptions at the CLI boundary.
- Stop and reconcile the PRD/architecture if implementation reveals a contract ambiguity.

## Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 0 | Full blueprint documents | Complete | Document presence and consistency validation |
| 1 | Package and CLI contract | Not started | Install, help, CLI contract tests |
| 2 | Combined-log parser | Not started | Parser unit tests and coverage |
| 3 | Aggregation/cardinality | Not started | Metric, determinism, cap-boundary tests |
| 4 | Terminal renderer | Not started | Golden and TTY/color tests |
| 5 | JSON renderer | Not started | Golden/schema/stdout tests |
| 6 | CSV renderer | Not started | Golden/escaping/formula tests |
| 7 | Streaming I/O and failures | Not started | Integration tests for `0/1/2/3/4` |
| 8 | Benchmark and package | Not started | Full suite, wheel check, measured 1 GB benchmark |

## Current Handoff

Blueprint planning is complete; no product code is implemented. The next authorized action is Step 1 of `IMPLEMENTATION_PLAN.md`. Reconfirm the exact staged candidate and verification contract before accepting implementation work.
