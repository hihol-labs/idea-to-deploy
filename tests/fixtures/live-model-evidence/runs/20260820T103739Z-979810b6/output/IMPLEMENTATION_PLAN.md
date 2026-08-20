# Implementation Plan: nginx-report

This plan covers one WIP unit at a time and contains eight dependency-ordered
steps, fitting the approved one-weekend scope. It is planning only: none of the
listed product files or commands have been implemented or run yet.

## Architectural Runway

| # | Item | Why first | Estimate |
|---:|---|---|---:|
| 1 | `src/` package and console-script skeleton | Gives every test and module a stable import/entry point | 1 h |
| 2 | Shared dataclasses and typed exceptions | Prevents parser/aggregator/presenter contracts from drifting | 1 h |
| 3 | Golden combined-log fixtures and expected report | Makes exact semantics executable before feature work | 1 h |
| 4 | Quality and pytest configuration | Enables a gate after every step | 0.5 h |

There is no database, auth system, API server, Docker setup, or CI/CD deployment
runway because those would contradict the architecture. CI configuration is a
release convenience, not a runtime dependency.

## Global Implementation Rules

- Follow `PROJECT_ARCHITECTURE.md` and change the spec before changing public behavior.
- Keep the parser/aggregation hot loop free of Rich rendering and Click callbacks.
- Never buffer the complete input or emit a partial report.
- Treat log fields as untrusted data and never invoke a shell or Rich markup parser on them.
- Preserve the complete exit-code contract in every step: `0` success/help/version;
  `1` operational input/output/decode/gzip/unexpected failure; `2` Click usage
  error; `3` no valid records; `4` unique-cardinality exhaustion.

## STEP 1: Package Skeleton and Executable Contracts

**Goal:** A pip-installable Python 3.11 package exposes a placeholder
`nginx-report` command, and test/quality tools can import the package.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 4 and 11; `PRD.md` FR-1.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click and Rich runtime dependencies, pytest/Ruff/mypy development groups, `src` discovery, and the console script.
2. Create `src/nginx_report/__init__.py` with a package version.
3. Create `src/nginx_report/cli.py` with the Click command signature, options, and a `main()` boundary without metric behavior.
4. Create `src/nginx_report/models.py` for frozen `LogRecord`, `ErrorUrlMetric`, `HourlyMetric`, and `Report` dataclasses.
5. Create `src/nginx_report/errors.py` for typed operational, no-valid-record, and unique-cardinality errors.
6. Create `tests/test_package.py` and `tests/test_cli.py` for import, version, help, and initial option-validation contracts.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_package.py tests/test_cli.py -q`
- `nginx-report --help && nginx-report --version`
- `python3.11 -m ruff check src tests && python3.11 -m mypy src`

**Commit:** `step-1: scaffold package and CLI contracts`

## STEP 2: Combined-Log Sources and Parser

**Goal:** Plain files and stdin yield validated domain records one line at a
time; malformed lines are distinguishable from operational failures.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 3–5; `PRD.md` US-1 and FR-2.

**Tasks:**

1. Create `src/nginx_report/sources.py` with lazy sequential named-file and single-stdin iterators carrying source name and line number.
2. Create `src/nginx_report/parser.py` with one compiled combined-format parser and strict timestamp, request, status, URL, IP, and User-Agent extraction.
3. Add `tests/fixtures/mixed.log`, `tests/fixtures/malformed.log`, and `tests/fixtures/expected_report.json` with fixed human-reviewable cases.
4. Create `tests/test_sources.py` for ordering, stdin, UTF-8 decoding, missing files, and read failures.
5. Create `tests/test_parser.py` for IPv4/IPv6, quoted fields, query strings, timezone offsets, `-` User-Agent, and malformed cases.

**Verification:**

- `python3.11 -m pytest tests/test_sources.py tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_report.parser --cov-fail-under=95`
- `python3.11 -m ruff check src/nginx_report/sources.py src/nginx_report/parser.py tests`
- `python3.11 -m mypy src/nginx_report/sources.py src/nginx_report/parser.py`

**Commit:** `step-2: parse combined logs from streaming sources`

## STEP 3: Exact Streaming Aggregation

**Goal:** Valid records produce all four exact metrics with deterministic top
ten ordering, 24 percentage buckets, and a strict User-Agent cap.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 6 and 12; `PRD.md` US-2 through US-5.

**Tasks:**

1. Create `src/nginx_report/aggregate.py` with IP and error-URL counters, 24 integer hour buckets, total counters, and exact User-Agent set.
2. Apply deterministic `(count descending, key ascending)` ordering and return at most ten IP/URL rows.
3. Compute each hourly percentage as `100 × hourly_request_count / total_valid_requests` and unique share from exact counts.
4. Enforce the positive cap before inserting the first cap-plus-one User-Agent and raise the exit-4 domain error.
5. Create `tests/test_aggregate.py` for empty, ties, 4xx/5xx splits, all 24 hours, formulas, cap boundary, cap exhaustion, and count conservation.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_report.aggregate --cov-fail-under=95`
- `python3.11 -m ruff check src/nginx_report/aggregate.py tests/test_aggregate.py`
- `python3.11 -m mypy src/nginx_report/aggregate.py`

**Commit:** `step-3: add exact streaming metrics and cardinality guard`

## STEP 4: Terminal, JSON, and CSV Presenters

**Goal:** One immutable report renders into three mutually consistent output
contracts with no ANSI leakage into machine formats.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface`; `PRD.md` US-6 and FR-4.

**Tasks:**

1. Create `src/nginx_report/presenters/__init__.py` with presenter selection types.
2. Create `src/nginx_report/presenters/terminal.py` with Rich summary and metric tables, markup escaping, TTY color detection, and `--no-color` behavior.
3. Create `src/nginx_report/presenters/json_output.py` with exact schema version 1 and stable primitive types.
4. Create `src/nginx_report/presenters/csv_output.py` with the documented header, input-summary row, section order, empty-cell rules, quoting, and `\n` terminators.
5. Create `tests/test_presenters.py` with complete golden snapshots and cross-mode metric equivalence assertions.

**Verification:**

- `python3.11 -m pytest tests/test_presenters.py -q`
- `python3.11 -m pytest tests/test_presenters.py --cov=nginx_report.presenters --cov-fail-under=95`
- `python3.11 -m ruff check src/nginx_report/presenters tests/test_presenters.py`
- `python3.11 -m mypy src/nginx_report/presenters`

**Commit:** `step-4: render stable terminal JSON and CSV reports`

## STEP 5: CLI Orchestration and Exit Codes

**Goal:** The installed command connects sources, parser, aggregator, and the
chosen presenter while honoring stdout/stderr and all failure semantics.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface` and Section 13;
`PRD.md` FR-5 through FR-7.

**Tasks:**

1. Complete `src/nginx_report/cli.py` orchestration without retaining input lines.
2. Reject `--json --csv`, non-positive caps, and repeated stdin as Click usage errors.
3. Count malformed lines, map zero valid records to 3, and map cap exhaustion to 4 before presentation.
4. Map input/read/decode/output/broken-pipe and unexpected operational failures to 1 with concise stderr diagnostics.
5. Guarantee report bytes appear only after successful finalization, preventing partial reports.
6. Extend `tests/test_cli.py` with subprocess/Click-runner cases for codes 0, 1, 2, 3, and 4 and stdout/stderr isolation.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m pytest tests/test_cli.py --cov=nginx_report.cli --cov-fail-under=95`
- `nginx-report --json tests/fixtures/mixed.log | python3.11 -m json.tool >/dev/null`
- `nginx-report --csv tests/fixtures/mixed.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-5: wire CLI and complete exit-code contract`

## STEP 6: End-to-End and Contract Test Matrix

**Goal:** Golden flows prove that files and stdin yield identical metrics,
machine schemas are stable, and every public failure mode is replayable.

**Time:** ~2.5 hours

**Context:** `PRD.md` Release Criteria; `PROJECT_ARCHITECTURE.md` Section 14.

**Tasks:**

1. Create `tests/test_end_to_end.py` to run the installed console script against fixed fixtures in terminal, JSON, and CSV modes.
2. Assert file-versus-stdin equality, multi-file composition, tie ordering, malformed counts, 24 hourly rows, and exact formulas.
3. Add explicit fixtures/cases for unreadable input, invalid UTF-8, no valid records, usage error, and cap exhaustion.
4. Assert failure runs produce empty stdout and the complete `0/1/2/3/4` mapping.
5. Add property-focused cases for count conservation and hourly unrounded sum.

**Verification:**

- `python3.11 -m pytest tests/test_end_to_end.py -q`
- `python3.11 -m pytest --cov=nginx_report --cov-report=term-missing --cov-fail-under=90`
- `python3.11 -m ruff check src tests && python3.11 -m mypy src`

**Commit:** `step-6: lock end-to-end report and error contracts`

## STEP 7: Gzip and Measured Performance Gate

**Goal:** The P1 gzip path works safely and a documented benchmark proves or
refutes the 1 GB/30 s target without weakening correctness.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 5 and 12; `PRD.md` US-7 and NFRs.

**Tasks:**

1. Extend `src/nginx_report/sources.py` for `.gz` auto-detection, explicit `--gzip`, and truncated-gzip operational errors.
2. Extend `src/nginx_report/cli.py` with the paired gzip option and stdin policy.
3. Add gzip cases to `tests/test_sources.py` and `tests/test_end_to_end.py`.
4. Create `benchmarks/generate_log.py` for a deterministic representative 1 GB fixture with documented IP/URL/UA cardinalities.
5. Create `benchmarks/run_benchmark.py` to record Python/platform/hardware metadata, wall time, bytes/lines, and peak RSS without joining the input into memory.
6. Create `tests/test_performance.py` for an opt-in benchmark assertion; profile the hot loop if it misses 30 seconds and record findings in `benchmarks/README.md`.

**Verification:**

- `python3.11 -m pytest tests/test_sources.py tests/test_end_to_end.py -q`
- `python3.11 benchmarks/generate_log.py --bytes 1000000000 --output /tmp/nginx-report-1gb.log`
- `python3.11 benchmarks/run_benchmark.py --max-seconds 30 --max-rss-mib 512 /tmp/nginx-report-1gb.log`
- `python3.11 -m pytest -m performance tests/test_performance.py -q`

**Commit:** `step-7: add gzip input and measured performance gate`

## STEP 8: Documentation, Packaging, and Release Readiness

**Goal:** A clean Python 3.11 environment installs the wheel and reproduces
the documented help, success paths, schemas, and complete error contract.

**Time:** ~2 hours

**Context:** All blueprint documents; `STRATEGIC_PLAN.md` Definition of Done;
`PRD.md` Release Criteria.

**Tasks:**

1. Update `README.md` with actual installation, examples, schemas, supported grammar, privacy, and performance baseline.
2. Add `LICENSE`, `CHANGELOG.md`, and packaging metadata only if required for the chosen public release.
3. Create `.github/workflows/ci.yml` for Python 3.11 tests, coverage, Ruff, mypy, and wheel build without deploying anything.
4. Build source/wheel artifacts and test-install the wheel in a clean virtual environment.
5. Reconcile all public options and exit codes across CLI help, README, PRD, architecture, implementation guide, and `CLAUDE.md`.
6. Record the benchmark environment/result and check every Definition of Done item with evidence.

**Verification:**

- `python3.11 -m pytest --cov=nginx_report --cov-report=term-missing --cov-fail-under=90`
- `python3.11 -m ruff check src tests benchmarks && python3.11 -m mypy src`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-report-release-venv && /tmp/nginx-report-release-venv/bin/pip install dist/*.whl && /tmp/nginx-report-release-venv/bin/nginx-report --help`
- `/tmp/nginx-report-release-venv/bin/nginx-report --json tests/fixtures/mixed.log | /tmp/nginx-report-release-venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-8: document verify and package release candidate`

## Weekend Boundaries

| Block | Steps | Outcome |
|---|---|---|
| Saturday morning | 1–2 | Executable package, source iteration, parser |
| Saturday afternoon | 3–4 | Exact metrics and three presenters |
| Sunday morning | 5–6 | Complete CLI and contract matrix |
| Sunday afternoon | 7–8 | Gzip, benchmark, packaging, release evidence |

Do not advance to the next step while the current step's verification is red.
If the performance gate fails, profile and rescope supported input assumptions;
do not bypass the gate or substitute approximate results without a spec change.
