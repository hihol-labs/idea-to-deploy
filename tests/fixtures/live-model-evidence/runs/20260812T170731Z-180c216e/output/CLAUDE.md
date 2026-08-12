# Project Instructions: Nginx Stream Insights

## Context

Build a local Python 3.11 CLI that streams nginx combined access logs and reports top 10 IPs, top 10 4xx/5xx URLs, hourly request percentages, and unique User-Agent share. Default output is Rich terminal text; JSON and CSV are pipeline contracts. The target is a representative 1 GB in under 30 seconds on a documented laptop.

This file governs implementation sessions. `PRD.md` defines behavior, `PROJECT_ARCHITECTURE.md` defines technical/public interfaces, `IMPLEMENTATION_PLAN.md` defines order and evidence, and `CLAUDE_CODE_GUIDE.md` supplies step prompts. If they conflict, reconcile the specifications before writing code; architecture is the technical source of truth.

## Rules

1. Keep WIP=1 and implement only the active plan step.
2. Do not add a database, persistence, HTTP API, authentication, server, cloud, Kubernetes, or telemetry.
3. Process input once and never accumulate raw lines or parsed request records.
4. Use Python 3.11, Click, Rich, dataclasses, and standard pip packaging.
5. Compute hourly distribution with `100 × hourly_request_count / total_valid_requests`.
6. Preserve public exits exactly: `0` success, `1` internal/runtime failure, `2` CLI usage error, `3` input/data error, `4` unique-cardinality exhaustion. Never omit or remap 4.
7. Keep renderer logic separate from parsing and aggregation; structured stdout contains no diagnostics or color.
8. Use synthetic log fixtures; do not commit production logs or sensitive values.
9. Record actual test/build/benchmark evidence. Do not infer that unrun commands pass.
10. Update the specification before changing public behavior or schemas.
11. At the end of every session or meaningful work block, save context through `/session-save`.

## Planned Structure

```text
pyproject.toml
src/nginx_stream_insights/
  __init__.py
  __main__.py
  cli.py
  models.py
  parser.py
  aggregate.py
  errors.py
  renderers/
    __init__.py
    terminal.py
    json.py
    csv.py
tests/
  fixtures/
  expected/
  test_contract.py
  test_packaging.py
  test_parser.py
  test_aggregate.py
  test_input.py
  test_terminal_renderer.py
  test_json_renderer.py
  test_csv_renderer.py
  test_cli.py
benchmarks/
  generate_log.py
  run.py
  README.md
```

## Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 0 | Full blueprint documents | Complete | Document validation only; no product code |
| 1 | Fixtures and contracts | Not started | Contract test collection/goldens reviewed |
| 2 | Package skeleton | Not started | Build and packaging smoke tests |
| 3 | Models and parser | Not started | Parser tests and lint |
| 4 | Streaming aggregation | Not started | Aggregate tests |
| 5 | Input/error boundary | Not started | Input and exit-code tests |
| 6 | Rich renderer | Not started | Terminal golden/color tests |
| 7 | JSON renderer | Not started | JSON golden and parse check |
| 8 | CSV renderer | Not started | CSV golden and parse check |
| 9 | End-to-end quality | Not started | Lint, coverage, build, clean install |
| 10 | Performance/release | Not started | Recorded 1 GB timing and peak RSS |

## Current Next Action

Begin Step 1 from `IMPLEMENTATION_PLAN.md`; do not start package/product implementation until its public contracts and synthetic fixtures are reviewed.
