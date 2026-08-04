# Implementation Plan: Nginx Stream Insights

## 1. Delivery Rules

This is a future implementation plan; this blueprint does not implement product code. Execute one step at a time (WIP=1), keep the PRD and architecture as source of truth, and freeze/test the exact staged candidate before accepting a step. The normative exit-code contract for every step is: `0` success, `1` operational I/O failure, `2` usage/option error, `3` input-data failure or no valid requests, and `4` unique-cardinality exhaustion. Code `4` must never be omitted or remapped.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python 3.11 package and test skeleton | Every vertical slice needs an installable entry point and common checks | 1.0 h |
| 2 | Immutable domain and output contracts | Prevents renderer/parser semantic drift | 1.0 h |
| 3 | Representative fixtures and benchmark protocol | Makes correctness and the 30-second constraint measurable early | 1.5 h |
| 4 | CI-quality local command set | Gives every later step the same machine oracle | 0.5 h |

There is intentionally no database schema, authentication layer, Docker setup, API scaffold, or deployment infrastructure in the runway.

## STEP 1: Package Skeleton and Quality Baseline

**Goal:** A pip-installable Python 3.11 package exposes a Click command, with no analytics implemented yet.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§5, 12; `PRD.md` NFR-03.

**Tasks:**

1. Create `pyproject.toml` with build metadata, Python `>=3.11,<3.12`, Click/Rich runtime dependencies, development extras, and `nginx-stream-insights` entry point.
2. Create `src/nginx_stream_insights/__init__.py` with package version and `src/nginx_stream_insights/cli.py` with help/version only.
3. Create `tests/test_cli.py`, `tests/conftest.py`, and tool configuration for pytest, coverage, Ruff, and mypy.
4. Record the full `0/1/2/3/4` contract in CLI help even before later paths are wired.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-insights --help`
- `.venv/bin/ruff check . && .venv/bin/mypy src && .venv/bin/pytest`

**Commit:** `step-1: establish installable CLI and quality baseline`

## STEP 2: Report Models and Golden Contracts

**Goal:** Metric and serialization semantics are executable before parser implementation.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§6–9; `PRD.md` US-02 through US-06.

**Tasks:**

1. Create `src/nginx_stream_insights/models.py` with frozen `LogRecord`, `RankedItem`, and `Report` dataclasses and invariants.
2. Create `tests/fixtures/combined.log`, `tests/fixtures/common.log`, `tests/fixtures/malformed.log`, and `tests/fixtures/expected_report.json` with reviewed, non-production samples.
3. Create `tests/test_models.py` and `tests/test_report_contract.py` for deterministic ordering, 24-hour shape, and 0–100 percentage semantics.

**Verification:**

- `.venv/bin/pytest tests/test_models.py tests/test_report_contract.py -q`
- `.venv/bin/ruff check src/nginx_stream_insights/models.py tests`
- `.venv/bin/mypy src/nginx_stream_insights/models.py`

**Commit:** `step-2: freeze report model and golden analytics contract`

## STEP 3: Streaming Parser and Input Boundary

**Goal:** Combined/common logs are decoded and parsed incrementally from a file or stdin.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§4–6, 10; `PRD.md` US-01 and §8.

**Tasks:**

1. Create `src/nginx_stream_insights/parser.py` with a compiled/scanner parser, offset-aware timestamp conversion, and typed `ParseError`.
2. Create `src/nginx_stream_insights/io.py` to own file handles but never close caller-owned stdin.
3. Create `tests/test_parser.py` for IPv4/IPv6, quotes, query strings, common-format fallback, invalid timestamps/status, oversized tokens, and decoding errors.
4. Create `tests/test_io.py` for file/stdin equivalence and missing/unreadable sources.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py tests/test_io.py -q`
- `.venv/bin/pytest --cov=nginx_stream_insights.parser --cov=nginx_stream_insights.io --cov-branch --cov-fail-under=90`

**Commit:** `step-3: add bounded nginx stream parser and input boundary`

## STEP 4: Aggregation Core and Metric Safety

**Goal:** One pass computes all four required metrics with exact denominators and deterministic rankings.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§6–7, 10–11; `PRD.md` US-02 through US-05.

**Tasks:**

1. Create `src/nginx_stream_insights/aggregate.py` with IP/error-URL counters, 24 hourly buckets, guarded User-Agent set, and finalization.
2. Implement hourly percentages using literal semantics `100 × hourly_request_count / total_valid_requests` and exact User-Agent share.
3. Raise `CardinalityLimitError` before exceeding the configured set and map it later to exit `4`.
4. Create `tests/test_aggregate.py` with boundary statuses, ties, malformed exclusion, zero valid input, and cardinality exhaustion.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py tests/test_report_contract.py -q`
- `.venv/bin/pytest tests/test_aggregate.py --cov=nginx_stream_insights.aggregate --cov-branch --cov-fail-under=90`

**Commit:** `step-4: implement exact streaming aggregations and cardinality guard`

## STEP 5: Terminal Renderer

**Goal:** Default output is a readable Rich report with safe color behavior.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§8–9, 13; `PRD.md` US-07.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/__init__.py` and `renderers/terminal.py`.
2. Render summary, ranked sections, all 24 hours, and User-Agent values from `Report` only.
3. Treat log-derived values as literal text, auto-disable ANSI off-TTY, and support forced color/no-color.
4. Create `tests/renderers/test_terminal.py` with snapshots or structural assertions for empty error sets, long/control-rich values, and redirected output.

**Verification:**

- `.venv/bin/pytest tests/renderers/test_terminal.py -q`
- `.venv/bin/python -m nginx_stream_insights.cli --no-color tests/fixtures/combined.log`

**Commit:** `step-5: render safe human-readable terminal report`

## STEP 6: JSON and CSV Renderers

**Goal:** Pipeline outputs implement stable schemas and match terminal report semantics.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§8–9; `PRD.md` US-06 and §9.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/json.py` with schema version 1.
2. Create `src/nginx_stream_insights/renderers/csv.py` with `section,key,count,percentage` rows.
3. Create `tests/renderers/test_json.py`, `tests/renderers/test_csv.py`, and `tests/renderers/test_equivalence.py`.
4. Assert valid JSON/CSV quoting, two-decimal output, no ANSI, and semantic equivalence from one `Report` fixture.

**Verification:**

- `.venv/bin/pytest tests/renderers -q`
- `.venv/bin/python -m nginx_stream_insights.cli --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-6: add stable equivalent JSON and CSV output`

## STEP 7: Complete CLI and Exit-Code Contract

**Goal:** The real command wires input, aggregation, renderers, diagnostics, options, and every failure code.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface`; `PRD.md` US-01, US-06, US-08.

**Tasks:**

1. Complete `src/nginx_stream_insights/cli.py` with `INPUT`, `--json`, `--csv`, `--top`, `--max-unique-user-agents`, `--encoding`, and color options.
2. Map outcomes exactly: `0` success; `1` operational I/O failure; `2` Click usage/option error; `3` input-data failure/no valid records; `4` unique-cardinality exhaustion.
3. Keep diagnostics on stderr, successful data on stdout, and suppress tracebacks for expected failures/normal pipe closure.
4. Expand `tests/test_cli.py` and create `tests/test_exit_codes.py` exercising all five codes and mutually exclusive formats.

**Verification:**

- `.venv/bin/pytest tests/test_cli.py tests/test_exit_codes.py -q`
- `.venv/bin/pytest -q --cov=nginx_stream_insights --cov-branch --cov-fail-under=90`
- `.venv/bin/nginx-stream-insights --json tests/fixtures/combined.log > /tmp/nginx-stream-insights-report.json`

**Commit:** `step-7: wire CLI options diagnostics and exit codes 0 through 4`

## STEP 8: Performance and Robustness Gate

**Goal:** Evidence proves the candidate handles representative scale safely and within the target.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§10–13; `PRD.md` NFR-01, NFR-02, NFR-06.

**Tasks:**

1. Create `benchmarks/generate_log.py` with a deterministic seed and documented synthetic grammar; generated logs remain benchmark data, never production claims.
2. Create `benchmarks/run.sh` to record file size, Python/OS/CPU/storage context, wall time, peak RSS, and a JSON result digest.
3. Create `tests/test_robustness.py` for huge fields, control characters, hostile Rich markup, broken output, and cardinality exhaustion.
4. Profile parser/aggregation hotspots only if the first 1 GB run misses the target; preserve observable contracts through optimizations.

**Verification:**

- `.venv/bin/pytest tests/test_robustness.py -q`
- `.venv/bin/python benchmarks/generate_log.py --bytes 1073741824 --output /tmp/nginx-stream-insights-1gb.log`
- `benchmarks/run.sh /tmp/nginx-stream-insights-1gb.log` (median of three warm-cache runs must be <30 s)

**Commit:** `step-8: prove gigabyte performance and hostile-input robustness`

## STEP 9: Packaging, Documentation, and Release Candidate

**Goal:** A clean Python 3.11 environment can install and use a fully documented release candidate.

**Time:** ~2 hours

**Context:** All blueprint documents; `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Finalize `README.md`, `CHANGELOG.md`, `LICENSE`, package metadata, and examples for file/stdin, terminal/JSON/CSV, percentage semantics, and exit `0/1/2/3/4`.
2. Create `tests/test_packaging.py` or `scripts/smoke-dist.sh` to build and install the wheel in a clean temporary environment.
3. Run license/dependency audit, full tests, benchmark evidence check, and exact-candidate Idea to Deploy verification/adjudication.
4. Tag only the candidate whose staged content matches current verification evidence.

**Verification:**

- `.venv/bin/python -m build`
- `.venv/bin/ruff check . && .venv/bin/mypy src && .venv/bin/pytest -q --cov=nginx_stream_insights --cov-branch --cov-fail-under=90`
- `scripts/smoke-dist.sh dist/*.whl`

**Commit:** `step-9: prepare verified pip release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | Steps 1–3 | Runway, contracts, streaming input | Friday evening–Saturday morning |
| Weekend block 2 | Steps 4–6 | Metrics and all report formats | Saturday |
| Weekend block 3 | Steps 7–8 | Full behavior, failures, and performance | Sunday morning |
| Weekend block 4 | Step 9 | Distribution and release evidence | Sunday afternoon |

## Dependency and Scope Guardrails

Steps follow architecture dependency order, while metric slices are prioritized by RICE within that order. P2 gzip/custom formats begin only after Step 9 and a new scope decision. Do not add a database, API, authentication, daemon, cloud integration, Docker, or Kubernetes as implementation “preparation.” If a benchmark forces a design change, update `PROJECT_ARCHITECTURE.md` and `PRD.md` before changing code.
