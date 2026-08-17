# Implementation Plan: Nginx Stream Analyzer

This is a planning document only. It defines eight dependency-ordered steps
for a one-weekend delivery; it does not authorize code changes in the current
blueprint session. `PROJECT_ARCHITECTURE.md` is the technical source of truth,
and P0 acceptance criteria in `PRD.md` are the behavioral source of truth.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package metadata, `src` layout, and console entry point | Every later CLI and clean-install check depends on it | 1 hour |
| 2 | Domain dataclasses and exception taxonomy | Parser, aggregator, renderers, and exit mapping need stable boundaries | 1 hour |
| 3 | Fixture and benchmark specifications | Prevents implementation from redefining correctness or performance | 1 hour |
| 4 | Static/test tool configuration | Makes every feature increment independently verifiable | 0.5 hour |

There is intentionally no database schema, migration, authentication system,
Docker setup, service deployment, or CI dependency in the runway.

## Step 1: Establish the Installable Package and Contracts

**Goal:** A clean Python 3.11 environment can install the project and invoke a
placeholder-free CLI whose help, version, options, and exit-code constants
match the architecture.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface”, “Package and
Module Layout”, and “Packaging and Runtime”.

**Tasks:**

1. Create `pyproject.toml` with runtime dependencies, development extras,
   `src` package discovery, and the `nginx-stream-analyzer` console entry.
2. Create `src/nginx_stream_analyzer/__init__.py` with the package version.
3. Create `src/nginx_stream_analyzer/cli.py` with Click option declarations
   and centralized exit-code constants; do not implement metric logic here.
4. Create `tests/test_cli.py` for help/version, mutually exclusive formats,
   invalid cardinality, repeated stdin, and directory input.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-analyzer --help`
- `.venv/bin/pytest -q tests/test_cli.py`

**Commit:** `step-1: establish package and CLI contract`

## Step 2: Model Records, Reports, and Failures

**Goal:** Typed, framework-independent dataclasses express every parsed field,
report value, and expected failure without importing Click or Rich.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` section “Data Model and Invariants”.

**Tasks:**

1. Create `src/nginx_stream_analyzer/models.py` with frozen `LogRecord`,
   `RankedCount`, `ParseStats`, and `Report` dataclasses plus validation.
2. Create `src/nginx_stream_analyzer/errors.py` with operational, parse, and
   cardinality exception types used by the CLI exit mapper.
3. Create `tests/test_models.py` covering 24-bucket, count, percentage, and
   common-format nullability invariants.

**Verification:**

- `.venv/bin/pytest -q tests/test_models.py`
- `.venv/bin/mypy src/nginx_stream_analyzer/models.py src/nginx_stream_analyzer/errors.py`

**Commit:** `step-2: define domain and error models`

## Step 3: Implement Lazy Input and Nginx Parsing

**Goal:** Files and stdin yield combined/common `LogRecord` objects one line at
a time with source-aware, privacy-safe diagnostics.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface / Inputs” and
“Error, Privacy, and Security Boundaries”; PRD stories US-01 and US-02.

**Tasks:**

1. Create `src/nginx_stream_analyzer/sources.py` for ordered lazy iteration,
   stdin ownership, UTF-8 handling, and source/line locations.
2. Create `src/nginx_stream_analyzer/parser.py` for combined/common grammar,
   escaped quoted fields, request-line validation, and offset-aware timestamps.
3. Add `tests/fixtures/combined.log`, `tests/fixtures/common.log`, and malformed
   cases containing escaped characters, IPv6, `-`, and boundary statuses.
4. Create `tests/test_sources.py` and `tests/test_parser.py` for strict and
   non-strict behavior, including proof that diagnostics omit full records.

**Verification:**

- `.venv/bin/pytest -q tests/test_sources.py tests/test_parser.py`
- `.venv/bin/ruff check src/nginx_stream_analyzer/sources.py src/nginx_stream_analyzer/parser.py tests`

**Commit:** `step-3: stream and parse nginx records`

## Step 4: Aggregate Exact Metrics with Bounded Cardinality

**Goal:** One scan produces deterministic top-IP, error-URL, hourly, and
User-Agent metrics while failing safely before an exact key budget is exceeded.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Metric Definitions” and
“Streaming Algorithm and Complexity”; PRD stories US-03 through US-06.

**Tasks:**

1. Create `src/nginx_stream_analyzer/aggregate.py` with 24 counters, exact IP
   and error-URL counters, an exact User-Agent set, and pre-insert limits.
2. Finalize top tens with deterministic count-descending/key-ascending ties.
3. Calculate hourly percentages using
   `100 × hourly_request_count / total_valid_requests` and User-Agent share
   from distinct non-missing values over total valid requests.
4. Create `tests/test_aggregate.py` for status 399/400/599 boundaries, ties,
   missing UAs, all 24 buckets, zero errors, and exhaustion at limit + 1.

**Verification:**

- `.venv/bin/pytest -q tests/test_aggregate.py`
- `.venv/bin/mypy src/nginx_stream_analyzer/aggregate.py`

**Commit:** `step-4: add bounded streaming aggregation`

## Step 5: Render Terminal, JSON, and CSV from One Report

**Goal:** All three output modes carry identical values and stable ordering;
machine modes contain no ANSI codes or stdout diagnostics.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “CLI Interface / Outputs”; PRD
stories US-07 and US-08.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/__init__.py` with the renderer
   protocol/dispatcher.
2. Create `renderers/terminal.py` with Rich tables and `auto|always|never`
   color behavior.
3. Create `renderers/json.py` with schema version 1 and 24 ordered hour rows.
4. Create `renderers/csv.py` with the documented long-form columns and order.
5. Create `tests/test_renderers.py` with golden outputs, escaping, Unicode,
   null common-format UA values, and semantic parity assertions.

**Verification:**

- `.venv/bin/pytest -q tests/test_renderers.py`
- `.venv/bin/pytest -q tests/test_renderers.py -k 'json or csv or parity'`

**Commit:** `step-5: render equivalent text JSON and CSV reports`

## Step 6: Integrate the CLI and Complete Exit Semantics

**Goal:** The installed command connects all layers and honors the complete
`0/1/2/3/4` contract without partial reports on failure.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “CLI Interface / Exit Codes”;
PRD story US-09.

**Tasks:**

1. Update `src/nginx_stream_analyzer/cli.py` to select sources, parser,
   aggregator, and renderer while keeping diagnostics on stderr.
2. Map success to 0, operational/I/O failure to 1, Click usage errors to 2,
   log data/strict parse failure to 3, and unique-cardinality exhaustion to 4.
3. Ensure broken downstream pipes terminate quietly according to CLI norms and
   never corrupt a traceback into pipeline output.
4. Expand `tests/test_cli.py` with subprocess tests for every exit code,
   stdin/files, malformed-only input, and no-partial-output guarantees.

**Verification:**

- `.venv/bin/pytest -q tests/test_cli.py`
- `printf '%s\n' 'malformed' | .venv/bin/nginx-stream-analyzer --strict >/tmp/nginx-stream-analyzer.out; test $? -eq 3`
- `test ! -s /tmp/nginx-stream-analyzer.out`

**Commit:** `step-6: integrate CLI and exit contracts`

## Step 7: Prove Correctness, Safety, and Performance

**Goal:** Automated evidence establishes output correctness, streaming memory
behavior, package quality, and the 1 GB / 30 s release gate.

**Time:** ~3 hours plus benchmark runtime

**Context:** `STRATEGIC_PLAN.md` KPIs and Definition of Done;
`PROJECT_ARCHITECTURE.md` section “Performance Verification”.

**Tasks:**

1. Create `tests/test_integration.py` for known whole-report fixtures across
   terminal, JSON, CSV, combined/common, multi-file, and stdin modes.
2. Create `tests/test_performance.py` for opt-in 1 GB benchmark execution and
   high-cardinality fail-fast behavior; keep corpus generation outside timing.
3. Add Ruff, mypy, coverage, and pytest configuration to `pyproject.toml`.
4. Record benchmark environment and result in `docs/BENCHMARK.md`; do not claim
   the target from estimates or smaller fixtures.
5. Run a dependency vulnerability/license review and document any accepted risk.

**Verification:**

- `.venv/bin/ruff check .`
- `.venv/bin/mypy src`
- `.venv/bin/pytest --cov=nginx_stream_analyzer --cov-report=term-missing --cov-fail-under=90`
- `NGINX_ANALYZER_BENCHMARK_FILE=/absolute/path/to/1gb.log .venv/bin/pytest -q tests/test_performance.py -m performance`

**Commit:** `step-7: verify correctness and performance`

## Step 8: Build and Validate the Release Artifact

**Goal:** A clean environment installs the built wheel, the public docs match
the command, and the release candidate is handoff-ready.

**Time:** ~1.5 hours

**Context:** `README.md`, all P0 requirements in `PRD.md`, and the Definition
of Done in `STRATEGIC_PLAN.md`.

**Tasks:**

1. Update `README.md` with final install, examples, metric definitions, privacy
   note, formats, and full exit-code table.
2. Build wheel and source distribution into `dist/` using `python -m build`.
3. Install the wheel into a new temporary virtual environment and run help,
   version, fixture, JSON, and CSV smoke tests.
4. Reconcile this plan’s status table in `CLAUDE.md`; leave deferred gzip and
   custom formats explicitly unstarted.

**Verification:**

- `.venv/bin/python -m build`
- `.venv/bin/python -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-stream-analyzer-release-venv && /tmp/nginx-stream-analyzer-release-venv/bin/pip install dist/*.whl`
- `/tmp/nginx-stream-analyzer-release-venv/bin/nginx-stream-analyzer --version`

**Commit:** `step-8: validate release artifact and handoff`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable skeleton and trustworthy parser | 4–5 hours |
| Saturday PM | 4–5 | Complete metrics and all renderers | 5–6 hours |
| Sunday AM | 6–7 | Integrated behavior and quality/performance evidence | 5–6 hours |
| Sunday PM | 8 | Clean artifact and documentation handoff | 1–2 hours |

## Cross-Step Acceptance Contract

Every implementation step preserves these exit meanings: `0` success, `1`
operational/I/O failure, `2` CLI usage error, `3` malformed/unsupported log
data failure, and `4` unique-cardinality exhaustion. No step may omit, remap,
or reuse code 4. No implementation step may introduce authentication, a
database, HTTP API, service process, cloud resource, container requirement, or
Kubernetes manifest.
