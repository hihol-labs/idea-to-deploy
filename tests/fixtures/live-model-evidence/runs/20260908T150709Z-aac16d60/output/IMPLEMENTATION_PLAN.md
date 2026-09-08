# Implementation Plan: nginx-insights

## 1. Delivery Rules

This plan implements the P0 contract in `PRD.md` using the selected architecture in `PROJECT_ARCHITECTURE.md`. It creates no database, API, server, cloud, or Kubernetes resources. Keep one active step at a time, update the specification before changing behavior, and preserve stdout/stderr separation.

The implementation must preserve the complete exit-code contract: `0` success; `1` input/output or unexpected operational failure; `2` usage/configuration error; `3` zero valid requests; `4` unique-cardinality exhaustion.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package metadata and console entry point | Every CLI and packaging test depends on import/install behavior | 0.5 h |
| 2 | Typed models and exit taxonomy | Parser, aggregator, and renderers need stable contracts | 0.5 h |
| 3 | Golden fixtures and test configuration | Behavior must be executable before feature expansion | 0.5 h |
| 4 | Deterministic benchmark generator | Performance work needs a repeatable corpus | 0.5 h |

## STEP 1: Package Skeleton and Contracts

**Goal:** an installable Python 3.11 package exposes a working help/version command and shared types.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 6, and 9; `PRD.md` FR-001 and NFR-006.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, pytest tooling, and the `nginx-insights` console entry point.
2. Create `src/nginx_insights/__init__.py`, `src/nginx_insights/__main__.py`, and `src/nginx_insights/cli.py`.
3. Create `src/nginx_insights/models.py` and `src/nginx_insights/errors.py` with dataclasses and named `0/1/2/3/4` exit constants.
4. Create `tests/test_cli.py` for help and version behavior.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-insights --help`

**Commit:** `step-1: establish package and CLI contracts`

## STEP 2: Log Parser and Normalization

**Goal:** common/combined nginx lines become typed records, and malformed lines become explicit invalid results.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 11; `PRD.md` FR-002 and FR-003.

**Tasks:**

1. Create `src/nginx_insights/parser.py` for offset-aware timestamps, status validation, optional request/UA fields, IPv4, and IPv6.
2. Create `src/nginx_insights/normalize.py` to remove URL query/fragment data and preserve path semantics.
3. Create `tests/fixtures/access.log` and `tests/fixtures/malformed.log` with domain-specific cases.
4. Create `tests/test_parser.py` and `tests/test_normalize.py` covering declared boundaries.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py tests/test_normalize.py -q`

**Commit:** `step-2: parse and normalize nginx records`

## STEP 3: Streaming Aggregation Core

**Goal:** valid records update exact counters in one pass without retaining raw lines.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 7; `PRD.md` FR-004 through FR-008.

**Tasks:**

1. Create `src/nginx_insights/aggregate.py` with counts for IPs, 4xx/5xx paths, 24 hourly buckets, valid/invalid lines, and bounded unique UAs.
2. Create `src/nginx_insights/report.py` for deterministic top-10 selection and report snapshots.
3. Calculate hourly percentages with `100 × hourly_request_count / total_valid_requests` and UA share using the architecture denominator.
4. Create `tests/test_aggregate.py` for status boundaries, ties, absent UAs, percentages, and cap overflow.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`

**Commit:** `step-3: add one-pass report aggregation`

## STEP 4: Input Orchestration and Failure Mapping

**Goal:** stdin and one or more files form a logical stream with deterministic diagnostics and exit codes.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 6; `PRD.md` FR-001, FR-009, and FR-014.

**Tasks:**

1. Create `src/nginx_insights/input.py` for buffered stdin/file iteration and ownership-aware closing.
2. Wire parsing and aggregation through `src/nginx_insights/cli.py`.
3. Map unreadable input to 1, invalid options to 2, zero valid records to 3, and UA-cap exhaustion to 4.
4. Extend `tests/test_cli.py` for multiple files, `-`, empty/all-invalid input, file failure, and cap exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`

**Commit:** `step-4: orchestrate streams and exit behavior`

## STEP 5: JSON Renderer

**Goal:** `--json` emits a stable, parseable, versioned report with no non-JSON stdout text.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` section 6 Outputs; `PRD.md` FR-011.

**Tasks:**

1. Create `src/nginx_insights/render_json.py` using the standard JSON serializer.
2. Create `tests/golden/report.json` and `tests/test_render_json.py` for schema keys, types, ordering, Unicode, and percentage precision.
3. Integrate `--json` and stderr-only diagnostics in `src/nginx_insights/cli.py`.

**Verification:**

- `python3.11 -m pytest tests/test_render_json.py tests/test_cli.py -q`
- `nginx-insights --json tests/fixtures/access.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: add stable JSON output`

## STEP 6: CSV Renderer

**Goal:** `--csv` emits the fixed long-form schema and safely escapes arbitrary keys.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` section 6 Outputs; `PRD.md` FR-012.

**Tasks:**

1. Create `src/nginx_insights/render_csv.py` with standard-library CSV writing.
2. Create `tests/golden/report.csv` and `tests/test_render_csv.py` for the exact header, metric rows, quoting, and stable order.
3. Enforce `--json`/`--csv` mutual exclusion in `src/nginx_insights/cli.py`.

**Verification:**

- `python3.11 -m pytest tests/test_render_csv.py tests/test_cli.py -q`
- `nginx-insights --csv tests/fixtures/access.log | python3.11 -c "import csv,sys; list(csv.DictReader(sys.stdin))"`

**Commit:** `step-6: add pipeline-safe CSV output`

## STEP 7: Rich Terminal Renderer

**Goal:** default output is a readable four-section terminal report with correct color behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 6 Outputs; `PRD.md` FR-010 and FR-013.

**Tasks:**

1. Create `src/nginx_insights/render_terminal.py` with literal-text Rich tables for all four metrics.
2. Integrate auto/forced/disabled color handling and reject color flags in machine modes.
3. Create `tests/test_render_terminal.py` for headings, values, no-color output, and control/markup-like keys.

**Verification:**

- `python3.11 -m pytest tests/test_render_terminal.py tests/test_cli.py -q`
- `nginx-insights --no-color tests/fixtures/access.log`

**Commit:** `step-7: render the default terminal report`

## STEP 8: End-to-End Contract and Quality Tests

**Goal:** all modes agree on metrics, and every documented boundary is regression-tested.

**Time:** ~2 hours

**Context:** all P0 acceptance criteria in `PRD.md`; `PROJECT_ARCHITECTURE.md` sections 7, 8, and 11.

**Tasks:**

1. Create `tests/test_end_to_end.py` to compare terminal, JSON, and CSV values from the same fixture.
2. Create `tests/test_exit_codes.py` covering exactly `0/1/2/3/4`, including code 4 for unique-cardinality exhaustion.
3. Add coverage and static-check configuration to `pyproject.toml`.
4. Test pipe closure, Unicode, dangerous terminal sequences, and mixed valid/invalid streams.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_insights --cov-report=term-missing --cov-fail-under=90`
- `python3.11 -m compileall -q src tests`

**Commit:** `step-8: lock end-to-end behavior`

## STEP 9: Performance Qualification

**Goal:** demonstrate the 1 GB/30-second target and record peak memory on the reference laptop.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 10; `PRD.md` NFR-001 through NFR-003.

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically stream a representative corpus without committing the generated log.
2. Create `benchmarks/run_benchmark.py` to run three trials and report size, wall time, throughput, peak RSS, Python, OS, CPU, and storage context.
3. Create `tests/test_performance_smoke.py` for a small non-release regression and mark it `performance`.
4. Optimize only measured hot spots while preserving golden results.

**Verification:**

- `python3.11 benchmarks/generate_log.py --bytes 1073741824 --output /tmp/nginx-insights-1gb.log`
- `python3.11 benchmarks/run_benchmark.py --input /tmp/nginx-insights-1gb.log --trials 3 --max-seconds 30`
- `python3.11 -m pytest -q -m performance`

**Commit:** `step-9: qualify throughput and memory`

## STEP 10: Packaging and Release Readiness

**Goal:** a clean Python 3.11 environment can build, install, run, and understand the tool.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` NFR-006 and release criteria.

**Tasks:**

1. Update `README.md` with verified install, examples, schemas, exit codes, and limitations.
2. Add `LICENSE` with the selected open-source license and `CHANGELOG.md` with the initial contract.
3. Build wheel/sdist and inspect their contents.
4. Run the full suite and a clean-virtual-environment smoke test.

**Verification:**

- `python3.11 -m pytest -q`
- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-insights-release-venv && /tmp/nginx-insights-release-venv/bin/pip install dist/*.whl && /tmp/nginx-insights-release-venv/bin/nginx-insights --help`

**Commit:** `step-10: prepare installable release`

## Sprint Boundaries

For the one-weekend scope, “sprint” means a bounded work block rather than a multi-week ceremony.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1-2 | Executable contracts and correct parsing | 3 hours |
| Saturday PM | 3-4 | Complete streaming computation and failures | 4 hours |
| Sunday AM | 5-7 | All output modes | 3.5 hours |
| Sunday PM | 8-10 | Quality, performance, and package readiness | 6 hours |

## Dependencies and Parallelism

The critical path is 1 → 2 → 3 → 4 → 5/6/7 → 8 → 9 → 10. Renderer steps 5–7 may be implemented independently only after `ReportSnapshot` is stable, but WIP remains one step. Performance changes happen after correctness is frozen so they can be checked against golden outputs.
