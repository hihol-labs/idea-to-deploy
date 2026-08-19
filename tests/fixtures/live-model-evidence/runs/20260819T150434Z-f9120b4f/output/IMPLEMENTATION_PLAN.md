# Implementation Plan: nginx-log-insights

## Delivery Rules

This plan implements the contracts in `PRD.md` and
`PROJECT_ARCHITECTURE.md`; it does not authorize a database, HTTP API, server,
cloud, Docker, or Kubernetes work. Preserve WIP=1: complete and verify each step
before beginning the next. Commands shown here are future acceptance commands,
not evidence that product code exists today.

Every implementation step must preserve this complete exit-code contract:

| Code | Meaning |
|---:|---|
| `0` | Successful report/help/version |
| `1` | Input/output failure |
| `2` | CLI usage or option/configuration error |
| `3` | Parse/validation failure or no valid requests |
| `4` | Unique-cardinality exhaustion; never emit a partial report |

Code 4 must not be omitted, remapped, or collapsed into a generic failure.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` package, build metadata, test configuration | Later behavior must run against the installed package | 1 h |
| 2 | Golden valid/invalid log fixtures | Parser and output requirements need replayable examples | 1 h |
| 3 | Benchmark fixture generator and measurement protocol | Performance risk must be measurable before polish | 1 h |

No database schema, auth system, API scaffold, Docker setup, or CI deployment
runway exists because those components are explicitly outside the architecture.

## Step 1: Package and Test Skeleton

**Goal:** A Python 3.11 wheel exposes a placeholder-free console entry point and
the test tools can import the installed package.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` → Package Structure, Packaging and Deployment.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build backend,
   pytest/coverage configuration, and the `nginx-log-insights` script.
2. Create `src/nginx_log_insights/__init__.py` with package version metadata.
3. Create `src/nginx_log_insights/cli.py` with the Click command surface only;
   do not claim metric behavior before later steps.
4. Create `tests/test_package.py` to verify the installed version and help output.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `python3.11 -m pytest tests/test_package.py -q`
- `nginx-log-insights --help`

**Commit:** `step-1: establish installable CLI package`

## Step 2: Combined-Log Parser and Domain Models

**Goal:** Valid combined records become typed `AccessRecord` values and invalid
records are rejected with line context but without full-line disclosure.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` → Data Contracts, Inputs.

**Tasks:**

1. Create `src/nginx_log_insights/models.py` with all documented dataclasses.
2. Create `src/nginx_log_insights/parser.py` with a precompiled combined-log
   parser, timestamp/status validation, and typed `ParseError`.
3. Create `tests/fixtures/combined_valid.log` and
   `tests/fixtures/combined_invalid.log` with deterministic cases.
4. Create `tests/test_parser.py` covering escaping, timezone offsets, `-` fields,
   status bounds, blanks, malformed requests, and safe diagnostics.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_log_insights.parser --cov-fail-under=95`

**Commit:** `step-2: parse nginx combined records`

## Step 3: Streaming Aggregation and Safety Bound

**Goal:** One-pass aggregation produces exact metric dataclasses and raises a
typed exhaustion error before exceeding the configured unique-key budget.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` → Streaming and Resource Bounds, Data Contracts.

**Tasks:**

1. Create `src/nginx_log_insights/aggregate.py` with `StreamingAggregator`,
   24 hourly counters, IP/error-URL counters, UA set, and shared unique budget.
2. Implement deterministic ranking and renderer-neutral unrounded percentages.
3. Create `tests/test_aggregate.py` covering 4xx/5xx filtering, ties, all 24
   hours, query strings, literal `-` UA, and boundary/off-by-one exhaustion.
4. Add `tests/fixtures/known_report.log` with hand-calculated expected results.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_log_insights.aggregate --cov-fail-under=95`

**Commit:** `step-3: aggregate exact streaming metrics`

## Step 4: CLI Orchestration and Exit Codes

**Goal:** File/stdin streaming, tolerant/strict parsing, mutually exclusive
options, and every `0/1/2/3/4` exit path match the public contract.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` → CLI Interface, Error Handling.

**Tasks:**

1. Complete `src/nginx_log_insights/cli.py` with `INPUT`, `--json`, `--csv`,
   `--max-unique-keys`, `--strict`, `--no-color`, help, and version.
2. Map input/output errors to 1, Click/config errors to 2, parse/empty-input
   errors to 3, and unique-cardinality exhaustion to 4.
3. Ensure unsuccessful paths never emit a partial stdout report.
4. Create `tests/test_cli.py` covering file/stdin parity and the exact exit matrix.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m pytest tests/test_cli.py -k 'exit or stdin or strict' -q`

**Commit:** `step-4: enforce CLI and exit contracts`

## Step 5: Rich Terminal Renderer

**Goal:** Default output clearly presents all metrics, safely escapes input,
and applies color only under the documented conditions.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` → Outputs, Security and Privacy.

**Tasks:**

1. Create `src/nginx_log_insights/renderers/__init__.py` for renderer selection.
2. Create `src/nginx_log_insights/renderers/terminal.py` with summary, ranking,
   hourly, and User-Agent tables; disable Rich markup for log-derived values.
3. Add TTY, redirected-output, and `--no-color` cases to `tests/test_cli.py`.
4. Create `tests/test_terminal_output.py` with semantic assertions rather than
   brittle full-screen snapshots.

**Verification:**

- `python3.11 -m pytest tests/test_terminal_output.py tests/test_cli.py -q`
- `nginx-log-insights tests/fixtures/known_report.log --no-color`

**Commit:** `step-5: render safe terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** Both machine formats implement stable, ANSI-free schemas with values
identical to terminal semantics.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` → Outputs; `PRD.md` → US-7.

**Tasks:**

1. Create `src/nginx_log_insights/renderers/json_output.py` using the standard
   JSON encoder and the documented top-level keys.
2. Create `src/nginx_log_insights/renderers/csv_output.py` using `csv.writer`
   and the `section,rank,key,count,percentage` schema.
3. Create `tests/test_output_contracts.py` to parse each output, compare semantic
   equality, assert ordering/rounding, and reject ANSI bytes.
4. Add broken-pipe/output-error cases to `tests/test_cli.py` and assert exit 1.

**Verification:**

- `python3.11 -m pytest tests/test_output_contracts.py tests/test_cli.py -q`
- `nginx-log-insights tests/fixtures/known_report.log --json | python3.11 -m json.tool >/dev/null`

**Commit:** `step-6: add stable JSON and CSV contracts`

## Step 7: Correctness, Privacy, and Full-Suite Hardening

**Goal:** Cross-cutting tests prove deterministic results, safe diagnostics,
memory-bound behavior, and complete exit-code coverage.

**Time:** ~2 hours

**Context:** `PRD.md` → Non-Functional Requirements, Release Acceptance.

**Tasks:**

1. Create `tests/test_security.py` for terminal markup, control characters,
   malicious URLs, and diagnostics that do not echo source lines.
2. Create `tests/test_integration.py` comparing file/stdin and all renderers on
   the golden report.
3. Add property-oriented generated cases inside `tests/test_aggregate.py` for
   ordering and hourly-percentage invariants without a new runtime dependency.
4. Configure coverage exclusions narrowly in `pyproject.toml` and reach at
   least 90% line coverage across project code.

**Verification:**

- `python3.11 -m pytest --cov=nginx_log_insights --cov-report=term-missing --cov-fail-under=90`
- `python3.11 -m compileall -q src tests`

**Commit:** `step-7: harden correctness and privacy`

## Step 8: Performance Gate

**Goal:** A reproducible measurement proves or disproves the 1 GB/<30-second
target without timing fixture generation.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` → KPIs; `PRD.md` → Performance Acceptance Method.

**Tasks:**

1. Create `tests/performance/generate_fixture.py` to deterministically generate
   a representative 1 GB combined log with documented cardinalities.
2. Create `tests/performance/run_benchmark.sh` to validate fixture size, time an
   installed-wheel invocation, record peak RSS, and validate output afterward.
3. Create `tests/test_performance.py` for a small CI-safe streaming smoke test;
   keep the 1 GB test an explicit local/release gate.
4. Create `BENCHMARK.md` with reference machine, commands, result fields, and
   optimization notes; record real results only when executed.

**Verification:**

- `python3.11 -m pytest tests/test_performance.py -q`
- `python3.11 tests/performance/generate_fixture.py --bytes 1073741824 --output /tmp/nginx-log-insights-1gb.log`
- `bash tests/performance/run_benchmark.sh /tmp/nginx-log-insights-1gb.log`

**Commit:** `step-8: verify one-gigabyte performance target`

## Step 9: Packaging, Documentation, and Release Candidate

**Goal:** A clean environment can build, inspect, install, and run the exact
release candidate using only published documentation.

**Time:** ~2 hours

**Context:** All blueprint documents; especially `PROJECT_ARCHITECTURE.md` → Packaging and Deployment.

**Tasks:**

1. Update `README.md` with verified install, examples, schemas, limits, privacy,
   and the complete exit-code table.
2. Update `CLAUDE.md` status and record deferred P1/P2 scope explicitly.
3. Create `CHANGELOG.md` with the initial release contract and known limitations.
4. Build wheel/sdist, inspect metadata, install the wheel into a clean virtual
   environment, and run golden CLI cases.
5. Freeze the exact candidate and run the repository Verification Loop and
   risk-tier checker required by `.itd/VERIFICATION_CONTRACT.json`.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m pytest -q`
- `python3.11 -m venv /tmp/nginx-log-insights-release-venv && /tmp/nginx-log-insights-release-venv/bin/pip install dist/*.whl && /tmp/nginx-log-insights-release-venv/bin/nginx-log-insights tests/fixtures/known_report.log --json`

**Commit:** `step-9: prepare verified release candidate`

## Sprint Boundaries

For a one-weekend delivery, “sprint” means a focused half-day block.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Block 1 | 1–2 | Installable skeleton and trustworthy parser | Saturday morning |
| Block 2 | 3–4 | Metrics, safety bound, and CLI contract | Saturday afternoon |
| Block 3 | 5–7 | All output formats and hardening | Sunday morning |
| Block 4 | 8–9 | Performance evidence and release packaging | Sunday afternoon |

## Dependency and Scope Checkpoints

- Do not start renderers until the report dataclass and golden aggregation pass.
- Do not optimize before the benchmark identifies a hot path.
- Do not weaken exactness or code 4 to pass the performance target.
- Any database, service, authentication, custom-format parser, or configurable
  top-N proposal requires a PRD and scope-lock change before implementation.
- Completion requires current machine evidence; a prose claim or standalone
  “passed” message is insufficient.

