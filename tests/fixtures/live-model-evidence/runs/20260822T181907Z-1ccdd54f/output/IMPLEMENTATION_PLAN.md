# Implementation Plan: nginx-stream-report

## Scope and Delivery Rule

This plan covers only the P0 local CLI in `PRD.md`. It contains eight dependency-ordered steps suitable for one weekend. Each step must leave the repository testable, must update documentation when behavior changes, and must not introduce authentication, a database, an HTTP API, a server, cloud infrastructure, Docker, or Kubernetes.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and test configuration | Every feature needs an installable import/CLI boundary | 1.0 h |
| 2 | Dataclasses, typed failures, and output schema | Parser, aggregation, renderers, and tests need one contract | 1.0 h |
| 3 | Fixture and benchmark strategy | Correctness and performance must be measurable before polish | 0.5 h |

No database schema, authentication system, API skeleton, container, or CI deployment runway is appropriate for this architecture.

## Step 1: Package and CLI Skeleton

**Goal:** A clean Python 3.11 environment can install the project and invoke an empty but correctly validated CLI surface.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface” and “Components and Source Layout”.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click, Rich, pytest tooling, build backend, and `nginx-stream-report` console entry point.
2. Create `src/nginx_stream_report/__init__.py`, `src/nginx_stream_report/__main__.py`, and `src/nginx_stream_report/cli.py`.
3. Create `tests/test_cli.py` for `--help`, `--version`, invalid options, stdin selection, and JSON/CSV mutual exclusion.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`
- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/nginx-stream-report --help`

**Commit:** `step-1: scaffold installable CLI`

## Step 2: Domain Models and Failure Contract

**Goal:** All later modules share typed immutable data and an explicit application failure model.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Components and Source Layout”, “Metric Semantics”, and “Exit Codes”.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with `ParsedRequest`, mutable `AggregateState`, ranked-row, and immutable `Report` dataclasses.
2. Create `src/nginx_stream_report/errors.py` with input, parse/data, and unique-cardinality exception types.
3. Add model invariant and CLI error-mapping tests to `tests/test_models.py` and `tests/test_cli.py`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_models.py tests/test_cli.py -q`
- `.venv/bin/python -m compileall -q src`

**Commit:** `step-2: define report and error contracts`

## Step 3: Combined-Log Streaming Parser

**Goal:** Supported nginx combined lines become minimal `ParsedRequest` values without retaining source lines.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Parsing Contract” and “Streaming and Resource Model”; `PRD.md` FR-001–FR-004.

**Tasks:**

1. Create `src/nginx_stream_report/parser.py` with a compiled anchored grammar or equivalent tokenizer and line-numbered errors.
2. Create `tests/fixtures/combined.log` containing valid IPv4/IPv6, timezone, escaped quote, status-boundary, missing-UA, and malformed cases.
3. Create `tests/test_parser.py` to prove exact extraction, empty-line handling, decoding behavior, and sanitized errors.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py -q`
- `.venv/bin/python -m pytest tests/test_parser.py --cov=nginx_stream_report.parser --cov-fail-under=90`

**Commit:** `step-3: parse nginx combined logs`

## Step 4: Streaming Aggregation and Cardinality Safety

**Goal:** One-pass aggregation produces all four exact metrics and fails safely at the User-Agent ceiling.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Metric Semantics” and “Streaming and Resource Model”; `PRD.md` FR-005–FR-009.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with IP/error-URL counters, 24 fixed hour buckets, exact User-Agent set, and report finalization.
2. Apply deterministic top-10 ordering and retain unrounded percentages in `Report`.
3. Create `tests/test_aggregate.py` for error status boundaries, ties, zero buckets, exact formulas, empty User-Agents, and ceiling exhaustion.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate.py --cov=nginx_stream_report.aggregate --cov-fail-under=95`

**Commit:** `step-4: aggregate exact streaming metrics`

## Step 5: Terminal Renderer

**Goal:** Default output is a readable four-section Rich report with safe color behavior.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Outputs” and “Error Handling and Security”; `PRD.md` FR-010.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/__init__.py` and `src/nginx_stream_report/renderers/terminal.py`.
2. Escape user-derived values, format percentages consistently, and honor `--no-color` and non-TTY output.
3. Create `tests/fixtures/terminal.txt` and terminal golden cases in `tests/test_renderers.py`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py -q -k terminal`
- `.venv/bin/nginx-stream-report --no-color tests/fixtures/combined.log`

**Commit:** `step-5: render safe terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** Pipelines receive stable, ANSI-free machine output with the same report semantics.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Output Schemas and Compatibility” and “CLI Interface”; `PRD.md` FR-011.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/json.py` for schema version 1.
2. Create `src/nginx_stream_report/renderers/csv.py` with normalized RFC 4180 rows.
3. Create `tests/fixtures/report.json`, `tests/fixtures/report.csv`, and parser-backed golden tests in `tests/test_renderers.py`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py -q -k 'json or csv'`
- `.venv/bin/nginx-stream-report --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/nginx-stream-report --csv tests/fixtures/combined.log | .venv/bin/python -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: add stable JSON and CSV output`

## Step 7: End-to-End CLI and Exit Codes

**Goal:** File/stdin ownership, diagnostics, strict mode, rendering, and every documented exit status work as one command.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` entire “CLI Interface”; `PRD.md` release acceptance.

**Tasks:**

1. Complete `src/nginx_stream_report/cli.py` orchestration without full-file reads or partial reports.
2. Extend `tests/test_cli.py` with file/stdin parity, malformed summaries, strict mode, no-valid-data behavior, I/O failure, usage error, cardinality exhaustion, broken pipe, and stdout/stderr isolation.
3. Add `tests/test_integration.py` to compare metric meanings across terminal, JSON, and CSV.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py tests/test_integration.py -q`
- `.venv/bin/python -m pytest -q --cov=nginx_stream_report --cov-fail-under=90`

**Commit:** `step-7: integrate CLI and exit behavior`

## Step 8: Performance, Packaging, and Release Evidence

**Goal:** The exact candidate is installable and has recorded correctness, performance, and memory evidence.

**Time:** ~3 hours

**Context:** `PRD.md` non-functional requirements and release acceptance; `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Create `tests/perf/generate_log.py` as a deterministic streaming generator and `tests/perf/benchmark.py` to record file size, seed, hardware, Python version, elapsed time, and peak RSS.
2. Add packaging metadata and usage documentation to `pyproject.toml` and the project user documentation without changing the product contract.
3. Build wheel/sdist, install the wheel into a new temporary virtual environment, run smoke/golden tests, and record benchmark evidence in the project verification state required by `.itd/VERIFICATION_CONTRACT.json`.

**Verification:**

- `.venv/bin/python -m pytest -q --cov=nginx_stream_report --cov-fail-under=90`
- `.venv/bin/python -m build`
- `.venv/bin/python tests/perf/generate_log.py --size-gib 1 --seed 20260822 --output .benchmark/nginx-1g.log`
- `.venv/bin/python tests/perf/benchmark.py .benchmark/nginx-1g.log --max-seconds 30 --max-rss-mib 256`

**Commit:** `step-8: verify performance and package release`

## Complete Exit-Code Acceptance Matrix

Every implementation step that touches CLI behavior must preserve this mapping:

| Code | Required test scenario |
|---:|---|
| `0` | Valid report, including non-strict skipped malformed records |
| `1` | Missing/unreadable input or read failure |
| `2` | Invalid option, invalid ceiling, or `--json` with `--csv` |
| `3` | Strict malformed record, decoding failure, or zero valid requests |
| `4` | Exact unique User-Agent cardinality ceiling exceeded |

No code may be remapped, omitted, or replaced by a traceback. Acceptance requires current exact-candidate evidence under the repository's Idea to Deploy verification contract; narration alone is not completion.
