# Implementation Plan: nginx-log-top

## Scope and Ordering

This is a planning document; no product code is included. The sequence follows dependencies and the approved RICE priorities from `STRATEGIC_PLAN.md`: establish the stream/parser contract first, add the high-value counters, then expose renderers and harden the package. The intended delivery window is one weekend.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python 3.11 package and console-entry skeleton | Gives every later module a stable import and command boundary | 1 hour |
| 2 | Typed models and error taxonomy | Prevents renderer/parser coupling and freezes exit behavior | 1 hour |
| 3 | Representative fixtures and benchmark generator | Makes correctness and performance measurable before optimization | 1.5 hours |

There is no database, auth system, server, Docker setup, or CI/CD deployment runway because those components are outside the accepted architecture.

## Step 1: Package and CLI Skeleton

**Goal:** A pip-installable Python 3.11 package exposes `nginx-log-top`, `python -m nginx_log_top`, help, and version commands.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface,” “Package and Module Structure,” and “Packaging and Deployment.”

**Files:**

1. Create `pyproject.toml` with build metadata, Python `>=3.11`, Click/Rich dependencies, optional test tools, and the console script.
2. Create `src/nginx_log_top/__init__.py` with version lookup.
3. Create `src/nginx_log_top/__main__.py` as the module entry point.
4. Create `src/nginx_log_top/cli.py` with Click arguments/options and mutually exclusive output-mode validation.
5. Create `tests/test_cli.py` for help, version, invalid combinations, and stdin defaults.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `nginx-log-top --help`
- `python3.11 -m nginx_log_top --version`
- `pytest -q tests/test_cli.py`

**Commit:** `step-1: scaffold installable CLI package`

## Step 2: Domain Models, Errors, and Fixtures

**Goal:** Immutable records, analysis results, and typed failure categories encode the public behavior independently of I/O.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model” and “Error Handling and Security.”

**Files:**

1. Create `src/nginx_log_top/models.py` with frozen `ParsedRequest`, `RankedCount`, `HourlyBucket`, and `AnalysisResult` dataclasses.
2. Create `src/nginx_log_top/errors.py` with `InputFailure`, `MalformedLine`, and `UniqueCardinalityExhausted`.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/mixed.log`, and `tests/fixtures/empty.log` with documented expected totals.
4. Create `tests/test_models.py` for invariants and immutability.

**Verification:**

- `pytest -q tests/test_models.py`
- `python3.11 -m compileall -q src tests`

**Commit:** `step-2: define analysis contracts and fixtures`

## Step 3: Streaming Combined-Log Parser

**Goal:** Each physical input line is converted to a typed request or a safe line-numbered parsing error without retaining source data.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Parser,” “Inputs,” and “Performance and Resource Model.”

**Files:**

1. Create `src/nginx_log_top/parser.py` with one compiled Combined Log Format pattern, request-target extraction, status validation, and offset-aware timestamp parsing.
2. Create `tests/test_parser.py` covering IPv4/IPv6, query strings, missing values, escaped fields, timezones, non-ASCII values, and malformed lines.
3. Extend `tests/fixtures/mixed.log` with boundary and invalid cases.

**Verification:**

- `pytest -q tests/test_parser.py`
- `ruff check src/nginx_log_top/parser.py tests/test_parser.py`
- `mypy src/nginx_log_top/parser.py`

**Commit:** `step-3: add streaming nginx parser`

## Step 4: Aggregation and Metric Semantics

**Goal:** One pass computes all four requested metrics, deterministic top-10 rankings, malformed totals, and exact User-Agent cardinality with a hard ceiling.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Aggregator,” “Outputs,” and “Data Model”; `PRD.md` P0 requirements.

**Files:**

1. Create `src/nginx_log_top/aggregate.py` with IP/error-URL counters, a 24-slot hourly array, User-Agent set, and `finalize()`.
2. Create `tests/test_aggregate.py` covering ties, top-10 truncation, 399/400/599 boundaries, empty input, all hours, and exact percentages.
3. Add `tests/fixtures/high_cardinality.log` as a small deterministic exhaustion fixture.

**Verification:**

- `pytest -q tests/test_aggregate.py`
- `pytest -q tests/test_aggregate.py -k 'hourly or cardinality or ranking'`
- Assert hourly percentages use `100 × hourly_request_count / total_valid_requests` and total approximately 100% when input is nonempty.

**Commit:** `step-4: implement bounded streaming metrics`

## Step 5: Terminal Renderer

**Goal:** Default interactive output uses readable Rich tables and never emits ANSI escapes to a redirected stream or with `--no-color`.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Outputs” and “Renderers.”

**Files:**

1. Create `src/nginx_log_top/renderers/__init__.py` with the renderer protocol.
2. Create `src/nginx_log_top/renderers/text.py` with summary and four stable report sections.
3. Create `tests/test_renderers.py` with text snapshots, empty-result behavior, and ANSI assertions.

**Verification:**

- `pytest -q tests/test_renderers.py -k text`
- `nginx-log-top tests/fixtures/combined.log --no-color`
- `test -z "$(nginx-log-top tests/fixtures/combined.log | sed -n '/\x1b/p')"`

**Commit:** `step-5: render deterministic terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** Pipelines receive stable, ANSI-free JSON and RFC 4180 CSV matching the schemas in the architecture.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “CLI Interface,” especially “Outputs.”

**Files:**

1. Create `src/nginx_log_top/renderers/json.py` with schema version `1` and ordered data construction.
2. Create `src/nginx_log_top/renderers/csv.py` with header `section,rank,key,count,percentage`.
3. Extend `tests/test_renderers.py` with structural JSON/CSV tests and Unicode/quoting cases.
4. Extend `tests/test_cli.py` with file/stdin parity and machine-mode stdout/stderr tests.

**Verification:**

- `pytest -q tests/test_renderers.py tests/test_cli.py`
- `nginx-log-top --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-log-top --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.reader(sys.stdin))'`

**Commit:** `step-6: add pipeline-safe JSON and CSV`

## Step 7: Integrate Error and Exit-Code Contract

**Goal:** The CLI owns streams correctly, distinguishes every public failure, suppresses partial reports on fatal errors, and handles broken pipes cleanly.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Exit Codes” and “Error Handling and Security.”

**Files:**

1. Update `src/nginx_log_top/cli.py` to connect parser, analyzer, and renderer while mapping typed errors.
2. Update `src/nginx_log_top/errors.py` only if integration reveals a missing typed boundary.
3. Extend `tests/test_cli.py` with explicit cases for every exit code, strict/default malformed handling, diagnostics, broken pipes, and no partial output after cardinality failure.

**Verification:**

- `pytest -q tests/test_cli.py`
- `pytest -q`
- Manually verify the full contract: `0/1/2/3/4`, where `0` is success, `1` input I/O failure, `2` usage error, `3` strict parsing/internal format failure, and `4` unique-cardinality exhaustion.

**Commit:** `step-7: enforce complete CLI failure contract`

## Step 8: Performance, Packaging, and Release Evidence

**Goal:** The installable candidate passes quality gates and processes the deterministic 1 GB workload in under 30 seconds on the documented laptop.

**Time:** ~4 hours

**Context:** `STRATEGIC_PLAN.md` KPIs and Definition of Done; `PROJECT_ARCHITECTURE.md` “Performance and Resource Model.”

**Files:**

1. Create `scripts/generate_benchmark_log.py` to deterministically stream a requested byte size without checking generated data into Git.
2. Create `tests/test_performance.py` with a small default test and an opt-in 1 GB marker.
3. Create `README.md` with Quick Start, schemas, exit codes, supported format, and benchmark reproduction.
4. Update `pyproject.toml` with test, lint, typing, build, and coverage configuration.
5. Update `CLAUDE.md` status and record benchmark environment/result in a release note or checked-in benchmark table.

**Verification:**

- `ruff format --check . && ruff check . && mypy src`
- `pytest --cov=nginx_log_top --cov-report=term-missing --cov-fail-under=90`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `python3.11 scripts/generate_benchmark_log.py --size 1GB --output /tmp/nginx-log-top-1gb.log`
- `/usr/bin/time -v nginx-log-top --json /tmp/nginx-log-top-1gb.log >/dev/null` and confirm elapsed time is `< 30 s` while recording maximum RSS.

**Commit:** `step-8: verify performance and package release`

## Weekend Boundaries

| Boundary | Steps | Outcome |
|---|---|---|
| Saturday morning | 1–3 | Installable command and trusted streaming parser |
| Saturday afternoon | 4–6 | Complete metrics and all output formats |
| Sunday | 7–8 | Full failure contract, test evidence, benchmark, and package candidate |

## Completion Gate

Do not call the implementation complete until all tests pass from a fresh Python 3.11 environment, coverage meets the documented threshold, build artifacts validate, the complete exit-code contract `0/1/2/3/4` has automated coverage, and the representative 1 GB benchmark is recorded below 30 seconds. A failed performance gate triggers profiling and focused optimization, not undocumented semantic changes.

