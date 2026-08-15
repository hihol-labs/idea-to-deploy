# Implementation Plan: Nginx Stream Analyzer

## Delivery Principles

This is a planning artifact; no product code is implemented by this blueprint. Future implementation follows WIP=1, updates the spec before behavior, and accepts each step only from the frozen staged candidate's machine oracle and current risk-tier adjudication receipt.

The plan contains eight steps sized for one weekend. Dependencies, not raw RICE score alone, determine order.

## Architectural Runway

| # | Item | Why first | Estimate |
|---:|---|---|---:|
| 1 | Python 3.11 package and console entry point | Every behavior needs an installable invocation boundary | 1 h |
| 2 | Domain dataclasses and public errors | Parser, aggregation, rendering, and tests need shared contracts | 1 h |
| 3 | Fixture and benchmark generators | Correctness and performance require repeatable evidence early | 1 h |
| 4 | Verification configuration | Candidate checks must exist before feature work is accepted | 1 h |

No database schema, authentication system, API service, Docker setup, or CI/CD deployment pipeline belongs in the runway because the architecture is a local stateless CLI.

## Step 1: Package Skeleton and CLI Boundary

**Goal:** A Python 3.11 package installs locally and exposes a Click command whose interface and failure mapping are testable.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Model,” “CLI Interface,” and “Packaging and Runtime”; PRD FR-001, FR-011, FR-013.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click and Rich runtime dependencies, pytest tooling, and the `nginx-stream-analyzer` console script.
2. Create `src/nginx_stream_analyzer/__init__.py` with package version metadata.
3. Create `src/nginx_stream_analyzer/cli.py` with `INPUT`, `--json`, `--csv`, `--no-color`, `--version`, and `--help`; keep analysis unimplemented behind an explicit internal boundary.
4. Create `src/nginx_stream_analyzer/errors.py` with domain failures mapped to the full public exit contract.
5. Create `tests/test_cli.py` for help, version, option conflict, and too-many-input behavior.

**Verification:**

- `python3.11 -m pip install -e .`
- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-stream-analyzer --help`
- Assert success is 0, I/O failure is 1, usage failure is 2, invalid data is 3, and unique-cardinality exhaustion is 4.

**Commit:** `step-1: establish package and CLI contract`

## Step 2: Domain Models, Input Adapter, and Fixtures

**Goal:** File/stdin lines enter through a streaming adapter, and stable dataclasses describe records and reports.

**Time:** ~2 hours

**Context:** Architecture “Data and State Model” and “Component Model”; PRD US-2, FR-001, NFR-003.

**Tasks:**

1. Create `src/nginx_stream_analyzer/models.py` with frozen `AccessRecord`, ranked-row, hourly-row, summary, and `AnalysisReport` dataclasses.
2. Create `src/nginx_stream_analyzer/input.py` to yield decoded lines from one path or stdin without seeking or whole-file buffering.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/mixed.log`, and `tests/fixtures/malformed.log` with small auditable cases.
4. Create `tests/test_input.py` for file/stdin equivalence, read errors, replacement decoding, and non-seekable streams.

**Verification:**

- `python3.11 -m pytest tests/test_input.py -q`
- `python3.11 -m pytest tests/test_input.py -q --disable-warnings --maxfail=1`
- Inspect a non-seekable stdin test to confirm no rewind or list conversion occurs.

**Commit:** `step-2: define records and streaming input`

## Step 3: Supported Nginx Parser

**Goal:** Supported combined/common-compatible lines become typed records with deterministic malformed-line behavior.

**Time:** ~3 hours

**Context:** Architecture “Parsed record,” “Streaming Algorithm,” and CLI input rules; PRD FR-002, FR-003 and edge cases.

**Tasks:**

1. Create `src/nginx_stream_analyzer/parser.py` with a precompiled parser for the declared fields and nginx timestamp format.
2. Extract request target without method/protocol and validate status as a three-digit value in the supported range.
3. Return a structured parse failure rather than throwing raw input into diagnostics.
4. Create `tests/test_parser.py` for escaped quotes, timezone offsets, query strings, `-` User-Agent, status boundaries, invalid bytes, and malformed requests.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_stream_analyzer.parser --cov-fail-under=90`
- Run the parser fixture twice and compare typed results for determinism.

**Commit:** `step-3: parse supported nginx records`

## Step 4: Streaming Aggregation and Cardinality Guard

**Goal:** One pass computes the four exact metric families and fails before unsafe distinct-key growth.

**Time:** ~4 hours

**Context:** Architecture “Aggregation state,” “Cardinality safety,” “Streaming Algorithm,” and numerical rules; PRD FR-004–FR-007, FR-012.

**Tasks:**

1. Create `src/nginx_stream_analyzer/aggregate.py` with counters, fixed 24-hour storage, exact User-Agent set, and hard distinct-key limits.
2. Implement deterministic count-desc/key-asc top-10 selection.
3. Compute hourly percentages using exactly `100 × hourly_request_count / total_valid_requests` and unique User-Agent share using the valid-request denominator.
4. Reject zero-valid-record input as invalid data and stop pre-insertion on cardinality exhaustion.
5. Create `tests/test_aggregate.py` for error-status boundaries, ties, all 24 hours, percentage rounding boundaries, mixed malformed input, and limit edges.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_stream_analyzer.aggregate --cov-fail-under=90`
- Confirm a stream at the limit succeeds and the next distinct value exits through code 4 without a partial report.

**Commit:** `step-4: add bounded streaming metrics`

## Step 5: Rich Terminal Renderer

**Goal:** Default output is a readable four-section terminal report with safe, terminal-aware color.

**Time:** ~2 hours

**Context:** Architecture “Outputs” and “Error Handling and Security”; PRD US-6, FR-008, NFR-006.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/__init__.py` with the renderer protocol.
2. Create `src/nginx_stream_analyzer/renderers/text.py` with input totals and four Rich tables.
3. Escape or disable markup for all values originating in log records.
4. Update `src/nginx_stream_analyzer/cli.py` to choose text output by default and honor terminal detection and `--no-color`.
5. Add text-mode cases to `tests/test_cli.py` including redirected output and malicious markup/control values.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q -k 'text or color or markup'`
- `nginx-stream-analyzer tests/fixtures/combined.log > /tmp/nginx-analyzer-text.txt`
- Verify the redirected file contains all four section labels and no ANSI escape sequence.

**Commit:** `step-5: render safe terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** Pipelines receive deterministic, ANSI-free data matching the versioned JSON and normalized CSV contracts.

**Time:** ~3 hours

**Context:** Architecture CLI output schemas and “Output Determinism”; PRD US-5, FR-009, FR-010.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/json.py` for the schema-version-1 report.
2. Create `src/nginx_stream_analyzer/renderers/csv.py` for `section,rank,key,count,percentage` and fixed section order.
3. Add spreadsheet-formula injection neutralization to CSV keys while preserving count semantics.
4. Update `src/nginx_stream_analyzer/cli.py` to select one renderer and keep diagnostics on stderr.
5. Create `tests/golden/report.json`, `tests/golden/report.csv`, and structured-output tests in `tests/test_cli.py`.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q -k 'json or csv'`
- `nginx-stream-analyzer --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-stream-analyzer --csv tests/fixtures/combined.log | python3.11 -c "import csv,sys; list(csv.DictReader(sys.stdin))"`
- Confirm both formats are ANSI-free and exercise exit codes `0/1/2/3/4`, including code 4 for unique-cardinality exhaustion.

**Commit:** `step-6: add pipeline output formats`

## Step 7: End-to-End Errors, Packaging, and Security

**Goal:** All public paths behave consistently after installation, including failures and hostile values.

**Time:** ~3 hours

**Context:** Architecture exit codes, security, and packaging; PRD FR-011–FR-013, NFR-004–NFR-006.

**Tasks:**

1. Complete `src/nginx_stream_analyzer/cli.py` orchestration without duplicating parser or aggregation logic.
2. Extend `tests/test_cli.py` to cover file/stdin parity, mixed malformed input, stdout/stderr separation, broken input, zero-valid input, and cardinality exhaustion.
3. Create `tests/test_security.py` for Rich markup, control characters, CSV formulas, huge malformed lines, and diagnostic redaction.
4. Add package metadata, license reference, and console-entry integration coverage to `pyproject.toml`.
5. Update project documentation only after behavior matches the PRD.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_stream_analyzer --cov-report=term-missing --cov-fail-under=90`
- Build and install a wheel in a clean temporary virtual environment, then run `nginx-stream-analyzer --version`.
- Run a matrix proving: 0 complete success, 1 I/O failure, 2 usage failure, 3 no valid records, 4 unique-cardinality exhaustion.

**Commit:** `step-7: integrate errors and harden package`

## Step 8: Performance Qualification and Release Evidence

**Goal:** The exact release candidate is correctness-tested and demonstrates the 1 GB target under recorded conditions.

**Time:** ~4 hours

**Context:** Architecture “Performance Plan”; PRD NFR-001–NFR-003 and “Release Acceptance.”

**Tasks:**

1. Create `tests/generate_benchmark_log.py` to deterministically generate a representative supported-format 1 GB file outside Git.
2. Create `tests/test_performance.py` for smaller CI-scale streaming and memory-regression checks.
3. Create `docs/BENCHMARK.md` to record generator seed, file size, CPU, storage, OS, Python version, command, wall time, peak RSS, and result.
4. Profile only if the first benchmark misses the target; preserve parsing and metric semantics while optimizing.
5. Freeze the exact staged candidate, run its declared machine oracle, and obtain the current risk-tier checker/adjudication receipt before accepting release.

**Verification:**

- `python3.11 -m pytest -q`
- `/usr/bin/time -v nginx-stream-analyzer --json /tmp/nginx-analyzer-1gb.log >/tmp/nginx-analyzer-report.json`
- Confirm elapsed time is below 30 seconds on the documented reference laptop and the output parses as JSON.
- Run the repository Verification Loop for the exact staged candidate and retain its current adjudication receipt.

**Commit:** `step-8: qualify performance and release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable boundary, models, input, parser | ~7 h |
| Saturday PM | 4 | Correct bounded analytics | ~4 h |
| Sunday AM | 5–6 | Human and pipeline renderers | ~5 h |
| Sunday PM | 7–8 | Integration, security, benchmark, release evidence | ~7 h |

## Requirements Traceability

| Plan step | Primary PRD coverage |
|---|---|
| 1 | FR-001, FR-011, FR-013 |
| 2 | US-2, NFR-003 |
| 3 | FR-002, FR-003 |
| 4 | FR-004–FR-007, FR-012 |
| 5 | FR-008, NFR-006 |
| 6 | FR-009, FR-010, NFR-004 |
| 7 | FR-011–FR-013, NFR-005, NFR-006 |
| 8 | NFR-001–NFR-003, release acceptance |

## Implementation-Wide Exit-Code Contract

Every step preserves this complete mapping: `0` complete success; `1` input/output failure; `2` CLI usage failure; `3` zero valid supported records; `4` unique-cardinality exhaustion. The shorthand contract is `0/1/2/3/4`. Code 4 must be implemented, tested, documented, and never omitted or remapped.

## Deferred Work

After MVP acceptance, P1 may add configurable top-N and explicit additional formats. P2 may add gzip input or a clearly opt-in approximate-cardinality mode. Authentication, database, HTTP API, server, cloud, and Kubernetes remain out of scope.
