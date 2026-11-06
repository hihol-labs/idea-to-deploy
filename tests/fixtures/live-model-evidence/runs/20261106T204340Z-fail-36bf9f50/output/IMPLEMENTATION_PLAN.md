# Implementation Plan: Nginx Lens

Planning only; all steps below are unstarted. Commands are future implementation checks, not results from this session. See [PRD](PRD.md), [architecture](PROJECT_ARCHITECTURE.md) and [guide](CLAUDE_CODE_GUIDE.md). Full exit contract throughout: 0 success; 1 I/O/runtime failure; 2 usage error; 3 nonempty all-invalid input; 4 unique-cardinality exhaustion.

## Architectural Runway
| Item | Why first | Effort |
|---|---|---|
| Package layout and test runner | Importable, testable increments | Step 1, 2 h |
| Golden combined-log fixtures and report model | Freeze observable semantics | Step 2, 2 h |
| Bounded input and aggregate contracts | Avoid unbounded implementation choices | Steps 2–3 |
No database, auth, Docker or hosted CI runway is needed. Test locally; adding CI requires separate scope authorization.

## Step 1: Package Skeleton
**Goal:** Local install and help/version work.
**Time:** 2 hours.
**Context:** Architecture installation and CLI interface.
**Tasks:** Create `pyproject.toml`, `src/nginx_lens/__init__.py`, `cli.py`, `tests/test_cli.py` and `LICENSE`; declare Python 3.11, Click/Rich, test extras and console entry point. Test help, version, invalid flags and mutually exclusive formats.
**Verification:** `python -m pip install -e '.[test]'`; `python -m pytest tests/test_cli.py`.
**Proposed commit:** `step-1: package and CLI skeleton` (only after green tests and authorization for any external action).

## Step 2: Bounded Reader and Parser
**Goal:** Incremental valid records with explicit malformed counts.
**Time:** 2 hours.
**Context:** Architecture components, data model and resource limits.
**Tasks:** Create `reader.py`, `parser.py`, `models.py`, `tests/test_reader.py`, `tests/test_parser.py`, `tests/fixtures/combined.log`; cover escaped quotes, IPv6, offsets, UTF-8 errors, overlong-line draining, missing fields and trailing garbage. These dependencies precede higher RICE metric work.
**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py`.
**Proposed commit:** `step-2: bounded combined-log ingestion`.

## Step 3: Rankings and Cardinality Safety
**Goal:** Exact top rankings with atomic distinct-entry admission.
**Time:** 2 hours.
**Context:** Architecture metric and resource semantics; highest RICE metric/safety work.
**Tasks:** Create `aggregate.py`, `errors.py`, `tests/test_rankings.py`, `tests/test_limits.py`; test count/key ties, 399/400/599/600 status handling, cap at/beyond boundary and cross-namespace admission. Status 600 is malformed at parser level.
**Verification:** `python -m pytest tests/test_rankings.py tests/test_limits.py`.
**Proposed commit:** `step-3: exact rankings and limits`.

## Step 4: Hourly and UA Metrics
**Goal:** Complete report model with exact counts and defined percentages.
**Time:** 2 hours.
**Context:** Architecture data model and PRD hourly/UA stories.
**Tasks:** Extend `aggregate.py`, `models.py`; create `tests/test_metrics.py` with UTC date-boundary, empty-input, duplicate-UA, sentinel and 50% fixtures. Hourly percentage is `100 × hourly_request_count / total_valid_requests`.
**Verification:** `python -m pytest tests/test_metrics.py tests/test_rankings.py tests/test_limits.py`.
**Proposed commit:** `step-4: hourly and UA summaries`.

## Step 5: Three Output Formats
**Goal:** Deterministic human and pipeline reports.
**Time:** 2 hours.
**Context:** Architecture CLI output schema.
**Tasks:** Create `render.py`, `tests/test_render.py`, `tests/fixtures/report.json`, `tests/fixtures/report.csv`; verify CSV quoting, JSON numeric percentages, all 24 hours, terminal control escaping, Rich markup safety and TTY/NO_COLOR behavior.
**Verification:** `python -m pytest tests/test_render.py`.
**Proposed commit:** `step-5: terminal JSON and CSV rendering`.

## Step 6: End-to-End Failure Contract
**Goal:** Wire input, parse, aggregate and render with correct failure behavior.
**Time:** 2 hours.
**Context:** Architecture CLI exit and stdout/stderr contract.
**Tasks:** Extend `cli.py`, `errors.py`; create `tests/test_integration.py` covering file/stdin equality, unreadable input, invalid options, malformed mixtures, all-invalid input, exhaustion, read failure and broken pipe. Verify 0/1/2/3/4 without leaking raw logs or partial success reports.
**Verification:** `python -m pytest tests/test_cli.py tests/test_integration.py`.
**Proposed commit:** `step-6: integrate pipeline and exit behavior`.

## Step 7: Performance and Packaging Qualification
**Goal:** Measure the throughput target and validate installable artifact.
**Time:** 2 hours.
**Context:** Architecture performance protocol and strategy DoD.
**Tasks:** Create `scripts/generate_benchmark.py`, `scripts/benchmark.py`, `tests/test_benchmark_fixture.py`, `docs/BENCHMARK.md`; generate deterministic decimal 1 GB fixture with known counts under cap, record three runs and RSS, profile if slow. Build wheel and install it into a fresh venv. Fixture generation is outside timed runs.
**Verification:** `python -m pytest tests/test_benchmark_fixture.py`; `python scripts/benchmark.py --bytes 1000000000 --runs 3`; `python -m pip wheel . --no-deps -w dist`; clean-venv `nginx-lens --help`.
**Proposed commit:** `step-7: measured performance and wheel qualification`.

## Step 8: Release Documentation and Local Review
**Goal:** A reviewable local release candidate with documented limitations.
**Time:** 2 hours.
**Context:** Strategy DoD, PRD release criteria.
**Tasks:** Update `README.md`, `CLAUDE_CODE_GUIDE.md`, `CLAUDE.md`, `docs/BENCHMARK.md`; add `docs/TROUBLESHOOTING.md` only after Must work is green. Reconcile actual step statuses, inspect security handling and record review evidence. Do not publish or push without confirmation.
**Verification:** `python -m pytest --cov=nginx_lens --cov-branch --cov-fail-under=85`; exercise installed CLI against sanitized fixture in all formats. Check complete exit contract 0/1/2/3/4 in documentation.
**Proposed commit:** `step-8: document and qualify local release`.

## Dependency and Priority Order
Step 1 enables tests; step 2 enables the high-RICE ranking/safety increment (step 3); step 4 completes metrics before output and integration. Steps 5–8 finish Must delivery before Should troubleshooting. Eight steps fit one weekend; no multi-sprint cadence applies. Proposed commits are suggestions, not commits executed by the blueprint.
