# Implementation Plan: Nginx Stream Insights

## Planning Contract

This is an eight-step, one-weekend plan. Each step ends in a runnable,
reviewable increment and lists the files and checks expected during future
implementation. This document does not implement product code.

The public exit-code contract is fixed for every step and output mode:

- `0`: success, help, or version; a successful report has at least one valid record.
- `1`: input/output or unexpected runtime failure.
- `2`: Click usage or option-validation error.
- `3`: zero valid log records.
- `4`: unique-cardinality exhaustion; no partial report.

Hourly distribution always means a percentage calculated as
`100 × hourly_request_count / total_valid_requests`.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` package, console entry point, test layout | All feature work needs an installable and testable boundary | 1 hour |
| 2 | Domain dataclasses and typed errors | Parser, aggregator, CLI, and renderers need one contract | 1 hour |
| 3 | Representative combined-log fixtures and golden schemas | Correctness and output stability need executable examples | 1 hour |
| 4 | Benchmark generator/runner design | The 1 GB / 30 s constraint must shape implementation early | 1 hour |

No database, authentication, HTTP service, Docker environment, CI/CD
deployment, or cloud infrastructure belongs in the runway.

## STEP 1: Package and CLI contract skeleton

**Goal:** A wheel installs on Python 3.11 and the command exposes the approved
help, options, and stable exit-code constants.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface” and “Packaging
and Deployment”.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, pytest tooling, a
   `src/` package, and the `nginx-stream-insights` entry point.
2. Create `src/nginx_stream_insights/__init__.py`, `__main__.py`, `cli.py`, and
   `errors.py`; centralize exit values `0/1/2/3/4` without implementing metrics.
3. Create `tests/test_cli_contract.py` to cover help/version, mutually exclusive
   formats, color option validation, input selection, and exit mapping.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-insights --help`
- `.venv/bin/pytest -q tests/test_cli_contract.py`

**Commit:** `step-1: establish package and cli contracts`

## STEP 2: Domain models and combined-log parser

**Goal:** Supported combined-log lines become validated, timezone-aware
`AccessRecord` values; malformed input has bounded diagnostics.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Supported Log Contract”, “Data
Model”, and “Error, Resource, and Security Boundaries”.

**Tasks:**

1. Create `src/nginx_stream_insights/models.py` with the dataclasses defined by
   the architecture.
2. Create `src/nginx_stream_insights/parser.py` with one compiled combined-log
   parser, request-target normalization, status validation, and safe diagnostic
   sampling.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, and
   `tests/test_parser.py` covering IPv4, IPv6, offsets, escaping, queries,
   malformed requests, and overlong lines.

**Verification:**

- `.venv/bin/pytest -q tests/test_parser.py`
- `.venv/bin/python -m compileall -q src`

**Commit:** `step-2: parse nginx combined logs safely`

## STEP 3: Streaming input and aggregation

**Goal:** Files and stdin are processed once to produce exact counters, hourly
buckets, diagnostics, and guarded User-Agent cardinality.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Flow and Streaming
Invariants” and “Performance Strategy”.

**Tasks:**

1. Create `src/nginx_stream_insights/io.py` for buffered, incremental file and
   stdin iteration with typed I/O failures.
2. Create `src/nginx_stream_insights/aggregator.py` for IP and error-URL
   counters, 24 local-hour buckets, and the exact User-Agent set/ceiling.
3. Create `tests/test_io.py` and `tests/test_aggregator.py`; assert multiple
   files combine in order and the first excess unique User-Agent triggers the
   code-4 error path.

**Verification:**

- `.venv/bin/pytest -q tests/test_io.py tests/test_aggregator.py`
- `.venv/bin/pytest -q tests/test_aggregator.py -k cardinality`

**Commit:** `step-3: aggregate records in one pass`

## STEP 4: Deterministic report construction

**Goal:** Aggregate state freezes into one renderer-independent report with
stable rankings and correct percentages.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Flow and Streaming
Invariants” and “Data Model”.

**Tasks:**

1. Create `src/nginx_stream_insights/report.py` to apply `count DESC, key ASC`,
   truncate rankings to 10, and emit all 24 hourly buckets.
2. Calculate each hourly percentage with
   `100 × hourly_request_count / total_valid_requests` and unique User-Agent
   share with its documented percentage formula.
3. Create `tests/test_report.py` for ties, fewer/more than 10 keys, empty hours,
   rounding, totals, and immutable output.

**Verification:**

- `.venv/bin/pytest -q tests/test_report.py`
- `.venv/bin/pytest -q tests/test_report.py -k 'percentage or tie or top'`

**Commit:** `step-4: build deterministic analysis reports`

## STEP 5: Rich terminal renderer

**Goal:** Default execution emits four readable ordered sections, safe terminal
content, and correct automatic color behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “CLI Interface”, especially text
outputs and `--color`.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/__init__.py` and
   `renderers/rich_text.py` with four Rich tables plus diagnostic totals.
2. Escape log-derived markup, honor `auto|always|never`, and keep warnings on
   stderr.
3. Create `tests/test_rich_output.py` using terminal and non-terminal console
   captures to assert section order, escaping, and ANSI behavior.

**Verification:**

- `.venv/bin/pytest -q tests/test_rich_output.py`
- `.venv/bin/nginx-stream-insights --color never tests/fixtures/combined.log`

**Commit:** `step-5: render safe rich terminal output`

## STEP 6: JSON and CSV renderers

**Goal:** Pipelines receive versioned, deterministic, color-free JSON and CSV
representations of the same report.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “CLI Interface”, JSON and CSV
output schemas.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/json_output.py` with the complete
   top-level schema and diagnostic fields.
2. Create `src/nginx_stream_insights/renderers/csv_output.py` with the normalized
   six-column schema, standard CSV quoting, and spreadsheet-formula protection.
3. Create `tests/golden/report.json`, `tests/golden/report.csv`, and
   `tests/test_structured_output.py` for schema, parsing, ordering, stdout/stderr
   separation, and absence of ANSI escapes.

**Verification:**

- `.venv/bin/pytest -q tests/test_structured_output.py`
- `.venv/bin/nginx-stream-insights --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-6: add stable json and csv output`

## STEP 7: End-to-end failures and golden flows

**Goal:** The installed command correctly integrates all modules and proves the
complete `0/1/2/3/4` exit-code contract without partial reports.

**Time:** ~2 hours

**Context:** `PRD.md` P0 acceptance criteria and
`PROJECT_ARCHITECTURE.md` section “CLI Interface”.

**Tasks:**

1. Wire `cli.py` to the input, parser, aggregator, report, and renderer layers;
   preserve a single exception-to-exit translation boundary.
2. Create `tests/test_end_to_end.py` for file/stdin equivalence, multiple files,
   each renderer, malformed-with-valid success, missing file (1), usage error
   (2), zero valid records (3), and cardinality exhaustion (4).
3. Verify code 4 writes no text/JSON/CSV report to stdout and that a broken pipe
   terminates quietly according to the architecture.

**Verification:**

- `.venv/bin/pytest -q tests/test_end_to_end.py`
- `.venv/bin/pytest -q --cov=nginx_stream_insights --cov-report=term-missing --cov-fail-under=90`

**Commit:** `step-7: enforce end-to-end cli contracts`

## STEP 8: Performance, packaging, and release evidence

**Goal:** A clean wheel and measured benchmark demonstrate release readiness on
the documented reference environment.

**Time:** ~3 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done and
`PROJECT_ARCHITECTURE.md` sections “Packaging and Deployment” and “Performance
Strategy”.

**Tasks:**

1. Create `benchmarks/generate_log.py` and `benchmarks/run_benchmark.py` to
   produce/reuse a deterministic 1 GB fixture and record environment, wall
   time, throughput, and peak RSS without including the fixture in the wheel.
2. Create `tests/test_wheel_smoke.py`; update `README.md` with actual install,
   examples, schemas, limitations, and exit codes `0/1/2/3/4`.
3. Build the wheel, install it in a fresh Python 3.11 environment, run golden
   flows, and run three benchmark trials. Profile and optimize only if the
   median does not meet 30 seconds.

**Verification:**

- `.venv/bin/python -m build`
- `.venv/bin/pytest -q`
- `.venv/bin/python benchmarks/run_benchmark.py --size-gib 1 --runs 3 --max-seconds 30`

**Commit:** `step-8: verify performance and release artifact`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable contract and trustworthy parsing | ~3.5 hours |
| Saturday PM | 3–4 | Complete one-pass analytics and report model | ~4 hours |
| Sunday AM | 5–6 | Human and pipeline outputs | ~3.5 hours |
| Sunday PM | 7–8 | Integrated contracts, benchmark, and wheel | ~5 hours |

## Dependency and Handoff Rules

WIP stays at one step. A step advances only when its listed checks pass and the
current exact candidate is accepted under the repository’s verification
contract. If performance fails, remain in Step 8 and attach profiler evidence;
do not reopen architecture without a measured bottleneck. Changes to behavior
begin in `PRD.md` and `PROJECT_ARCHITECTURE.md`, then propagate to tests and
implementation.

