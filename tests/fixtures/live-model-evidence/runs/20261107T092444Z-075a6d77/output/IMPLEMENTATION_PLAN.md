# Implementation Plan: Nginx Lens

Planning only. All steps below are pending; commands describe future verification, not checks already run. Total budget: approximately 16 hours across one weekend. Follow [PRD.md](PRD.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), and RICE order in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md), subject to dependencies. Prompts: [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md); status: [CLAUDE.md](CLAUDE.md); usage: [README.md](README.md).

## Architectural Runway

| Item | Why first | Effort included below |
|---|---|---|
| Package metadata and console entry point | Every integration check needs an installed command | Step 1 |
| Typed records and synthetic fixtures | Freeze metric semantics before aggregation | Steps 1–2 |
| Pytest configuration | Verify each increment before building on it | Step 1 |

No database, migrations, auth, Docker, deployment, or CI-service setup is needed. Commands run locally. No push, publishing, or deletion is authorized by this plan.

## Shared Exit and Output Contract

Every step and implementation prompt preserves **0/1/2/3/4**: 0 successful report or help/version (empty input succeeds); 1 I/O, broken pipe, interruption, or unexpected internal failure; 2 usage error; 3 strict parse failure or nonempty input with no valid records; 4 unique-cardinality exhaustion. Processing failures emit no report; output-device failures may leave partial bytes. Diagnostics use stderr. No remapping Click defaults or silently dropping code 4.

## Step 1: Package and Contract Fixtures

**Goal:** Establish a Python 3.11 package with typed contracts and repeatable tests.
**Time:** 1 hour.
**Context:** Architecture Components and Data Model; PRD F1–F7.
**Tasks:**
1. Create `pyproject.toml` with Click/Rich runtime dependencies, pytest/pytest-cov/build dev extras, and `nginx-lens = nginx_lens.cli:main` entry point.
2. Create `src/nginx_lens/__init__.py`, `src/nginx_lens/__main__.py`, initial `src/nginx_lens/cli.py`, and `src/nginx_lens/models.py` dataclasses.
3. Create `tests/conftest.py`, `tests/test_packaging.py`, and synthetic `tests/fixtures/combined.log` plus `tests/fixtures/expected.json`; include known denominators and tie cases.
**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_packaging.py`; `python -m nginx_lens --help`. Verify Python 3.11 and the console entry point.
**Suggested commit:** `step-1: establish package and fixture contracts` (only on later commit authorization).

## Step 2: Bounded Reader and Combined Parser

**Goal:** Stream validated records without retaining lines.
**Time:** 2 hours.
**Context:** Architecture Input and Parsing Contract; highest-RICE story.
**Tasks:**
1. Create `src/nginx_lens/reader.py` with 64 KiB line bound, oversized-line draining, strict UTF-8, and final-line support.
2. Create `src/nginx_lens/parser.py` with escaped quoted fields, IP validation, timestamp offset/hour extraction, request/status/byte validation, and missing-field policy.
3. Create `tests/test_reader.py` and `tests/test_parser.py` for IPv6, escapes, malformed timestamps/UTF-8, long lines, and blank/truncated records.
**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py`. Instrument a generated stream to confirm incremental reads; reject whole-input reads.
**Suggested commit:** `step-2: parse combined logs with bounded reading`.

## Step 3: Exact Metrics and Cardinality Guard

**Goal:** Derive all four metrics from one pass with truthful failure at the limit.
**Time:** 3 hours.
**Context:** Architecture Metric Semantics and Capacity; PRD F2–F4/F6.
**Tasks:**
1. Create `src/nginx_lens/aggregate.py` with exact counts, 24 hour buckets, nonmissing UA set, shared-key preflight checks, and bounded top-10 selection.
2. Finalize `Report` in `src/nginx_lens/models.py`, preserving raw URL queries and deterministic ordering.
3. Create `tests/test_aggregate.py` with independent hand-calculated fixtures, zero denominators, ties, status boundaries, repeated/missing UAs, and multi-date/offset hours.
**Verification:** `python -m pytest tests/test_aggregate.py`; verify one record adding keys to several collections is checked atomically. Hourly percentage is `100 × hourly_request_count / total_valid_requests`; UA share uses distinct nonmissing UAs over total valid requests. Test exactly-at-limit and over-limit paths.
**Suggested commit:** `step-3: aggregate exact traffic metrics with key budget`.

## Step 4: CLI Orchestration and Failures

**Goal:** Make file/stdin processing obey the complete public contract.
**Time:** 2 hours.
**Context:** Architecture CLI Interface; PRD automation story.
**Tasks:**
1. Implement `src/nginx_lens/cli.py` flags, input ownership, malformed counters, strict/tolerant policy, EOF handling, and explicit exception mapping.
2. Add `tests/test_cli.py` covering 0/1/2/3/4, both export flags, explicit color with exports, invalid limits, empty/all-invalid/mixed inputs, interrupted reads, and error precedence.
3. Keep stdout empty until parsing completes; errors must not echo raw input.
**Verification:** `python -m pytest tests/test_cli.py`; `python -m nginx_lens --version`. Use injected I/O failures and controlled cardinality fixtures rather than OS-permission assumptions.
**Suggested commit:** `step-4: enforce CLI and exit-code contract`.

## Step 5: JSON and CSV Exports

**Goal:** Support deterministic, lossless pipeline reports.
**Time:** 2 hours.
**Context:** Architecture CLI Interface schemas; PRD pipeline story.
**Tasks:**
1. Create machine serializers in `src/nginx_lens/renderers.py`; wire export selection in `src/nginx_lens/cli.py`.
2. Add `tests/test_exports.py` for schema version 1, numeric types, two-decimal rounding, CSV long-form rows, quoted keys, Unicode, and empty reports.
3. Add subprocess tests for stderr separation and a broken output pipe mapping to 1.
**Verification:** `python -m pytest tests/test_exports.py`; `nginx-lens --json tests/fixtures/combined.log`; `nginx-lens --csv tests/fixtures/combined.log`. Parse outputs with json/csv in tests and compare against the independent oracle.
**Suggested commit:** `step-5: provide stable JSON and CSV reports`.

## Step 6: Terminal Report

**Goal:** Present all metrics clearly and safely by default.
**Time:** 2 hours.
**Context:** Architecture Security and CLI Interface; PRD terminal story.
**Tasks:**
1. Add Rich tables and labeled counts/percentages to `src/nginx_lens/renderers.py`.
2. Implement TTY/NO_COLOR/explicit color behavior in `src/nginx_lens/cli.py`.
3. Add `tests/test_terminal.py` for redirected output, forced color, control-byte escaping, markup safety, 24 hour rows, and missing-data labels.
**Verification:** `python -m pytest tests/test_terminal.py`; `nginx-lens --color never tests/fixtures/combined.log`. Manually inspect a TTY report without using raw production logs.
**Suggested commit:** `step-6: render safe readable terminal summaries`.

## Step 7: Capacity Evidence and Regression Pass

**Goal:** Establish measured throughput, memory, and correctness evidence.
**Time:** 2.5 hours.
**Context:** Architecture benchmark conditions and strategic DoD.
**Tasks:**
1. Create `bench/generate.py` for a deterministic 1,000,000,000-byte valid combined fixture under the shared-key cap; record generation parameters and byte count.
2. Create `bench/run.py` to measure installed CLI wall time through EOF and JSON serialization, peak RSS, and environment metadata; fixture generation is outside timed runs.
3. Record individual runs and median in `bench/RESULTS.md`; add high-cardinality and long-line stress cases to `tests/test_capacity.py`. Never commit the generated GB file.
**Verification:** `python -m pytest --cov=nginx_lens --cov-branch --cov-report=term-missing`; `python bench/generate.py --bytes 1000000000 --output bench/access.log`; `python bench/run.py --input bench/access.log --runs 3 --format json`. Require median <30 seconds and fixture peak RSS <512 MiB. Do not fabricate a passing result if the target is missed; profile and record remaining risk within the time budget.
**Suggested commit:** `step-7: record reproducible capacity evidence`.

## Step 8: Wheel and Handoff

**Goal:** Deliver a reproducibly installable local tool with accurate documentation.
**Time:** 1.5 hours.
**Context:** Strategic DoD and PRD maintainer story.
**Tasks:**
1. Finalize `pyproject.toml`, add `LICENSE`, and update `README.md` with verified installed commands and limitations.
2. Add `tests/test_wheel.py` to install the built wheel into a temporary Python 3.11 venv and execute help, sample text, JSON, CSV, and exit-code cases outside the source directory.
3. Update `CLAUDE.md` step status and save continuity with `/session-save`; record review status truthfully. Request approval separately before any package publication.
**Verification:** `python -m build`; `python -m pytest tests/test_wheel.py`; `python -m pytest`. Inspect wheel contents and confirm console/module parity. No deployment check is applicable.
**Suggested commit:** `step-8: validate wheel and document local delivery`.

## Scheduling and Release Boundary

Steps 1–4 form Saturday's 8-hour milestone; steps 5–8 form Sunday's 8-hour milestone. There are eight steps, so no additional multi-sprint cadence is needed. gzip and top-N are deferred. None of the suggested commits or product checks has been executed in this documentation-only session.
