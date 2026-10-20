# Implementation Plan: nginx-log-report

## Scope and Delivery Model

This plan delivers the P0 local CLI in one weekend. It intentionally creates no database, HTTP API, authentication, server, cloud resource, or Kubernetes manifest. `PROJECT_ARCHITECTURE.md` is the technical source of truth; `PRD.md` defines acceptance behavior.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml` package and console entry point | Every test and command needs an installable boundary | 1 h |
| 2 | Domain/error contracts | All modules must share data and `0/1/2/3/4` failure semantics | 1 h |
| 3 | Deterministic fixtures and benchmark generator | Correctness and speed need reproducible inputs before features | 1.5 h |
| 4 | CI/static-test configuration | Keeps Python 3.11 checks repeatable while features land | 1 h |

## STEP 1: Package Skeleton and CLI Contract

**Goal:** An installable Python 3.11 package exposes `nginx-log-report --help` and `--version`.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Components and Responsibilities” and “CLI Interface”.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, pytest tooling, and the `nginx-log-report` console script.
2. Create `src/nginx_log_report/__init__.py`, `__main__.py`, and `cli.py` with the documented arguments/options but no aggregation logic.
3. Create `tests/test_cli_contract.py` for help, version, option validation, and mutual exclusion.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli_contract.py -q`
- `nginx-log-report --help`

**Commit:** `step-1: scaffold installable CLI contract`

## STEP 2: Domain Models and Exit Semantics

**Goal:** Renderer-neutral records/reports and one authoritative failure mapping exist.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Calculations” and “CLI Interface”.

**Tasks:**

1. Create `src/nginx_log_report/model.py` with frozen `LogRecord`, ranking entry, hourly entry, and `Report` dataclasses.
2. Create `src/nginx_log_report/errors.py` with typed usage/input/cardinality/internal errors.
3. Update `src/nginx_log_report/cli.py` to enforce the complete contract: `0` success, `1` unexpected runtime/internal failure, `2` usage/configuration error, `3` input/read/decode/parse failure or no valid records, `4` unique-cardinality exhaustion.
4. Add `tests/test_exit_codes.py` that exercises `0/1/2/3/4`; code 4 must not be omitted or remapped.

**Verification:**

- `python3.11 -m pytest tests/test_exit_codes.py -q`
- `python3.11 -m compileall -q src tests`

**Commit:** `step-2: define report and exit contracts`

## STEP 3: Streaming Input and Combined-Log Parser

**Goal:** Files and stdin yield validated records one at a time with source-aware rejections.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Parsing Contract” and “Performance and Resource Strategy”.

**Tasks:**

1. Create `src/nginx_log_report/stream.py` for buffered sequential files/stdin and source line numbers.
2. Create `src/nginx_log_report/parser.py` with one compiled combined-log pattern and timestamp validation.
3. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` with small, hand-auditable cases.
4. Create `tests/test_parser.py` and `tests/test_stream.py` for IPv4, IPv6, quoting, timezone offsets, truncated lines, multiple files, and stdin.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py tests/test_stream.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_log_report.parser --cov-branch --cov-fail-under=90`

**Commit:** `step-3: stream and parse combined logs`

## STEP 4: Exact Streaming Aggregations

**Goal:** All four reports are calculated in one pass without retaining raw records.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “Data Model and Calculations”; `PRD.md` FR-3 through FR-6.

**Tasks:**

1. Create `src/nginx_log_report/aggregate.py` for IP/error URL counters, 24 buckets, and exact nonempty User-Agent set.
2. Implement stable top-10 ordering and percentage numerator/denominator handling.
3. Implement hourly percentage exactly as `100 × hourly_request_count / total_valid_requests`.
4. Create `tests/test_aggregate.py` covering ties, no errors, all hours, skipped lines, UA semantics, and percentage totals.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_log_report.aggregate --cov-branch --cov-fail-under=90`

**Commit:** `step-4: implement streaming report calculations`

## STEP 5: Cardinality Guardrails and Strict Mode

**Goal:** Unbounded distinct input cannot cause silent approximation or uncontrolled growth.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “Cardinality Bound”; `PRD.md` FR-2 and FR-8.

**Tasks:**

1. Add pre-insert cardinality checks for client IP, error URL, and User-Agent dimensions in `aggregate.py`.
2. Wire `--max-unique` and `--strict` through `cli.py`.
3. Create `tests/test_cardinality.py` for limit-minus-one, exact-limit, over-limit, repeated-key, and empty-stdout cases.
4. Extend `tests/test_exit_codes.py` to prove malformed input maps to 3 and unique-cardinality exhaustion maps to 4.

**Verification:**

- `python3.11 -m pytest tests/test_cardinality.py tests/test_exit_codes.py -q`
- `python3.11 -m nginx_log_report --max-unique 0 tests/fixtures/combined.log; test $? -eq 2`

**Commit:** `step-5: enforce strict and cardinality failures`

## STEP 6: Terminal, JSON, and CSV Renderers

**Goal:** One report renders as colored human output or stable pipeline-safe schemas.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “CLI Interface”; `PRD.md` FR-7.

**Tasks:**

1. Create `src/nginx_log_report/render/__init__.py`, `terminal.py`, `json.py`, and `csv.py`.
2. Create `tests/golden/report.json` and `tests/golden/report.csv` from the audited fixture.
3. Create `tests/test_renderers.py` for schema shape, deterministic order, valid decoding, CSV quoting, and absence of ANSI sequences in machine modes.
4. Update `cli.py` to select exactly one renderer and keep diagnostics on stderr.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `nginx-log-report --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-log-report --csv tests/fixtures/combined.log | python3.11 -c "import csv,sys; assert list(csv.DictReader(sys.stdin))"`

**Commit:** `step-6: add stable output renderers`

## STEP 7: End-to-End Quality Gate

**Goal:** The installed command satisfies all P0 scenarios and remains internally consistent.

**Time:** ~2.5 hours

**Context:** `PRD.md` “Acceptance Scenarios” and “Release Criteria”.

**Tasks:**

1. Create `tests/test_integration.py` covering stdin, multiple files, totals, all output modes, stdout/stderr separation, and malformed behavior.
2. Configure lint/type/coverage commands in `pyproject.toml` and CI in `.github/workflows/test.yml` for Python 3.11.
3. Check that CLI help, `README.md`, schemas, and the `0/1/2/3/4` exit-code mapping agree.
4. Build wheel/sdist and install the wheel in a clean temporary virtual environment.

**Verification:**

- `python3.11 -m pytest --cov=nginx_log_report --cov-branch --cov-fail-under=90`
- `python3.11 -m ruff check src tests`
- `python3.11 -m mypy src`
- `python3.11 -m build`

**Commit:** `step-7: verify end-to-end CLI quality`

## STEP 8: Performance Evidence and Release Documentation

**Goal:** The performance claim is measured and the package is handoff-ready without publishing it.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Performance and Resource Strategy”; `STRATEGIC_PLAN.md` KPIs.

**Tasks:**

1. Create `bench/generate_log.py` to generate a deterministic representative log outside tracked artifacts, and `bench/run.sh` to record command, bytes, Python version, CPU, wall time, and peak RSS.
2. Create `tests/test_benchmark_contract.py` for generator validity and byte target; keep the 1 GB run out of the fast unit suite.
3. Update `README.md` with measured results, supported input, schemas, limits, and troubleshooting.
4. Update `CLAUDE.md` status and record any P1 gzip work as deferred; do not publish or deploy.

**Verification:**

- `python3.11 -m pytest -q`
- `python3.11 bench/generate_log.py --bytes 1073741824 --output /tmp/nginx-log-report-benchmark.log`
- `/usr/bin/time -v nginx-log-report --json /tmp/nginx-log-report-benchmark.log >/tmp/nginx-log-report-result.json`
- `python3.11 -m build && python3.11 -m twine check dist/*`

**Commit:** `step-8: document benchmark and release readiness`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable boundary, contracts, and parsing | ~6 h |
| Saturday PM | 4–5 | Correct one-pass metrics and resource safety | ~5 h |
| Sunday AM | 6–7 | Output modes and end-to-end quality | ~5.5 h |
| Sunday PM | 8 | Performance evidence and handoff | ~2.5 h |

## Dependency and Rollback Notes

Each step lands only after its verification commands pass. If a step fails, revert only that unaccepted step and keep the last green package boundary. Gzip (P1) and configurable top-N (P2) must not displace P0 correctness or benchmark work. Package-index publication, deployment, deletion, and other external actions require separate human approval.
