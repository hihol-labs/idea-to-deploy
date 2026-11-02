# Implementation Plan: nginx-stream-report

This is an eight-step, one-weekend plan ordered first by architectural dependency and then by RICE value. No step is complete until its listed checks run green. The complete exit-code contract throughout implementation is `0/1/2/3/4`: success, internal error, CLI usage error, input error, and unique-cardinality exhaustion.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml` and `src/` package | Every test and console invocation depends on packaging | 0.5 h |
| 2 | Typed dataclass contracts | Parser, aggregator, and renderers need one schema | 0.5 h |
| 3 | Golden fixtures and benchmark generator | Prevents implementation-specific acceptance criteria | 0.5 h |
| 4 | Test/lint/type-check configuration | Gives every later step a repeatable gate | 0.5 h |

No database, auth, Docker, service deployment, or CI deployment runway is needed for this local-only CLI.

## STEP 1: Package and Contract Skeleton

**Goal:** A pip-installable Python 3.11 package exposes a Click command and typed report contracts.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections Component Model, Data Model, Packaging and Deployment.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click/Rich dependencies, test tools, and the `nginx-stream-report` entry point.
2. Create `src/nginx_stream_report/__init__.py`, `__main__.py`, and `cli.py` with help/version and placeholder orchestration only.
3. Create `src/nginx_stream_report/models.py` with the five specified dataclasses and invariants.
4. Create `tests/test_models.py` and `tests/test_cli.py` for imports, help, version, and dataclass validation.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_models.py tests/test_cli.py -q`
- `nginx-stream-report --help`

**Commit:** `step-1: scaffold package and domain contracts`

## STEP 2: Streaming Input and Combined-Log Parser

**Goal:** File and stdin lines become validated `ParsedRequest` values without whole-input buffering.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Parsing Contract and CLI Interface; `PRD.md` FR-1.

**Tasks:**

1. Create `src/nginx_stream_report/input.py` with context-managed file/stdin iteration.
2. Create `src/nginx_stream_report/parser.py` with one compiled combined-format parser and classified malformed results.
3. Add `tests/fixtures/access_combined.log` and `tests/fixtures/access_malformed.log` with IPv4, IPv6, offsets, quotes, `-` bytes, and invalid cases.
4. Create `tests/test_parser.py` and `tests/test_input.py`, including a spy stream that fails if full-file reads occur.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py tests/test_input.py -q`
- `python3.11 -m ruff check src tests`
- `python3.11 -m mypy src`

**Commit:** `step-2: add streaming input and nginx parser`

## STEP 3: One-Pass Aggregation and Cardinality Guard

**Goal:** One pass computes all raw counters and deterministically stops at the User-Agent cap.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Data Model and Streaming Invariants; `PRD.md` FR-2 through FR-5.

**Tasks:**

1. Create `src/nginx_stream_report/aggregator.py` for IP, 4xx/5xx URL, hourly, malformed, total, and User-Agent state.
2. Add a typed `UniqueCardinalityExhausted` exception that is raised before inserting the cap-plus-one value.
3. Create `tests/test_aggregator.py` for boundary statuses, repeated agents, cap/cap+1, timezones, and malformed accounting.
4. Add a high-cardinality synthetic test that proves no partial report is returned after exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_aggregator.py -q`
- `python3.11 -m pytest --cov=nginx_stream_report --cov-report=term-missing -q`

**Commit:** `step-3: implement streaming aggregations and UA guard`

## STEP 4: Report Finalization and Formulas

**Goal:** Raw state becomes a deterministic report containing top-10 rankings, 24 hourly percentages, and exact User-Agent share.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Data Model; `PRD.md` FR-2 through FR-5.

**Tasks:**

1. Create `src/nginx_stream_report/report.py` with deterministic count-descending/key-ascending ranking.
2. Implement 24 buckets using `100 × hourly_request_count / total_valid_requests` and safe zero-input handling.
3. Implement unique share as a percentage and centralize two-decimal serialization policy without rounding internal values.
4. Create `tests/test_report.py` for top-10 truncation, ties, formula totals, empty input, and rounding edges.

**Verification:**

- `python3.11 -m pytest tests/test_report.py -q`
- `python3.11 -m pytest tests/test_aggregator.py tests/test_report.py -q`

**Commit:** `step-4: finalize deterministic report metrics`

## STEP 5: Rich, JSON, and CSV Renderers

**Goal:** The same report renders as safe colored text, stable JSON, or normalized CSV.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface Outputs; `PRD.md` FR-6.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/__init__.py` and `rich_text.py` with escaped values and color policy.
2. Create `renderers/json_output.py` with the specified schema and ordered 24-hour array.
3. Create `renderers/csv_output.py` using Python `csv` and the five-column normalized schema.
4. Create `tests/test_renderers.py` with golden outputs, quotes/newlines, ANSI absence, and cross-format equality assertions.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `python3.11 -m pytest -q`

**Commit:** `step-5: add text JSON and CSV output`

## STEP 6: CLI Integration and Exit Codes

**Goal:** End-to-end file/stdin execution honors options, stdout/stderr separation, and all exit codes `0/1/2/3/4` including code `4` for unique-cardinality exhaustion.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface and Error Handling; `PRD.md` FR-1, FR-6, FR-7.

**Tasks:**

1. Complete `src/nginx_stream_report/cli.py` orchestration and mutually exclusive option validation.
2. Map unexpected, usage, input/strict, and cardinality failures to `1`, `2`, `3`, and `4` respectively.
3. Create `tests/test_cli_integration.py` covering file/stdin parity, every output mode, malformed behavior, unreadable input, and each exit code.
4. Add subprocess tests that prove stdout contains only complete successful reports and stderr contains diagnostics.

**Verification:**

- `python3.11 -m pytest tests/test_cli_integration.py -q`
- `nginx-stream-report --json tests/fixtures/access_combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-stream-report --csv tests/fixtures/access_combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: integrate CLI and complete exit contract`

## STEP 7: Performance and Resource Gate

**Goal:** Reproducible evidence shows a representative 1 GB input completes in under 30 seconds with acceptable memory.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Performance Design; `STRATEGIC_PLAN.md` KPIs.

**Tasks:**

1. Create `benchmarks/generate_fixture.py` to deterministically generate representative valid/error/high-cardinality lines to a requested byte size.
2. Create `benchmarks/run.sh` to record Python/CPU metadata, elapsed time, and peak RSS without committing the 1 GB fixture.
3. Profile `parser.py` and `aggregator.py`; optimize only measured hotspots while retaining behavior.
4. Create `tests/test_performance_smoke.py` with a small non-hardware-gating regression fixture; keep the 1 GB gate manual/reference-run specific.

**Verification:**

- `python3.11 benchmarks/generate_fixture.py --size-gib 1 --output /tmp/nginx-stream-report-1g.log`
- `/usr/bin/time -v nginx-stream-report --json /tmp/nginx-stream-report-1g.log >/dev/null`
- `python3.11 -m pytest tests/test_performance_smoke.py -q`

**Commit:** `step-7: add reproducible performance gate`

## STEP 8: Release Documentation and Artifact Validation

**Goal:** A clean Python 3.11 environment can build, install, run, and verify the documented CLI contract.

**Time:** ~1.5 hours

**Context:** All blueprint documents, especially `PRD.md` acceptance criteria.

**Tasks:**

1. Update `README.md` with installation, examples, output schemas, privacy note, and exit codes `0/1/2/3/4`, where `4` is unique-cardinality exhaustion.
2. Add `CHANGELOG.md`, `LICENSE`, and package metadata required for an open-source release.
3. Add `tests/test_wheel.py` or an equivalent clean-environment smoke script for wheel installation and console entry point.
4. Run the complete static, unit, integration, coverage, build, artifact, and performance checks; record results without publishing.

**Verification:**

- `python3.11 -m ruff check src tests benchmarks`
- `python3.11 -m mypy src`
- `python3.11 -m pytest --cov=nginx_stream_report --cov-fail-under=90 -q`
- `python3.11 -m build && python3.11 -m twine check dist/*`

**Commit:** `step-8: validate release candidate artifacts`

## Weekend Boundaries

| Block | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable skeleton and correct parsing | ~3 h |
| Saturday PM | 3–4 | Complete metric computation | ~3.5 h |
| Sunday AM | 5–6 | Output and public CLI contract | ~3.5 h |
| Sunday PM | 7–8 | Performance evidence and release readiness | ~3.5 h |

## Completion Gate

Completion requires all P0 acceptance criteria, the full automated test suite, ≥90% coverage, lint/type checks, clean wheel installation, and the documented 1 GB run under 30 seconds. Artifact publication, push, or external release is not part of implementation and requires explicit human confirmation.

