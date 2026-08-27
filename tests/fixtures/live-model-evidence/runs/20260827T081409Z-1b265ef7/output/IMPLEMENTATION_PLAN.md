# Implementation Plan: Nginx Stream Analyzer

## Scope and Operating Rules

This is an eight-step, one-weekend plan. Preserve WIP=1: complete and verify one step before starting the next. `PRD.md` is the behavioral source; `PROJECT_ARCHITECTURE.md` is the technical source. No database, API, server, auth, cloud, container, or Kubernetes work is permitted.

The exit-code contract is fixed throughout implementation: `0` successful output; `1` input/I/O failure; `2` CLI usage/configuration error; `3` no valid requests; `4` unique-cardinality exhaustion. No implementation step may omit, remap, or silently absorb code `4`.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` package and pip entry points | Every executable test depends on import/install behavior | 1 hour |
| 2 | Domain models and error taxonomy | Prevent renderer/parser coupling and freeze exits | 1 hour |
| 3 | Fixture and golden-output conventions | Enables test-first parser and renderer work | 1 hour |
| 4 | Benchmark protocol | Prevents optimizing against an undefined laptop/data shape | 0.5 hour |

## Step 1: Package and CLI Skeleton

**Goal:** A Python 3.11 package installs and exposes both command forms with help/version behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Component Model, CLI Interface, Packaging and Deployment.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, and `nginx-stream-analyzer` console entry.
2. Create `src/nginx_stream_analyzer/__init__.py`, `__main__.py`, and `cli.py`.
3. Create `tests/test_cli.py` for help, version, module entry, invalid option, and format-conflict behavior.
4. Add developer test/lint/type dependencies in the chosen packaging extra without adding runtime services.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m nginx_stream_analyzer --help`
- `pytest -q tests/test_cli.py`

**Commit:** `step-1: scaffold installable cli package`

## Step 2: Domain Models and Exit Policy

**Goal:** Typed results and failures express all data and process outcomes before parsing is implemented.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections Data Model and Streaming Algorithm, CLI Interface/Exit Codes, Output Schema.

**Tasks:**

1. Create `src/nginx_stream_analyzer/models.py` with dataclasses for parsed records, ranked IP/error items, hourly buckets, User-Agent summary, and complete analysis result.
2. Create `src/nginx_stream_analyzer/errors.py` with I/O, no-valid-data, and cardinality-exhaustion domain errors.
3. Update `cli.py` with the single exception-to-exit mapping and stderr-only diagnostics.
4. Create `tests/test_errors.py` covering codes `0/1/2/3/4`, explicitly asserting `4` for unique-cardinality exhaustion.

**Verification:**

- `pytest -q tests/test_errors.py tests/test_cli.py`
- `python3.11 -m nginx_stream_analyzer --top 0; test $? -eq 2`

**Commit:** `step-2: define models and complete exit contract`

## Step 3: Access-Log Parser

**Goal:** Supported common and combined lines become exact `ParsedRecord` values; malformed input is safely rejected.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Supported Input Contract and Security and Privacy; `PRD.md` FR-02 and Metric Semantics.

**Tasks:**

1. Create `src/nginx_stream_analyzer/parser.py` with a precompiled parser, strict timestamp/status/request validation, and a maximum-line-length policy.
2. Create `tests/fixtures/access_valid.log` and `tests/fixtures/access_mixed.log` with common, combined, timezone, escaped, blank, malformed, 4xx, and 5xx cases.
3. Create `tests/test_parser.py` with parameterized records and rejection reasons; ensure diagnostic excerpts are bounded.
4. Confirm log tokens are treated as data and Rich markup is never interpreted downstream.

**Verification:**

- `pytest -q tests/test_parser.py`
- `pytest -q --cov=nginx_stream_analyzer.parser --cov-fail-under=90 tests/test_parser.py`

**Commit:** `step-3: parse supported nginx access logs`

## Step 4: One-Pass Aggregation

**Goal:** A single input traversal computes every required metric exactly and deterministically.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Data Model and Streaming Algorithm; `PRD.md` FR-03 through FR-07.

**Tasks:**

1. Create `src/nginx_stream_analyzer/aggregate.py` with line/valid/malformed totals, IP/error counters, 24 hourly buckets, and exact User-Agent set.
2. Implement deterministic count-descending/key-ascending top-N selection and separate 4xx/5xx URL subtotals.
3. Implement hourly percentages using `100 × hourly_request_count / total_valid_requests` and User-Agent share with the specified denominator.
4. Enforce `--max-unique-user-agents` before inserting a new value; raise the error mapped to exit `4`.
5. Create `tests/test_aggregate.py` including ties, missing agents, zero hours, ceiling boundary, boundary+1, and a generator that proves one-pass consumption.

**Verification:**

- `pytest -q tests/test_aggregate.py`
- `pytest -q --cov=nginx_stream_analyzer.aggregate --cov-fail-under=90 tests/test_aggregate.py`

**Commit:** `step-4: implement guarded streaming aggregates`

## Step 5: Terminal Renderer

**Goal:** Default output is a safe, readable Rich report with correct color behavior.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface/Outputs and Security and Privacy; `PRD.md` FR-08.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/__init__.py` and `text.py`.
2. Render summary, top IP, error URL, 24-hour distribution, and User-Agent sections from `AnalysisResult` only.
3. Implement auto/forced/disabled color and disable Rich markup for untrusted values.
4. Create `tests/golden/report.txt` and `tests/test_text_renderer.py` for no-color output, TTY behavior, escaping, zero rows, and malformed warning separation.

**Verification:**

- `pytest -q tests/test_text_renderer.py`
- `python3.11 -m nginx_stream_analyzer --no-color tests/fixtures/access_valid.log > /tmp/nginx-report.txt`

**Commit:** `step-5: render safe rich terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** Pipeline formats are deterministic, machine-readable, and isolated from diagnostics.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Output Schema and CLI Interface/Outputs; `PRD.md` FR-09 and FR-10.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/json.py` with schema version 1 and six-decimal percentage serialization.
2. Create `src/nginx_stream_analyzer/renderers/csv.py` with the exact normalized header and fixed section order.
3. Connect mutually exclusive `--json` and `--csv` options in `cli.py`.
4. Create `tests/golden/report.json`, `tests/golden/report.csv`, `tests/test_json_renderer.py`, and `tests/test_csv_renderer.py` including hostile quoting/Unicode values.

**Verification:**

- `pytest -q tests/test_json_renderer.py tests/test_csv_renderer.py`
- `python3.11 -m nginx_stream_analyzer --json tests/fixtures/access_valid.log | python3.11 -m json.tool >/dev/null`
- `python3.11 -m nginx_stream_analyzer --csv tests/fixtures/access_valid.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: add stable json and csv output`

## Step 7: End-to-End Contracts and Packaging

**Goal:** All input modes, outputs, failures, and installation behavior work as one product.

**Time:** ~2.5 hours

**Context:** all P0 requirements in `PRD.md`; full CLI Interface in `PROJECT_ARCHITECTURE.md`.

**Tasks:**

1. Create `tests/test_integration.py` comparing file and stdin results in all formats.
2. Add subprocess cases for missing file (`1`), usage conflict (`2`), all-malformed input (`3`), and unique-cardinality exhaustion (`4`), asserting empty stdout on failures.
3. Create `tests/test_install.py` or a documented isolated-venv smoke command for wheel installation and both entry points.
4. Build wheel/sdist and inspect them to exclude fixtures, logs, and local artifacts.
5. Update user-facing usage documentation only after behavior is verified.

**Verification:**

- `pytest -q --cov=nginx_stream_analyzer --cov-fail-under=90`
- `python3.11 -m build`
- `python3.11 -m twine check dist/*`

**Commit:** `step-7: verify cli contracts and distributions`

## Step 8: Performance, Safety, and Release Gate

**Goal:** The exact candidate meets correctness, bounded-operation, and 1 GB performance acceptance.

**Time:** ~3 hours

**Context:** `STRATEGIC_PLAN.md` KPIs/Definition of Done; `PROJECT_ARCHITECTURE.md` Performance and Resource Strategy; `PRD.md` NFRs and Release Acceptance.

**Tasks:**

1. Create `benchmarks/generate_log.py` for deterministic external-size fixtures and `benchmarks/run.py` to record wall time, environment, throughput, and peak RSS; generated 1 GB data remains ignored/untracked and is hash-declared if used by the project oracle.
2. Create `tests/test_resource_guards.py` for maximum line length, hostile terminal strings, malformed-heavy streams, and cardinality ceiling behavior.
3. Run the small oracle first, then the 1 GB benchmark on the named laptop; profile and make only evidence-driven optimizations that preserve specs.
4. Freeze the exact staged candidate, run its machine oracle, apply the project risk-tier checker, and retain a current revalidated adjudication receipt before accepting completion.
5. Reconcile `.itd-memory` state and update `CLAUDE.md` step statuses at handoff.

**Verification:**

- `pytest -q --cov=nginx_stream_analyzer --cov-fail-under=90`
- `python3.11 benchmarks/run.py --size-gib 1 --max-seconds 30`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- Run the commands named by the active `.itd/VERIFICATION_CONTRACT.json` against the exact frozen candidate.

**Commit:** `step-8: meet performance and release gates`

## Weekend Checkpoints

| Checkpoint | Steps | Required result |
|---|---|---|
| Saturday midday | 1–3 | Installable CLI and trustworthy parser |
| Saturday evening | 4 | Four metrics and exhaustion behavior correct |
| Sunday midday | 5–7 | Three output modes and all exit contracts integrated |
| Sunday evening | 8 | Benchmark evidence and handoff-ready candidate |

## Plan Completion Evidence

Implementation is not complete because a step is narrated or committed. Each step requires its listed commands, and final acceptance requires the current project verification receipt. Any failed performance or correctness check returns the active unit to recovery; it is not waived by the weekend schedule.
