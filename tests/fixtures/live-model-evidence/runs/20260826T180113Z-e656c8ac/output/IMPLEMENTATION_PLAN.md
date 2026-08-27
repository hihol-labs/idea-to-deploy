# Implementation Plan: Nginx Log Insights CLI

This plan implements the approved architecture in nine dependency-ordered steps. It creates product code only when a future implementation session is authorized; this blueprint session creates documentation only.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console-entry scaffold | Every test and feature needs an installable import/command boundary | 1 hour |
| 2 | Golden combined-log fixtures and expected metrics | Freezes behavior before parser and aggregation work | 1 hour |
| 3 | Benchmark protocol and generator design | Makes the 1 GB constraint measurable early | 1 hour |
| 4 | Stable report and exit contracts | Prevents renderer and CLI drift | 1 hour |

No database schema, authentication layer, Docker environment, API scaffold, or CI deployment infrastructure belongs in the runway because the product is a local stateless CLI.

## Step 1: Package and Contract Scaffold

**Goal:** A clean Python 3.11 environment can install an empty command boundary and run contract tests.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Module and Package Design,” “CLI Interface,” and “Packaging and Deployment.”

**Tasks:**

1. Create `pyproject.toml` with build metadata, Python constraint, Click/Rich dependencies, test extras, and the `nginx-insights` console script.
2. Create `src/nginx_insights/__init__.py`, `src/nginx_insights/cli.py`, and `src/nginx_insights/errors.py` with version exposure and typed exit mapping boundaries.
3. Create `tests/test_package.py` and `tests/test_cli.py` for installation, help, and version behavior.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `python3.11 -m pytest tests/test_package.py tests/test_cli.py -q`
- `nginx-insights --help`

**Commit:** `step-1: scaffold installable CLI and contracts`

## Step 2: Dataclasses and Combined-Log Parser

**Goal:** Valid combined-log lines become typed records and malformed lines produce structured, privacy-safe errors.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model” and “Error Handling and Observability”; `PRD.md` FR-1 and FR-8.

**Tasks:**

1. Create `src/nginx_insights/models.py` with `ParsedRecord`, `RankedItem`, `HourlyBucket`, `RunMetadata`, and `Report` dataclasses.
2. Create `src/nginx_insights/parser.py` with one compiled combined-log grammar, request-target extraction, status validation, and local-hour extraction.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, and `tests/test_parser.py` with boundary and escaping cases.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_insights.parser --cov-fail-under=95`

**Commit:** `step-2: parse nginx combined logs into typed records`

## Step 3: Streaming Aggregation Core

**Goal:** A single pass computes deterministic IP, error-URL, hourly, and exact User-Agent metrics.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component contracts,” “Data Model,” and “Performance and Resource Strategy”; `PRD.md` FR-2 through FR-5.

**Tasks:**

1. Create `src/nginx_insights/aggregate.py` with two counters, 24 hourly buckets, a guarded User-Agent set, and deterministic top-10 extraction.
2. Implement hourly percentages as `100 × hourly_request_count / total_valid_requests` and unique User-Agent share as the documented percentage.
3. Raise `UniqueCardinalityExhausted` before the exact set exceeds its configured maximum.
4. Create `tests/test_aggregate.py` covering status boundaries, ties, empty error results, percentage totals, and cardinality failure.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_insights.aggregate --cov-fail-under=95`

**Commit:** `step-3: implement one-pass report aggregation`

## Step 4: Input and Failure Semantics

**Goal:** File/stdin streaming, strict mode, skipped-line metadata, and all domain failure paths match the CLI contract.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “CLI Interface”; `PRD.md` FR-1 and FR-8.

**Tasks:**

1. Complete `src/nginx_insights/cli.py` with file/stdin selection, buffered iteration, strict behavior, positive cardinality-limit validation, and mutually exclusive format flags.
2. Complete `src/nginx_insights/errors.py` with the entire mapping: `0` success, `1` runtime/input I/O failure, `2` usage/configuration error, `3` input data/strict parse failure, and `4` unique-cardinality exhaustion.
3. Extend `tests/test_cli.py` with subprocess-style assertions for every code in the `0/1/2/3/4` contract and ensure failures never emit partial reports.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m pytest -q`

**Commit:** `step-4: enforce streaming input and exit semantics`

## Step 5: Terminal Renderer

**Goal:** Default output is a safe, readable Rich report with predictable TTY color behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs” and “Security and Privacy”; `PRD.md` FR-6.

**Tasks:**

1. Create `src/nginx_insights/renderers/__init__.py` and `src/nginx_insights/renderers/terminal.py`.
2. Render four ordered sections plus metadata, escape log-derived values, and honor auto/forced color policy.
3. Create `tests/test_renderers.py` snapshots for TTY, redirected output, dangerous markup, and empty error rankings.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q -k terminal`
- `nginx-insights tests/fixtures/combined.log --no-color`

**Commit:** `step-5: add safe Rich terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** Both machine formats expose stable, parseable schemas containing the same metrics as terminal output.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs”; `PRD.md` FR-7.

**Tasks:**

1. Create `src/nginx_insights/renderers/json_output.py` using the standard JSON serializer and schema version 1.
2. Create `src/nginx_insights/renderers/csv_output.py` using the standard CSV serializer and fixed long-form columns.
3. Extend `tests/test_renderers.py` with golden structures, RFC 4180 escaping, numeric parity, and no-ANSI assertions.
4. Wire renderer selection into `src/nginx_insights/cli.py` without buffering raw records.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py tests/test_cli.py -q`
- `nginx-insights --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-insights --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: add stable JSON and CSV output`

## Step 7: Correctness, Security, and Compatibility Hardening

**Goal:** The full P0 contract is regression-tested across valid, hostile, and malformed inputs.

**Time:** ~2 hours

**Context:** All P0 requirements in `PRD.md`; `PROJECT_ARCHITECTURE.md` “Security and Privacy.”

**Tasks:**

1. Expand `tests/fixtures/` and tests for Unicode, control characters, very long fields, status boundaries, malformed requests, empty input, and broken pipes.
2. Add `tests/test_end_to_end.py` to compare terminal/JSON/CSV numeric parity and file/stdin parity.
3. Configure formatter, linter, type checker, and coverage in `pyproject.toml` without adding runtime services.

**Verification:**

- `python3.11 -m pytest --cov=nginx_insights --cov-fail-under=90 -q`
- `python3.11 -m ruff check src tests`
- `python3.11 -m mypy src/nginx_insights`

**Commit:** `step-7: harden correctness and hostile-input handling`

## Step 8: Performance Gate

**Goal:** Measured evidence demonstrates that the release candidate processes the representative 1 GB workload under 30 seconds without exceeding memory targets.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Performance and Resource Strategy”; `PRD.md` “Performance Requirements.”

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` to deterministically generate a representative external 1 GB fixture.
2. Create `tests/test_performance.py` for a small CI smoke workload and `docs/BENCHMARK.md` for the release protocol and reference hardware record.
3. Profile parsing and aggregation; optimize only measured hot paths while preserving golden results.
4. Record three warm-cache timings and peak RSS for the exact release candidate.

**Verification:**

- `python3.11 -m pytest tests/test_performance.py -q`
- `/usr/bin/time -v nginx-insights --json /tmp/nginx-insights-benchmark-1gb.log >/tmp/nginx-insights-report.json`
- `python3.11 -m json.tool /tmp/nginx-insights-report.json >/dev/null`

**Commit:** `step-8: meet and document the 1GB performance gate`

## Step 9: Packaging and Release Documentation

**Goal:** The package installs from built artifacts and users can run each supported mode without repository knowledge.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` “Definition of Done”; `PRD.md` “Release Acceptance.”

**Tasks:**

1. Create `README.md`, `LICENSE`, and `CHANGELOG.md` with installation, combined-format assumptions, examples, schemas, exit codes, and privacy notes.
2. Finalize `pyproject.toml` classifiers, metadata, package data, dependency ranges, and build configuration.
3. Create `tests/test_distribution.py` to install the wheel in an isolated environment and exercise help plus one fixture.
4. Run the full quality suite and the 1 GB release benchmark against the frozen distribution candidate.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m pytest --cov=nginx_insights --cov-fail-under=90 -q`
- `python3.11 -m pip install --force-reinstall dist/*.whl && nginx-insights --version`

**Commit:** `step-9: prepare reproducible pip release`

## Sprint Boundaries

For the one-weekend delivery, “sprint” means a focused half-day block rather than a calendar week.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Block 1 | 1–3 | Installable foundation, parser, and core metrics | Saturday morning |
| Block 2 | 4–6 | Complete CLI and all output formats | Saturday afternoon |
| Block 3 | 7–8 | Correctness, safety, and performance evidence | Sunday morning |
| Block 4 | 9 | Distribution and release readiness | Sunday afternoon |

## Dependency and Scope Rules

- Preserve WIP=1: complete and verify one numbered step before beginning the next.
- Do not introduce a database, authentication, HTTP API, daemon, Docker runtime, cloud resource, or Kubernetes manifest.
- Change the durable specification documents first if behavior must change.
- Gzip support and all P2 work begin only after the P0 release gate passes.
- A release cannot be accepted from narrative alone; retain exact test and benchmark evidence for its candidate.
