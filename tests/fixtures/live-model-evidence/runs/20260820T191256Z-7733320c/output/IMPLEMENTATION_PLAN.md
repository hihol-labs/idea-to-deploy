# Implementation Plan: Nginx Stream Analytics CLI

This is a planning guide only; no product code is included. Steps follow dependency order while preserving the strategic RICE ordering where dependencies allow. Total estimate: 14–18 focused hours over one weekend.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console-entry skeleton | Every test and feature needs import/install boundaries | 1 h |
| 2 | Dataclass and output schema contracts | Parser, aggregator, and renderers need stable types | 1 h |
| 3 | Test fixtures and benchmark generator design | Correctness and performance must be measurable before feature completion | 1 h |

There is intentionally no database schema, authentication layer, HTTP API, Docker setup, or deployment pipeline runway.

## Step 1: Package and Quality Baseline

**Goal:** a Python 3.11 wheel exposes the empty `nginx-log-report` Click command and the quality toolchain is executable.  
**Time:** ~1.5 hours  
**Context:** PROJECT_ARCHITECTURE.md “Packaging and Deployment”, “Component Model”.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, console script, pytest, Ruff, and mypy configuration.
2. Create `src/nginx_stream_analytics/__init__.py` and `src/nginx_stream_analytics/cli.py` with version/help plumbing only.
3. Create `tests/test_cli.py` for install/import/help smoke behavior.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/nginx-log-report --help`

**Commit:** `step-1: establish package and CLI baseline`

## Step 2: Domain and Schema Contracts

**Goal:** parser records and report/output schemas are explicit and independently testable.  
**Time:** ~1.5 hours  
**Context:** PROJECT_ARCHITECTURE.md “Data and Streaming Model”, “CLI Interface”.

**Tasks:**

1. Create `src/nginx_stream_analytics/models.py` with frozen/slotted dataclasses for `LogRecord`, ranked items, hourly buckets, totals, and `Report`.
2. Create `src/nginx_stream_analytics/errors.py` with domain exceptions for input, no-valid-records, and cardinality exhaustion.
3. Create `tests/test_models.py` and `tests/contracts/expected_schema.json` to lock types and JSON field names.

**Verification:**

- `.venv/bin/python -m pytest tests/test_models.py -q`
- `.venv/bin/python -m mypy src`

**Commit:** `step-2: define domain and report contracts`

## Step 3: Streaming Input and Parser

**Goal:** file/stdin input yields valid records once while malformed input is counted safely.  
**Time:** ~2.5 hours  
**Context:** PROJECT_ARCHITECTURE.md “Data and Streaming Model”, PRD US-1.

**Tasks:**

1. Create `src/nginx_stream_analytics/input.py` for read-only buffered file/stdin iteration and maximum-line-length enforcement.
2. Create `src/nginx_stream_analytics/parser.py` for the documented combined-format subset without retaining raw lines.
3. Create `tests/fixtures/access_small.log`, `tests/fixtures/access_malformed.log`, `tests/test_input.py`, and `tests/test_parser.py` covering IPv4/IPv6, request targets, timestamp hours, User-Agents, blanks, escapes, and malformed fields.

**Verification:**

- `.venv/bin/python -m pytest tests/test_input.py tests/test_parser.py -q`
- `.venv/bin/python -m ruff check src/nginx_stream_analytics/input.py src/nginx_stream_analytics/parser.py`

**Commit:** `step-3: stream and parse nginx records`

## Step 4: Exact Aggregations and Guardrails

**Goal:** all four metrics are correct, deterministic, and bounded by the unique-cardinality policy.  
**Time:** ~2.5 hours  
**Context:** PROJECT_ARCHITECTURE.md “Data and Streaming Model”, PRD US-2 through US-5.

**Tasks:**

1. Create `src/nginx_stream_analytics/aggregate.py` with exact IP/error-URL counters, fixed 24-hour buckets, non-empty User-Agent set, and pre-insertion guard checks.
2. Compute hourly percentages only as `100 × hourly_request_count / total_valid_requests`; compute unique User-Agent share against `total_valid_requests`.
3. Create `tests/test_aggregate.py` for status boundaries 399/400/599/600, deterministic ties, zero buckets, malformed exclusion, empty agents, and just-below/at/above guardrail cases.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate.py --cov=nginx_stream_analytics.aggregate --cov-fail-under=95`

**Commit:** `step-4: implement exact bounded aggregations`

## Step 5: JSON and CSV Renderers

**Goal:** stable, ANSI-free pipeline output matches versioned schemas.  
**Time:** ~1.5 hours  
**Context:** PROJECT_ARCHITECTURE.md “CLI Interface / Outputs”, PRD US-7.

**Tasks:**

1. Create `src/nginx_stream_analytics/render/__init__.py` and `render/json.py` for the versioned JSON object.
2. Create `src/nginx_stream_analytics/render/csv.py` using `csv.writer` and the long-form `metric,rank,key,count,percentage` schema.
3. Create `tests/golden/report.json`, `tests/golden/report.csv`, and `tests/test_machine_renderers.py` for byte-stable output, quoting, Unicode, and absence of ANSI.

**Verification:**

- `.venv/bin/python -m pytest tests/test_machine_renderers.py -q`
- `.venv/bin/python -m json.tool tests/golden/report.json >/dev/null`

**Commit:** `step-5: add deterministic machine renderers`

## Step 6: Rich Terminal Renderer

**Goal:** default output is readable, TTY-aware, and safe for untrusted log text.  
**Time:** ~1.5 hours  
**Context:** PROJECT_ARCHITECTURE.md “Security and Privacy”, PRD US-6.

**Tasks:**

1. Create `src/nginx_stream_analytics/render/terminal.py` with four labeled tables, totals, fixed percentage formatting, and markup disabled/escaped for data.
2. Add `tests/golden/report.txt` and `tests/test_terminal_renderer.py` covering no-color stability, narrow terminal behavior, control text, and TTY color policy.

**Verification:**

- `.venv/bin/python -m pytest tests/test_terminal_renderer.py -q`
- `.venv/bin/python -m pytest tests/test_terminal_renderer.py -k control -q`

**Commit:** `step-6: add safe Rich terminal report`

## Step 7: CLI Integration and Exit Contract

**Goal:** the public command connects the pipeline and enforces all options, streams, and failures.  
**Time:** ~2 hours  
**Context:** PROJECT_ARCHITECTURE.md “CLI Interface”, PRD “Output Contract”.

**Tasks:**

1. Complete `src/nginx_stream_analytics/cli.py` with optional input, `--json`, `--csv`, `--no-color`, and positive `--max-unique`.
2. Map success/input/usage/no-valid/cardinality outcomes to exactly `0/1/2/3/4`; code `4` means unique-cardinality exhaustion.
3. Buffer rendering until complete aggregation so every nonzero exit produces no partial JSON/CSV.
4. Expand `tests/test_cli.py` and add `tests/test_exit_codes.py` to exercise file/stdin, flag conflicts, stdout/stderr isolation, and every exit code.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py tests/test_exit_codes.py -q`
- `.venv/bin/nginx-log-report --json tests/fixtures/access_small.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-7: integrate CLI and exit codes`

## Step 8: Performance, Packaging, and Release Evidence

**Goal:** the exact release candidate meets correctness, installation, privacy, and 1 GB performance gates.  
**Time:** ~2.5 hours  
**Context:** PROJECT_ARCHITECTURE.md “Performance and Capacity”, STRATEGIC_PLAN.md “Definition of Done”.

**Tasks:**

1. Create `benchmarks/generate_log.py` and `benchmarks/run_benchmark.py` to deterministically generate/measure a representative uncommitted 1 GB fixture, wall time, peak RSS, and line count.
2. Create `tests/test_end_to_end.py` for terminal/JSON/CSV golden flows and `tests/test_install.py` for wheel console-entry smoke behavior.
3. Update `README.md` with install, examples, schemas, supported format, performance environment, privacy, and exit codes.
4. Build wheel/sdist and run the Idea to Deploy Verification Loop against the exact staged candidate; apply the risk-tier checker and retain its current adjudication receipt.

**Verification:**

- `.venv/bin/python -m pytest -q`
- `.venv/bin/python -m ruff check src tests benchmarks && .venv/bin/python -m mypy src`
- `.venv/bin/python benchmarks/run_benchmark.py --size-gib 1 --max-seconds 30`
- `.venv/bin/python -m build && .venv/bin/python -m twine check dist/*`

**Commit:** `step-8: verify performance and package release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable skeleton and trustworthy parsing | 4–5 h |
| Saturday PM | 4–5 | Correct metrics and machine output | 4 h |
| Sunday AM | 6–7 | Terminal UX and complete CLI behavior | 3–4 h |
| Sunday PM | 8 | Performance and release evidence | 3–4 h |

## Universal Exit-Code Contract

Every implementation step and guide must preserve: `0` success, `1` input/I/O or unexpected runtime failure, `2` CLI usage error, `3` no valid records, and `4` unique-cardinality exhaustion. Code 4 must never be omitted, remapped, or converted to a partial/approximate success.

## Handoff Rule

At the end of each step, record commands and real outputs, reconcile `.itd-memory/STATE.json`, and leave only one active unit. Completion requires a current adjudication receipt for the exact candidate, not narration or a standalone passing message.
