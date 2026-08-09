# Implementation Plan: nginx-log-top

This is a future implementation sequence, not product code. Steps follow dependencies first and then the approved RICE value order. Total target effort is one weekend.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package and test skeleton | All modules and checks need stable import/entry-point paths | 1 h |
| 2 | Golden fixtures and benchmark protocol | Output and performance claims need reproducible evidence | 1 h |
| 3 | Domain/output contracts | Parser, aggregation, and renderers must agree on exact data | 1 h |

No database, authentication, API, Docker, or CI/CD runway is needed for this local weekend CLI.

## Step 1: Package and Contract Skeleton

**Goal:** The package installs on Python 3.11 and exposes the planned entry points without implementing metrics.

**Time:** ~1 hour  
**Context:** `PROJECT_ARCHITECTURE.md` — Component Boundaries and CLI Interface.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click, Rich, build metadata, and `nginx-log-top` entry point.
2. Create `src/nginx_log_top/__init__.py`, `src/nginx_log_top/__main__.py`, and `src/nginx_log_top/cli.py`.
3. Create `tests/test_cli.py` for help, version, invocation, and mutually exclusive format options.

**Verification:**

- `python3.11 -m pip install -e .`
- `python3.11 -m pytest tests/test_cli.py`
- `nginx-log-top --help`

**Commit:** `step-1: establish package and CLI contracts`

## Step 2: Domain Models and Supported Fixtures

**Goal:** Typed records and report snapshots encode the documented semantics, backed by representative fixtures.

**Time:** ~1 hour  
**Context:** `PROJECT_ARCHITECTURE.md` — Domain and Parsing Contract.

**Tasks:**

1. Create `src/nginx_log_top/models.py` with frozen `AccessRecord`, `Diagnostics`, ranked item, and `ReportSnapshot` dataclasses.
2. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, and `tests/fixtures/ties.log` with non-sensitive synthetic lines.
3. Create `tests/test_models.py` for invariants and serialization-ready values.

**Verification:**

- `python3.11 -m pytest tests/test_models.py`
- `python3.11 -m compileall -q src`

**Commit:** `step-2: define domain records and fixtures`

## Step 3: Combined-Log Streaming Parser

**Goal:** Supported lines parse incrementally with timezone-correct timestamps and classified failures.

**Time:** ~2 hours  
**Context:** `PROJECT_ARCHITECTURE.md` — Domain and Parsing Contract; Error Handling and Security.

**Tasks:**

1. Create `src/nginx_log_top/parser.py` with a compiled parser and line-numbered `ParseResult` behavior.
2. Create `src/nginx_log_top/errors.py` for expected input/parser failures and exit mappings.
3. Create `tests/test_parser.py` covering the normative lexical grammar: IPv4/IPv6, absent fields, target spaces/query strings, escaped quote/backslash/hex, `-` bytes, timezone offsets, 64 KiB boundary, and malformed/truncated cases.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py`
- `python3.11 -m ruff check src/nginx_log_top/parser.py tests/test_parser.py`

**Commit:** `step-3: parse nginx combined logs incrementally`

## Step 4: Streaming Aggregation

**Goal:** One pass produces all four exact metrics and diagnostics with deterministic ties.

**Time:** ~2 hours  
**Context:** `PROJECT_ARCHITECTURE.md` — System Context and Data Flow; Performance and Resource Strategy.

**Tasks:**

1. Create `src/nginx_log_top/aggregate.py` with IP/error-URL counters, 24 buckets, exact User-Agent set, and finalization.
2. Create `tests/test_aggregate.py` for 4xx/5xx bounds, all hours, tie sorting, top-10 truncation, duplicates, and empty snapshots.
3. Add `tests/test_streaming.py` with an iterator that fails if eagerly materialized.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py tests/test_streaming.py`
- `python3.11 -m ruff check src tests`

**Commit:** `step-4: compute exact reports in one pass`

## Step 5: Input Lifecycle, Diagnostics, and Exit Codes

**Goal:** File/stdin handling and every documented terminal condition behave predictably.

**Time:** ~1.5 hours  
**Context:** `PROJECT_ARCHITECTURE.md` — CLI Interface.

**Tasks:**

1. Complete `src/nginx_log_top/cli.py` stream ownership, UTF-8 error handling, zero-valid input behavior, and broken-pipe handling.
2. Complete `src/nginx_log_top/errors.py` mapping to codes 1, 2, 3, and 4.
3. Extend `tests/test_cli.py` with stdin, missing/unreadable file, invalid bytes, all-malformed, mixed-valid, broken-pipe, and stderr separation cases.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py`
- `sh -c 'nginx-log-top tests/fixtures/combined.log >/dev/null'`

**Commit:** `step-5: enforce input and exit-code contract`

## Step 6: Terminal Renderer

**Goal:** Default output is readable, safely escaped, colored only when appropriate, and contains all reports.

**Time:** ~1.5 hours  
**Context:** `PROJECT_ARCHITECTURE.md` — Outputs and Security.

**Tasks:**

1. Create `src/nginx_log_top/render/__init__.py` and `src/nginx_log_top/render/terminal.py`.
2. Add `tests/test_terminal_output.py` and `tests/golden/terminal.txt` for section ordering, no-color behavior, diagnostics, markup-like values, ESC/C0/C1/DEL, and bidi/format controls.
3. Update `src/nginx_log_top/cli.py` to select terminal rendering by default.

**Verification:**

- `python3.11 -m pytest tests/test_terminal_output.py`
- `NO_COLOR=1 nginx-log-top tests/fixtures/combined.log | diff -u tests/golden/terminal.txt -`

**Commit:** `step-6: render safe terminal reports`

## Step 7: JSON and CSV Renderers

**Goal:** Pipelines receive stable, ANSI-free, deterministic machine formats.

**Time:** ~2 hours  
**Context:** `PROJECT_ARCHITECTURE.md` — CLI Interface and Output Schema Examples.

**Tasks:**

1. Create `src/nginx_log_top/render/json.py` and `src/nginx_log_top/render/csv.py`.
2. Create `tests/test_json_output.py`, `tests/test_csv_output.py`, `tests/golden/report.json`, and `tests/golden/report.csv`; assert normative types, 24 buckets, half-up precision, row matrix/order, UTF-8, empty cells, and LF/CRLF contracts.
3. Extend `src/nginx_log_top/cli.py` to select exactly one renderer and prevent partial machine output on known failures.

**Verification:**

- `python3.11 -m pytest tests/test_json_output.py tests/test_csv_output.py`
- `nginx-log-top --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-log-top --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-7: add stable JSON and CSV contracts`

## Step 8: Performance, Packaging, and Release Evidence

**Goal:** The exact candidate is installable, fully tested, and meets the declared 1 GB performance target.

**Time:** ~3 hours  
**Context:** `STRATEGIC_PLAN.md` — KPIs and Definition of Done; `PROJECT_ARCHITECTURE.md` — Performance.

**Tasks:**

1. Create `tools/generate_benchmark_fixture.py` with deterministic seed/size/cardinality controls and a benchmark manifest containing the architecture's environment, fixture, run, hash, and threshold fields.
2. Create `tests/test_end_to_end.py` and `tests/test_performance_smoke.py`; keep the full 1 GB run as an explicit release benchmark rather than a normal unit test.
3. Update `README.md` with installation, examples, supported format, output schema, limitations, and benchmark environment/result.
4. Add `LICENSE`, build wheel/sdist, install the wheel in a fresh virtual environment, and exercise all three output modes.

**Verification:**

- `python3.11 -m pytest`
- `python3.11 -m ruff check src tests tools`
- `python3.11 -m build`
- `/usr/bin/time -f 'elapsed=%e rss_kb=%M' nginx-log-top --json .bench/combined-1gb.log >/dev/null`
- `sha256sum .bench/combined-1gb.log`

**Commit:** `step-8: verify performance and release artifacts`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Runway, models, and trustworthy parsing | Saturday morning |
| Weekend block 2 | 4–5 | Complete metric and failure behavior | Saturday afternoon |
| Weekend block 3 | 6–7 | Human and pipeline output | Sunday morning |
| Weekend block 4 | 8 | Performance and release evidence | Sunday afternoon |

## Plan Acceptance

Do not reorder renderers ahead of domain aggregation, and do not accept the release from prose. Record command outputs, the benchmark environment, fixture hash, elapsed time, and peak RSS for the exact candidate. See [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) for execution prompts.
