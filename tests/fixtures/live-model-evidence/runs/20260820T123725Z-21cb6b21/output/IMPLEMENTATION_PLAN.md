# Implementation Plan: nginx-analyzer

## Delivery Contract

This is a planning document; it does not implement product code. Work is limited to the Python 3.11 local CLI described in `PROJECT_ARCHITECTURE.md` and `PRD.md`. Preserve WIP=1: finish and verify each step before starting the next.

Every step inherits the complete exit-code contract:

| Code | Meaning |
|---:|---|
| `0` | Success, help, or version |
| `1` | Unexpected internal/runtime failure |
| `2` | CLI usage or option-validation error |
| `3` | Input/data failure |
| `4` | Unique-cardinality exhaustion |

Code 4 must remain dedicated to exact User-Agent cardinality exhaustion and must never be omitted or remapped.

## Architectural Runway

These foundations precede feature development and deliberately exclude databases, authentication, servers, Docker, cloud, and Kubernetes.

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` package and pip metadata | Every module, test, and console command depends on import/install structure | 0.75 h |
| 2 | Frozen models and typed domain errors | Aggregation, rendering, and exit mapping need one shared semantic contract | 0.75 h |
| 3 | Deterministic fixtures and test harness | Parsing and metric work need golden evidence before optimization | 1.0 h |
| 4 | Benchmark fixture generator | Performance must be measured early enough to change parsing tactics | 0.5 h |

## Step 1: Scaffold the Installable Package

**Goal:** A clean Python 3.11 environment can build and install a package exposing `nginx-analyzer`.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Components and Responsibilities” and “Packaging and Deployment”; `PRD.md` FR-10.

**Files:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click and Rich runtime dependencies, build metadata, and the console-script entry point.
2. Create `src/nginx_analyzer/__init__.py` with the package version.
3. Create `src/nginx_analyzer/__main__.py` delegating to the CLI entry point.
4. Create `src/nginx_analyzer/cli.py` with help/version only; reserve exception mapping for later steps.
5. Create `tests/test_packaging.py` for import and runner smoke checks.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e .`
- `.venv/bin/python -m nginx_analyzer --help`
- `.venv/bin/nginx-analyzer --version`
- `.venv/bin/python -m pytest tests/test_packaging.py -q`

**Commit:** `step-1: scaffold pip-installable CLI package`

## Step 2: Define Models, Errors, and Exit Ownership

**Goal:** Domain objects and all five process outcomes have one typed source of truth.

**Time:** ~1 hour

**Context:** Architecture “Data Model” and “CLI Interface”; PRD FR-9.

**Files:**

1. Create `src/nginx_analyzer/models.py` with frozen dataclasses for `AccessRecord`, ranked rows, hourly rows, User-Agent summary, and final report.
2. Create `src/nginx_analyzer/errors.py` with input/data and cardinality-exhaustion exceptions.
3. Extend `src/nginx_analyzer/cli.py` with a single mapping for `0` success, `1` unexpected internal/runtime failure, `2` Click usage error, `3` input/data failure, and `4` unique-cardinality exhaustion.
4. Create `tests/test_exit_codes.py` covering the mapping without relying on string matching alone.

**Verification:**

- `.venv/bin/python -m pytest tests/test_exit_codes.py -q`
- `.venv/bin/python -m mypy src/nginx_analyzer`

**Commit:** `step-2: define report models and exit contracts`

## Step 3: Build the Streaming Input and Combined-Log Parser

**Goal:** A file or stdin is parsed incrementally into the fields required by every metric.

**Time:** ~2 hours

**Context:** Architecture “Parsed record,” “Error Handling and Observability,” and “Performance and Resource Model”; PRD US-1.

**Files:**

1. Create `src/nginx_analyzer/input.py` for read-only buffered binary file/stdin iteration and safe I/O errors.
2. Create `src/nginx_analyzer/parser.py` with one compiled combined-log parser, escaped quoted-field handling, timestamp/status validation, and request-target extraction.
3. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` with deterministic, non-sensitive cases.
4. Create `tests/test_parser.py` for IPv4, IPv6, offsets, escaped fields, literal `-`, invalid bytes, empty lines, and malformed records.
5. Create `tests/test_input.py` proving file/stdin byte parity and bounded iteration.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py tests/test_input.py -q`
- `.venv/bin/python -m pytest tests/test_parser.py --cov=nginx_analyzer.parser --cov-fail-under=90`

**Commit:** `step-3: stream and parse nginx combined logs`

## Step 4: Implement One-Pass Aggregation

**Goal:** One stream produces exact top-IP, error-URL, hourly, and User-Agent inputs without retaining raw records.

**Time:** ~2 hours

**Context:** Architecture “Aggregate state” and “Data Model”; PRD US-2 through US-5.

**Files:**

1. Create `src/nginx_analyzer/aggregate.py` with IP and error-target counters, 24 buckets, totals, bounded exact User-Agent set, and deterministic top-10 tie-breaking.
2. Finalize report dataclasses in `src/nginx_analyzer/models.py` so every renderer consumes precomputed values.
3. Create `tests/test_aggregate.py` covering statuses 399/400/499/500/599/600, ties, query strings, offset-local hours, literal `-`, and ceiling boundary.
4. Create `tests/fixtures/golden.log` plus `tests/fixtures/golden-report.json` as the cross-renderer semantic oracle.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate.py --cov=nginx_analyzer.aggregate --cov-fail-under=90`
- `.venv/bin/python -m pytest tests/test_aggregate.py -k cardinality -q`

**Commit:** `step-4: aggregate all metrics in one pass`

## Step 5: Render Rich Terminal Output

**Goal:** The default command produces a readable, TTY-aware report without allowing log content to become markup.

**Time:** ~1.5 hours

**Context:** Architecture “Outputs” and “Security and Privacy”; PRD US-6.

**Files:**

1. Create `src/nginx_analyzer/renderers/__init__.py` with renderer protocol/export definitions.
2. Create `src/nginx_analyzer/renderers/rich_text.py` with summary and four report sections.
3. Extend `src/nginx_analyzer/cli.py` with default Rich selection and `--no-color`.
4. Create `tests/test_rich_output.py` for TTY/non-TTY behavior, ANSI absence, escaped markup/control fields, empty ranking sections, and golden values.

**Verification:**

- `.venv/bin/python -m pytest tests/test_rich_output.py -q`
- `.venv/bin/nginx-analyzer --no-color tests/fixtures/golden.log > /tmp/nginx-analyzer-rich.txt`
- `.venv/bin/python -c "from pathlib import Path; assert b'\\x1b[' not in Path('/tmp/nginx-analyzer-rich.txt').read_bytes()"`

**Commit:** `step-5: add safe Rich terminal report`

## Step 6: Add JSON and CSV Pipeline Formats

**Goal:** Scripts receive stable, color-free machine formats with identical report semantics.

**Time:** ~2 hours

**Context:** Architecture “Output Schemas”; PRD US-7 and FR-8.

**Files:**

1. Create `src/nginx_analyzer/renderers/json_output.py` with schema version 1.
2. Create `src/nginx_analyzer/renderers/csv_output.py` with normalized row order and standard CSV quoting.
3. Extend `src/nginx_analyzer/cli.py` with mutually exclusive `--json` and `--csv` options.
4. Create `tests/test_json_output.py`, `tests/test_csv_output.py`, and `tests/test_renderer_parity.py`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_json_output.py tests/test_csv_output.py tests/test_renderer_parity.py -q`
- `.venv/bin/nginx-analyzer --json tests/fixtures/golden.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/python -c "import csv,subprocess; out=subprocess.check_output(['.venv/bin/nginx-analyzer','--csv','tests/fixtures/golden.log'], text=True); assert list(csv.DictReader(out.splitlines()))"`

**Commit:** `step-6: add stable JSON and CSV renderers`

## Step 7: Complete CLI Validation and Failure Paths

**Goal:** File/stdin execution, tolerant/strict parsing, option validation, and every exit code work end to end.

**Time:** ~1.5 hours

**Context:** Architecture `## CLI Interface`; PRD US-1, US-5, US-7, and US-8.

**Files:**

1. Complete `src/nginx_analyzer/cli.py` options: `--strict`, `--encoding`, and `--max-unique-user-agents`.
2. Complete `src/nginx_analyzer/input.py` and `src/nginx_analyzer/errors.py` diagnostics without raw-line leakage.
3. Create `tests/test_cli.py` for file/stdin parity, tolerant counts, strict failure, unreadable/empty input, codec/option errors, and format exclusivity.
4. Extend `tests/test_exit_codes.py` with actual subprocess scenarios proving `0/1/2/3/4`; inject a controlled internal exception only through a test seam for code 1.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py tests/test_exit_codes.py -q`
- `.venv/bin/python -m pytest -q`
- `.venv/bin/python -m coverage report --fail-under=90`

**Commit:** `step-7: complete CLI and all failure contracts`

## Step 8: Prove Performance and Resource Bounds

**Goal:** The documented canonical 1 GB workload finishes under 30 seconds with recorded peak memory and no semantic regression.

**Time:** ~2 hours

**Context:** Architecture “Performance and Resource Model”; PRD NFR-1 and NFR-2.

**Files:**

1. Create `benchmarks/generate_fixture.py` to deterministically produce exactly 1 GB of supported, non-sensitive log data without committing the generated file.
2. Create `benchmarks/run_benchmark.py` to record interpreter, OS, CPU, storage note, input size, wall time, valid-record count, and peak RSS.
3. Create `benchmarks/README.md` with reproducible commands, warm-up rule, and pass threshold.
4. Create `tests/test_high_cardinality.py` for exhaustion at ceiling+1 and bounded diagnostics.
5. Optimize `src/nginx_analyzer/parser.py` or `aggregate.py` only when profiler evidence identifies a bottleneck; preserve golden semantics.

**Verification:**

- `.venv/bin/python benchmarks/generate_fixture.py --size-bytes 1073741824 --output /tmp/nginx-analyzer-1gb.log`
- `.venv/bin/python benchmarks/run_benchmark.py /tmp/nginx-analyzer-1gb.log --max-seconds 30 --max-rss-mib 512`
- `.venv/bin/python -m pytest tests/test_high_cardinality.py tests/test_renderer_parity.py -q`

**Commit:** `step-8: prove one-gigabyte performance target`

## Step 9: Package and Release-Check the MVP

**Goal:** A wheel installs cleanly and every P0 acceptance criterion has current evidence.

**Time:** ~1.5 hours

**Context:** All architecture sections; PRD “Release Acceptance”; `STRATEGIC_PLAN.md` Definition of Done.

**Files:**

1. Create `README.md` with supported format, installation, file/stdin examples, all output modes, semantics, and exit codes.
2. Create `CHANGELOG.md` with the initial machine-schema version and supported scope.
3. Create `tests/test_acceptance.py` mapping P0 criteria to golden end-to-end executions.
4. Finalize `pyproject.toml` package metadata and source distribution/wheel inclusion.

**Verification:**

- `.venv/bin/python -m pytest -q --cov=nginx_analyzer --cov-report=term-missing --cov-fail-under=90`
- `.venv/bin/python -m build`
- `python3.11 -m venv /tmp/nginx-analyzer-release-venv && /tmp/nginx-analyzer-release-venv/bin/python -m pip install dist/*.whl`
- `/tmp/nginx-analyzer-release-venv/bin/nginx-analyzer --json tests/fixtures/golden.log | /tmp/nginx-analyzer-release-venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/python benchmarks/run_benchmark.py /tmp/nginx-analyzer-1gb.log --max-seconds 30 --max-rss-mib 512`

**Commit:** `step-9: verify and package MVP release`

## Sprint Boundaries

For the one-weekend constraint, “sprint” means a focused half-day block.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable skeleton, contracts, and correct streaming parser | ~4 hours |
| Saturday PM | 4–5 | All metric semantics and safe terminal report | ~4 hours |
| Sunday AM | 6–7 | Machine outputs and complete failure behavior | ~4 hours |
| Sunday PM | 8–9 | Performance proof, clean package, and release acceptance | ~4 hours |

## Dependency and Scope Rules

- Implement in numerical order; a failed verification keeps the current step active.
- Do not begin output formatting before the golden aggregate model is green.
- Do not optimize before recording a profile and preserving golden tests.
- Do not introduce a database, HTTP API, server, authentication, cloud, Docker, or Kubernetes.
- Gzip and custom formats remain P2 and are excluded from this nine-step MVP.
- Changes to formulas, URL normalization, timestamp behavior, output schema, or exit codes require updates to `PRD.md` and `PROJECT_ARCHITECTURE.md` before code.
