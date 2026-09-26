# Implementation Plan: nginx-stream-report

## Planning Rules

This is a one-weekend, eight-step plan ordered by dependency and the approved RICE priorities. Each step should leave the repository verifiable. Product behavior comes from `PRD.md`; component and interface contracts come from `PROJECT_ARCHITECTURE.md`. Do not add a database, API, server, authentication, cloud resources, Docker, or Kubernetes.

The public exit-code contract is fixed throughout implementation: `0` success, `1` I/O or unexpected runtime failure, `2` CLI usage error, `3` input data/format failure, and `4` unique-cardinality exhaustion. No step may omit, reuse, or remap code 4.

## Architectural Runway

Infrastructure and architecture work required before feature work:

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console entry point | Every behavior needs an installable/importable boundary | 1.0 h |
| 2 | Typed records and error taxonomy | Parsing, aggregation, renderers, and tests share these contracts | 1.0 h |
| 3 | Representative fixtures and quality commands | Enables red/green work without production data | 1.0 h |

No database schema, authentication system, container setup, or CI deployment runway is appropriate for this local-only CLI.

## Step 1: Package Skeleton and Quality Baseline

**Goal:** A Python 3.11 package can be installed and `nginx-report --help` starts through Click.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 1, 3, 6, and 10.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click and Rich runtime dependencies, pytest/Ruff/mypy test extras, build backend, and `nginx-report = nginx_stream_report.cli:main`.
2. Create `src/nginx_stream_report/__init__.py` with package version exposure.
3. Create `src/nginx_stream_report/cli.py` with the Click command signature and option validation, leaving analysis calls as explicit not-yet-implemented boundaries only during this step.
4. Create `tests/test_cli.py` for help, version, mutually exclusive `--json`/`--csv`, and invalid cardinality ceiling.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/pip install -e '.[test]'`
- `.venv/bin/nginx-report --help`
- `.venv/bin/pytest tests/test_cli.py -q`
- `.venv/bin/ruff check src tests && .venv/bin/mypy src`

**Commit:** `step-1: scaffold installable CLI package`

## Step 2: Domain Models, Errors, and Fixtures

**Goal:** Shared typed contracts and a safe representative fixture corpus exist before parser implementation.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 5, and 7.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with `LogRecord`, `RankedCount`, `HourlyShare`, and immutable `Report` dataclasses.
2. Create `src/nginx_stream_report/errors.py` with typed usage-adjacent, I/O, data-format, and unique-cardinality errors carrying codes 1/3/4; Click retains code 2.
3. Create `tests/fixtures/combined.log` with valid IPv4, IPv6, 2xx, 4xx, 5xx, query-string, empty-UA, and tie-order cases using synthetic values.
4. Create `tests/fixtures/mixed-invalid.log` with synthetic malformed lines and document that fixtures contain no production data.
5. Create `tests/test_models.py` and `tests/test_errors.py` to freeze invariants and the full `0/1/2/3/4` mapping.

**Verification:**

- `.venv/bin/pytest tests/test_models.py tests/test_errors.py -q`
- `.venv/bin/ruff check src tests && .venv/bin/mypy src`

**Commit:** `step-2: define report and error contracts`

## Step 3: Combined-Log Parser

**Goal:** Supported nginx combined-log lines parse into the minimal record without retaining unused fields.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 5; P0 parsing criteria in `PRD.md`.

**Tasks:**

1. Create `src/nginx_stream_report/parser.py` with one compiled expression and timestamp/status/request extraction.
2. Create `tests/test_parser.py` with valid combined format, IPv4/IPv6, timezone-bearing timestamps, request targets with query strings, 399/400/599/600 boundaries, embedded escaped quote cases, and malformed lines.
3. Ensure parser diagnostics identify source and physical line without echoing the full sensitive log line.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py -q`
- `.venv/bin/ruff check src tests && .venv/bin/mypy src`

**Commit:** `step-3: parse nginx combined logs`

## Step 4: Streaming Aggregation

**Goal:** One pass computes exact top IPs, error URLs, hourly percentages, and unique User-Agent share.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3, 4, 5, and 8.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with `AggregateState`, update logic, deterministic top-10 ranking, 24 hourly rows, and report finalization.
2. Create `src/nginx_stream_report/analyzer.py` to iterate file/stdin once, apply default skip and strict failure policies, and rate-limit warnings.
3. Enforce `--max-unique-user-agents` before insertion of an over-limit distinct nonempty value and raise the code-4 error.
4. Create `tests/test_aggregate.py` and `tests/test_analyzer.py` covering formulas, status boundaries, ties, empty input, skipped lines, strict mode, and exhaustion.
5. Add a test stream that fails if the analyzer calls `read()`/`readlines()` to prove line iteration.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py tests/test_analyzer.py -q`
- `.venv/bin/pytest --cov=nginx_stream_report --cov-report=term-missing`

**Commit:** `step-4: implement single-pass metrics`

## Step 5: Terminal Renderer

**Goal:** The default command prints four readable deterministic sections and clear diagnostics.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 6 and 7; terminal requirements in `PRD.md`.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/__init__.py` and `src/nginx_stream_report/renderers/terminal.py`.
2. Render totals, top IPs, error URLs, all 24 hourly percentages, and unique-UA count/share with Rich.
3. Escape or disable Rich markup for every log-derived value; honor `--no-color` and non-TTY color suppression.
4. Create `tests/test_terminal_renderer.py` using a controlled console and assertions on content/order rather than terminal width.

**Verification:**

- `.venv/bin/pytest tests/test_terminal_renderer.py -q`
- `.venv/bin/nginx-report --no-color tests/fixtures/combined.log`

**Commit:** `step-5: render terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** `--json` and `--csv` emit only stable, pipeline-safe machine data.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 6 output schemas and section 9 security requirements.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/json.py` with schema version 1 and the exact documented keys.
2. Create `src/nginx_stream_report/renderers/csv.py` with the normalized five-column schema, standard quoting, and spreadsheet-formula neutralization.
3. Wire renderer selection in `src/nginx_stream_report/cli.py`; keep diagnostics exclusively on stderr.
4. Create `tests/test_json_renderer.py`, `tests/test_csv_renderer.py`, and pipeline assertions in `tests/test_cli.py`.

**Verification:**

- `.venv/bin/pytest tests/test_json_renderer.py tests/test_csv_renderer.py tests/test_cli.py -q`
- `.venv/bin/nginx-report --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `.venv/bin/nginx-report --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: add JSON and CSV contracts`

## Step 7: End-to-End Failure and Exit-Code Contract

**Goal:** File/stdin success paths and every public failure code behave consistently without expected tracebacks.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 6 and 7.

**Tasks:**

1. Complete exception mapping in `src/nginx_stream_report/cli.py` for codes `0/1/2/3/4` exactly.
2. Add `tests/test_integration.py` for success `0`, unreadable input `1`, usage `2`, strict malformed input `3`, and unique-cardinality exhaustion `4` in terminal, JSON, and CSV invocations where applicable.
3. Test stdin, empty input, warning suppression, invalid UTF-8, non-TTY output, broken-pipe handling, and absence of tracebacks for expected failures.
4. Ensure no partial report is emitted after a strict or exhaustion failure.

**Verification:**

- `.venv/bin/pytest tests/test_integration.py -q`
- `.venv/bin/pytest -q --cov=nginx_stream_report --cov-fail-under=90`
- `.venv/bin/ruff check src tests && .venv/bin/mypy src`

**Commit:** `step-7: enforce CLI failure contract`

## Step 8: Performance, Packaging, and Release Evidence

**Goal:** The exact candidate is packaged, documented, and measured against the 1 GB / 30 s target.

**Time:** ~3 hours

**Context:** `STRATEGIC_PLAN.md` KPIs and Definition of Done; `PROJECT_ARCHITECTURE.md` sections 8 and 10.

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` to deterministically stream a synthetic fixture of an exact requested byte target without checking in the 1 GB artifact.
2. Create `tests/test_performance.py` for a smaller CI smoke threshold and document the full local benchmark command.
3. Update `README.md` with installation, examples, schemas, limitations, and full exit-code contract.
4. Build sdist/wheel into `dist/`, install the wheel into a fresh virtual environment, and run smoke tests.
5. Record environment, fixture byte size/cardinalities, three run times, median, and peak RSS in `BENCHMARK.md`.
6. Run the complete verification suite and inspect the source distribution for accidental logs or secrets.

**Verification:**

- `.venv/bin/python scripts/generate_benchmark_log.py --bytes 1073741824 > /tmp/nginx-stream-report-1gb.log`
- `/usr/bin/time -v .venv/bin/nginx-report --json /tmp/nginx-stream-report-1gb.log >/dev/null`
- `.venv/bin/pytest -q --cov=nginx_stream_report --cov-fail-under=90`
- `.venv/bin/ruff check src tests scripts && .venv/bin/mypy src`
- `.venv/bin/python -m build && .venv/bin/python -m twine check dist/*`

**Commit:** `step-8: validate performance and package release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Installable skeleton, contracts, and correct parser | Friday evening / Saturday morning |
| Weekend block 2 | 4–6 | Metrics and all three renderers | Saturday |
| Weekend block 3 | 7–8 | Failure contract, benchmark, packaging, and docs | Sunday |

## Release Gate

Release only when all P0 acceptance criteria pass, coverage is at least 90%, lint/type checks pass, a clean wheel install succeeds, and the documented reference laptop processes the 1 GB fixture in under 30 seconds. A failed target remains a failed gate; do not replace exact metrics or suppress code 4 to make the benchmark appear successful.

