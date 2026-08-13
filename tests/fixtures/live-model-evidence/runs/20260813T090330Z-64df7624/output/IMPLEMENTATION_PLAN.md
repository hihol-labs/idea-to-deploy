# Implementation Plan: Nginx Insights CLI

This is a dependency-ordered, one-weekend plan. It describes future implementation work; it does not include product code. `PRD.md` is the behavior source of truth and `PROJECT_ARCHITECTURE.md` is the interface source of truth.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package metadata and `src/` layout | Every module and CLI test needs an importable package | 0.5 h |
| 2 | Domain dataclasses and typed failures | Parser, aggregator, and renderers need one stable contract | 0.75 h |
| 3 | Deterministic fixtures and benchmark specification | Correctness and performance need evidence before optimization | 0.75 h |

No database schema, authentication, HTTP layer, Docker setup, or CI deployment runway is appropriate for this local CLI.

## Step 1: Scaffold the Installable CLI

**Goal:** A clean Python 3.11 environment can install the package and invoke Click help.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` Sections 5 and `CLI Interface`.

**Files:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, test extras, and the `nginx-insights` console entry point.
2. Create `src/nginx_insights/__init__.py` with the package version.
3. Create `src/nginx_insights/cli.py` with the documented arguments and mutually exclusive output validation.
4. Create `tests/test_cli.py` with help, version, and invalid-option cases.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`
- `.venv/bin/nginx-insights --help`
- `.venv/bin/pytest tests/test_cli.py -q`

**Commit:** `step-1: scaffold installable CLI`

## Step 2: Define Domain and Failure Contracts

**Goal:** Typed immutable records and domain failures encode report invariants and the complete exit contract.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` Sections 5 and `CLI Interface`; `PRD.md` Section 7.

**Files:**

1. Create `src/nginx_insights/models.py` with `LogRecord`, `RankedCount`, `HourlyBucket`, `UserAgentSummary`, and `Report` dataclasses.
2. Create `src/nginx_insights/errors.py` with I/O, data, and cardinality exception types.
3. Extend `tests/test_cli.py` to assert the exact `0/1/2/3/4` contract: 0 success; 1 I/O/decoding; 2 usage; 3 data; 4 unique-cardinality exhaustion.

**Verification:**

- `.venv/bin/pytest tests/test_cli.py -q`
- `.venv/bin/python -m compileall -q src`

**Commit:** `step-2: define report and exit contracts`

## Step 3: Implement Combined-Log Parsing

**Goal:** Lines stream into valid `LogRecord` objects with deterministic malformed-line handling.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Section 6; `PRD.md` FR-1 and FR-2.

**Files:**

1. Create `src/nginx_insights/parser.py` with one precompiled combined-format parser and timezone-aware timestamp parsing.
2. Create `tests/fixtures/combined.log` with valid, malformed, IPv4, IPv6, quoting, timezone, and error-status examples.
3. Create `tests/test_parser.py` covering field extraction, malformed input, strict mode, UTF-8 failure, and source-local hour behavior.
4. Update `src/nginx_insights/cli.py` to stream a path or stdin and map parser outcomes.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py tests/test_cli.py -q`
- `.venv/bin/nginx-insights --strict tests/fixtures/combined.log --json`

**Commit:** `step-3: parse nginx combined logs`

## Step 4: Implement One-Pass Aggregation

**Goal:** One scan produces exact top lists, 24 hourly percentages, and User-Agent share.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Section 7; `PRD.md` FR-3 through FR-6.

**Files:**

1. Create `src/nginx_insights/aggregate.py` with IP, error-target, hourly, and User-Agent accumulators.
2. Create `tests/test_aggregate.py` covering 4xx/5xx inclusion, non-error exclusion, top-10 truncation, deterministic ties, empty hours, and missing User-Agents.
3. Verify hourly percentages use `100 × hourly_request_count / total_valid_requests`, never an unscaled fraction.
4. Update `src/nginx_insights/cli.py` to finalize one immutable `Report` after EOF.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest tests/test_aggregate.py -q -k 'hourly or user_agent or tie'`

**Commit:** `step-4: aggregate required metrics`

## Step 5: Enforce Cardinality Safety

**Goal:** Unique state remains explicitly bounded and exhaustion is distinguishable from all other failures.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 7 and `CLI Interface`; `PRD.md` US-6.

**Files:**

1. Extend `src/nginx_insights/aggregate.py` to enforce `--max-unique` independently for IP, error URL, and User-Agent collections before insertion.
2. Extend `src/nginx_insights/errors.py` and `src/nginx_insights/cli.py` to emit a safe diagnostic and exit 4 without a partial report.
3. Add exhaustion boundary cases to `tests/test_aggregate.py` and `tests/test_cli.py`.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py tests/test_cli.py -q -k cardinality`
- `sh -c '.venv/bin/nginx-insights --max-unique 1 tests/fixtures/combined.log --json >/tmp/nginx-insights-out; test $? -eq 4 && test ! -s /tmp/nginx-insights-out'`

**Commit:** `step-5: bound unique cardinality`

## Step 6: Build the Three Renderers

**Goal:** Terminal, JSON, and CSV outputs match stable, testable schemas.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface`; `PRD.md` US-1, US-3, and US-4.

**Files:**

1. Create `src/nginx_insights/renderers/__init__.py` with renderer selection.
2. Create `src/nginx_insights/renderers/terminal.py` with escaped Rich tables and TTY-aware color.
3. Create `src/nginx_insights/renderers/json.py` with schema version 1 and 24 ordered buckets.
4. Create `src/nginx_insights/renderers/csv.py` with `metric,rank,key,count,percentage` rows.
5. Create `tests/test_renderers.py` and golden files under `tests/fixtures/expected/`.

**Verification:**

- `.venv/bin/pytest tests/test_renderers.py tests/test_cli.py -q`
- `.venv/bin/nginx-insights tests/fixtures/combined.log --json | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-6: render terminal JSON and CSV reports`

## Step 7: Integrate Error, Pipe, and Privacy Behavior

**Goal:** End-to-end commands are predictable in pipelines and never expose raw log lines.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Sections 10–11; `PRD.md` NFR-3 and NFR-4.

**Files:**

1. Extend `src/nginx_insights/cli.py` for broken pipes, stdout/stderr separation, UTF-8 errors, and no-partial-output behavior.
2. Extend `tests/test_cli.py` with file/stdin equivalence, empty input, zero-valid input, strict mode, broken pipe, ANSI absence, and raw-line redaction.
3. Update golden fixtures only through reviewed behavior changes in `PRD.md` first.

**Verification:**

- `.venv/bin/pytest tests/test_cli.py tests/test_renderers.py -q`
- `sh -c 'printf "" | .venv/bin/nginx-insights --json >/tmp/nginx-insights-out; test $? -eq 3 && test ! -s /tmp/nginx-insights-out'`

**Commit:** `step-7: harden pipeline behavior`

## Step 8: Prove Performance and Package the Release

**Goal:** The exact release candidate is installable and meets correctness and 1 GB performance gates.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Section 12; `STRATEGIC_PLAN.md` Definition of Done.

**Files:**

1. Create `tests/generate_benchmark.py` to deterministically generate the external 1 GB fixture and expected aggregate totals.
2. Create `tests/test_performance.py` for a small CI-safe streaming regression; keep the 1 GB run an explicit release gate.
3. Update `README.md` with installation, metric formulas, schemas, examples, supported format, and the `0/1/2/3/4` contract, including code 4 for unique-cardinality exhaustion.
4. Update package metadata and changelog/release notes without adding any server or deployment files.

**Verification:**

- `.venv/bin/pytest -q --cov=nginx_insights --cov-fail-under=90`
- `.venv/bin/python -m build`
- `python3.11 -m venv /tmp/nginx-insights-smoke && /tmp/nginx-insights-smoke/bin/pip install dist/*.whl && /tmp/nginx-insights-smoke/bin/nginx-insights --version`
- `/usr/bin/time -v .venv/bin/nginx-insights /tmp/nginx-insights-1gb.log --json > /tmp/nginx-insights-report.json` and record <30 seconds plus valid expected totals on the reference laptop.

**Commit:** `step-8: verify and package release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Installable CLI and correct parsing | ~4 hours |
| Weekend block 2 | 4–5 | Exact metrics with bounded memory | ~4 hours |
| Weekend block 3 | 6–7 | Stable outputs and pipeline behavior | ~4 hours |
| Weekend block 4 | 8 | Performance evidence and release artifact | ~3 hours |

## Cross-Step Acceptance Rules

- Preserve WIP=1: complete and verify one step before starting the next.
- The exact public exit-code contract is always `0/1/2/3/4`: 0 success, 1 input I/O/decoding, 2 usage, 3 log-data failure, and 4 unique-cardinality exhaustion.
- Never emit a successful or partial report for codes 1–4.
- Change `PRD.md` acceptance criteria before changing public behavior.
- Do not add authentication, a database, HTTP API, server, cloud resources, Docker, or Kubernetes.

