# Implementation Plan: Nginx Insight

## 1. Delivery Rules

This is an implementation plan, not implementation. Execute one step at a time and keep `PRD.md` plus `PROJECT_ARCHITECTURE.md` as the source of truth. Do not introduce a database, authentication, HTTP API, server, cloud, Docker, or Kubernetes.

Every step that touches command behavior must preserve the complete exit-code contract:

- `0` success.
- `1` processing/data error.
- `2` CLI usage error.
- `3` input/output error.
- `4` unique-cardinality exhaustion.

Code 4 is mandatory and must never be omitted, approximated away, or remapped.

## 2. Architectural Runway

These foundations precede feature behavior:

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console entry point | Every verification command depends on an installable/importable package | 1 h |
| 2 | Typed domain and exception contracts | Parser, aggregator, renderer, and exit behavior need one vocabulary | 1 h |
| 3 | Deterministic fixtures and oracle helpers | Correctness must be checked before optimizing | 1.5 h |
| 4 | Benchmark generator/protocol | The 1 GB target needs reproducible evidence, not an end-of-project estimate | 1 h |

There is no database schema, auth subsystem, API framework, Docker environment, or CI/CD deployment runway because each contradicts the approved architecture. Quality automation may be added to the repository, but it cannot become a product runtime dependency.

## 3. Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday | 1–4 | Installable core, parsing, and all exact metrics | 1 day |
| Sunday | 5–8 | Output contracts, operational errors, performance, and release proof | 1 day |

## STEP 1: Package Skeleton and Public Contracts

**Goal:** An isolated Python 3.11 environment can install the project and invoke a placeholder command boundary; no metric behavior is claimed yet.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 5, 12; `PRD.md` FR-01 and non-goals.

**Tasks:**

1. Create `pyproject.toml` with build metadata, Python `>=3.11,<4`, Click/Rich runtime dependencies, test/quality extras, package discovery, and `nginx-insight = nginx_insight.cli:main`.
2. Create `src/nginx_insight/__init__.py` with package version metadata only.
3. Create `src/nginx_insight/model.py` with typed dataclasses for `LogRecord`, `RankedCount`, `HourlyBucket`, and immutable `ReportSnapshot`.
4. Create `src/nginx_insight/cli.py` with the Click option declarations and a thin callable boundary; keep parsing/aggregation/rendering out of this module.
5. Create `tests/test_cli.py` to assert help/version behavior and mutual exclusions, including usage exit code 2.
6. Configure Ruff, mypy, and pytest in `pyproject.toml`; do not add product code unrelated to this step.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-insight --help`
- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/ruff check . && .venv/bin/mypy src`

**Commit:** `step-1: establish package and CLI contracts`

## STEP 2: Combined-Log Parser and Input Iterator

**Goal:** Files/stdin stream into validated `LogRecord` instances with source/line diagnostics and no retained raw-log collection.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5–6 and CLI inputs; `PRD.md` US-01, FR-02, FR-03.

**Tasks:**

1. Create `src/nginx_insight/parser.py` with a compiled combined-format parser, strict UTF-8 decoding, timestamp/status/request validation, and structured parse exceptions.
2. Add a sequential input iterator that accepts paths or one stdin marker, opens one file at a time, and attaches source plus 1-based line number.
3. Create `tests/fixtures/valid_combined.log`, `tests/fixtures/mixed_combined.log`, and focused fixtures for spaces/quotes, `-` bytes, timestamps, invalid UTF-8, and malformed requests.
4. Create `tests/test_parser.py` covering accepted grammar, every rejection boundary, default skip accounting, strict failure, and non-retention behavior.
5. Extend `tests/test_cli.py` for missing/unreadable input code 3 and duplicate stdin/invalid option code 2.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py tests/test_cli.py -q`
- `.venv/bin/python -m pytest tests/test_parser.py --cov=nginx_insight.parser --cov-fail-under=90`
- `.venv/bin/ruff check src/nginx_insight/parser.py tests/test_parser.py && .venv/bin/mypy src`

**Commit:** `step-2: stream and validate combined nginx logs`

## STEP 3: Streaming Aggregation and Cardinality Guard

**Goal:** One pass produces exact counters for all four metrics while enforcing bounded unique state.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5, 7, 10 and ADR-002; `PRD.md` US-02 through US-05.

**Tasks:**

1. Create `src/nginx_insight/aggregate.py` with `StreamingAggregator`, separate capped IP/error-URL/User-Agent collections, a 24-element hour counter, and `CardinalityExhausted`.
2. Implement top-10 selection with deterministic count-descending/key-ascending ties and without full-entry sorting where bounded selection is practical.
3. Compute every hourly percentage with `100 × hourly_request_count / total_valid_requests`.
4. Compute unique User-Agent share as `100 × unique_user_agent_count / total_valid_requests`; define both as zero for no valid requests.
5. Create `tests/test_aggregate.py` for 4xx/5xx boundaries, fewer/more than ten keys, ties, all hours, empty input, repeated agents, and each independent cardinality ceiling.
6. Assert that insertion past a ceiling raises before a misleading snapshot can be rendered and maps ultimately to exit code 4.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate.py --cov=nginx_insight.aggregate --cov-fail-under=90`
- `.venv/bin/python -m pytest tests/test_aggregate.py -k 'cardinality or hourly or top' -q`

**Commit:** `step-3: implement bounded one-pass metrics`

## STEP 4: End-to-End Application Service

**Goal:** The CLI coordinates input, parsing, aggregation, and immutable report creation with complete operational outcomes.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 2, 8, 9; `PRD.md` US-01, US-08, FR-08, FR-09.

**Tasks:**

1. Wire `src/nginx_insight/cli.py` to the iterator and aggregator without embedding domain logic.
2. Ensure default malformed lines produce counts and warnings while strict malformed lines produce exit 1.
3. Map invalid usage to 2, input/output failures to 3, and `CardinalityExhausted` to 4; retain 0 for successful reports.
4. Buffer/finalize the report before machine rendering so failures cannot leave partial JSON/CSV documents.
5. Extend `tests/test_cli.py` with subprocess tests for stdin, ordered multi-file aggregation, empty input, and every `0/1/2/3/4` result.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/python -m pytest tests/test_cli.py -k 'exit or stdin or multiple or strict' -q`
- `printf '' | .venv/bin/nginx-insight --json`

**Commit:** `step-4: connect streaming pipeline and exit behavior`

## STEP 5: Rich Terminal Renderer

**Goal:** Default output is a readable, safe, optionally colored report containing every required metric.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface and security section; `PRD.md` US-06.

**Tasks:**

1. Create `src/nginx_insight/render/__init__.py` with a narrow renderer protocol/type alias.
2. Create `src/nginx_insight/render/terminal.py` with Rich summary, ranked tables, all 24 hourly rows, and the unique-UA count/share.
3. Escape untrusted Rich markup and implement `--color/--no-color` plus automatic behavior.
4. Add terminal golden fixtures under `tests/fixtures/golden/` and `tests/test_outputs.py` cases for empty lists, long/untrusted values, rounding, and no-color output.

**Verification:**

- `.venv/bin/python -m pytest tests/test_outputs.py -k terminal -q`
- `.venv/bin/nginx-insight --no-color tests/fixtures/valid_combined.log`
- `! .venv/bin/nginx-insight --no-color tests/fixtures/valid_combined.log | LC_ALL=C grep $'\033'`

**Commit:** `step-5: render safe Rich terminal report`

## STEP 6: JSON and CSV Pipeline Renderers

**Goal:** Pipeline users receive deterministic, ANSI-free, fully documented JSON or CSV.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` JSON/CSV contracts; `PRD.md` US-07, FR-07, FR-10.

**Tasks:**

1. Create `src/nginx_insight/render/json_output.py` with the exact schema-version-1 document and newline termination.
2. Create `src/nginx_insight/render/csv_output.py` with fixed `metric,rank,key,count,percentage` columns, RFC-compatible quoting, deterministic rows, and spreadsheet-formula neutralization.
3. Route diagnostics exclusively to stderr and prove no ANSI bytes appear in either machine format.
4. Add JSON/CSV golden files under `tests/fixtures/golden/` and comprehensive cases to `tests/test_outputs.py`.
5. Extend `tests/test_cli.py` to prove mutual exclusion exits 2 and output-write failure exits 3.

**Verification:**

- `.venv/bin/python -m pytest tests/test_outputs.py tests/test_cli.py -q`
- `.venv/bin/nginx-insight --json tests/fixtures/valid_combined.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/python -c "import csv,sys; list(csv.DictReader(sys.stdin))" < <(.venv/bin/nginx-insight --csv tests/fixtures/valid_combined.log)`

**Commit:** `step-6: add stable JSON and CSV reports`

## STEP 7: Performance and Robustness Qualification

**Goal:** Correctness and resource behavior are measured against representative large data; optimizations remain evidence-driven.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 10–11; `PRD.md` non-functional requirements and kill criteria.

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically generate representative valid/malformed lines and controlled IP/URL/User-Agent cardinalities without becoming runtime code.
2. Create `tests/test_performance.py` as a small CI-safe regression/smoke check; keep the 1 GB benchmark an explicit local qualification command.
3. Record reference laptop hardware/OS, Python version, generated-data parameters, warm-up, three runs, median wall time, and peak RSS in a benchmark section of the eventual README/release notes.
4. Profile the unoptimized implementation; change only demonstrated hot paths and rerun all correctness/golden tests after each optimization.
5. Test high-cardinality failure at each collection and confirm exit 4 with empty machine stdout.
6. Run adversarial field fixtures to verify Rich escaping, CSV formula neutralization, and privacy-safe diagnostics.

**Verification:**

- `.venv/bin/python benchmarks/generate_log.py --size-bytes 1073741824 --output /tmp/nginx-insight-benchmark.log --seed 20260819`
- `/usr/bin/time -v .venv/bin/nginx-insight --json /tmp/nginx-insight-benchmark.log >/dev/null`
- `.venv/bin/python -m pytest -q`
- `.venv/bin/ruff check . && .venv/bin/mypy src`

**Commit:** `step-7: qualify performance and hostile inputs`

## STEP 8: Package and Release Acceptance

**Goal:** A clean environment can build, install, execute, and verify the documented MVP without undeclared services.

**Time:** ~3 hours

**Context:** All blueprint documents, especially `STRATEGIC_PLAN.md` Definition of Done and `PRD.md` release criteria.

**Tasks:**

1. Create/update `README.md` with under-30-second quick start, supported combined format, metric definitions, JSON/CSV schemas, privacy notes, cardinality guidance, and benchmark context.
2. Create `LICENSE` using the project owner's selected open-source license before public distribution; do not guess ownership metadata.
3. Create `.gitignore` for Python virtual environments, caches, coverage, builds, and benchmark logs.
4. Build wheel/sdist and install the wheel into a fresh virtual environment.
5. Run all quality, acceptance, golden, and benchmark checks; record real evidence and do not substitute expected outcomes.
6. Confirm the final docs and `--help` present exactly `0/1/2/3/4`, with code 4 meaning unique-cardinality exhaustion.

**Verification:**

- `.venv/bin/python -m pytest --cov=nginx_insight --cov-report=term-missing -q`
- `.venv/bin/ruff check . && .venv/bin/mypy src`
- `.venv/bin/python -m build && .venv/bin/python -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-insight-release-venv && /tmp/nginx-insight-release-venv/bin/pip install dist/*.whl && /tmp/nginx-insight-release-venv/bin/nginx-insight --help`

**Commit:** `step-8: document and verify release candidate`

## 4. Acceptance Matrix

| Contract | Primary evidence |
|---|---|
| Correct combined-log parsing | Parser boundary fixtures and >=90% parser coverage |
| Top-10 IP/error URL correctness | Hand-computed oracle fixtures and deterministic tie tests |
| Hourly formula | 24-bucket fixture verifying `100 × hourly_request_count / total_valid_requests` |
| Unique-UA exactness and exhaustion | Duplicate/empty/cap boundary tests and subprocess exit 4 |
| Terminal/JSON/CSV stability | Golden outputs and ANSI/escaping tests |
| `0/1/2/3/4` exit mapping | Parameterized subprocess matrix |
| 1 GB under 30 seconds | Recorded deterministic three-run median on reference laptop |
| Stateless/no-service architecture | Dependency/static review and clean wheel installation |

## 5. Deferred Work

Custom log-format grammars, configurable top-N, compressed inputs, tail/reopen behavior, multiprocessing, and historical analytics require separate scope decisions. None may be smuggled into the weekend MVP.
