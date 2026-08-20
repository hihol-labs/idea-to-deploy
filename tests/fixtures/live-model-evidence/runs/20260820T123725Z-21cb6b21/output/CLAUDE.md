# Project Instructions: nginx-analyzer

## Project Context

Build a local, open-source Python 3.11 CLI for DevOps and SRE engineers. It streams one nginx combined access log from a file or stdin and reports:

1. Top 10 client IPs by valid request count.
2. Top 10 exact request targets by combined 4xx/5xx count.
3. A 24-bucket hourly request distribution as percentages.
4. The percentage share of distinct logged User-Agent values.

Default output is TTY-aware colored Rich text. `--json` and `--csv` are stable, ANSI-free pipeline formats. The cash budget is $0 and the MVP schedule is one weekend. The canonical 1 GB fixture must complete in under 30 seconds on the documented reference laptop.

## Sources of Truth

Read in this order before changing behavior:

1. `PRD.md` — product requirements and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` — normative architecture and `## CLI Interface` contract.
3. `IMPLEMENTATION_PLAN.md` — dependency-ordered steps and verification commands.
4. `CLAUDE_CODE_GUIDE.md` — replayable step prompts.
5. `STRATEGIC_PLAN.md` — product boundaries, priorities, risks, and release Definition of Done.
6. `.itd/` contracts and `.itd-memory/` state — active scope and verification evidence.

When behavior changes, update the PRD and architecture first, then adjust implementation. Never let generated code silently become the specification.

## Required Stack

| Concern | Required choice |
|---|---|
| Runtime | Python 3.11 |
| CLI | Click |
| Terminal UI | Rich |
| Domain records | Standard-library dataclasses |
| Packaging | pip-installable `src/` layout with `pyproject.toml` |
| Architecture | One local process with stateless streaming aggregates |

Runtime dependencies beyond Click and Rich require a documented architecture decision. Prefer the Python standard library for parsing, counters, CSV, JSON, dates, and packaging support.

## Immutable Product Boundaries

- No authentication or authorization.
- No database, cache, persistent index, or migration.
- No HTTP API, server, daemon, or web UI.
- No cloud service, telemetry, Docker requirement, or Kubernetes.
- No shell evaluation, network access, DNS resolution, or upload of log data.
- No product code outside the currently active and scope-locked implementation step.
- No silent approximation when exact cardinality exceeds its memory ceiling.

## Semantic Rules

- Supported MVP input is one uncompressed nginx combined-format stream.
- Input is processed line by line; raw records are not retained.
- Default mode skips and counts malformed non-empty lines; `--strict` fails at the first one.
- Top-10 ties are resolved by descending count then ascending UTF-8 lexical key.
- Error URLs include statuses 400–599 and retain query strings.
- Hour buckets use the hour as logged with no timezone conversion.
- Hourly request distribution must use the literal percentage formula `100 × hourly_request_count / total_valid_requests`; never expose it as an unscaled fraction.
- User-Agent share is `100 × distinct_user_agent_count / total_valid_requests`.
- Rich, JSON, and CSV must derive from one shared report model.

## Complete Exit-Code Contract

Every implementation guide, CLI change, test plan, and user-facing document must preserve:

| Code | Meaning |
|---:|---|
| `0` | Successful report, help, or version output |
| `1` | Unexpected internal/runtime failure |
| `2` | CLI usage or option-validation error |
| `3` | Input/data failure, including unreadable input, strict malformed input, or zero valid records |
| `4` | Unique-cardinality exhaustion |

Code `4` is mandatory and reserved. Codes 3 and 4 emit a concise stderr diagnostic and no partial report. Machine-format stdout must never contain diagnostics or ANSI escapes.

## Planned Repository Structure

```text
pyproject.toml
src/nginx_analyzer/
  __init__.py
  __main__.py
  cli.py
  errors.py
  input.py
  parser.py
  models.py
  aggregate.py
  renderers/
    __init__.py
    rich_text.py
    json_output.py
    csv_output.py
tests/
  fixtures/
  test_packaging.py
  test_exit_codes.py
  test_input.py
  test_parser.py
  test_aggregate.py
  test_rich_output.py
  test_json_output.py
  test_csv_output.py
  test_renderer_parity.py
  test_cli.py
  test_high_cardinality.py
  test_acceptance.py
benchmarks/
  generate_fixture.py
  run_benchmark.py
  README.md
```

This tree is a plan, not evidence that the files already exist.

## Engineering Rules

- Preserve WIP=1: only one implementation-plan step may be active.
- Before changing scope, update `.itd/SCOPE_LOCK.md` and reconcile the active unit in durable state.
- Add or update acceptance tests with behavior; do not implement P2 features during the MVP.
- Treat log fields as untrusted text. Escape Rich markup and control characters; never echo raw malformed lines in diagnostics.
- Profile before performance optimization and preserve golden semantics after every optimization.
- Verify file and stdin parity and all three output formats.
- Run commands named by the active Idea to Deploy verification contract; do not infer success from code inspection.
- Do not claim a unit complete without current evidence and the repository-required adjudication receipt.
- At the end of every session or significant block of work, save context through `/session-save`.

## Planned Step Status

| Step | Deliverable | Status |
|---:|---|---|
| 1 | Installable package scaffold | Not started |
| 2 | Models, errors, and exit ownership | Not started |
| 3 | Streaming input and combined-log parser | Not started |
| 4 | One-pass aggregations and golden model | Not started |
| 5 | Safe Rich terminal renderer | Not started |
| 6 | JSON and CSV renderers | Not started |
| 7 | Complete CLI and failure paths | Not started |
| 8 | 1 GB performance and memory proof | Not started |
| 9 | Clean package and release acceptance | Not started |

Planning documents are complete only when verified separately; product implementation remains not started. The next implementation action is Step 1 after a future coding task explicitly authorizes it.

## Standard Verification Expectations

Use the exact step commands from `IMPLEMENTATION_PLAN.md`. At release, the minimum evidence set is:

- Full pytest suite with at least 90% product-module line coverage.
- Subprocess evidence for exit codes `0/1/2/3/4`.
- Parsed JSON and CSV contract checks plus Rich no-ANSI/no-injection tests.
- Clean Python 3.11 wheel install and console-command smoke run.
- Canonical exact 1 GB benchmark under 30 seconds with peak RSS recorded.

If any check fails, keep the active unit open, record the failure as recovery work, and state one next action.
