# Implementation Plan: nginx-log-insights

## Scope and Sequencing

This is an eight-step, one-weekend plan for the P0 product. It orders work by architectural dependency and then by RICE value. P1 gzip/custom formats and P2 configurable top-N/approximation are deferred. Product code is not part of this blueprint session.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package metadata and `src/` layout | Every test and feature needs an importable package and console entry point | 1 hour |
| 2 | Domain and failure contracts | Prevent parser, aggregator, renderer, and CLI semantics from drifting | 1 hour |
| 3 | Test fixtures and benchmark generator | Makes correctness and performance measurable before feature completion | 1.5 hours |
| 4 | CI/test commands | Keeps Python 3.11, packaging, and output contracts repeatable | 1 hour |

No database schema, authentication system, API scaffold, Docker environment, or deployment infrastructure belongs in the runway because the accepted architecture excludes them.

## Step 1: Package Skeleton and Executable Contract

**Goal:** A Python 3.11 package builds and exposes an inert, testable Click entry point with the final option surface.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface,” “Components and Responsibilities,” and “Deployment and Distribution.”

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click and Rich runtime dependencies, pytest tooling, wheel metadata, and `nginx-log-insights = nginx_log_insights.cli:main`.
2. Create `src/nginx_log_insights/__init__.py` and `src/nginx_log_insights/__main__.py`.
3. Create `src/nginx_log_insights/cli.py` with all documented options, mutual exclusion, stdin/path validation, and placeholder orchestration that is not accepted as feature completion.
4. Create `tests/test_cli_contract.py` for help, version, invalid option, JSON/CSV conflict, and `--max-unique` validation.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli_contract.py -q`
- `nginx-log-insights --help`

**Commit:** `step-1: scaffold package and CLI contract`

## Step 2: Domain Models, Errors, and Fixtures

**Goal:** Typed data and failure semantics establish one shared contract for all stages.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Streaming State” and “Exit Codes”; `PRD.md` FR-09.

**Tasks:**

1. Create `src/nginx_log_insights/models.py` with frozen `LogRecord`, `RankedCount`, `HourlyBucket`, `UserAgentSummary`, and `Report` dataclasses.
2. Create `src/nginx_log_insights/errors.py` with `InputError` and `CardinalityLimitError` carrying safe diagnostics.
3. Create `tests/fixtures/valid_combined.log`, `tests/fixtures/mixed_combined.log`, and focused malformed/IPv6/quoting fixtures without sensitive real data.
4. Extend `tests/test_cli_contract.py` to inject each domain failure and assert the complete contract: `0` success, `1` input/data failure, `2` CLI usage failure, `3` unexpected internal failure, and `4` unique-cardinality exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_cli_contract.py -q`
- `python3.11 -m pytest --collect-only -q`

**Commit:** `step-2: define domain and exit-code contracts`

## Step 3: Streaming Input and Combined-Log Parser

**Goal:** Files and stdin yield validated records one line at a time, with malformed records counted safely.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Inputs,” “Parsing Contract,” and “Failure, Resource, and Security Boundaries”; `PRD.md` US-1.

**Tasks:**

1. Create `src/nginx_log_insights/inputs.py` with read-only file/stdin context management, sequential multi-file iteration, decoding handling, and a 1 MiB line limit.
2. Create `src/nginx_log_insights/parser.py` with a compiled combined-format parser and explicit timestamp, status, request, and User-Agent validation.
3. Create `tests/test_inputs.py` for stdin, multiple files, unreadable paths, decode failure, and closure behavior.
4. Create `tests/test_parser.py` for IPv4, IPv6, offsets, quoting, query strings, empty User-Agent, error statuses, and every malformed fixture.

**Verification:**

- `python3.11 -m pytest tests/test_inputs.py tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_log_insights.parser --cov-report=term-missing`

**Commit:** `step-3: stream and parse combined logs`

## Step 4: Exact Streaming Aggregation

**Goal:** One pass produces exact counters, hourly buckets, and User-Agent cardinality with deterministic top-10 results and explicit exhaustion.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Streaming State” and “Performance and Capacity”; `PRD.md` US-2 through US-5.

**Tasks:**

1. Create `src/nginx_log_insights/aggregate.py` with an `Aggregator` that tracks line totals, IP counts, 400–599 URL counts, 24 hours, and distinct non-empty User-Agents.
2. Enforce `max_unique` before inserting a new key into each guarded structure and raise `CardinalityLimitError` without partial finalization.
3. Implement deterministic top-10 selection and percentage calculations; hourly percentages must use `100 × hourly_request_count / total_valid_requests`.
4. Create `tests/test_aggregate.py` for exact counts, 399/400/599/600 boundaries, ties, all hours, rounding, empty User-Agents, and just-below/at/above cardinality ceilings.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_log_insights.aggregate --cov-report=term-missing`

**Commit:** `step-4: implement guarded streaming metrics`

## Step 5: Text, JSON, and CSV Renderers

**Goal:** The same report is emitted as terminal text, JSON schema v1, or normalized CSV without cross-stream contamination.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs”; `PRD.md` US-6 and “Output Contract.”

**Tasks:**

1. Create `src/nginx_log_insights/renderers/__init__.py` and `src/nginx_log_insights/renderers/text.py` with Rich summary/ranking/hour tables and auto color detection.
2. Create `src/nginx_log_insights/renderers/json.py` using the standard JSON encoder and exact documented field names/types.
3. Create `src/nginx_log_insights/renderers/csv.py` using `csv.DictWriter` and deterministic normalized row order.
4. Create `tests/golden/report.json`, `tests/golden/report.csv`, and `tests/test_renderers.py` to verify schemas, quoting, percentages, tie order, ANSI behavior, and injected streams.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `python3.11 -m pytest tests/test_renderers.py --cov=nginx_log_insights.renderers --cov-report=term-missing`

**Commit:** `step-5: add deterministic report renderers`

## Step 6: End-to-End CLI Orchestration

**Goal:** The installed command connects input, parsing, aggregation, rendering, diagnostics, and all application exit codes.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` entire “CLI Interface”; `PRD.md` all P0 stories.

**Tasks:**

1. Complete `src/nginx_log_insights/cli.py` orchestration with no output until aggregation has finalized successfully.
2. Map Click usage errors to `2`, `InputError` to `1`, `CardinalityLimitError` to `4`, unexpected internal failures to `3`, and successful output to `0`.
3. Create `tests/test_cli_integration.py` for files, stdin, multiple files, malformed-line diagnostics, text/JSON/CSV, colors, no-valid-records, and exact stdout/stderr separation.
4. Add explicit cases proving `0/1/2/3/4`; code `4` must mean unique-cardinality exhaustion and must never be remapped.

**Verification:**

- `python3.11 -m pytest tests/test_cli_integration.py -q`
- `python3.11 -m nginx_log_insights --json tests/fixtures/valid_combined.log | python3.11 -m json.tool >/dev/null`
- `python3.11 -m nginx_log_insights --csv tests/fixtures/valid_combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: integrate CLI pipeline and failures`

## Step 7: Performance and Resource Acceptance

**Goal:** Measured evidence establishes whether the implementation meets 1 GB under 30 seconds and its memory/cardinality boundaries.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Performance and Capacity”; `PRD.md` NFR-01, NFR-02, and NFR-04.

**Tasks:**

1. Create `benchmarks/generate_log.py` to reproducibly generate nonsensitive combined-format input of an exact requested byte size and controlled cardinalities.
2. Create `benchmarks/run_benchmark.sh` to record environment, bytes, elapsed time, peak RSS, valid count, and output digest without timing fixture generation.
3. Create `tests/test_performance_smoke.py` for a small CI-scale linearity and memory-regression smoke check.
4. Profile only after the baseline; optimize measured parser/allocation hotspots while preserving golden outputs and exact semantics.
5. Record reference results in `benchmarks/RESULTS.md`, including whether the release gate passed. Do not claim the target without this evidence.

**Verification:**

- `python3.11 benchmarks/generate_log.py --bytes 1073741824 --output /tmp/nginx-log-insights-1g.log`
- `bash benchmarks/run_benchmark.sh /tmp/nginx-log-insights-1g.log`
- `python3.11 -m pytest tests/test_performance_smoke.py -q`

**Commit:** `step-7: verify throughput and memory targets`

## Step 8: Packaging, Security, and Release Gate

**Goal:** A clean environment can install and run the wheel, and all product acceptance evidence is recorded.

**Time:** ~2.5 hours

**Context:** `STRATEGIC_PLAN.md` “Definition of Done”; `PRD.md` “Release Acceptance”; `PROJECT_ARCHITECTURE.md` “Deployment and Distribution.”

**Tasks:**

1. Create or finish `README.md` with installation, examples, schemas, malformed-line behavior, cardinality limits, performance conditions, and exit codes.
2. Create `LICENSE` with the selected open-source license and `CHANGELOG.md` for the initial release.
3. Create `tests/test_package_smoke.sh` to build a wheel, install it into a fresh Python 3.11 virtual environment, and exercise help plus a fixture report.
4. Review dependencies and malicious log fixtures; verify no network access, raw-line leakage, unsafe formatting, or retained data.
5. Run the full suite and verify every P0 acceptance criterion, including all `0/1/2/3/4` statuses and the current 1 GB result.

**Verification:**

- `python3.11 -m pytest --cov=nginx_log_insights --cov-report=term-missing --cov-fail-under=90`
- `python3.11 -m build`
- `bash tests/test_package_smoke.sh`
- `python3.11 -m pip check`

**Commit:** `step-8: complete release acceptance`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Executable contract, domain model, and trustworthy parsing | ~6 hours |
| Saturday PM | 4–5 | All metrics and all output formats | ~6 hours |
| Sunday AM | 6–7 | End-to-end behavior and measured performance | ~5.5 hours |
| Sunday PM | 8 | Packaging, security checks, and release decision | ~2.5 hours |

## Cross-Cutting Verification Contract

Every implementation step must preserve:

- Python 3.11 compatibility and a pip-installable wheel.
- One process, one streaming pass, and no database, API, server, authentication, cloud, or Kubernetes assets.
- The complete exit-code contract: `0` success, `1` input/data failure, `2` CLI usage failure, `3` unexpected internal failure, `4` unique-cardinality exhaustion.
- Exact metrics and the literal hourly formula `100 × hourly_request_count / total_valid_requests`.
- Deterministic rankings and JSON/CSV ordering.
- Tests and evidence before a step is marked complete.
