# Implementation Plan: nginx-insights

This is a documentation-only plan. Execution must preserve WIP=1 and implement one numbered step at a time. The ordering follows dependencies and the RICE priorities in `STRATEGIC_PLAN.md`.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package skeleton and Python 3.11 tool configuration | Every module/test and pip installation depends on it | 1.0 h |
| 2 | Golden nginx fixtures and output schemas | Freezes interpretation before implementation | 1.0 h |
| 3 | Benchmark generator outside the repository fixture set | Makes the 1 GB target reproducible without committing huge data | 0.5 h |

No database schema, authentication, API scaffold, Docker setup, or CI/CD deployment runway exists because this is a local stateless CLI.

## STEP 1: Freeze Package and Contract Skeleton

**Goal:** A Python 3.11 package installs locally and exposes a placeholder console command while output/exit contracts are test-addressable.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 2, 3, 8; `PRD.md` FR-09 and NFR-05.

**Tasks:**

1. Create `pyproject.toml` with `src` packaging, Python 3.11 constraint, Click/Rich dependencies, test extras, and `nginx-insights` entry point.
2. Create `src/nginx_insights/__init__.py`, `src/nginx_insights/__main__.py`, and `src/nginx_insights/cli.py` without implementing analytics yet.
3. Create `tests/test_packaging.py` and `tests/test_cli_contract.py` for help/version and mutually exclusive output flags.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `python3.11 -m pytest tests/test_packaging.py tests/test_cli_contract.py -q`
- `nginx-insights --help`

**Commit:** `step-1: establish package and CLI contracts`

## STEP 2: Model and Parse nginx Records

**Goal:** Supported common/combined lines produce typed records; malformed lines produce explicit parse results without crashing.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 6; `PRD.md` FR-02.

**Tasks:**

1. Create `src/nginx_insights/models.py` with slot/frozen `AccessRecord` and report dataclasses.
2. Create `src/nginx_insights/parser.py` with compiled parsing machinery, timestamp parsing, request/path normalization, and typed parse error.
3. Create fixtures under `tests/fixtures/` for common, combined, IPv6, offsets, escapes, dashes, and malformed lines.
4. Create `tests/test_parser.py` covering each field and rejection boundary.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_insights.parser --cov-fail-under=95`

**Commit:** `step-2: parse supported nginx access records`

## STEP 3: Implement Streaming Input and Accounting

**Goal:** File and stdin lines flow through the parser once with identical accounting and no whole-file read.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3, 5, 9; `PRD.md` FR-01 and NFR-02.

**Tasks:**

1. Create `src/nginx_insights/input.py` for file/stdin iteration and UTF-8 failure classification.
2. Create `src/nginx_insights/errors.py` for typed input, parse-quality, and cardinality failures.
3. Create `tests/test_input.py` and `tests/test_streaming.py` for stdin/file parity, unreadable paths, invalid bytes, and an iterator that forbids unbounded reads.

**Verification:**

- `python3.11 -m pytest tests/test_input.py tests/test_streaming.py -q`
- `python3.11 -m pytest tests/test_cli_contract.py -k input_error -q`

**Commit:** `step-3: stream file and stdin input`

## STEP 4: Aggregate the Four Required Metrics

**Goal:** One pass produces exact deterministic top lists, 24 hourly buckets, and User-Agent cardinality/share.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 4; `PRD.md` FR-03 through FR-06.

**Tasks:**

1. Create `src/nginx_insights/aggregate.py` with IP/path counters, 24 hour counters, User-Agent set, and final report snapshot.
2. Implement error filtering for 400–599 and count-descending/label-ascending ranking.
3. Implement hourly percentage exactly as `100 × hourly_request_count / total_valid_requests` and unique User-Agent share against observations.
4. Create `tests/test_aggregate.py` with boundary statuses, ties, empty hours, absent User-Agents, and formula checks.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_insights.aggregate --cov-fail-under=95`

**Commit:** `step-4: compute exact streaming metrics`

## STEP 5: Enforce Cardinality and Exit Semantics

**Goal:** Resource exhaustion and all other failure classes map consistently to the complete `0/1/2/3/4` contract: `0` success, `1` unexpected internal failure, `2` usage/input I/O error, `3` parse-quality failure, and `4` unique-cardinality exhaustion.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 5; `PRD.md` FR-08 and FR-09.

**Tasks:**

1. Add per-dimension `--max-unique` enforcement to `src/nginx_insights/aggregate.py` at the exact boundary.
2. Add `--fail-on-malformed` and exception-to-exit mapping in `src/nginx_insights/cli.py`.
3. Create `tests/test_exit_codes.py` for codes 0, 1, 2, 3, and 4, stdout suppression, and stderr diagnostics.
4. Add cap boundary cases to `tests/test_aggregate.py` for IP, path, and User-Agent state.

**Verification:**

- `python3.11 -m pytest tests/test_exit_codes.py tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_exit_codes.py -k 'cardinality or malformed or io' -q`

**Commit:** `step-5: enforce resource and exit contracts`

## STEP 6: Build Terminal, JSON, and CSV Renderers

**Goal:** All output formats serialize the same report deterministically and preserve stdout/stderr and ANSI contracts.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface; `PRD.md` FR-07 and FR-10.

**Tasks:**

1. Create `src/nginx_insights/renderers/__init__.py` and `terminal.py` for Rich summary/ranking/hour/User-Agent tables.
2. Create `src/nginx_insights/renderers/json.py` with the specified stable object shape.
3. Create `src/nginx_insights/renderers/csv.py` with `section,rank,label,count,percentage` rows via the standard `csv` module.
4. Create `tests/test_terminal_output.py`, `tests/test_json_output.py`, and `tests/test_csv_output.py` using golden fixtures and hostile control characters.

**Verification:**

- `python3.11 -m pytest tests/test_terminal_output.py tests/test_json_output.py tests/test_csv_output.py -q`
- `python3.11 -m nginx_insights --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-6: add deterministic report renderers`

## STEP 7: Integrate End-to-End CLI Behavior

**Goal:** The installed command meets all P0 stories for files and pipelines.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface; all P0 requirements in `PRD.md`.

**Tasks:**

1. Wire input, parser, aggregator, and renderer selection in `src/nginx_insights/cli.py`.
2. Add `--no-color`, `--max-unique`, `--fail-on-malformed`, `--json`, and `--csv` validation.
3. Create `tests/test_cli_e2e.py` for file/stdin parity, each format, malformed policies, deterministic reruns, and pipe use.

**Verification:**

- `python3.11 -m pytest tests/test_cli_e2e.py tests/test_exit_codes.py -q`
- `nginx-insights tests/fixtures/combined.log`
- `nginx-insights --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-7: integrate end-to-end CLI`

## STEP 8: Meet the Performance and Quality Gates

**Goal:** Correctness remains intact while a reproducible 1 GB run finishes under 30 seconds and memory behavior is measured.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 9 and 10; `PRD.md` NFR-01 through NFR-04.

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically write a representative local fixture excluded by `.gitignore`.
2. Create `benchmarks/run_benchmark.py` to measure wall time, input bytes, throughput, and peak RSS without including fixture generation.
3. Add `tests/test_report_invariants.py` comparing optimized aggregation with small known results.
4. Profile and optimize only measured hot paths while retaining golden results.

**Verification:**

- `python3.11 benchmarks/generate_log.py --bytes 1073741824 --output .benchmark-data/access.log`
- `python3.11 benchmarks/run_benchmark.py --input .benchmark-data/access.log --max-seconds 30`
- `python3.11 -m pytest -q --cov=nginx_insights --cov-report=term-missing --cov-fail-under=90`

**Commit:** `step-8: verify performance and quality gates`

## STEP 9: Package and Release-Readiness Check

**Goal:** A clean Python 3.11 environment can install the artifacts and reproduce documented behavior.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` release acceptance.

**Tasks:**

1. Update `README.md` and CLI help to match the implemented interface and measured benchmark environment.
2. Create `CHANGELOG.md` with the MVP contract and known limitations.
3. Build wheel and source distribution into `dist/` and inspect package contents.
4. Run the complete suite and smoke-test the wheel in a new temporary virtual environment.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_insights --cov-fail-under=90`
- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m venv .release-venv && .release-venv/bin/pip install dist/*.whl && .release-venv/bin/nginx-insights --help`

**Commit:** `step-9: prepare verified installable release`

## Sprint Boundaries

For a one-weekend delivery, “sprints” are short working blocks rather than week-long iterations.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Package, parse, and stream foundations | ~5.5 h |
| Saturday PM | 4–5 | Correct aggregations and failure boundaries | ~4.5 h |
| Sunday AM | 6–7 | Output contracts and full CLI | ~5 h |
| Sunday PM | 8–9 | Performance proof and release readiness | ~5 h |

## Completion Evidence

Completion requires current test output, coverage output, the performance-run record with machine details, build/twine checks, and the clean-wheel smoke test. A prose claim or a renderer snapshot alone is insufficient.
