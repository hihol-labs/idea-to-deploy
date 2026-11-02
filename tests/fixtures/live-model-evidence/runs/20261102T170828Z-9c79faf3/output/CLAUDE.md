# nginx-stream-insights Project Instructions

## Project Context

Build a local Python 3.11 CLI for DevOps/SRE engineers that streams nginx common or combined access logs and reports top client IPs, top URLs among 4xx/5xx responses, hourly request distribution, and unique User-Agent share. Default output is colored terminal text; JSON and CSV are stable pipeline interfaces.

The durable specification is `PRD.md`; architectural and CLI details are in `PROJECT_ARCHITECTURE.md`; priorities are in `STRATEGIC_PLAN.md`; implementation order and checks are in `IMPLEMENTATION_PLAN.md`; reusable prompts are in `CLAUDE_CODE_GUIDE.md`.

## Non-negotiable Architecture

- Use Python 3.11, Click, Rich, dataclasses, `src/` packaging, and pip distribution.
- Use one local process and stream raw lines; never retain the full input.
- No authentication, database, HTTP API, server, telemetry, cloud, Docker runtime, or Kubernetes.
- Preserve the decision: **no database — stateless streaming processing; no HTTP API — CLI-only tool**.
- Do not add dependencies or multiprocessing without measured need and a specification update.
- Treat exact frequency maps and User-Agent sets as cardinality-dependent memory; enforce the documented ceiling.

## Product Semantics

- Errors are statuses 400–599.
- URL means the request-target token, including its query string in MVP.
- Use the logged timestamp’s hour without timezone conversion.
- Hourly percentage is `100 × hourly_request_count / total_valid_requests`; zero valid requests yields `0.0`, never an unscaled fraction.
- Unique User-Agent share is `100 × distinct_nonempty_user_agents / total_valid_requests`; empty/missing agents do not enter the set.
- Rankings sort by count descending and key ascending; hours are always `00` through `23`.
- Mixed valid/malformed input succeeds and reports malformed count; non-empty all-malformed input is a parse-policy failure.

## CLI and Exit Codes

Keep stdout exclusively for report data and stderr for diagnostics. Text is default; JSON and CSV are mutually exclusive. Disable color for non-TTY output and `--no-color`.

The complete exit-code contract is:

| Code | Meaning |
|---:|---|
| 0 | Success, including empty input |
| 1 | Input I/O or unexpected runtime I/O failure |
| 2 | CLI usage/configuration error |
| 3 | Non-empty input with no valid records |
| 4 | Unique-cardinality exhaustion |

Never omit, reuse, or remap code 4.

## Expected Repository Structure

```text
src/nginx_stream_insights/
  __init__.py
  __main__.py
  cli.py
  input.py
  parser.py
  models.py
  aggregator.py
  renderers/{__init__,text,json,csv}.py
tests/
  fixtures/
  golden/
  test_cli.py
  test_parser.py
  test_input.py
  test_aggregator.py
  test_renderers.py
  test_follow.py
  test_end_to_end.py
benchmarks/
  generate_log.py
  run.sh
  README.md
```

This is the intended future structure, not permission to generate all files at once. Follow the active implementation step.

## Engineering Rules

1. WIP is one: work on one step from `IMPLEMENTATION_PLAN.md` at a time.
2. Update specification documents before changing user-visible behavior.
3. Add tests with new code and run the relevant suite before any commit; “tests written” is not “tests passed.”
4. Keep parser, aggregation, input, and rendering separated. Renderers consume one canonical `Report`.
5. Avoid raw-line logging and network access. Use non-sensitive handcrafted or generated fixtures.
6. Profile before optimizing. The acceptance benchmark is 1 GB under 30 seconds on the documented reference laptop.
7. Do not publish, push, deploy, delete material data, or perform any external action without explicit human confirmation.
8. Report commands actually run and their outcomes. Failed or skipped validation means the step is not complete.
9. At the end of every session or significant work block, save context through `/session-save`.

## Verification Baseline

Run the focused commands specified for the active step. Before release readiness, the minimum gate is:

```text
python3.11 -m pytest --cov=nginx_stream_insights --cov-fail-under=90 -q
python3.11 -m build
bash scripts/smoke-wheel.sh dist/*.whl
bash benchmarks/run.sh /tmp/nginx-stream-insights-1gb.log
```

Do not invent successful output. Record environment details and measured benchmark results.

## Implementation Status

| Step | Scope | Status |
|---:|---|---|
| 1 | Package skeleton | Not started |
| 2 | Models and parser | Not started |
| 3 | Streaming aggregation | Not started |
| 4 | Terminal renderer/CLI | Not started |
| 5 | JSON and CSV | Not started |
| 6 | Follow mode and controls | Not started |
| 7 | Performance and quality gate | Not started |
| 8 | Packaging and release readiness | Not started |

No product code exists as part of the blueprint phase. Update this table only from verified evidence.

