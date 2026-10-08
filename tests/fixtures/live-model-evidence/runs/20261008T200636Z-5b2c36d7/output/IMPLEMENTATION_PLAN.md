# Implementation Plan: nginx-log-insights

## Plan Contract

This is a one-weekend, P0-only plan. It creates product code only in a future implementation session; this blueprint session creates documentation only. Steps are ordered by dependency, with high-RICE metrics implemented as soon as the parser runway exists. Do not begin P1/P2 work until Step 9 accepts every P0 criterion.

The required exit-code contract applies throughout: `0` success, `1` runtime or I/O failure, `2` CLI usage error, `3` parse-quality failure, and `4` unique-cardinality exhaustion. No implementation step may omit, reuse, or remap code 4.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and test configuration | Every behavior needs an importable package and repeatable commands | 0.5 h |
| 2 | Typed domain/error contracts | Parser, aggregation, renderers, and CLI must share stable boundaries | 0.5 h |
| 3 | Representative fixtures and benchmark generator | Correctness and performance need evidence before optimization | 0.5 h |

No database schema, authentication system, HTTP API, Docker environment, or CI/CD service is runway for this local CLI.

## Step 1: Package Skeleton and Contract Tests

**Goal:** A pip-installable empty command exposes help/version and the test harness encodes CLI/output contracts before business logic.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Boundaries,” “CLI Interface,” and “Packaging and Deployment”; `PRD.md` US-5 through US-7.

**Files:**

1. Create `pyproject.toml` with Python `>=3.11`, Click, Rich, console entry point, build metadata, and pytest/coverage tooling.
2. Create `src/nginx_log_insights/__init__.py` and `src/nginx_log_insights/__main__.py`.
3. Create `src/nginx_log_insights/cli.py` with the Click command shell and mutually exclusive output validation.
4. Create `tests/test_cli_contract.py` for help, version, option conflicts, and usage exit code 2.
5. Create `tests/conftest.py` for CLI runner and fixture helpers.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/python -m pytest tests/test_cli_contract.py -q`
- `.venv/bin/nginx-log-insights --help`

**Commit:** `step-1: establish package and cli contracts`

## Step 2: Domain Models, Errors, and Log Fixtures

**Goal:** All later layers share typed dataclasses, named failures, and deterministic valid/malformed inputs.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` “Data Model and Streaming State” and “Error and Resource Handling.”

**Files:**

1. Create `src/nginx_log_insights/models.py` with `AccessRecord`, `ParseStats`, `RankedCount`, `HourlyBucket`, and `Report` dataclasses.
2. Create `src/nginx_log_insights/errors.py` with parse-quality, cardinality, and expected runtime error types.
3. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` covering IPv4, IPv6, ties, all status classes, repeated/missing User-Agents, quoting, and time offsets.
4. Create `tests/test_models.py` for immutability and basic invariants.

**Verification:**

- `.venv/bin/python -m pytest tests/test_models.py -q`
- `.venv/bin/python -m compileall -q src tests`

**Commit:** `step-2: define domain and error contracts`

## Step 3: Combined-Log Streaming Parser

**Goal:** Parse supported records incrementally and classify every physical line without side effects.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Input and Parsing Contract”; `PRD.md` FR-01 through FR-03.

**Files:**

1. Create `src/nginx_log_insights/parser.py` with one precompiled grammar, timestamp/status conversion, and structured parse failure.
2. Create `tests/test_parser.py` for valid IPv4/IPv6 records, request targets, timestamps, escaped quotes, malformed fields, and decoding policy.
3. Extend `tests/fixtures/combined.log` only when a new case has an explicit expected parse result.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py -q`
- `.venv/bin/python -m pytest tests/test_parser.py --cov=nginx_log_insights.parser --cov-branch --cov-fail-under=90`

**Commit:** `step-3: parse nginx combined logs`

## Step 4: Exact Streaming Aggregation and Guards

**Goal:** One-pass aggregation produces exact renderer-neutral results and fails safely at the unique-value ceiling.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Data Model and Streaming State”; `PRD.md` US-1 through US-4 and US-6.

**Files:**

1. Create `src/nginx_log_insights/aggregate.py` with IP/error-URL counters, 24 hour buckets, User-Agent set, parse stats, and finalization.
2. Implement deterministic top-ten tie ordering and percentages, including `100 × hourly_request_count / total_valid_requests`.
3. Enforce `max_unique_values` before any new IP, error URL, or User-Agent key is retained; raise the error that maps to exit code 4.
4. Create `tests/test_aggregate.py` for every metric, boundary, tie, malformed-line, zero-valid, and ceiling case.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate.py --cov=nginx_log_insights.aggregate --cov-branch --cov-fail-under=90`

**Commit:** `step-4: implement exact guarded aggregation`

## Step 5: Terminal, JSON, and CSV Renderers

**Goal:** All three formats represent the same report while preserving stdout/stderr and color contracts.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs” and “Output Schemas and Numerical Rules”; `PRD.md` US-5.

**Files:**

1. Create `src/nginx_log_insights/renderers/__init__.py` defining the renderer boundary.
2. Create `src/nginx_log_insights/renderers/terminal.py` with escaped Rich tables and `--no-color` support.
3. Create `src/nginx_log_insights/renderers/json.py` with schema version 1.
4. Create `src/nginx_log_insights/renderers/csv.py` with `metric,rank,key,count,percentage` rows via `csv.writer`.
5. Create `tests/test_renderers.py` and golden files under `tests/golden/` for deterministic outputs.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py -q`
- `.venv/bin/python -m pytest tests/test_renderers.py --cov=nginx_log_insights.renderers --cov-branch --cov-fail-under=90`

**Commit:** `step-5: add terminal json and csv renderers`

## Step 6: End-to-End CLI and Exit Codes

**Goal:** File/stdin processing, diagnostics, renderers, and every exit status work together exactly once at the CLI boundary.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` `## CLI Interface`; `PRD.md` US-5 and US-6.

**Files:**

1. Complete `src/nginx_log_insights/cli.py` to open input, stream parser results, select a renderer, and translate expected errors.
2. Expand `tests/test_cli_contract.py` for file/stdin parity, stdout/stderr separation, strict/non-strict behavior, no ANSI in JSON/CSV, and the complete `0/1/2/3/4` mapping.
3. Create `tests/test_end_to_end.py` asserting known fixture metrics in every format.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli_contract.py tests/test_end_to_end.py -q`
- `.venv/bin/nginx-log-insights --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/nginx-log-insights --max-unique-values 1 tests/fixtures/combined.log >/dev/null; test $? -eq 4`

**Commit:** `step-6: wire cli and complete exit contract`

## Step 7: Full Correctness, Quality, and Security Pass

**Goal:** Core behavior is regression-protected, typed/linted, and safe for untrusted log text.

**Time:** ~1.5 hours

**Context:** `PRD.md` all P0 acceptance criteria; `PROJECT_ARCHITECTURE.md` “Security and Privacy.”

**Files:**

1. Add missing edge cases to `tests/test_parser.py`, `tests/test_aggregate.py`, and `tests/test_renderers.py` based on the acceptance matrix.
2. Create `tests/test_untrusted_output.py` for Rich markup/control text and CSV quoting.
3. Update `pyproject.toml` with final lint, type, and coverage configuration.

**Verification:**

- `.venv/bin/python -m pytest --cov=nginx_log_insights --cov-branch --cov-fail-under=90`
- `.venv/bin/python -m ruff check src tests`
- `.venv/bin/python -m mypy src`

**Commit:** `step-7: harden correctness and output safety`

## Step 8: Performance Benchmark and Optimization

**Goal:** Record reproducible evidence that representative 1 GB processing meets the time and memory goals, optimizing only measured bottlenecks.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` success metrics and risks; `PROJECT_ARCHITECTURE.md` “Testing and Performance Architecture”; `PRD.md` US-7.

**Files:**

1. Create `benchmarks/generate_log.py` to deterministically produce a production-shaped 1 GB combined-log fixture outside Git.
2. Create `benchmarks/run.sh` to capture Python version, OS/hardware notes, input bytes, wall time, exit code, and peak RSS for three runs.
3. Create `benchmarks/README.md` documenting fixture parameters and median calculation.
4. Optimize `src/nginx_log_insights/parser.py` or `aggregate.py` only when profiling identifies a hot path; preserve all golden results.

**Verification:**

- `.venv/bin/python benchmarks/generate_log.py --bytes 1073741824 --output /tmp/nginx-log-insights-1gb.log`
- `sh benchmarks/run.sh /tmp/nginx-log-insights-1gb.log`
- `.venv/bin/python -m pytest -q`

**Commit:** `step-8: verify one-gigabyte performance target`

## Step 9: Packaging, Documentation, and Release Gate

**Goal:** A clean environment installs the final wheel, user documentation matches behavior, and all P0 evidence is recorded.

**Time:** ~1.5 hours

**Context:** All blueprint documents, especially `PRD.md` release criteria and `PROJECT_ARCHITECTURE.md` package contract.

**Files:**

1. Finalize `README.md` with install, examples, schemas, performance context, limitations, and untrusted-CSV warning.
2. Create `CHANGELOG.md` for version `0.1.0` and create `LICENSE` using the selected permissive license.
3. Finalize package metadata in `pyproject.toml` and package inclusion rules.
4. Update `CLAUDE.md` status only after each verification command has actually passed.

**Verification:**

- `.venv/bin/python -m build`
- `python3.11 -m venv /tmp/nginx-log-insights-smoke && /tmp/nginx-log-insights-smoke/bin/pip install dist/*.whl && /tmp/nginx-log-insights-smoke/bin/nginx-log-insights --help`
- `.venv/bin/python -m pytest --cov=nginx_log_insights --cov-branch --cov-fail-under=90`
- Re-run `sh benchmarks/run.sh /tmp/nginx-log-insights-1gb.log` against the exact release candidate.

**Commit:** `step-9: prepare verified 0.1.0 release`

## Weekend Boundaries

| Block | Steps | Goal | Duration |
|---|---|---|---:|
| Saturday morning | 1–3 | Runway and parser | 4 hours |
| Saturday afternoon | 4–5 | Metrics and output formats | 4.5 hours |
| Sunday morning | 6–7 | Integrated CLI and quality | 3.5 hours |
| Sunday afternoon | 8–9 | Performance evidence and release | 3.5 hours |

## Traceability Matrix

| Requirement group | Implementation steps | Primary evidence |
|---|---|---|
| Input and parsing | 2–3, 6 | Parser and CLI tests |
| Four reports | 4–6 | Aggregator, golden, and end-to-end tests |
| Output modes | 5–7 | Renderer goldens and clean-stream assertions |
| Exit `0/1/2/3/4` | 1, 4, 6 | CLI integration tests including code 4 |
| pip installation | 1, 9 | Clean-wheel smoke test |
| 1 GB under 30 seconds | 8–9 | Three-run benchmark record |

## Deferred Work

Direct gzip input, configurable log formats, and internal follow mode are P1/P2. Authentication, database, HTTP API, server, cloud, and Kubernetes remain out of scope rather than future implementation steps.
