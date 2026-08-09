# Implementation Plan: Nginx Insights CLI

## Plan Contract

This is a one-weekend, documentation-only handoff plan. Implementation must preserve the product and architecture contracts in [PRD.md](PRD.md) and [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). Steps are ordered by dependency, with RICE value used within those constraints. WIP remains one step at a time.

Every implementation step uses this complete exit-code contract: `0` success; `1` unexpected runtime, processing, or output failure; `2` invalid CLI usage/options; `3` unreadable input or no valid records; `4` unique-cardinality exhaustion. Code `4` must never be omitted, remapped, or collapsed into code `1`.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml` package and console-script contract | All tests and commands need an installable import boundary | 1 hour |
| 2 | Typed records and domain errors | Parser, aggregator, and renderers need stable interfaces | 1 hour |
| 3 | Test fixtures and golden schemas | Behavior must be frozen before feature implementation | 1.5 hours |
| 4 | Benchmark protocol | Performance risk must be visible before polish | 1 hour |

No database, auth, API, Docker, cloud, or Kubernetes runway is needed.

## STEP 1: Package and CLI Contract

**Goal:** A Python 3.11 package installs locally and exposes `nginx-insights` with help, version, mutually exclusive output flags, input selection, and the cardinality option.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface” and “Packaging and Runtime Layout”.

**Tasks:**

1. Create `pyproject.toml` with Click, Rich, the `src` layout, Python bounds, console entry point, and development tool configuration.
2. Create `src/nginx_insights/__init__.py` with package version exposure.
3. Create `src/nginx_insights/cli.py` with declarations only sufficient for the CLI contract and dependency-injected execution boundary.
4. Create `tests/integration/test_cli_contract.py` covering help, version, defaults, and invalid option combinations.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `nginx-insights --help`
- `pytest -q tests/integration/test_cli_contract.py`

**Commit:** `step-1: establish package and CLI contract`

## STEP 2: Domain Models and Exit Semantics

**Goal:** Typed records, reports, and controlled failures encode the stable contracts without renderer or parser coupling.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Algorithms” and “Exit codes”.

**Tasks:**

1. Create `src/nginx_insights/models.py` with frozen dataclasses for records, rankings, hourly buckets, User-Agent summary, and report.
2. Create `src/nginx_insights/errors.py` with named domain exceptions mapped to codes 3 and 4; leave Click usage failures at 2 and unexpected failures at 1.
3. Create `tests/unit/test_models.py` and `tests/unit/test_errors.py` to freeze invariants and the complete `0/1/2/3/4` mapping.

**Verification:**

- `pytest -q tests/unit/test_models.py tests/unit/test_errors.py`
- `python -m mypy src/nginx_insights`

**Commit:** `step-2: define domain and failure contracts`

## STEP 3: Combined-Log Parser

**Goal:** Each supported nginx combined-log line becomes one normalized `AccessRecord`, while malformed lines produce structured rejections without raw-line leakage.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Input contract” and `PRD.md` FR-1.

**Tasks:**

1. Create `src/nginx_insights/parser.py` with a once-compiled parser and request-target extraction.
2. Create `tests/fixtures/combined.log` and malformed, escaping, IPv4/IPv6, timestamp, empty-UA, and boundary-status fixtures.
3. Create `tests/unit/test_parser.py` with parameterized accepted/rejected records.

**Verification:**

- `pytest -q tests/unit/test_parser.py`
- `ruff check src/nginx_insights/parser.py tests/unit/test_parser.py`

**Commit:** `step-3: parse nginx combined logs`

## STEP 4: Streaming Aggregations

**Goal:** One-pass aggregation produces exact deterministic top-10 metrics, 24 hourly percentages, and exact User-Agent share with cardinality protection.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Data Model and Algorithms”; `PRD.md` FR-2 through FR-6.

**Tasks:**

1. Create `src/nginx_insights/aggregator.py` with incremental counters, hourly array, exact User-Agent set, and finalization.
2. Implement hourly percentages with exactly `100 × hourly_request_count / total_valid_requests`.
3. Enforce `--max-unique-user-agents` before inserting a new distinct value and raise the code-4 domain failure.
4. Create `tests/unit/test_aggregator.py` for ordering, status boundaries, all 24 buckets, percentage math, empty UA behavior, limit boundary, and no partial report.

**Verification:**

- `pytest -q tests/unit/test_aggregator.py`
- `python -m mypy src/nginx_insights/aggregator.py`

**Commit:** `step-4: implement exact streaming metrics`

## STEP 5: Terminal Renderer

**Goal:** Default output is a compact Rich report with TTY-aware color and escaped untrusted fields.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Output contract” and “Security and Privacy”.

**Tasks:**

1. Create `src/nginx_insights/renderers/__init__.py` and `src/nginx_insights/renderers/rich.py`.
2. Render summary, two top-10 tables, 24 hourly rows, and the User-Agent percentage without changing report values.
3. Create `tests/unit/test_rich_renderer.py` for TTY/non-TTY color, `--no-color`, markup escaping, and stable labels.

**Verification:**

- `pytest -q tests/unit/test_rich_renderer.py`
- `pytest -q tests/unit/test_rich_renderer.py --color=no`

**Commit:** `step-5: add safe terminal reporting`

## STEP 6: JSON and CSV Renderers

**Goal:** Pipeline modes emit only versioned, parseable data matching the documented schemas.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Output contract”; `PRD.md` FR-8 and FR-9.

**Tasks:**

1. Create `src/nginx_insights/renderers/json.py` with schema version 1 and numeric percentages.
2. Create `src/nginx_insights/renderers/csv.py` with `metric,rank,key,count,percentage` rows.
3. Create `tests/fixtures/expected/report.json` and `tests/fixtures/expected/report.csv`.
4. Create `tests/unit/test_machine_renderers.py` to validate schemas, escaping, determinism, and absence of ANSI codes.

**Verification:**

- `pytest -q tests/unit/test_machine_renderers.py`
- `python -m json.tool tests/fixtures/expected/report.json >/dev/null`

**Commit:** `step-6: add stable JSON and CSV output`

## STEP 7: End-to-End Execution and Failure Paths

**Goal:** File and stdin processing connect parser, aggregator, and renderers while preserving clean stdout/stderr and every exit code.

**Time:** ~3 hours

**Context:** Full “CLI Interface” and “Error Handling and Observability” sections in `PROJECT_ARCHITECTURE.md`.

**Tasks:**

1. Complete orchestration in `src/nginx_insights/cli.py`, including text decoding, malformed-line summary, renderer selection, and broken-pipe handling.
2. Create `tests/integration/test_end_to_end.py` for file/stdin parity and terminal/JSON/CSV output.
3. Create `tests/integration/test_exit_codes.py` proving `0/1/2/3/4`; code 4 means unique-cardinality exhaustion and produces no partial report.

**Verification:**

- `pytest -q tests/integration/test_end_to_end.py tests/integration/test_exit_codes.py`
- `nginx-insights --json tests/fixtures/combined.log | python -m json.tool >/dev/null`
- `nginx-insights --csv tests/fixtures/combined.log | python -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-7: integrate stream processing and exit behavior`

## STEP 8: Quality, Performance, and Release Readiness

**Goal:** The exact installable candidate passes correctness, security, packaging, and the stated 1 GB performance acceptance gate.

**Time:** ~4 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PROJECT_ARCHITECTURE.md` “Performance and Verification”.

**Tasks:**

1. Create `tests/performance/generate_log.py` with deterministic seed and recorded fixture mix; do not commit a 1 GB fixture.
2. Create `tests/performance/run_benchmark.py` to record environment, bytes, elapsed time, throughput, peak RSS, and exit status.
3. Complete `README.md` with installed usage and schemas; add license and changelog only if the release process requires them.
4. Run dependency, lint, type, unit, integration, coverage, build, clean-install, and benchmark checks.
5. Freeze the exact candidate and accept it only through the applicable repository Verification Loop risk route.

**Verification:**

- `ruff check . && ruff format --check .`
- `python -m mypy src/nginx_insights`
- `pytest --cov=nginx_insights --cov-fail-under=90`
- `python -m build && python -m twine check dist/*`
- `python tests/performance/generate_log.py --bytes 1000000000 --output /tmp/nginx-insights-1gb.log && python tests/performance/run_benchmark.py --input /tmp/nginx-insights-1gb.log --max-seconds 30`

**Commit:** `step-8: verify performance and release readiness`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday foundation | 1–3 | Installable boundary, typed contracts, trustworthy parsing | Half day |
| Saturday metrics | 4 | All exact report calculations | Half day |
| Sunday delivery | 5–7 | Human and pipeline outputs with end-to-end behavior | Half day |
| Sunday acceptance | 8 | Benchmark and release evidence | Half day |

## Dependencies and Stop Conditions

- Do not begin a renderer before the report dataclasses and metric tests are stable.
- Do not optimize before a profiler identifies the limiting path.
- If the 1 GB target fails after focused profiling, invoke the reassessment criteria in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md); do not silently add multiprocessing, persistence, or approximate semantics.
- Gzip input is P1 and begins only after every P0 acceptance criterion passes.
