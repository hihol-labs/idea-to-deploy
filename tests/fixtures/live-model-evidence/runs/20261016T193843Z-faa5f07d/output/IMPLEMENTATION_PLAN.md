# Implementation Plan: nginx-log-top

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml`, `src/`, and test skeleton | Every feature needs an installable import and console entry point | 1 h |
| 2 | Domain dataclasses and typed errors | Parser, aggregator, renderers, and exit handling need one contract | 1 h |
| 3 | Representative fixtures and benchmark generator | Correctness and performance must be measurable before optimization | 1.5 h |

No database schema, authentication layer, API, Docker setup, or CI deployment infrastructure belongs in this runway because the approved product is a local stateless CLI.

## Step 1: Package and CLI Skeleton

**Goal:** A pip-installable Python 3.11 package exposes a working help/version command.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections Component Boundaries, CLI Interface, Packaging and Deployment.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, pytest tooling, and the `nginx-log-top` console entry point.
2. Create `src/nginx_log_top/__init__.py`, `src/nginx_log_top/__main__.py`, and `src/nginx_log_top/cli.py`.
3. Create `tests/test_cli.py` for help, version, and mutually exclusive options.

**Verification:**

- `python -m pip install -e .`
- `nginx-log-top --help`
- `pytest -q tests/test_cli.py`

**Commit:** `step-1: scaffold installable CLI`

## Step 2: Domain Models and Exit Semantics

**Goal:** Shared dataclasses and typed errors encode every report and expected failure.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections Data Model and CLI Interface.

**Tasks:**

1. Create `src/nginx_log_top/models.py` with `AccessRecord`, `AggregateState`, `RankedItem`, and `Report`.
2. Create `src/nginx_log_top/errors.py` with usage/I/O, no-valid-input, and cardinality exceptions.
3. Add CLI exception mapping for the complete `0/1/2/3/4` contract: success, internal failure, usage/I/O, no valid records, and unique-cardinality exhaustion.
4. Add `tests/test_exit_codes.py` with one subprocess-level case per code.

**Verification:**

- `pytest -q tests/test_exit_codes.py`
- `python -m compileall -q src`

**Commit:** `step-2: define models and exit contract`

## Step 3: Streaming Input and Parser

**Goal:** Stdin and ordered file inputs yield normalized records without retaining raw logs.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Parsing Contract and CLI Interface; `PRD.md` P0-1 and P0-2.

**Tasks:**

1. Create `src/nginx_log_top/inputs.py` for buffered stdin/file iteration and path validation.
2. Create `src/nginx_log_top/parser.py` for combined/common line parsing.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/common.log`, and `tests/fixtures/mixed.log` with synthetic non-sensitive data.
4. Create `tests/test_inputs.py` and `tests/test_parser.py`, including malformed bytes, status bounds, quotes, query strings, and timestamps.

**Verification:**

- `pytest -q tests/test_inputs.py tests/test_parser.py`
- `python -m nginx_log_top tests/fixtures/combined.log --json`

**Commit:** `step-3: parse streaming nginx inputs`

## Step 4: One-Pass Aggregation

**Goal:** One pass computes all required metrics with deterministic top-ten results.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Data Model and Performance and Resource Budget; `PRD.md` P0-3 through P0-6.

**Tasks:**

1. Create `src/nginx_log_top/aggregate.py` to update request, IP, error URL, hour, and User-Agent state.
2. Implement all 24 hourly percentages with `100 × hourly_request_count / total_valid_requests`.
3. Enforce `--max-unique-user-agents` before adding a new distinct value and raise the code-4 domain error on exhaustion.
4. Create `tests/test_aggregate.py` for ties, zero buckets, errors, empty User-Agents, percentage tolerance, and cap boundaries.

**Verification:**

- `pytest -q tests/test_aggregate.py`
- `pytest -q --cov=nginx_log_top --cov-report=term-missing`

**Commit:** `step-4: implement exact streaming metrics`

## Step 5: Terminal Renderer

**Goal:** Default output presents all metrics as readable Rich tables without leaking control sequences when disabled.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface outputs; `PRD.md` P0-7.

**Tasks:**

1. Create `src/nginx_log_top/renderers/__init__.py` and `src/nginx_log_top/renderers/text.py`.
2. Implement summary, top IP, error URL, hourly, and User-Agent sections.
3. Create `tests/test_text_renderer.py` with forced color and no-color snapshots.

**Verification:**

- `pytest -q tests/test_text_renderer.py`
- `nginx-log-top --color=never tests/fixtures/combined.log`

**Commit:** `step-5: add Rich terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** Pipelines receive stable, ANSI-free, deterministic machine output.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface outputs; `PRD.md` P0-7.

**Tasks:**

1. Create `src/nginx_log_top/renderers/json.py` with `schema_version: 1`.
2. Create `src/nginx_log_top/renderers/csv.py` using the standard library CSV writer and canonical header.
3. Create `tests/golden/report.json`, `tests/golden/report.csv`, `tests/test_json_renderer.py`, and `tests/test_csv_renderer.py`.
4. Verify the complete `0/1/2/3/4` exit-code behavior is identical for both machine modes, including code 4 for unique-cardinality exhaustion.

**Verification:**

- `pytest -q tests/test_json_renderer.py tests/test_csv_renderer.py tests/test_exit_codes.py`
- `nginx-log-top --json tests/fixtures/combined.log | python -m json.tool >/dev/null`

**Commit:** `step-6: add stable JSON and CSV output`

## Step 7: Follow Mode and Process Robustness

**Goal:** The optional P1 follow workflow is interruptible and does not weaken pipeline behavior.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface; `PRD.md` P1.

**Tasks:**

1. Extend `src/nginx_log_top/inputs.py` with complete-line polling for one regular file.
2. Extend `src/nginx_log_top/cli.py` with validation and quiet Ctrl-C finalization.
3. Add `tests/test_follow.py` and broken-pipe coverage to `tests/test_cli.py`.

**Verification:**

- `pytest -q tests/test_follow.py tests/test_cli.py`
- `timeout 2s nginx-log-top --follow tests/fixtures/combined.log --json || test $? -eq 124`

**Commit:** `step-7: add bounded follow workflow`

## Step 8: Performance Benchmark and Profiling

**Goal:** Record reproducible evidence for the 1 GB / 30 s acceptance target and memory behavior.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Performance and Resource Budget; `PRD.md` P0-8.

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically stream-generate a representative fixture without committing it.
2. Create `benchmarks/run.sh` to capture Python/hardware metadata, elapsed time, and peak RSS.
3. Create `benchmarks/README.md` with reproduction steps and the latest measured result.
4. Profile `parser.py` and `aggregate.py` only if the initial run misses the target; preserve output semantics during optimization.

**Verification:**

- `python benchmarks/generate_log.py --bytes 1073741824 --output /tmp/nginx-log-top-1gb.log`
- `sh benchmarks/run.sh /tmp/nginx-log-top-1gb.log`

**Commit:** `step-8: verify performance budget`

## Step 9: Release Readiness

**Goal:** The documented package is reproducible and all acceptance checks pass from a clean environment.

**Time:** ~2 hours

**Context:** All architecture and PRD sections.

**Tasks:**

1. Update `README.md` with final installation, examples, formats, limitations, and exit codes.
2. Add `CHANGELOG.md` and package metadata/license files as appropriate.
3. Run the complete suite, coverage, build, install, and artifact smoke tests.
4. Confirm code 4 remains `unique-cardinality exhaustion` everywhere and the full `0/1/2/3/4` contract is documented.

**Verification:**

- `pytest -q --cov=nginx_log_top --cov-fail-under=90`
- `python -m build && python -m pip install --force-reinstall dist/*.whl && nginx-log-top --version`

**Commit:** `step-9: prepare first release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable CLI and trustworthy parsing | Half day |
| Saturday PM | 4–5 | Correct metrics and terminal experience | Half day |
| Sunday AM | 6–7 | Pipeline formats and live-file robustness | Half day |
| Sunday PM | 8–9 | Performance evidence and release readiness | Half day |

## Global Acceptance Gate

The implementation is acceptable only when the test suite passes, coverage is at least 90% for package code, clean installation succeeds, JSON/CSV golden files match, each exit code `0/1/2/3/4` has an end-to-end test, and the recorded representative 1 GB benchmark is below 30 seconds.

