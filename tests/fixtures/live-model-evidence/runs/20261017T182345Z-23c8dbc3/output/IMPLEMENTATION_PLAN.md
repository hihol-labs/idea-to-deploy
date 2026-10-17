# Implementation Plan: nginx-stream-report

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package skeleton and console entry point | Every test and feature needs an installable import/command boundary | 1 hour |
| 2 | Typed model and error contracts | Keeps parser, aggregator, and CLI behavior aligned | 1 hour |
| 3 | Representative fixtures and benchmark generator | Makes correctness and performance measurable before optimization | 1.5 hours |

No database, authentication, Docker, server, or CI/CD deployment runway is needed for this local stateless CLI.

## Step 1: Package and CLI Skeleton

**Goal:** A Python 3.11 package installs locally and exposes `nginx-stream-report`.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections Architecture Summary, Packaging and Deployment, and CLI Interface.

**Tasks:**

1. Create `pyproject.toml` with package metadata, Python constraint, Click/Rich dependencies, dev extras, and console script.
2. Create `src/nginx_stream_report/__init__.py`, `src/nginx_stream_report/__main__.py`, and `src/nginx_stream_report/cli.py`.
3. Create `tests/test_cli.py` for help, version, and initial invocation behavior.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-report --help`
- `.venv/bin/pytest tests/test_cli.py -q`

**Commit:** `step-1: scaffold installable CLI package`

## Step 2: Models, Errors, and Fixtures

**Goal:** Domain records, report shapes, public failures, and representative logs are explicit and testable.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Data Model and Streaming State and Error Handling and Observability.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with frozen/slotted dataclasses for records and report results.
2. Create `src/nginx_stream_report/errors.py` with typed no-valid-input and cardinality-exhaustion errors.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, and `tests/fixtures/empty.log` with synthetic, non-sensitive data.
4. Create `tests/test_models.py` to lock result invariants.

**Verification:**

- `.venv/bin/pytest tests/test_models.py -q`
- `.venv/bin/python -m compileall -q src`

**Commit:** `step-2: define domain and error contracts`

## Step 3: Streaming Combined-Log Parser

**Goal:** Supported nginx combined lines become validated records without retaining input.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section Parsing Contract.

**Tasks:**

1. Create `src/nginx_stream_report/parser.py` with one compiled parser and deterministic parse results.
2. Create `tests/test_parser.py` for IPv4/IPv6-like tokens, offsets, request targets, quoted User-Agents, invalid statuses, truncated lines, and invalid bytes.
3. Update `src/nginx_stream_report/cli.py` to lazily iterate a path or stdin.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py tests/test_cli.py -q`
- `.venv/bin/python -m nginx_stream_report tests/fixtures/combined.log`

**Commit:** `step-3: parse nginx combined logs as a stream`

## Step 4: Core Aggregations

**Goal:** One pass computes deterministic top IPs, error URLs, hourly percentages, and exact unique User-Agent share.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Data Model and Streaming State and Performance Design.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with counters, 24 hourly slots, exact User-Agent set, and result finalization.
2. Enforce the unique User-Agent ceiling before inserting a new value and raise the typed exhaustion error.
3. Create `tests/test_aggregate.py` for top-10 truncation, deterministic ties, 4xx/5xx filtering, `100 × hourly_request_count / total_valid_requests`, zero-valid behavior, and ceiling exhaustion.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest --cov=nginx_stream_report --cov-report=term-missing -q`

**Commit:** `step-4: implement one-pass report aggregation`

## Step 5: Rich Terminal Renderer

**Goal:** Default output clearly presents all four reports and summary metadata, with color only when appropriate.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Output Schemas and CLI Interface.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/__init__.py` and `src/nginx_stream_report/renderers/text.py`.
2. Add `--color/--no-color` and automatic TTY detection in `src/nginx_stream_report/cli.py`.
3. Create `tests/test_text_renderer.py` for section presence, totals, color override, and narrow terminals.

**Verification:**

- `.venv/bin/pytest tests/test_text_renderer.py tests/test_cli.py -q`
- `.venv/bin/nginx-stream-report --no-color tests/fixtures/combined.log`

**Commit:** `step-5: add terminal report renderer`

## Step 6: JSON and CSV Renderers

**Goal:** Pipelines receive schema-stable, ANSI-free JSON or CSV on stdout.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections CLI Interface and Output Schemas.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/json.py` with schema version 1.
2. Create `src/nginx_stream_report/renderers/csv.py` with the normalized `report,key,count,percentage,rank` schema.
3. Update `src/nginx_stream_report/cli.py` with mutually exclusive `--json` and `--csv` flags.
4. Create `tests/test_json_renderer.py` and `tests/test_csv_renderer.py` that parse outputs and assert deterministic ordering.

**Verification:**

- `.venv/bin/pytest tests/test_json_renderer.py tests/test_csv_renderer.py tests/test_cli.py -q`
- `.venv/bin/nginx-stream-report --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-6: add machine-readable output formats`

## Step 7: Complete Failure and Exit-Code Contract

**Goal:** Automation can distinguish success, defects, usage/input failures, empty-valid input, and cardinality exhaustion.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section CLI Interface / Exit codes.

**Tasks:**

1. Update `src/nginx_stream_report/cli.py` and `src/nginx_stream_report/errors.py` to implement the complete `0/1/2/3/4` contract.
2. Ensure code 4 means unique-cardinality exhaustion and never emits a partial report.
3. Extend `tests/test_cli.py` to exercise every code, malformed-line warnings, clean machine stdout, and file/stdin parity.

**Verification:**

- `.venv/bin/pytest tests/test_cli.py -q`
- `sh -c '.venv/bin/nginx-stream-report --max-unique-user-agents 1 tests/fixtures/combined.log >/dev/null; test "$?" -eq 4'`

**Commit:** `step-7: enforce CLI diagnostics and exit codes`

## Step 8: Performance Benchmark and Optimization

**Goal:** A reproducible test demonstrates 1 GB processing under 30 seconds on the reference laptop.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section Performance Design.

**Tasks:**

1. Create `benchmarks/generate_fixture.py` to deterministically stream-generate a 1 GB non-sensitive combined log.
2. Create `benchmarks/run_benchmark.py` to record input metadata, elapsed time, peak memory, and counts separately from report output.
3. Profile the parser and aggregator; make only evidence-backed changes in `parser.py` or `aggregate.py`.
4. Create `tests/test_performance_smoke.py` for a small fixture and document the manual 1 GB release gate.

**Verification:**

- `.venv/bin/pytest tests/test_performance_smoke.py -q`
- `.venv/bin/python benchmarks/generate_fixture.py --size-gib 1 --output /tmp/nginx-stream-report-benchmark.log`
- `.venv/bin/python benchmarks/run_benchmark.py /tmp/nginx-stream-report-benchmark.log --max-seconds 30`

**Commit:** `step-8: add reproducible throughput benchmark`

## Step 9: Release Quality and Documentation

**Goal:** The MVP is installable from built artifacts and all contracts are documented and verified.

**Time:** ~2 hours

**Context:** `PRD.md`, `README.md`, and `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Update `README.md` with actual installation, examples, schemas, limitations, privacy guidance, and benchmark environment.
2. Create `CHANGELOG.md` with the initial release contract.
3. Create `tests/test_packaging.py` or an equivalent isolated wheel smoke check.
4. Run static checks, coverage, full tests, and artifact installation without changing documented behavior.

**Verification:**

- `.venv/bin/pytest --cov=nginx_stream_report --cov-fail-under=90 -q`
- `.venv/bin/python -m build && .venv/bin/python -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-stream-report-smoke && /tmp/nginx-stream-report-smoke/bin/pip install dist/*.whl && /tmp/nginx-stream-report-smoke/bin/nginx-stream-report --help`

**Commit:** `step-9: verify and document MVP release`

## Weekend Boundaries

| Block | Steps | Goal | Duration |
|---|---|---|---:|
| Saturday AM | 1–3 | Installable shell, contracts, and parser | 4.5 h |
| Saturday PM | 4–5 | Complete metrics and terminal experience | 4 h |
| Sunday AM | 6–7 | Pipeline formats and robust process contract | 3.5 h |
| Sunday PM | 8–9 | Performance evidence and release quality | 4.5 h |

## Cross-Cutting Acceptance Gates

- The complete exit-code contract is `0/1/2/3/4`: success, internal error, usage/input error, zero valid requests, and unique-cardinality exhaustion.
- No step adds authentication, a database, HTTP API, server, cloud resource, or Kubernetes manifest.
- Every input path remains streaming; tests must catch accidental `read()`/`readlines()` use on the analysis path.
- JSON and CSV stdout must parse without stripping warnings or ANSI codes.
- A report is not releasable until the 1 GB/30 s gate passes on a named reference laptop.

