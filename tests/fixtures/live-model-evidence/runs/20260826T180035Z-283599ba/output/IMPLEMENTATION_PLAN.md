# Implementation Plan: Nginx Stream Analytics CLI

## Planning Rules

This plan implements `PRD.md` against `PROJECT_ARCHITECTURE.md`. It contains documentation only; commands are future verification instructions. Preserve one active step at a time, and do not begin P1/P2 work until all P0 acceptance checks pass.

The implementation must preserve exit codes `0/1/2/3/4`: 0 success, 1 input I/O failure, 2 usage/option error, 3 no valid nginx records, and 4 unique-cardinality exhaustion.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package and console entry point | Enables every CLI and packaging test | 1 hour |
| 2 | Domain/error dataclasses | Stabilizes boundaries between parser, aggregator, and renderers | 1 hour |
| 3 | Test fixtures and benchmark protocol | Makes correctness and performance measurable before feature work | 1 hour |

No database schema, authentication system, API, Docker setup, or CI deployment infrastructure is needed because the approved product is a local, stateless CLI.

## Step 1: Package Skeleton and Contract Tests

**Goal:** The pip package installs and exposes a Click command with frozen options and exit semantics.  
**Time:** ~1.5 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections Components and CLI Interface.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, build metadata, and `nginx-stream-report` entry point.
2. Create `src/nginx_stream_report/__init__.py`, `cli.py`, and `errors.py`.
3. Create `tests/test_cli.py` with help, version, option-conflict, and exit-code expectations.

**Verification:**

- `python3.11 -m pip install -e .`
- `nginx-stream-report --help`
- `python3.11 -m pytest tests/test_cli.py -q`

**Commit:** `step-1: establish package and CLI contract`

## Step 2: Parser and Fixtures

**Goal:** Common and combined nginx lines become validated `LogRecord` dataclasses one line at a time.  
**Time:** ~2 hours  
**Context:** Architecture sections Streaming and Data Model; PRD FR-1.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with `LogRecord` and parse-result dataclasses.
2. Create `src/nginx_stream_report/parser.py` with compiled parsing logic and timestamp/status validation.
3. Add representative files under `tests/fixtures/` and parser cases in `tests/test_parser.py`.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py -q --maxfail=1`

**Commit:** `step-2: parse nginx streams deterministically`

## Step 3: Core Ranked Aggregations

**Goal:** A single pass computes total/invalid counts, top client IPs, and top 4xx/5xx request targets.  
**Time:** ~2 hours  
**Context:** Architecture Streaming and Data Model; PRD FR-2 and FR-3.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with counter updates and bounded final top-N selection.
2. Extend `models.py` with immutable ranked-row and report dataclasses.
3. Create `tests/test_aggregate.py` covering boundaries, fewer-than-10 cases, and deterministic ties.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py -q -k 'top or tie or status'`

**Commit:** `step-3: aggregate top IPs and error URLs`

## Step 4: Hourly and User-Agent Metrics

**Goal:** The report includes all 24 hourly percentage buckets and exact unique User-Agent share with a hard cap.  
**Time:** ~2 hours  
**Context:** PRD FR-4 and FR-5.

**Tasks:**

1. Extend `aggregate.py` with a 24-element hourly counter and the exact formula `100 × hourly_request_count / total_valid_requests`.
2. Add exact nonempty User-Agent tracking and raise the typed exit-4 failure before the configured limit is exceeded.
3. Extend `tests/test_aggregate.py` with percentage, missing-UA, duplicate-UA, and limit-plus-one cases.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q -k 'hour or user_agent or cardinality'`
- `python3.11 -m pytest tests/test_cli.py -q -k 'exit_code_4'`

**Commit:** `step-4: add hourly and User-Agent metrics`

## Step 5: Terminal Renderer

**Goal:** Successful analysis produces a readable Rich report by default without corrupting redirected output.  
**Time:** ~1.5 hours  
**Context:** Architecture CLI Outputs; PRD FR-6.

**Tasks:**

1. Create `src/nginx_stream_report/render_text.py` for all report sections.
2. Wire automatic TTY color and `--color/--no-color` through `cli.py`.
3. Create `tests/test_renderers.py` snapshots/assertions for ordering, percentages, and ANSI suppression.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q -k text`
- `nginx-stream-report tests/fixtures/sample.log --no-color`

**Commit:** `step-5: render terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** Pipelines receive stable, parseable, style-free JSON or CSV.  
**Time:** ~1.5 hours  
**Context:** Architecture CLI Outputs; PRD FR-6.

**Tasks:**

1. Create `src/nginx_stream_report/render_json.py` with the specified object schema.
2. Create `src/nginx_stream_report/render_csv.py` with `section,rank,key,count,percentage` rows.
3. Extend `tests/test_renderers.py` and `tests/test_cli.py` with parsing and stdout/stderr separation checks.

**Verification:**

- `nginx-stream-report --json tests/fixtures/sample.log | python3.11 -m json.tool >/dev/null`
- `python3.11 -m pytest tests/test_renderers.py tests/test_cli.py -q`

**Commit:** `step-6: add machine-readable renderers`

## Step 7: Failure Semantics and Robustness

**Goal:** All expected failures are actionable, deterministic, and mapped to the complete contract.  
**Time:** ~1.5 hours  
**Context:** Architecture CLI Exit Codes and Security and Privacy.

**Tasks:**

1. Complete typed failures in `errors.py` and mapping in `cli.py` for `0/1/2/3/4`.
2. Add input read-error, malformed-only, oversized-line/control-character, and no-partial-output tests.
3. Verify code 4 retains the meaning unique-cardinality exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_cli.py -q -k 'exit_code'`

**Commit:** `step-7: enforce complete failure contract`

## Step 8: Performance and Memory Gate

**Goal:** The frozen release candidate processes the representative 1 GB fixture in under 30 seconds with documented peak memory.  
**Time:** ~2 hours  
**Context:** Architecture Performance and Resource Budgets; PRD Quality Requirements.

**Tasks:**

1. Create `tests/test_performance.py` and a deterministic procedure for generating or locating a representative 1 GB benchmark input outside Git.
2. Add timing and peak-RSS capture with hardware, Python, input-size, and checksum metadata.
3. Profile parser/aggregation hot paths and optimize only measured bottlenecks without changing report semantics.

**Verification:**

- `python3.11 -m pytest tests/test_performance.py -q --run-performance`
- `/usr/bin/time -v nginx-stream-report --json /path/to/representative-1gb.log >/dev/null`

**Commit:** `step-8: prove performance and memory target`

## Step 9: Packaging and Release Documentation

**Goal:** A clean Python 3.11 environment can install, run, and understand the release candidate.  
**Time:** ~1.5 hours  
**Context:** Strategic Definition of Done and all PRD P0 criteria.

**Tasks:**

1. Finalize `README.md`, package metadata, license references, and user examples.
2. Build wheel and source distribution and test them in a clean virtual environment.
3. Run the full correctness suite and the separately recorded performance gate; reconcile documentation against behavior.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m pytest -q`
- `python3.11 -m pip install --force-reinstall dist/*.whl && nginx-stream-report --version`

**Commit:** `step-9: prepare verified pip release`

## Sprint Boundaries

For the one-weekend delivery, “sprint” means a focused half-day block.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Runnable package and validated parser | Half day |
| Saturday PM | 3–4 | Complete report model and aggregations | Half day |
| Sunday AM | 5–7 | Human/machine output and failure contract | Half day |
| Sunday PM | 8–9 | Performance evidence and installable release | Half day |

