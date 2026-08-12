# Implementation Plan: Nginx Stream Insights

This is a planning document only. Steps are dependency-ordered; RICE informs priority after foundational contracts. Total delivery is one weekend. The complete public exit-code contract in every implementation step is `0` success, `1` internal/runtime failure, `2` usage error, `3` input/data error, and `4` unique-cardinality exhaustion.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Freeze CLI/output/exit contracts | Prevent renderer and test drift | 1 h |
| 2 | Package skeleton and quality config | Enables imports, linting, tests, and clean builds | 1 h |
| 3 | Synthetic fixture corpus and benchmark generator | Correctness and performance need reproducible inputs | 1.5 h |

No database schema, auth system, API, Docker setup, or CI deployment environment belongs in the runway because the architecture is a local stateless CLI.

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Contracts, package, parser | ~5 h |
| Saturday PM | 4–5 | Streaming metrics and domain error semantics | ~4 h |
| Sunday AM | 6–8 | Terminal and structured interfaces | ~5 h |
| Sunday PM | 9–10 | Integration, packaging, performance, release readiness | ~4 h |

## STEP 1: Freeze Fixtures and Public Contracts

**Goal:** Exact supported input, ordering, percentage, schemas, and `0/1/2/3/4` behavior are executable expectations.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Data Model and Streaming State, CLI Interface; `PRD.md` US-1–US-7.

**Tasks:**

1. Create `tests/fixtures/combined.log`, `malformed.log`, `ties.log`, and `empty.log` with synthetic, non-sensitive cases.
2. Create `tests/expected/report.json` and `tests/expected/report.csv` using the documented stable schemas.
3. Create `tests/test_contract.py` for all 24 hours, top-10/tie behavior, formulas, and exit meanings: `0` success, `1` internal/runtime, `2` usage, `3` input/data, `4` unique-cardinality exhaustion.

**Verification:**

- `python -m pytest tests/test_contract.py -q`

**Commit:** `step-1: freeze cli and report contracts`

## STEP 2: Build the Installable Package Skeleton

**Goal:** The command imports and packaging metadata builds on Python 3.11.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` Component Model and Packaging and Deployment.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click, Rich, test/lint extras, and the `nginx-stream-insights` entry point.
2. Create `src/nginx_stream_insights/__init__.py`, `__main__.py`, and `cli.py` without implementing analytics prematurely.
3. Create `tests/test_packaging.py` for version/help import smoke tests.

**Verification:**

- `python -m build`
- `python -m pytest tests/test_packaging.py -q`

**Commit:** `step-2: add python package skeleton`

## STEP 3: Implement Models and Combined-Log Parser

**Goal:** Valid lines become typed records and invalid lines yield explicit parse failures.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Data Model and Error and Validation Policy.

**Tasks:**

1. Create `src/nginx_stream_insights/models.py` with frozen/slot dataclasses.
2. Create `src/nginx_stream_insights/parser.py` with a compiled combined-format parser and timestamp/status validation.
3. Create `src/nginx_stream_insights/errors.py` with typed usage/input/cardinality/internal boundaries preserving codes `0/1/2/3/4`; code 4 is unique-cardinality exhaustion.
4. Create `tests/test_parser.py` covering quoting, IPv4/IPv6, status boundaries, malformed data, and UTF-8 handling at the I/O boundary.

**Verification:**

- `python -m pytest tests/test_parser.py -q`
- `python -m ruff check src/nginx_stream_insights/models.py src/nginx_stream_insights/parser.py src/nginx_stream_insights/errors.py`

**Commit:** `step-3: parse nginx combined logs`

## STEP 4: Implement One-Pass Aggregation

**Goal:** One stream yields a deterministic immutable snapshot containing all four metrics.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Data Model and Streaming State, Performance and Resource Model.

**Tasks:**

1. Create `src/nginx_stream_insights/aggregate.py` with counters, 24 hourly buckets, valid/invalid totals, and exact User-Agent set.
2. Enforce the cardinality guard as a typed failure mapped only to exit code 4; retain `0/1/2/3` meanings unchanged.
3. Compute hourly percentage with `100 × hourly_request_count / total_valid_requests` and deterministic ranked ties.
4. Create `tests/test_aggregate.py` for status filters, rankings, all-hour output, formulas, empty error rankings, and exhaustion.

**Verification:**

- `python -m pytest tests/test_aggregate.py -q`

**Commit:** `step-4: add streaming analytics`

## STEP 5: Wire Streaming Input and Failure Semantics

**Goal:** File/stdin processing remains sequential and strict/permissive behavior is stable.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface and Error and Validation Policy.

**Tasks:**

1. Complete input iteration in `src/nginx_stream_insights/cli.py` for path, `-`, and omitted stdin without closing caller-owned stdin.
2. Add `--strict`, line-number diagnostics, zero-valid-input detection, and concise stderr messages.
3. Map success/internal/usage/input/cardinality outcomes exactly to `0/1/2/3/4`, with code 4 exclusively meaning unique-cardinality exhaustion.
4. Create `tests/test_input.py` for unreadable files, decode errors, malformed lines, stdin, empty input, and unexpected failure mapping.

**Verification:**

- `python -m pytest tests/test_input.py -q`

**Commit:** `step-5: wire streaming input and errors`

## STEP 6: Implement Rich Terminal Output

**Goal:** Interactive users receive four clear tables with safe color behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface → Outputs.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/__init__.py` and `terminal.py`.
2. Render totals, top IPs, error URLs, 24-hour distribution, and User-Agent diversity without recalculating metrics.
3. Implement TTY-aware color and `--no-color`; preserve the complete `0/1/2/3/4` exit mapping and code 4 cardinality meaning.
4. Create `tests/test_terminal_renderer.py` using fixed snapshots and color/no-color assertions.

**Verification:**

- `python -m pytest tests/test_terminal_renderer.py -q`

**Commit:** `step-6: render rich terminal report`

## STEP 7: Implement Versioned JSON Output

**Goal:** `--json` emits one deterministic pipeline-safe document.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface → Outputs; `tests/expected/report.json`.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/json.py` with `schema_version` and documented sections.
2. Wire `--json` without terminal markup or stderr contamination.
3. Create `tests/test_json_renderer.py` for parsing, keys, types, ordering, stdout/stderr, and `0/1/2/3/4` behavior including code 4 exhaustion.

**Verification:**

- `python -m pytest tests/test_json_renderer.py -q`
- `nginx-stream-insights --json tests/fixtures/combined.log | python -m json.tool >/dev/null`

**Commit:** `step-7: add json report contract`

## STEP 8: Implement Normalized CSV Output

**Goal:** `--csv` emits deterministic rows consumable by standard CSV tools.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface → Outputs; `tests/expected/report.csv`.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/csv.py` using Python's `csv` module and the frozen five-column schema.
2. Make `--csv` mutually exclusive with `--json`, producing usage exit 2.
3. Create `tests/test_csv_renderer.py` for escaping, ordering, 24 hour rows, pipeline cleanliness, and all `0/1/2/3/4` meanings; code 4 remains unique-cardinality exhaustion.

**Verification:**

- `python -m pytest tests/test_csv_renderer.py -q`

**Commit:** `step-8: add csv report contract`

## STEP 9: Complete End-to-End and Quality Verification

**Goal:** All interfaces, errors, calculations, and streaming constraints pass together.

**Time:** ~2 hours

**Context:** Entire `PRD.md`; `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Create `tests/test_cli.py` with Click runner coverage for file/stdin and all formats/options.
2. Add subprocess tests for stdout/stderr separation and exact `0/1/2/3/4` exits, including code 4 as unique-cardinality exhaustion.
3. Run lint, typing if configured, coverage, build, and clean-wheel installation smoke tests.
4. Update `README.md` only after commands are proven.

**Verification:**

- `python -m ruff check .`
- `python -m pytest --cov=nginx_stream_insights --cov-report=term-missing --cov-fail-under=90`
- `python -m build`

**Commit:** `step-9: verify cli end to end`

## STEP 10: Prove Performance and Prepare Release

**Goal:** The release has reproducible evidence for the 1 GB/<30 s and bounded-memory claims.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Performance and Resource Model; `PRD.md` NFR-2/NFR-3.

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically generate a synthetic representative 1 GB fixture outside version control.
2. Create `benchmarks/run.py` to record elapsed time, peak RSS, environment, input bytes, and command result.
3. Add `benchmarks/README.md` with reproducible commands and interpretation; do not claim success without a real run.
4. Verify normal success `0`, internal `1`, usage `2`, input `3`, and unique-cardinality exhaustion `4` remain unchanged under subprocess execution.
5. Build and install the wheel in a clean Python 3.11 virtual environment; complete release checklist.

**Verification:**

- `/usr/bin/time -v python benchmarks/run.py --size-bytes 1073741824`
- `python -m build`
- `python -m pytest -q`

**Commit:** `step-10: prove performance and release readiness`

## Completion Gate

Release only when all P0/P1 acceptance criteria pass, the exact `0/1/2/3/4` contract is exercised, the current reference-laptop benchmark is below 30 seconds, memory evidence confirms no raw-record accumulation, documentation matches behavior, and a clean wheel install succeeds. P2 gzip support does not block MVP.
