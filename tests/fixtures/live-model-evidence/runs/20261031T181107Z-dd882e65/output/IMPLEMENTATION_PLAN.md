# Implementation Plan: nginx-log-report

## Delivery Strategy

Eight dependency-ordered steps fit the approved one-weekend scope. Each step ends with an executable check. Do not begin product code until the specifications in `PRD.md` and `PROJECT_ARCHITECTURE.md` are accepted as the source of truth.

Every implementation step must preserve the complete `0/1/2/3/4` contract: `0` success, `1` operational I/O failure, `2` CLI usage error, `3` no valid records, and `4` unique-cardinality exhaustion.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src` package and pip console entry point | Every behavior needs an importable, installable boundary | 1 hour |
| 2 | Representative fixtures and golden expectations | Parsing and output need stable evidence | 1 hour |
| 3 | Benchmark generator and measurement command | Performance risk must be visible before polish | 1 hour |

No database schema, authentication system, container stack, or CI deployment infrastructure is required; those would contradict the architecture.

## STEP 1: Package and CLI Skeleton

**Goal:** A clean Python 3.11 environment can install the package and invoke help/version.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections Components, CLI Interface, Packaging.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, pytest configuration, and console script.
2. Create `src/nginx_log_report/__init__.py`, `src/nginx_log_report/__main__.py`, and `src/nginx_log_report/cli.py`.
3. Create `tests/test_cli_basics.py` for help, version, mutually exclusive formats, and missing option arguments.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli_basics.py -q`
- `nginx-log-report --help`

**Commit:** `step-1: scaffold installable CLI package`

## STEP 2: Typed Domain Model and Combined-Log Parser

**Goal:** Valid combined-log lines become typed records and malformed lines return structured parse failures.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Data Model; `PRD.md` P0 requirements 1–2.

**Tasks:**

1. Create `src/nginx_log_report/model.py` with frozen dataclasses for `LogRecord`, `RankedItem`, and `Report`.
2. Create `src/nginx_log_report/parser.py` with one compiled expression and field validators.
3. Create `tests/fixtures/basic.log`, `tests/fixtures/mixed.log`, and `tests/test_parser.py` covering IPv4/IPv6 text, escaped values, timezone offsets, malformed status, and invalid encoding behavior.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_log_report.parser --cov-fail-under=95`

**Commit:** `step-2: parse nginx combined log records`

## STEP 3: Streaming Aggregation and Cardinality Guard

**Goal:** A line iterator produces all four exact metrics without retaining raw records, and cardinality overflow is explicit.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Data Model, Error Policy; `PRD.md` P0 requirements 3–7.

**Tasks:**

1. Create `src/nginx_log_report/aggregate.py` with `StreamingAggregator` and `UniqueCardinalityExhausted`.
2. Calculate hourly percentages with `100 × hourly_request_count / total_valid_requests` and unique share with the specified valid-request denominator.
3. Create `tests/test_aggregate.py` for status boundaries, all 24 buckets, deterministic ties, fewer than ten values, malformed counts, empty input, and the exact cardinality boundary.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_log_report.aggregate --cov-fail-under=95`

**Commit:** `step-3: add exact streaming metrics and limits`

## STEP 4: Terminal Renderer

**Goal:** The default command presents a readable four-section Rich report without interpreting log data as markup.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Outputs, Security; `PRD.md` Output Acceptance Contract.

**Tasks:**

1. Create `src/nginx_log_report/render/__init__.py` and `src/nginx_log_report/render/terminal.py`.
2. Implement TTY auto-color plus `--color/--no-color`, valid/malformed totals, rankings, 24-hour percentages, and unique share.
3. Create `tests/test_terminal_output.py` with snapshots for colored, no-color, escaping, and narrow-terminal cases.

**Verification:**

- `python3.11 -m pytest tests/test_terminal_output.py -q`
- `nginx-log-report --no-color tests/fixtures/basic.log`

**Commit:** `step-4: render safe Rich terminal report`

## STEP 5: JSON and CSV Renderers

**Goal:** Pipelines receive deterministic, ANSI-free structured reports matching the documented schemas.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Outputs; `PRD.md` P0 requirement 8.

**Tasks:**

1. Create `src/nginx_log_report/render/json.py` with the versioned JSON schema.
2. Create `src/nginx_log_report/render/csv.py` with `metric,rank,key,count,percentage` rows through `csv.writer`.
3. Create `tests/test_json_output.py` and `tests/test_csv_output.py` for schemas, escaping, deterministic order, empty cells, and format parity.

**Verification:**

- `python3.11 -m pytest tests/test_json_output.py tests/test_csv_output.py -q`
- `nginx-log-report --json tests/fixtures/basic.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: add stable JSON and CSV contracts`

## STEP 6: End-to-End CLI and Exit Codes

**Goal:** File, stdin, follow, diagnostics, and every exit code behave as one coherent CLI.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface and Error Policy; `PRD.md` release scenarios.

**Tasks:**

1. Complete `src/nginx_log_report/cli.py` stream ownership, renderer selection, `--follow`, clean interrupt, and stderr behavior.
2. Map the full contract without remapping: `0` success, `1` I/O failure, `2` usage error, `3` no valid records, `4` unique-cardinality exhaustion.
3. Create `tests/test_cli_integration.py` and `tests/test_exit_codes.py` covering file/stdin parity, broken input/output, all-invalid data, option conflicts, follow validation, and cardinality overflow.

**Verification:**

- `python3.11 -m pytest tests/test_cli_integration.py tests/test_exit_codes.py -q`
- `nginx-log-report --json tests/fixtures/basic.log >/tmp/nginx-log-report.json`

**Commit:** `step-6: integrate streams follow mode and exit contract`

## STEP 7: Performance and Resource Verification

**Goal:** The release candidate demonstrates the 1 GB/30 s target and records peak memory on the reference laptop.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Performance Design; `STRATEGIC_PLAN.md` KPIs and Risks.

**Tasks:**

1. Create `tests/performance/generate_log.py` to deterministically generate, not commit, a representative 1 GB file.
2. Create `tests/performance/test_streaming.py` for smaller CI-sized throughput and memory-regression checks.
3. Document reference hardware and `/usr/bin/time` procedure in `docs/PERFORMANCE.md`; profile with `python -m cProfile` only if the gate misses.

**Verification:**

- `python3.11 -m pytest tests/performance/test_streaming.py -q`
- `python3.11 tests/performance/generate_log.py --size-gib 1 --output /tmp/nginx-1g.log`
- `/usr/bin/time -f '%e seconds %M KiB' nginx-log-report --json /tmp/nginx-1g.log >/dev/null`

**Commit:** `step-7: verify streaming performance and memory`

## STEP 8: Release Documentation and Clean Install

**Goal:** A new user can install, run, and understand the CLI, and the full test suite proves the documented contract.

**Time:** ~1.5 hours

**Context:** All blueprint documents, especially `PRD.md` acceptance scenarios.

**Tasks:**

1. Update `README.md` with actual install, examples, formats, supported log grammar, limitations, and exit codes.
2. Add `CHANGELOG.md`, `LICENSE`, and packaging exclusions only after choosing the actual license and release version.
3. Update `CLAUDE.md` status and run build/install smoke tests in a fresh virtual environment.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_log_report --cov-fail-under=90`
- `python3.11 -m build`
- `python3.11 -m venv /tmp/nginx-log-report-venv && /tmp/nginx-log-report-venv/bin/pip install dist/*.whl && /tmp/nginx-log-report-venv/bin/nginx-log-report --version`

**Commit:** `step-8: prepare verified pip release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable shell and correct parser | ~3 hours |
| Saturday PM | 3–4 | Exact streaming core and terminal report | ~4.5 hours |
| Sunday AM | 5–6 | Pipeline formats and complete CLI contract | ~4 hours |
| Sunday PM | 7–8 | Performance evidence and release readiness | ~3.5 hours |

## Completion Gate

The plan is complete only after the full suite is green, coverage is at least 90%, clean-wheel installation succeeds, all acceptance scenarios pass, and the measured reference run processes 1 GB in under 30 seconds. If any gate fails, report the observed output and keep the corresponding step incomplete.
