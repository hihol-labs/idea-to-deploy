# Implementation Plan: nginx-log-top

This plan implements the P0 contract in `PRD.md` using the architecture in `PROJECT_ARCHITECTURE.md`. It contains documentation only; no listed product file exists yet.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console-entry skeleton | Every behavior and test needs stable import/CLI paths | 1 hour |
| 2 | Fixture corpus and output contracts | Prevents parser and renderer ambiguity | 1.5 hours |
| 3 | Benchmark generator and measurement protocol | Tests the highest technical risk before polish | 1 hour |
| 4 | CI test/build matrix | Makes Python 3.11 and wheel checks repeatable | 1 hour |

No database, authentication system, API, Docker, or deployment environment belongs in the runway.

## STEP 1: Package and Contract Skeleton

**Goal:** The package builds, the console command resolves, and exit constants are centralized.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections Component Boundaries, CLI Interface, Deployment and Packaging.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click, Rich, build metadata, and the `nginx-log-top` console script.
2. Create `src/nginx_log_top/__init__.py`, `src/nginx_log_top/__main__.py`, and `src/nginx_log_top/cli.py`.
3. Create `src/nginx_log_top/errors.py` with typed failures and the complete `0/1/2/3/4` contract: 0 success, 1 input I/O, 2 usage, 3 parse/output data failure, 4 unique-cardinality exhaustion.
4. Create `tests/test_cli_contract.py` for help, version, and invalid option behavior.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `python3.11 -m pytest tests/test_cli_contract.py -q`
- `nginx-log-top --help`

**Commit:** `step-1: establish package and CLI contracts`

## STEP 2: Domain Models and Combined-Log Parser

**Goal:** Supported lines parse into typed records, and malformed lines have precise diagnostics.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Data Model and Parsing Contract; `PRD.md` P0.2.

**Tasks:**

1. Create `src/nginx_log_top/models.py` with the documented dataclasses.
2. Create `src/nginx_log_top/parser.py` with one compiled combined-format grammar, timestamp parsing, request splitting, and safe field unescaping.
3. Create `tests/fixtures/access_combined.log` and `tests/fixtures/access_malformed.log` covering IPv4, IPv6, offsets, placeholders, escapes, 2xx/4xx/5xx, and malformed records.
4. Create `tests/test_parser.py` with exact parsed-field and rejection assertions.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_log_top.parser --cov-fail-under=95`

**Commit:** `step-2: parse nginx combined access logs`

## STEP 3: Streaming Aggregation and Cardinality Guard

**Goal:** A single pass computes all four correct reports without retaining raw requests.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Metric Semantics and Streaming and Resource Bounds; `PRD.md` P0.1/P0.3.

**Tasks:**

1. Create `src/nginx_log_top/aggregate.py` with counters, 24 hour buckets, exact User-Agent set, and deterministic top-10 finalization.
2. Add the configurable exact-cardinality ceiling and raise the typed exit-4 failure before an inexact result can be finalized.
3. Create `tests/test_aggregate.py` for rankings, tie order, error filtering, zero valid records, percentage formula, and the boundary at/over the unique limit.
4. Add invariant tests for totals and hourly counts.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_log_top.aggregate --cov-fail-under=95`

**Commit:** `step-3: add one-pass metric aggregation`

## STEP 4: Text Renderer

**Goal:** Default TTY output provides readable, safe Rich tables for every metric.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Outputs, Authentication and Trust Boundary; `PRD.md` P0.4.

**Tasks:**

1. Create `src/nginx_log_top/renderers/__init__.py` and `src/nginx_log_top/renderers/text.py`.
2. Escape untrusted IP/URL/User-Agent-derived content as plain text and preserve meaning without color.
3. Create `tests/golden/report.txt` and `tests/test_text_renderer.py` for TTY/non-TTY and forced color behavior.

**Verification:**

- `python3.11 -m pytest tests/test_text_renderer.py -q`
- `python3.11 -m pytest tests/test_text_renderer.py -k 'control or color' -q`

**Commit:** `step-4: render safe terminal report`

## STEP 5: JSON and CSV Renderers

**Goal:** Both pipeline formats serialize the same result with stable schema v1 semantics.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Output Schemas; `PRD.md` P0.4.

**Tasks:**

1. Create `src/nginx_log_top/renderers/json.py` with the documented object structure.
2. Create `src/nginx_log_top/renderers/csv.py` with `report,key,count,percentage` long-form rows.
3. Create `tests/golden/report.json`, `tests/golden/report.csv`, and `tests/test_structured_renderers.py`.
4. Verify standard-library parsing, UTF-8, newline handling, numeric types, and absence of ANSI escapes.

**Verification:**

- `python3.11 -m pytest tests/test_structured_renderers.py -q`
- `python3.11 -m json.tool tests/golden/report.json >/dev/null`

**Commit:** `step-5: add stable JSON and CSV reports`

## STEP 6: End-to-End CLI and Exit Mapping

**Goal:** Files and stdin connect to aggregation/rendering, with the complete failure contract enforced.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface; `PRD.md` P0.1/P0.5.

**Tasks:**

1. Complete `src/nginx_log_top/cli.py` option validation, buffered file/stdin lifecycle, strict/lenient handling, renderer selection, stderr diagnostics, and broken-pipe behavior.
2. Create `tests/test_cli_integration.py` to compare file/stdin values and golden outputs.
3. Add explicit cases for `0/1/2/3/4`, preserving code 4 for unique-cardinality exhaustion.
4. Ensure partial completed-looking reports are not emitted after fatal failures.

**Verification:**

- `python3.11 -m pytest tests/test_cli_integration.py -q`
- `python3.11 -m pytest -q`

**Commit:** `step-6: wire streaming CLI and exit codes`

## STEP 7: Performance and Resource Gate

**Goal:** The known-result 1 GB fixture finishes under 30 seconds with recorded peak memory.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Performance Verification; `STRATEGIC_PLAN.md` KPIs and Risks.

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` with deterministic volume, status, hour, IP, URL, and User-Agent distributions.
2. Create `tests/performance/test_one_gb.py` to validate known totals separately from timing.
3. Create `docs/PERFORMANCE.md` to record hardware, OS, Python, storage, command, elapsed time, peak RSS, and results.
4. Profile if the target fails; optimize measured parser/allocation hotspots without changing the result contract.

**Verification:**

- `python3.11 scripts/generate_benchmark_log.py --bytes 1073741824 /tmp/nginx-log-top-1gb.log`
- `/usr/bin/time -v nginx-log-top --json /tmp/nginx-log-top-1gb.log >/tmp/nginx-log-top-result.json`
- `python3.11 -m pytest tests/performance/test_one_gb.py -q`

**Commit:** `step-7: validate one-gigabyte performance target`

## STEP 8: Packaging, Documentation, and Release Candidate

**Goal:** A clean Python 3.11 environment can install the wheel and run documented flows.

**Time:** ~2 hours

**Context:** `README.md`; `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` Release Criteria.

**Tasks:**

1. Finalize `README.md` command examples, schemas, format support, limitations, and performance disclosure.
2. Create `LICENSE` using the selected open-source license and add `CHANGELOG.md` for the first release.
3. Create `.github/workflows/ci.yml` for lint, test, coverage, package build, and clean wheel smoke tests on Python 3.11.
4. Validate sdist/wheel metadata and that package data excludes test/benchmark logs.

**Verification:**

- `python3.11 -m pytest --cov=nginx_log_top --cov-fail-under=90`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-log-top-smoke && /tmp/nginx-log-top-smoke/bin/pip install dist/*.whl && /tmp/nginx-log-top-smoke/bin/nginx-log-top --help`

**Commit:** `step-8: prepare verified release candidate`

## Sprint Boundaries

The one-weekend constraint uses two compact delivery blocks rather than week-long sprints.

| Block | Steps | Goal | Duration |
|---|---|---|---|
| Saturday | 1–3 | Executable skeleton, parsing, and correct aggregation | ~5.5 hours |
| Sunday | 4–8 | Outputs, CLI integration, performance, and packaging | ~9 hours |

## Dependency and Acceptance Order

Steps are sequential because parser/model contracts feed aggregation, the canonical result feeds renderers, and only the integrated CLI can supply meaningful performance and packaging evidence. WIP remains one step. A step is accepted only after its listed checks pass; narration or a later step does not substitute for earlier evidence.

## Deferred Work

P1/P2 features—configurable top-N, JSON Schema publication, gzip, custom log formats, and network grouping—begin only after the release criteria in `PRD.md` pass. Authentication, database, API, server, cloud, and Kubernetes remain excluded.
