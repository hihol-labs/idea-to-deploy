# Implementation Plan: nginx-stream-stats

## 1. Execution Rules

This plan translates `PRD.md` and `PROJECT_ARCHITECTURE.md` into eight dependency-ordered steps suitable for one weekend. One step is active at a time (WIP=1). Each step ends with its named verification before the next begins. Product code is not part of the blueprint session; the paths below describe future work.

Every implementation and test must preserve this complete exit-code contract:

| Code | Meaning |
|---:|---|
| `0` | Successful complete report, help, or version |
| `1` | EOF with zero valid requests |
| `2` | Invalid CLI usage or configuration |
| `3` | Input I/O, unexpected runtime/internal, or non-UA resource failure |
| `4` | Unique-cardinality exhaustion |

No step may emit a partial report for codes 1, 2, 3, or 4 or remap code 4.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package, console entry point, quality configuration | Makes every later slice installable and testable | 1.0 h |
| 2 | Frozen domain and error contracts | Prevents renderers and aggregation from inventing incompatible shapes | 1.0 h |
| 3 | Representative small fixtures and golden expected metrics | Gives parsing and aggregation a shared correctness oracle | 0.5 h |

No database schema, migrations, auth, Docker, server, API, or CI/CD deployment infrastructure belongs in the runway; the architecture is a local pip package.

## Step 1: Package Skeleton and CLI Contract

**Goal:** A clean Python 3.11 environment can build/install the package and invoke a Click command whose help exposes the approved options.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface,” “Deployment and packaging,” and “Repository Layout”; `PRD.md` FR-1, FR-7, FR-9, FR-10.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click and Rich runtime dependencies, test/build tooling, and `nginx-stream-stats = nginx_stream_stats.cli:main`.
2. Create `src/nginx_stream_stats/__init__.py` with version exposure.
3. Create `src/nginx_stream_stats/cli.py` with Click argument/options, `--help`, `--version`, mutual exclusion, positive ceiling validation, and placeholders that remain internal until vertical behavior is complete.
4. Create `src/nginx_stream_stats/errors.py` defining typed application failures and a single mapping for codes `0/1/2/3/4`, including code 4 for `UniqueCardinalityExhausted`.
5. Create `tests/test_packaging.py` and initial `tests/test_cli.py` for help, version, invalid combinations, and invalid ceiling.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`
- `.venv/bin/python -m pytest tests/test_packaging.py tests/test_cli.py -q`
- `.venv/bin/nginx-stream-stats --help`

**Commit:** `step-1: establish package and CLI contract`

## Step 2: Domain Models and Nginx Parser

**Goal:** Documented common/combined lines parse into minimal typed records; malformed lines produce typed failures without retained input.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Data Contracts and Calculations” and “Component Boundaries”; `PRD.md` US-1 and FR-2/FR-3.

**Tasks:**

1. Create `src/nginx_stream_stats/models.py` with frozen/slotted `ParsedRecord`, ranked-entry, hourly-entry, metadata, User-Agent summary, and final report dataclasses.
2. Create `src/nginx_stream_stats/parser.py` with once-compiled common and combined grammars and one-line parsing.
3. Define timestamp, request-target, status, and missing User-Agent semantics exactly as the architecture specifies.
4. Create `tests/fixtures/access_combined.log`, `tests/fixtures/access_common.log`, and a malformed/special-character fixture small enough for review.
5. Create `tests/test_parser.py` covering IPv4/IPv6 tokens, time zones, quoted fields, status bounds, request extraction, absent UA, and typed malformed results.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py -q`
- `.venv/bin/python -m pytest tests/test_parser.py --maxfail=1 -q`

**Commit:** `step-2: define records and parse nginx formats`

## Step 3: Streaming Aggregation and Metric Semantics

**Goal:** One pass produces exact counters, 24 hourly buckets, exact unique User-Agent state, and deterministic top lists.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Aggregates,” “Cardinality boundary,” and “Performance and Resource Design”; `PRD.md` US-2 through US-5.

**Tasks:**

1. Create `src/nginx_stream_stats/aggregator.py` to update IP/error URL counters, fixed hourly buckets, line accounting, and the capped User-Agent set for each parsed record.
2. Enforce the ceiling before inserting an over-limit unique value and raise the typed code-4 failure.
3. Create `src/nginx_stream_stats/metrics.py` to rank at most 10 entries with descending count/ascending key ties and construct the immutable report.
4. Implement hourly percentages with exactly `100 × hourly_request_count / total_valid_requests` and User-Agent share with the documented present-UA denominator.
5. Create `tests/test_aggregator.py` and `tests/test_metrics.py`, including status 399/400/599 boundaries, ties, all 24 hours, zero-error list, missing UA, and ceiling-at/exceed cases.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregator.py tests/test_metrics.py -q`
- `.venv/bin/python -m pytest tests/test_aggregator.py -k cardinality -q`

**Commit:** `step-3: implement streaming metrics and limits`

## Step 4: Terminal Renderer

**Goal:** Default execution displays all required metrics as readable Rich output without allowing log values to become markup.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs,” “Security and Privacy”; `PRD.md` US-7 and FR-7.

**Tasks:**

1. Create `src/nginx_stream_stats/renderers/__init__.py` and `src/nginx_stream_stats/renderers/terminal.py`.
2. Render summary, two top-10 tables, the 24-hour distribution, and unique User-Agent count/share from the immutable report only.
3. Apply two-decimal display rounding and escape/disable Rich markup for every untrusted value.
4. Wire automatic, forced, and disabled color behavior in `src/nginx_stream_stats/cli.py`.
5. Add terminal cases to `tests/test_renderers.py` and `tests/test_cli.py`, including markup-like URLs/UAs and redirected no-ANSI output.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py tests/test_cli.py -k 'terminal or color or markup' -q`
- `.venv/bin/nginx-stream-stats --no-color tests/fixtures/access_combined.log`

**Commit:** `step-4: render safe terminal report`

## Step 5: JSON and CSV Pipeline Renderers

**Goal:** `--json` and `--csv` emit stable, valid, decoration-free representations of the same report.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs”; `PRD.md` US-6 and FR-7/FR-8.

**Tasks:**

1. Create `src/nginx_stream_stats/renderers/json.py` for the `schema_version: 1` object.
2. Create `src/nginx_stream_stats/renderers/csv.py` for the exact six-column schema and all report sections using the standard `csv` module.
3. Wire renderer selection without calculation logic in `src/nginx_stream_stats/cli.py`.
4. Add JSON/CSV parse-back, quoting, UTF-8, final-newline, no-ANSI, and cross-renderer-equivalence tests in `tests/test_renderers.py` and `tests/test_cli.py`.
5. Store reviewed expected output under `tests/fixtures/expected_report.json` and `tests/fixtures/expected_report.csv`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py tests/test_cli.py -k 'json or csv or equivalent' -q`
- `.venv/bin/nginx-stream-stats --json tests/fixtures/access_combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-5: add JSON and CSV contracts`

## Step 6: End-to-End I/O and Failure Semantics

**Goal:** File/stdin execution, malformed-line continuation, stdout/stderr isolation, atomic output, and every exit code behave exactly as documented.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Exit-code contract” and “Output Atomicity and Error Handling”; `PRD.md` FR-1, FR-3, FR-9.

**Tasks:**

1. Complete stream ownership and buffered iteration in `src/nginx_stream_stats/cli.py`.
2. Map empty/all-invalid input to 1, Click usage to 2, input/runtime/resource failures to 3, and unique-cardinality exhaustion only to 4.
3. Ensure failed aggregation renders no terminal/JSON/CSV fragment and diagnostics remain on stderr.
4. Handle downstream pipe closure without a traceback while preserving the defined application-error mapping.
5. Expand `tests/test_cli.py` with subprocess/file/stdin cases for exact codes `0/1/2/3/4`, partial malformed input, missing file, forced internal failure, and output atomicity.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/python -m pytest tests/test_cli.py -k 'exit_code or atomic or stdin' -q`

**Commit:** `step-6: enforce end-to-end CLI failure contract`

## Step 7: Correctness, Security, and Packaging Gates

**Goal:** A build candidate is independently parseable, deterministic, safe for untrusted log text, and installable from a wheel.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Security and Privacy” and “Test Architecture”; `PRD.md` NFR-2 through NFR-8.

**Tasks:**

1. Complete regression and golden-output coverage across `tests/test_*.py` without duplicating production calculations in the oracle.
2. Add adversarial data values for ANSI/control sequences, Rich markup, CSV formulas/quoting, JSON control characters, and sensitive malformed content.
3. Add deterministic repeat-run checks and a non-seekable stdin test.
4. Build wheel/sdist and install the wheel into a fresh temporary Python 3.11 environment.
5. Inspect build metadata to confirm only Click and Rich are direct runtime dependencies and no server/storage packages appear.

**Verification:**

- `.venv/bin/python -m pytest -q`
- `.venv/bin/python -m build`
- `python3.11 -m venv /tmp/nginx-stream-stats-wheel-test && /tmp/nginx-stream-stats-wheel-test/bin/python -m pip install dist/*.whl && /tmp/nginx-stream-stats-wheel-test/bin/nginx-stream-stats --version`

**Commit:** `step-7: verify correctness safety and wheel install`

## Step 8: Performance Gate and Release Documentation

**Goal:** The exact release candidate is shown to process a representative 1 GB fixture correctly in under 30 seconds on the declared reference laptop.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Performance and Resource Design”; `PRD.md` NFR-1 and “Release Acceptance”; `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Create `tests/test_performance.py` as an opt-in benchmark/check that accepts an externally generated 1 GB path rather than committing large data.
2. Create `scripts/generate_benchmark_log.py` with deterministic seed/config and independently known aggregate expectations; generated data must be labeled synthetic benchmark data, never production data.
3. Record reference laptop, OS, Python version, package candidate, input bytes/lines, cache procedure, elapsed time, peak RSS, and correctness result in `PERFORMANCE.md`.
4. Profile only if the first measured result misses the target; optimize the measured hot path without changing public contracts.
5. Update user documentation and Click help to match the final CLI, formats, formulas, limitations, and exit codes `0/1/2/3/4`.
6. Re-run the complete suite and exact 1 GB gate against the frozen release candidate.

**Verification:**

- `.venv/bin/python -m pytest -q`
- `.venv/bin/python scripts/generate_benchmark_log.py --size-bytes 1073741824 --output /tmp/nginx-stream-stats-1gb.log --expected /tmp/nginx-stream-stats-1gb.json`
- `NGINX_STATS_PERF_LOG=/tmp/nginx-stream-stats-1gb.log NGINX_STATS_EXPECTED=/tmp/nginx-stream-stats-1gb.json .venv/bin/python -m pytest tests/test_performance.py -m performance -q`

**Commit:** `step-8: prove performance and prepare release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable contract and reliable parsing | ~3.5 h |
| Saturday PM | 3–4 | Exact metrics and default terminal experience | ~4 h |
| Sunday AM | 5–6 | Pipeline formats and complete failure semantics | ~4 h |
| Sunday PM | 7–8 | Release correctness, packaging, and performance evidence | ~4.5 h |

## Traceability Matrix

| Requirement/story | Implemented in | Primary verification |
|---|---|---|
| US-1, FR-1–3 | Steps 1, 2, 6 | parser and file/stdin integration tests |
| US-2–5, FR-4–6 | Step 3 | exact aggregator/metrics tests |
| US-7, FR-7 | Step 4 | terminal/color/markup tests |
| US-6, FR-7–8 | Step 5 | parse-back and equivalence tests |
| FR-9 | Steps 1, 3, 6 | subprocess exit-code `0/1/2/3/4` matrix |
| FR-10, NFR-7/8 | Steps 1, 7 | clean wheel install and metadata inspection |
| NFR-1 | Step 8 | correctness-bound 1 GB benchmark under 30 seconds |
| NFR-2–6 | Steps 3, 6, 7 | non-seekable, deterministic, security, and atomicity tests |

## Completion Gate

The project is ready for release only when all eight step verifications have current evidence, the PRD P0 criteria pass, the precise `0/1/2/3/4` contract is demonstrated, and the measured 1 GB run is both correct and under 30 seconds. A narrative statement or an unfrozen benchmark is not acceptance evidence.
