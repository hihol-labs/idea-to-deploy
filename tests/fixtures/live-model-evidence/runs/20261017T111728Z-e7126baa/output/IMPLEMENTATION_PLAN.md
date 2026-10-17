# Implementation Plan: nginx-insights

## Delivery Constraints

This is an eight-step, one-weekend plan for Python 3.11. It implements only the contracts in `PRD.md` and `PROJECT_ARCHITECTURE.md`; it does not add a database, HTTP API, server, authentication, cloud, or Kubernetes. Each step ends in a small verifiable state.

The complete process contract used throughout is: `0` success, `1` runtime/output failure, `2` CLI usage error, `3` input/data error, and `4` unique-cardinality exhaustion. Code 4 must never be omitted, remapped, or collapsed into code 1.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml` package and console entry point | All tests and smoke runs need reproducible installation/imports | 1 h |
| 2 | Typed domain/error contracts | Parser, aggregator, renderers, and CLI need one vocabulary | 1 h |
| 3 | Representative fixtures and benchmark generator | Correctness and performance need stable inputs before optimization | 1.5 h |
| 4 | Ruff, mypy, pytest configuration | Every later increment needs a fast quality gate | 0.5 h |

No database schema, authentication runway, Docker setup, or CI deployment infrastructure is needed because this is a local stateless CLI.

## Step 1: Package Skeleton and CLI Boundary

**Goal:** A pip-installable Python 3.11 package exposes `nginx-insights --help` and validates the top-level option contract.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface” and “Packaging and Deployment”.

**Tasks:**

1. Create `pyproject.toml` with build metadata, Python range, Click/Rich runtime dependencies, dev groups, and console script.
2. Create `src/nginx_insights/__init__.py` with package version and `src/nginx_insights/cli.py` with the Click command/options.
3. Create `tests/test_cli.py` for help/version, conflicting formats, invalid `--top`, and invalid `--max-unique`.

**Verification:**

- `python -m pip install -e '.[dev]'`
- `nginx-insights --help`
- `pytest -q tests/test_cli.py`

**Commit:** `step-1: scaffold package and CLI contract`

## Step 2: Domain Models, Errors, and Log Parser

**Goal:** Common/combined lines become typed records; invalid lines become bounded categorized failures.

**Time:** ~3 hours

**Context:** Architecture sections “Domain Model and Metric Semantics” and “Parsing Design”.

**Tasks:**

1. Create `src/nginx_insights/models.py` with frozen `AccessRecord`, parse result, report row, and summary dataclasses.
2. Create `src/nginx_insights/errors.py` with usage-independent input, data, cardinality, and runtime exception types.
3. Create `src/nginx_insights/parser.py` with a compiled common/combined parser and timestamp/status/request validation.
4. Create `tests/fixtures/access.log` and `tests/test_parser.py` covering valid variants and each stable rejection category.

**Verification:**

- `pytest -q tests/test_parser.py`
- `ruff check src/nginx_insights/parser.py src/nginx_insights/models.py tests/test_parser.py`
- `mypy src/nginx_insights`

**Commit:** `step-2: add typed nginx log parser`

## Step 3: Streaming Aggregation and Cardinality Guard

**Goal:** One pass produces exact counters for all four required metrics without retaining records.

**Time:** ~3 hours

**Context:** Architecture sections “State and Storage” and “Domain Model and Metric Semantics”; PRD P0.2–P0.5 and P0.7.

**Tasks:**

1. Create `src/nginx_insights/aggregate.py` with scalar totals, 24 hour buckets, IP/error-URL/User-Agent maps, deterministic top-k selection, and guarded insertions.
2. Ensure hourly percentages use `100 × hourly_request_count / total_valid_requests` and rounding happens only in output models.
3. Add `tests/test_aggregate.py` for metric boundaries, tie ordering, missing User-Agent, zero valid input, and guard exhaustion in every dimension.

**Verification:**

- `pytest -q tests/test_aggregate.py`
- `pytest -q tests/test_aggregate.py -k cardinality`
- `mypy src/nginx_insights/aggregate.py`

**Commit:** `step-3: implement bounded streaming metrics`

## Step 4: Terminal Renderer

**Goal:** The default command produces readable Rich summary/tables without interpreting untrusted log text.

**Time:** ~2 hours

**Context:** Architecture “Output contract”; PRD P0.6.

**Tasks:**

1. Create `src/nginx_insights/output.py` with a terminal renderer using injected Rich `Console` instances.
2. Escape or render log-derived strings as plain text, emit 24 ordered hours, and support `--no-color`/non-TTY behavior.
3. Create `tests/test_output.py` with terminal snapshots/semantic assertions for color enabled and disabled.

**Verification:**

- `pytest -q tests/test_output.py -k terminal`
- `ruff check src/nginx_insights/output.py tests/test_output.py`

**Commit:** `step-4: render safe terminal report`

## Step 5: JSON and CSV Renderers

**Goal:** Machine modes implement stable schemas with clean stdout and correct quoting.

**Time:** ~2.5 hours

**Context:** Architecture “Output contract”; PRD “Output and Compatibility Requirements”.

**Tasks:**

1. Extend `src/nginx_insights/output.py` with one-document JSON serialization and normalized RFC 4180 CSV serialization.
2. Add schema-version constants to `src/nginx_insights/models.py`.
3. Extend `tests/test_output.py` to parse JSON/CSV, validate types/sections/order, exercise commas/quotes/newlines, and reject ANSI bytes.

**Verification:**

- `pytest -q tests/test_output.py -k 'json or csv'`
- `python -m json.tool < tests/fixtures/expected-report.json` if a golden JSON file is added

**Commit:** `step-5: add stable JSON and CSV output`

## Step 6: End-to-End CLI and Exit Codes

**Goal:** Input, parser, aggregator, renderer, diagnostics, and exact exit mapping work together.

**Time:** ~3 hours

**Context:** Architecture “CLI Interface”; PRD P0.1, P0.6, and P0.7.

**Tasks:**

1. Complete `src/nginx_insights/cli.py` to stream file/stdin, apply tolerant/strict policy, map domain failures, and delay structured serialization until aggregation succeeds.
2. Extend `tests/test_cli.py` with file/stdin equivalence, stderr separation, empty/malformed/encoding/missing input, simulated output failure, and guard exhaustion.
3. Assert the exact exit-code matrix: `0/1/2/3/4`, where `4` means unique-cardinality exhaustion.

**Verification:**

- `pytest -q tests/test_cli.py`
- `nginx-insights --json tests/fixtures/access.log | python -m json.tool`
- `nginx-insights --csv tests/fixtures/access.log | python -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: integrate CLI and complete exit contract`

## Step 7: Quality, Security, and Documentation

**Goal:** The package is typed, linted, documented, safely handles untrusted text, and installs cleanly.

**Time:** ~2.5 hours

**Context:** Architecture “Testing Strategy” and “API, Authentication, and Network Boundaries”.

**Tasks:**

1. Add focused test cases in `tests/test_cli.py` and `tests/test_output.py` for terminal control sequences, huge fields, broken pipes, and non-leaking diagnostics.
2. Update `README.md` with install, CLI examples, metric definitions, output schemas, limitations, and exit codes.
3. Add `LICENSE`, `CHANGELOG.md`, and packaging include/exclude rules as release preparation requires.

**Verification:**

- `ruff check .`
- `mypy src/nginx_insights`
- `pytest -q --cov=nginx_insights --cov-report=term-missing --cov-fail-under=90`
- `python -m build && python -m twine check dist/*`

**Commit:** `step-7: harden and document package`

## Step 8: Performance Acceptance and Release Candidate

**Goal:** The exact candidate is shown to satisfy or fail the 1 GB/30 s target with reproducible evidence.

**Time:** ~3 hours

**Context:** Architecture “Performance and Observability”; PRD P0.8; `STRATEGIC_PLAN.md` KPIs and kill criteria.

**Tasks:**

1. Create `tests/generate_benchmark_log.py` to deterministically generate a representative 1 GB corpus without committing it.
2. Create `tests/test_performance.py` for a small CI-scale regression and a separately marked 1 GB acceptance case.
3. Create `docs/PERFORMANCE.md` recording hardware, OS, Python/package versions, corpus parameters, exact command, elapsed time, peak RSS, and profiling-driven changes.
4. Build a wheel, install it in a clean Python 3.11 environment, and run all output modes against fixtures and the benchmark corpus.

**Verification:**

- `python tests/generate_benchmark_log.py --bytes 1073741824 --output /tmp/nginx-insights-1gb.log`
- `/usr/bin/time -v nginx-insights --json /tmp/nginx-insights-1gb.log > /tmp/nginx-insights-report.json`
- `pytest -q`
- `ruff check . && mypy src/nginx_insights && python -m build`

**Commit:** `step-8: validate performance and release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable boundary and correct parser | 4.5 h |
| Saturday PM | 3–4 | Exact streaming metrics and terminal report | 5 h |
| Sunday AM | 5–6 | Pipeline formats and end-to-end error semantics | 5.5 h |
| Sunday PM | 7–8 | Quality gate, measured performance, release candidate | 5.5 h |

## Final Acceptance Gate

Do not release unless all P0 acceptance criteria pass, the complete suite/lint/type/build commands pass, a clean install works, structured outputs validate, all exit codes `0/1/2/3/4` have integration coverage, and the recorded 1 GB run is under 30 seconds. A performance miss or code 4 during the representative run is a failed acceptance result, not a reason to silently sample.

