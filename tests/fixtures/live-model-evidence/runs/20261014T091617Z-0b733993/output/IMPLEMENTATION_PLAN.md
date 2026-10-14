# Implementation Plan: Nginx Stream Analyzer

## 1. Plan Rules

This is a planning artifact; it does not implement code. Work is WIP=1 and follows the P0 dependency path in `PROJECT_ARCHITECTURE.md`. A step is complete only after its listed commands pass and evidence is recorded. The process contract is invariant in every step: `0` success, `1` operational I/O failure, `2` CLI usage/configuration error, `3` input/data failure or zero valid requests, and `4` unique-cardinality exhaustion.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package, console entry point, quality tools | Every feature needs an installable/testable boundary | 1.0 h |
| 2 | Canonical fixtures and output/exit contracts | Prevents drift across parser, metrics, and renderers | 0.5 h |
| 3 | Performance fixture generator and benchmark protocol | Makes the 1 GB goal measurable before optimization | 0.5 h |

No database, auth, API, Docker, deployment pipeline, or infrastructure runway exists because the product is a local stateless CLI.

## Step 1: Package and CLI Skeleton

**Goal:** A clean Python 3.11 environment installs an inert command with validated options and help.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections 3, 4, and `CLI Interface`; `PRD.md` FR-1, FR-6, FR-7.

**Files:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, console script, pytest/Ruff/mypy configuration.
2. Create `src/nginx_stream_analyzer/__init__.py` and `src/nginx_stream_analyzer/cli.py`.
3. Create `src/nginx_stream_analyzer/errors.py` with the fixed 0/1/2/3/4 mapping.
4. Create `tests/test_cli.py` for help, version, conflicts, and invalid limits.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-analyzer --help`
- `.venv/bin/pytest tests/test_cli.py -q`

**Commit:** `step-1: scaffold package and CLI contract`

## Step 2: Domain Models and Supported Parser

**Goal:** Supported combined-log lines become typed records; invalid lines are classified without retention.

**Time:** ~2 hours

**Context:** Architecture sections 4, 5, 9; PRD FR-1.

**Files:**

1. Create `src/nginx_stream_analyzer/models.py` with immutable request/report dataclasses.
2. Create `src/nginx_stream_analyzer/parser.py` with a compiled grammar and timestamp parsing.
3. Create `tests/fixtures/access.log` with valid, malformed, escaped, timezone, and boundary-status lines.
4. Create `tests/test_parser.py` with field and failure assertions.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py -q`
- `.venv/bin/ruff check src/nginx_stream_analyzer/parser.py tests/test_parser.py`
- `.venv/bin/mypy src/nginx_stream_analyzer/models.py src/nginx_stream_analyzer/parser.py`

**Commit:** `step-2: parse supported nginx records`

## Step 3: Streaming Aggregation

**Goal:** One pass produces exact counters for all four reports with deterministic ordering and bounded User-Agent cardinality.

**Time:** ~2 hours

**Context:** Architecture section 5; PRD FR-2 through FR-5.

**Files:**

1. Create `src/nginx_stream_analyzer/aggregate.py` with counters, 24 buckets, bounded UA set, and report finalization.
2. Create `tests/test_aggregate.py` for top-10 truncation, ties, status boundaries, empty hours/UAs, denominators, and exhaustion.
3. Extend `tests/fixtures/access.log` only where a named aggregation boundary lacks coverage.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest tests/test_aggregate.py --cov=nginx_stream_analyzer.aggregate --cov-fail-under=95`

Explicitly assert `100 × hourly_request_count / total_valid_requests` and exit-path code 4 for unique-cardinality exhaustion.

**Commit:** `step-3: add bounded streaming metrics`

## Step 4: JSON and CSV Renderers

**Goal:** Pipeline modes emit deterministic, parseable, stdout-clean schemas.

**Time:** ~1.5 hours

**Context:** Architecture sections `CLI Interface` and 7; PRD FR-6 and section 7.

**Files:**

1. Create `src/nginx_stream_analyzer/renderers/__init__.py`.
2. Create `src/nginx_stream_analyzer/renderers/json.py` for schema version 1.
3. Create `src/nginx_stream_analyzer/renderers/csv.py` for `metric,rank,key,count,percentage,unit`.
4. Create `tests/golden/report.json`, `tests/golden/report.csv`, and `tests/test_renderers.py`.

**Verification:**

- `.venv/bin/pytest tests/test_renderers.py -q`
- `.venv/bin/nginx-stream-analyzer --json tests/fixtures/access.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/nginx-stream-analyzer --csv tests/fixtures/access.log | .venv/bin/python -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-4: add stable pipeline renderers`

## Step 5: Rich Terminal Renderer

**Goal:** Interactive users receive a readable colored report, while redirected output is plain and safe.

**Time:** ~1 hour

**Context:** Architecture sections `CLI Interface`, 7, and 9; PRD FR-6.

**Files:**

1. Create `src/nginx_stream_analyzer/renderers/terminal.py` with four sections and counts.
2. Create `tests/test_terminal_renderer.py` for no-color, escaping, empty rankings, and stable structure.
3. Update `src/nginx_stream_analyzer/cli.py` to dispatch exactly one renderer after aggregation.

**Verification:**

- `.venv/bin/pytest tests/test_terminal_renderer.py -q`
- `NO_COLOR=1 .venv/bin/nginx-stream-analyzer tests/fixtures/access.log`

**Commit:** `step-5: render safe terminal report`

## Step 6: End-to-End I/O and Exit Contract

**Goal:** File/stdin ownership, diagnostics, broken pipes, malformed data, and every exit code behave consistently.

**Time:** ~1.5 hours

**Context:** Architecture `CLI Interface` and section 9; PRD FR-1 and FR-7.

**Files:**

1. Complete `src/nginx_stream_analyzer/cli.py` orchestration and resource handling.
2. Complete `src/nginx_stream_analyzer/errors.py` mapping.
3. Create `tests/test_integration.py` using the installed-style Click/subprocess boundary.
4. Add `tests/fixtures/no-valid-lines.log` and a generated high-cardinality fixture helper.

**Verification:**

- `.venv/bin/pytest tests/test_cli.py tests/test_integration.py -q`
- `.venv/bin/pytest -q`

The integration matrix must observe codes `0/1/2/3/4`; code `4` remains unique-cardinality exhaustion and is never remapped.

**Commit:** `step-6: enforce complete process contract`

## Step 7: Performance and Hardening

**Goal:** Demonstrate the 1 GB/<30 s target, bounded resource behavior, and safe handling of adversarial text.

**Time:** ~2 hours

**Context:** Architecture sections 8–10; PRD non-functional requirements.

**Files:**

1. Create `scripts/generate_benchmark_log.py` to deterministically generate a 1 GB fixture outside Git.
2. Create `benchmarks/README.md` with checksum, laptop/OS/CPU/storage/Python/cache recording fields and command.
3. Create `tests/test_security_boundaries.py` for terminal escapes and diagnostic redaction.
4. Optimize only profiled hot paths in `parser.py`/`aggregate.py`, retaining behavior tests.

**Verification:**

- `.venv/bin/python scripts/generate_benchmark_log.py --size-gib 1 /tmp/nginx-benchmark.log`
- `/usr/bin/time -v .venv/bin/nginx-stream-analyzer --json /tmp/nginx-benchmark.log >/dev/null`
- `.venv/bin/pytest tests/test_security_boundaries.py -q`

Record wall time and peak RSS; accept only wall time <30 seconds on the designated laptop.

**Commit:** `step-7: verify performance and input safety`

## Step 8: Release Readiness

**Goal:** A fresh Python 3.11 environment installs the package, executes documented flows, and passes all gates.

**Time:** ~1 hour

**Context:** All Blueprint documents and Definition of Done in `STRATEGIC_PLAN.md`.

**Files:**

1. Create/update `README.md` with <30-second quick start, supported format, examples, schemas, exits, and limitations.
2. Create `LICENSE` using the selected open-source license.
3. Finalize package metadata and lock/check dependency bounds in `pyproject.toml`.
4. Record release checklist evidence in the project’s normal verification artifact.

**Verification:**

- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/mypy src`
- `.venv/bin/pytest --cov=nginx_stream_analyzer --cov-fail-under=90`
- `.venv/bin/python -m build && .venv/bin/python -m twine check dist/*`
- Install the wheel in a new temporary virtual environment and run file/stdin terminal, JSON, and CSV smoke flows.

**Commit:** `step-8: prepare verified local CLI release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable boundary and parser | ~3 h |
| Saturday PM | 3–4 | Required metrics and pipeline output | ~3.5 h |
| Sunday AM | 5–6 | Human output and complete error behavior | ~2.5 h |
| Sunday PM | 7–8 | Performance proof and release readiness | ~3 h |

## Final Acceptance Gate

Do not mark the plan complete from narration. Freeze the exact staged candidate, run the repository’s machine oracle, and apply the required risk-tier adjudication from `.itd/VERIFICATION_CONTRACT.json`. Product evidence must include all tests/static checks, installed-wheel smoke flows, codes 0/1/2/3/4, and the recorded 1 GB benchmark under 30 seconds. P1/P2 work is outside this weekend gate.
