# Implementation Plan: nginx-stream-insights

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Packaging and module skeleton | Makes every later unit importable and testable | 1 h |
| 2 | Fixtures and output schemas | Locks observable behavior before implementation | 1 h |
| 3 | Benchmark harness design | Measures the main feasibility risk early | 1 h |

No database, auth, Docker, server, or CI/CD deployment runway is needed for the approved local CLI.

## Step 1: Package Skeleton and Contracts

**Goal:** A pip-installable Python 3.11 package exposes a Click command and shared dataclasses.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Module Structure, Packaging and Runtime, CLI Interface.

**Tasks:**

1. Create `pyproject.toml` with Python, Click, Rich, pytest, coverage, build, and console-script metadata.
2. Create `src/nginx_stream_insights/__init__.py`, `cli.py`, and `models.py` with public type contracts only.
3. Create `tests/unit/test_models.py` and `tests/integration/test_cli_help.py`.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `python3.11 -m pytest tests/unit/test_models.py tests/integration/test_cli_help.py`
- `nginx-stream-insights --help`

**Commit:** `step-1: establish package and CLI contracts`

## Step 2: nginx Parser

**Goal:** Supported common and combined lines become validated `ParsedRequest` values without retaining raw input.

**Time:** ~2 hours

**Context:** `PRD.md` — Input and Edge Cases; `PROJECT_ARCHITECTURE.md` — Data Model.

**Tasks:**

1. Create `src/nginx_stream_insights/parser.py` with precompiled parsing and timestamp/status validation.
2. Add `tests/fixtures/access_combined.log` and `tests/fixtures/access_common.log` with valid and invalid examples.
3. Create `tests/unit/test_parser.py` for IPv4/IPv6, offsets, quoting, missing UA, malformed status, and malformed timestamp.

**Verification:**

- `python3.11 -m pytest tests/unit/test_parser.py`

**Commit:** `step-2: parse supported nginx formats`

## Step 3: Streaming Aggregator and Guards

**Goal:** One pass computes exact required metrics within a cardinality bound.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Data Model and Streaming Algorithm, Performance Budget.

**Tasks:**

1. Create `src/nginx_stream_insights/aggregator.py` with IP, error-URL, hour, and User-Agent accumulators.
2. Add deterministic top-10 selection and percentages using `100 × hourly_request_count / total_valid_requests`.
3. Add a typed cardinality exception and enforce `--max-unique` independently for exact structures.
4. Create `tests/unit/test_aggregator.py`, including empty input, ties, status boundaries, percentages, and exhaustion.

**Verification:**

- `python3.11 -m pytest tests/unit/test_aggregator.py`

**Commit:** `step-3: implement bounded streaming aggregation`

## Step 4: Terminal Renderer

**Goal:** Default output is a readable Rich report with all four metrics and input-quality counts.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Outputs; `PRD.md` — FR-7.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/__init__.py` and `renderers/text.py`.
2. Escape untrusted strings and implement TTY auto-color plus `--color/--no-color`.
3. Create `tests/unit/test_text_renderer.py` with snapshot-like semantic assertions and ANSI checks.

**Verification:**

- `python3.11 -m pytest tests/unit/test_text_renderer.py`

**Commit:** `step-4: render terminal report`

## Step 5: JSON and CSV Renderers

**Goal:** Pipelines receive stable, schema-versioned, ANSI-free output.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Outputs.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/json.py` with the documented top-level schema.
2. Create `src/nginx_stream_insights/renderers/csv.py` with the long-form `metric` schema.
3. Create `tests/unit/test_json_renderer.py` and `tests/unit/test_csv_renderer.py` for parseability, ordering, escaping, empty input, and headers.

**Verification:**

- `python3.11 -m pytest tests/unit/test_json_renderer.py tests/unit/test_csv_renderer.py`

**Commit:** `step-5: add pipeline output formats`

## Step 6: End-to-End CLI and Exit Codes

**Goal:** File/stdin flows, options, diagnostics, and every failure map to the public contract.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` — CLI Interface, Error and Safety Model.

**Tasks:**

1. Complete `src/nginx_stream_insights/cli.py` with buffered iteration and renderer selection.
2. Enforce mutual exclusion, positive `--max-unique`, parse policy, and stdout/stderr separation.
3. Create `tests/integration/test_cli.py` covering the complete `0/1/2/3/4` contract: 0 success, 1 I/O/decode, 2 usage, 3 strict parse, 4 unique-cardinality exhaustion.

**Verification:**

- `python3.11 -m pytest tests/integration/test_cli.py`
- `nginx-stream-insights --json tests/fixtures/access_combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-stream-insights --csv tests/fixtures/access_combined.log | python3.11 -c "import csv,sys; list(csv.DictReader(sys.stdin))"`

**Commit:** `step-6: integrate streaming CLI contract`

## Step 7: Performance and Quality Gate

**Goal:** Correctness, coverage, package build, scaling, and the 1 GB target have reproducible evidence.

**Time:** ~2.5 hours

**Context:** `STRATEGIC_PLAN.md` — Definition of Done; `PROJECT_ARCHITECTURE.md` — Performance Budget.

**Tasks:**

1. Create `tests/performance/generate_log.py` to generate a deterministic representative fixture outside Git.
2. Create `tests/performance/benchmark.py` to record bytes, records, wall time, throughput, peak RSS, CPU, disk, OS, and Python version.
3. Create `tests/unit/test_scaling.py` for bounded streaming behavior on a small generated input.
4. Add `pytest` coverage configuration and package-build validation.

**Verification:**

- `python3.11 -m pytest --cov=nginx_stream_insights --cov-report=term-missing --cov-fail-under=90`
- `python3.11 -m build`
- `python3.11 tests/performance/generate_log.py --size-gib 1 --output /tmp/nginx-stream-insights-1g.log`
- `python3.11 tests/performance/benchmark.py /tmp/nginx-stream-insights-1g.log --max-seconds 30`

**Commit:** `step-7: verify quality and performance budgets`

## Step 8: Documentation and Release Candidate

**Goal:** A new engineer can install, run, interpret, and safely extend the verified CLI.

**Time:** ~1.5 hours

**Context:** All blueprint documents, especially `README.md` and `CLAUDE.md`.

**Tasks:**

1. Update `README.md` with real installation, examples, schemas, limits, benchmark result, and exit codes.
2. Update `CLAUDE.md` status only after each verification command passes.
3. Add `CHANGELOG.md` and ensure wheel/sdist contain required package files.
4. Run the full suite from a clean virtual environment and perform a human review; do not publish without explicit approval.

**Verification:**

- `python3.11 -m pytest`
- `python3.11 -m build`
- `python3.11 -m pip install --force-reinstall dist/*.whl`
- `nginx-stream-insights --version`

**Commit:** `step-8: prepare verified local release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Contract, packaging, parser | 3.5 h |
| Saturday PM | 3–4 | Aggregation and terminal experience | 4 h |
| Sunday AM | 5–6 | Pipeline formats and complete CLI | 4 h |
| Sunday PM | 7–8 | Performance evidence and release readiness | 4 h |

## Completion Gate

All step-specific commands and the final full suite must pass in the implementation session. Documentation alone is not runtime evidence. Publishing to PyPI, pushing, opening a PR, or any other external action requires explicit human confirmation.

