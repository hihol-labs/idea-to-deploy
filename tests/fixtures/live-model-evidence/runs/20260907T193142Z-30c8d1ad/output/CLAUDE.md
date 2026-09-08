# Nginx Stream Analytics CLI — Project Memory

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps/SRE engineers that streams nginx Combined Log Format and reports top-10 client IPs, top-10 URLs with 4xx/5xx responses, hourly request distribution, and unique User-Agent share. Default output is Rich terminal text; JSON and CSV are pipeline formats. Budget is $0 and delivery is one weekend.

This file is implementation memory, not a substitute for the specifications. Read `PRD.md`, `PROJECT_ARCHITECTURE.md`, and `IMPLEMENTATION_PLAN.md` before changing behavior.

## Non-negotiable Decisions

- Local single-process CLI only; no authentication, database, HTTP API, server, cloud, or Kubernetes.
- Stateless one-pass processing; do not retain raw log records.
- Runtime stack: Python 3.11, Click, Rich, dataclasses; distribute through pip.
- Exact results up to an explicit distinct-key ceiling; never silently approximate or emit a partial successful report.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests` and is 0.0 for empty valid input.
- Deterministic top lists sort by count descending, then key ascending.
- Output data goes to stdout; diagnostics go to stderr; JSON/CSV never contain ANSI escapes.
- Exit codes: `0` success/help/version, `1` internal/runtime failure, `2` usage or unreadable input, `3` decode/parse failure, `4` unique-cardinality exhaustion.

## Planned Stack and Structure

```text
pyproject.toml
src/nginx_stream_analytics/
├── __init__.py
├── cli.py
├── models.py
├── parser.py
├── aggregate.py
├── errors.py
└── renderers/{__init__,terminal,json,csv}.py
tests/{fixtures,test_packaging,test_models,test_errors,test_parser,test_aggregate,test_renderers,test_cli,test_performance}.py
benchmarks/{generate_log,run}.py
```

Only planning documents exist at blueprint completion. Do not infer that the structure above has been implemented.

## Engineering Rules

1. Preserve WIP=1 and work on only the active `IMPLEMENTATION_PLAN.md` step.
2. Test behavior at the parser/aggregator boundary and through subprocess CLI integration.
3. Treat `PRD.md` acceptance criteria and `PROJECT_ARCHITECTURE.md` interfaces as source; update the spec before behavior.
4. Use `apply_patch` for intentional edits, preserve unrelated user work, and do not weaken tests or gates.
5. Benchmark claims must record reproducible machine, fixture, command, time, and memory evidence.
6. Freeze and verify the exact candidate through the Idea to Deploy Verification Loop; narration is not acceptance evidence.
7. Never commit generated 1 GB fixtures, logs, secrets, virtual environments, caches, or build outputs.
8. At the end of every session or significant block of work, save context through `/session-save`.

## Implementation Status

| Step | Scope | Status | Required evidence |
|---:|---|---|---|
| 1 | Packaging and public CLI contracts | Not started | build, install, help, packaging tests |
| 2 | Models, errors, fixtures | Not started | unit tests and type checks |
| 3 | Combined Log parser | Not started | parser suite under multiple timezones |
| 4 | Streaming aggregation | Not started | correctness and branch coverage |
| 5 | Three renderers | Not started | round-trip parity and coverage |
| 6 | CLI integration | Not started | file/stdin and exit 0/1/2/3/4 tests |
| 7 | Performance gate | Not started | reproducible 1 GB benchmark under 30 s |
| 8 | Release quality | Not started | full suite, wheel smoke, exact-candidate receipt |

## Current State

Blueprint documents are complete; product code has not been created. The next authorized action, after a separate implementation request, is Step 1 only. The external benchmark harness—not this blueprint session—owns the independent Devil's Advocate review.
