# Implementation Plan: Nginx Stream Report

This is a documentation-only execution plan. No product code is created by the blueprint. The sequence follows `PROJECT_ARCHITECTURE.md`, the RICE priorities in `STRATEGIC_PLAN.md`, and the P0 acceptance criteria in `PRD.md`.

## Architectural Runway

| # | Item | Why first | Effort |
|---|---|---|---:|
| 1 | Package/console-entry skeleton | every CLI test and installation check depends on it | 1 hour |
| 2 | canonical log fixtures and output schema fixtures | locks behavior before implementation | 1 hour |
| 3 | benchmark generator/harness | makes the 1 GB target testable before optimization | 1.5 hours |
| 4 | static/test configuration | provides repeatable evidence from the first feature | 0.5 hour |

No database, authentication, Docker, CI/CD service, or deployment infrastructure belongs in the runway.

## Step 1: Lock packaging and public contracts

**Goal:** a Python 3.11 package layout, console command name, exit codes, and schema versions are explicit.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` §§4, 6, 7, 12; `PRD.md` FR-001, FR-008.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click, Rich, build metadata, and `nginx-stream-report` console entry point.
2. Create `src/nginx_stream_report/__init__.py` with the package version.
3. Create `src/nginx_stream_report/cli.py` with the Click command surface and placeholder-free option validation.
4. Create `tests/test_cli.py` cases for help, version, mutual exclusion, and exit codes.

**Verification:**

- `python3.11 -m pip install -e .`
- `nginx-stream-report --help`
- `python3.11 -m pytest tests/test_cli.py -q`

**Commit:** `step-1: establish package and CLI contracts`

## Step 2: Establish fixtures and benchmark evidence

**Goal:** deterministic correctness inputs and a reproducible 1 GiB performance measurement exist before hot-path work.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§8–9; `PRD.md` AC-PERF-001.

**Tasks:**

1. Create `tests/fixtures/sample_access.log` covering IPv4, IPv6, all hours, ties, 2xx/3xx/4xx/5xx, quoted User-Agents, and query strings.
2. Create `tests/fixtures/malformed_access.log` with truncated, invalid-status, invalid-date, and arbitrary text records.
3. Create `tests/fixtures/expected_report.json` as the cross-renderer oracle.
4. Create `tests/test_performance.py` with a generated repeated-cardinality fixture, elapsed time, bytes/sec, and peak-memory capture; mark the 1 GiB run as an explicit benchmark test.

**Verification:**

- `python3.11 -m pytest tests/test_performance.py -q -m 'not benchmark'`
- `python3.11 -m pytest tests/test_performance.py -q -m benchmark --benchmark-log-size=1GiB`

**Commit:** `step-2: define fixtures and performance benchmark`

## Step 3: Implement the combined-log parser

**Goal:** valid standard combined-log lines become typed records and malformed lines are rejected predictably without aborting the stream.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§5, 8, 10; `PRD.md` FR-002.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with `AccessRecord` and report dataclasses.
2. Create `src/nginx_stream_report/parser.py` with one compiled pattern and timezone-aware timestamp conversion.
3. Create `tests/test_parser.py` with valid IPv4/IPv6, quoted fields, query targets, and every malformed fixture category.
4. Ensure exceptions contain line numbers/reasons but never echo an entire sensitive log line.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m ruff check src/nginx_stream_report/parser.py src/nginx_stream_report/models.py tests/test_parser.py`

**Commit:** `step-3: parse nginx combined logs safely`

## Step 4: Implement streaming aggregation

**Goal:** one pass produces all four exact metric families with deterministic top-10 ties.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§3, 5, 8; `PRD.md` FR-003–FR-006.

**Tasks:**

1. Create `src/nginx_stream_report/stats.py` with `StreamingStats.consume()` and `snapshot()`.
2. Count all valid records by IP and hour; count error URLs only for status 400–599.
3. Track exact User-Agent cardinality and compute its percentage against valid requests.
4. Create `tests/test_stats.py` for empty input, ties, fewer/more than ten keys, 4xx/5xx filtering, 24 buckets, and zero denominator.

**Verification:**

- `python3.11 -m pytest tests/test_stats.py -q`
- `python3.11 -m pytest tests/test_stats.py --cov=nginx_stream_report.stats --cov-fail-under=95`

**Commit:** `step-4: aggregate four report metrics in one pass`

## Step 5: Connect file and stdin streaming

**Goal:** the command incrementally processes either an explicit file or stdin and reports malformed-line totals.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§3, 6, 8; `PRD.md` FR-001, FR-002, FR-009.

**Tasks:**

1. Update `src/nginx_stream_report/cli.py` to open `INPUT` lazily with `-` mapped to stdin.
2. Connect parser and aggregator without `read()`/`readlines()` or retained raw lines.
3. Map usage, input, broken-pipe, and unexpected failures to the architecture exit-code contract.
4. Extend `tests/test_cli.py` with file/stdin parity, missing file, empty input, malformed input, and broken-pipe behavior.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -c "import pathlib; p=pathlib.Path('src/nginx_stream_report/cli.py').read_text(); assert '.readlines(' not in p and '.read(' not in p"`

**Commit:** `step-5: stream files and stdin through the report pipeline`

## Step 6: Add Rich terminal output

**Goal:** default invocation produces a readable colored report with all metrics and correct non-TTY behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` §7; `PRD.md` FR-007.

**Tasks:**

1. Create `src/nginx_stream_report/formatters/__init__.py`.
2. Create `src/nginx_stream_report/formatters/terminal.py` with summary and metric tables.
3. Escape untrusted values, honor `NO_COLOR`, and render explicit empty states.
4. Add terminal golden assertions to `tests/test_cli.py`, including no ANSI in captured non-TTY output.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q -k terminal`
- `NO_COLOR=1 nginx-stream-report tests/fixtures/sample_access.log | tee /tmp/nginx-stream-report.txt && test -s /tmp/nginx-stream-report.txt`

**Commit:** `step-6: render the default Rich terminal report`

## Step 7: Add JSON and CSV output

**Goal:** automation modes emit stable, decoration-free representations of the same report.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§6–7; `PRD.md` FR-008.

**Tasks:**

1. Create `src/nginx_stream_report/formatters/json_output.py` with `schema_version` and stable key meanings.
2. Create `src/nginx_stream_report/formatters/csv_output.py` with `section,rank,key,count,share_percent` rows.
3. Wire mutually exclusive `--json` and `--csv` flags in `src/nginx_stream_report/cli.py`.
4. Add schema, quoting, ordering, ANSI-absence, and semantic-parity tests to `tests/test_cli.py`.

**Verification:**

- `nginx-stream-report --json tests/fixtures/sample_access.log | python3.11 -m json.tool >/dev/null`
- `nginx-stream-report --csv tests/fixtures/sample_access.log | python3.11 -c "import csv,sys; rows=list(csv.DictReader(sys.stdin)); assert rows"`
- `python3.11 -m pytest tests/test_cli.py -q -k 'json or csv or parity'`

**Commit:** `step-7: add stable JSON and CSV renderers`

## Step 8: Harden correctness, privacy, and quality

**Goal:** the full implementation meets static, test, coverage, malformed-input, and privacy requirements.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` §10; `PRD.md` non-functional requirements.

**Tasks:**

1. Configure Ruff and a Python type checker in `pyproject.toml`.
2. Add property/fuzz-style parser cases without adding runtime dependencies.
3. Confirm fatal diagnostics use stderr and do not reproduce sensitive full lines.
4. Raise total test coverage to at least 90% and review all output paths for raw terminal markup.

**Verification:**

- `python3.11 -m ruff check .`
- `python3.11 -m mypy src/nginx_stream_report`
- `python3.11 -m pytest -q --cov=nginx_stream_report --cov-fail-under=90`

**Commit:** `step-8: harden correctness and input boundaries`

## Step 9: Meet the 1 GiB performance target

**Goal:** recorded evidence shows a 1 GiB representative log completes in under 30 seconds on the declared laptop.

**Time:** ~2–4 hours

**Context:** `PROJECT_ARCHITECTURE.md` §9; `PRD.md` AC-PERF-001.

**Tasks:**

1. Run `tests/test_performance.py` and record CPU, RAM, OS, Python version, bytes, records, elapsed time, throughput, and peak RSS in `BENCHMARK.md`.
2. If failing, profile parsing/timestamp/counter hot paths before changing code.
3. Add a constant-cardinality scale test to demonstrate memory independence from line count.
4. Reject multiprocessing unless profiling proves the single-process design cannot meet the target.

**Verification:**

- `python3.11 -m pytest tests/test_performance.py -q -m benchmark --benchmark-log-size=1GiB`
- `test -s BENCHMARK.md && grep -E 'elapsed|throughput|peak RSS|Python' BENCHMARK.md`

**Commit:** `step-9: prove the one-gigabyte performance target`

## Step 10: Package and document the release candidate

**Goal:** a clean Python 3.11 environment can build, install, and use the wheel according to the README.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` §12; `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` release criteria.

**Tasks:**

1. Update `README.md` with real installation, file/stdin examples, schemas, format limitation, privacy note, and benchmark result.
2. Add `LICENSE` after the maintainer selects the permissive OSI license.
3. Build wheel and sdist into `dist/`; inspect metadata and contents.
4. Install the wheel into a fresh virtual environment and execute terminal, JSON, and CSV smoke tests.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-stream-report-venv && /tmp/nginx-stream-report-venv/bin/pip install dist/*.whl && /tmp/nginx-stream-report-venv/bin/nginx-stream-report --json tests/fixtures/sample_access.log`

**Commit:** `step-10: package and verify the release candidate`

## Sprint boundaries

For a one-weekend project, these are work blocks rather than multi-week iterations.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Friday runway | 1–2 | executable contracts and evidence harness | 2.5 hours |
| Saturday core | 3–5 | parser, metrics, and streaming CLI | 6.5 hours |
| Saturday/Sunday UX | 6–7 | all three output modes | 3.5 hours |
| Sunday release | 8–10 | quality, performance, and installable artifact | 5.5–7.5 hours |

## Dependency and handoff rules

- Preserve WIP=1: finish and verify one step before starting the next.
- A failed verification leaves the step in recovery, never Done.
- Update specs before behavior if an acceptance criterion changes.
- Record actual commands and outputs in the Idea to Deploy state/evidence artifacts.
- P1/P2 work begins only after all P0 release criteria pass.

