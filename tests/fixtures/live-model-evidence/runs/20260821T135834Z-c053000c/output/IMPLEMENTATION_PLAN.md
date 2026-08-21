# Implementation Plan: Nginx Stream Analyzer

This plan implements [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) and the P0 requirements in [PRD.md](PRD.md). It contains eight dependency-ordered steps sized for one weekend. No step may weaken the complete exit-code contract: `0` success, `1` operational failure, `2` usage error, `3` non-empty input with zero valid records, and `4` unique-cardinality exhaustion.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package/console-entry skeleton | All tests and commands need an importable package | 1 hour |
| 2 | Golden log fixtures and schemas | Fixes behavior before implementation | 1 hour |
| 3 | Typed domain/error models | Parser, accumulator, and CLI share these contracts | 1 hour |
| 4 | Benchmark generator protocol | Makes the 1 GB target reproducible before optimization | 1 hour |

There is no database schema, authentication system, API, Docker setup, or deployment infrastructure in the runway because the approved architecture explicitly excludes them.

## Step 1: Package and Contract Skeleton

**Goal:** A pip-installable Python 3.11 package exposes a Click command with help/version and frozen output contracts.

**Time:** ~2 hours

**Context:** Architecture sections 3, 6, and 8; PRD FR-1 and FR-7.

**Tasks:**

1. Create `pyproject.toml` with build metadata, Python 3.11 constraint, Click/Rich dependencies, and the `nginx-stream-analyzer` console entry point.
2. Create `src/nginx_stream_analyzer/__init__.py`, `cli.py`, `errors.py`, and `models.py`.
3. Define named constants/enums for exits `0/1/2/3/4`; define frozen dataclasses without behavior.
4. Create `tests/test_cli_contract.py` for help, version, mutual exclusion, and exit-code constants.

**Verification:**

- `python3.11 -m pip install -e .`
- `nginx-stream-analyzer --help`
- `python3.11 -m pytest tests/test_cli_contract.py -q`

**Commit:** `step-1: establish package and CLI contracts`

## Step 2: Parser and Golden Fixtures

**Goal:** Individual standard combined-log lines parse deterministically into `AccessRecord`, while invalid lines return typed failures.

**Time:** ~3 hours

**Context:** Architecture sections 4 and 5; PRD FR-2.

**Tasks:**

1. Create `src/nginx_stream_analyzer/parser.py` with a compiled, anchored parser and explicit request/status/timestamp validation.
2. Create `tests/fixtures/combined_valid.log`, `combined_mixed.log`, and `combined_invalid.log` with IPv4, IPv6, escaped quotes, 4xx/5xx, and malformed cases.
3. Create `tests/test_parser.py` covering every parsing rule and UTF-8 replacement behavior.
4. Record the fixed MVP grammar in `README.md` without promising configurable formats.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_stream_analyzer.parser --cov-branch --cov-fail-under=90`

**Commit:** `step-2: parse supported nginx combined logs`

## Step 3: Streaming Aggregation and Cardinality Guard

**Goal:** One-pass aggregation produces all metric inputs and deterministically stops at the distinct-key budget.

**Time:** ~4 hours

**Context:** Architecture sections 4 and 7; PRD FR-3 through FR-6 and NFR-2.

**Tasks:**

1. Create `src/nginx_stream_analyzer/aggregate.py` with counters, a 24-element hour array, User-Agent set, invalid count, and pre-insert budget checks.
2. Create `src/nginx_stream_analyzer/report.py` to finalize top-10 rankings and percentages.
3. Calculate every hourly value with `100 × hourly_request_count / total_valid_requests`; calculate unique User-Agent percentage over the same valid-record denominator.
4. Create `tests/test_aggregate.py` for 4xx/5xx boundaries, deterministic ties, zero totals, invalid counts, and exhaustion mapped to exit `4`.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_stream_analyzer.aggregate --cov=nginx_stream_analyzer.report --cov-branch --cov-fail-under=90`

**Commit:** `step-3: add bounded streaming metrics`

## Step 4: Text, JSON, and CSV Renderers

**Goal:** One report model renders as readable Rich text and stable machine formats.

**Time:** ~3 hours

**Context:** Architecture CLI Interface and section 3; PRD FR-7.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/__init__.py`, `text.py`, `json.py`, and `csv.py`.
2. Implement Rich tables with escaped markup, auto color detection, `--no-color`, and `NO_COLOR`.
3. Implement JSON schema version 1 and normalized CSV columns `schema_version,section,key,count,percentage`.
4. Create `tests/test_renderers.py` plus `tests/golden/expected.json` and `tests/golden/expected.csv`.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `python3.11 -m pytest tests/test_renderers.py -k 'no_ansi or schema or deterministic' -q`

**Commit:** `step-4: render text JSON and CSV reports`

## Step 5: End-to-End CLI and Error Mapping

**Goal:** File and stdin inputs run through the full pipeline with clean stdout/stderr and exact exit behavior.

**Time:** ~3 hours

**Context:** Architecture CLI Interface; PRD FR-1, FR-2, FR-7, FR-8.

**Tasks:**

1. Complete `src/nginx_stream_analyzer/cli.py` orchestration without embedding parser or metric logic.
2. Map successful/empty input to `0`, I/O failures to `1`, Click usage failures to `2`, zero-valid non-empty data to `3`, and cardinality exhaustion to `4`.
3. Handle `BrokenPipeError` as an operational termination without a traceback.
4. Create `tests/test_cli_integration.py` covering file/stdin parity, all output modes, diagnostics, and exits `0/1/2/3/4`.

**Verification:**

- `python3.11 -m pytest tests/test_cli_integration.py -q`
- `nginx-stream-analyzer --json tests/fixtures/combined_valid.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: integrate CLI pipeline and failures`

## Step 6: Correctness and Property Coverage

**Goal:** Cross-module invariants are protected against regression on larger generated datasets.

**Time:** ~3 hours

**Context:** PRD acceptance criteria and Architecture section 10.

**Tasks:**

1. Create `tests/test_invariants.py` for `sum(hour_counts) == total_valid_requests`, ranking length ≤ 10, and percentage totals near 100% when valid records exist.
2. Add parameterized request/status/hour/cardinality cases without introducing a required property-testing dependency.
3. Add subprocess assertions that JSON/CSV stdout is parseable and stderr-only diagnostics do not corrupt it.
4. Ensure error tests individually assert the complete `0/1/2/3/4` mapping.

**Verification:**

- `python3.11 -m pytest -q`
- `python3.11 -m pytest --cov=nginx_stream_analyzer --cov-branch --cov-fail-under=90`

**Commit:** `step-6: lock cross-module correctness invariants`

## Step 7: Performance and Memory Acceptance

**Goal:** Reproducible evidence confirms the 1 GB / 30-second target and the bounded-cardinality behavior.

**Time:** ~4 hours

**Context:** Architecture section 7; PRD NFR-1 and NFR-2.

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` to stream a deterministic fixture without retaining it in memory.
2. Create `scripts/benchmark.py` to record input bytes, lines, unique counts, Python/OS/CPU/RAM, wall time, and peak RSS.
3. Create `tests/test_performance_smoke.py` for a small CI-safe stream; keep the 1 GB acceptance run opt-in and documented.
4. Profile parser and aggregation hot paths before any optimization; preserve exact outputs.

**Verification:**

- `python3.11 scripts/generate_benchmark_log.py --bytes 1073741824 /tmp/nginx-stream-analyzer-1gb.log`
- `python3.11 scripts/benchmark.py /tmp/nginx-stream-analyzer-1gb.log --max-seconds 30`
- `python3.11 -m pytest tests/test_performance_smoke.py -q`

**Commit:** `step-7: prove streaming performance target`

## Step 8: Packaging and Release Readiness

**Goal:** A clean Python 3.11 environment can install the wheel, run golden inputs, and rely on complete documentation.

**Time:** ~2 hours

**Context:** Strategic Definition of Done; Architecture section 8; PRD release criteria.

**Tasks:**

1. Finalize `README.md`, `CHANGELOG.md`, `LICENSE`, and package metadata.
2. Create `tests/test_wheel_install.py` or a shell-neutral release check that builds and installs in a temporary virtual environment.
3. Document input grammar, schemas, percentage denominator, limitations, and exits `0/1/2/3/4`.
4. Run the complete suite and 1 GB benchmark; attach results to the release record.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m pytest -q`
- `python3.11 -m venv /tmp/nginx-stream-analyzer-release-venv && /tmp/nginx-stream-analyzer-release-venv/bin/pip install dist/*.whl && /tmp/nginx-stream-analyzer-release-venv/bin/nginx-stream-analyzer --version`

**Commit:** `step-8: package verified MVP release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Friday | 1–2 | Freeze package, CLI, and parsing contracts | ~4 hours |
| Saturday | 3–5 | Deliver metrics, renderers, and end-to-end behavior | ~10 hours |
| Sunday | 6–8 | Prove correctness/performance and package release | ~9 hours |

## Final Acceptance

- All P0 criteria in [PRD.md](PRD.md) have automated evidence.
- Text, JSON, and CSV represent the same report model.
- Hourly distribution uses `100 × hourly_request_count / total_valid_requests`.
- The CLI independently demonstrates exit codes `0/1/2/3/4`, including code `4` for unique-cardinality exhaustion.
- The documented 1 GB benchmark completes under 30 seconds on the declared reference laptop.
- No database, HTTP API, authentication, server, cloud, Docker, or Kubernetes component has been introduced.
