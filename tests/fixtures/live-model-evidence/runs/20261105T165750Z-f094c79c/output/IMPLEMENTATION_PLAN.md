# Implementation Plan: Nginx Lens

Planning only: every step below is unstarted. Total estimate: 16 hours over one weekend. Follow [PRD.md](PRD.md) and [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md); priorities come from [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). Prompts are in [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md); status lives in [CLAUDE.md](CLAUDE.md).

## Shared Contracts

Every step preserves exit codes **0/1/2/3/4**: success / I/O or runtime failure / usage error / interruption / unique-cardinality exhaustion. Code 4 is reserved for the configured distinct-entry budget. Hourly percentage is `100 × hourly_request_count / total_valid_requests`. No database, HTTP API, authentication or deployment work is authorized. Commands below are future verification commands, not checks already run. Commit labels describe future local checkpoints, not commits performed by this blueprint.

## Architectural Runway

| Item | Why first | Effort |
|---|---|---|
| Package skeleton and test runner | Makes later checks executable | Step 1, 1 h |
| Record/report schemas and parser fixtures | Freezes data semantics before renderers | Steps 1–2, included |
| Exact-entry budget design | Prevents unsafe counter growth from the first aggregate | Step 3, included |

No database migrations, auth setup, CI deployment or Docker runway is needed. Dependencies override RICE ordering for the package skeleton; optional work is excluded from the weekend. Eight steps need no multi-sprint cadence.

## Step 1: Package and Contract Skeleton

**Goal:** Installable CLI skeleton and test infrastructure, without pretending metrics work yet.
**Time:** 1 hour.
**Context:** Architecture components, models and CLI interface.
**Tasks:**
1. Create `pyproject.toml`, `src/nginx_lens/__init__.py`, `src/nginx_lens/cli.py` and `src/nginx_lens/models.py`; pin supported runtime and define the console entry point.
2. Create `tests/test_cli.py` for help/version, conflicting formats and positive option bounds; add pytest as a development dependency.
**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_cli.py -q`; `nginx-lens --help`.
**Commit:** `step-1: package and CLI contracts`.

## Step 2: Bounded Reader and Combined Parser

**Goal:** Valid typed records stream from file/stdin with explicit malformed accounting.
**Time:** 3 hours.
**Context:** Architecture input grammar.
**Tasks:**
1. Create `src/nginx_lens/reader.py` and `src/nginx_lens/parser.py` with bounded oversized-line draining and strict UTF-8 decoding.
2. Create `tests/test_reader.py`, `tests/test_parser.py` and synthetic `tests/fixtures/combined.log`; cover escapes, status bounds, calendar/offset validation, IPv6, bad requests and EOF.
**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py -q`.
**Commit:** `step-2: bounded combined-log parsing`.

## Step 3: Exact Metrics and Budget

**Goal:** Four metric families are correct with deterministic ties and explicit cardinality failure.
**Time:** 2.5 hours.
**Context:** Architecture metric semantics and resource design.
**Tasks:**
1. Create `src/nginx_lens/aggregate.py`; update `models.py` for error splits, 24 UTC buckets and exact UA set.
2. Create `tests/test_aggregate.py` for hand-calculated reports, query grouping, zero denominators, timezone date rollover and lexicographic ties.
3. Implement atomic per-record budget preflight; test exact limit and overflow for IP, path and UA additions.
**Verification:** `python -m pytest tests/test_aggregate.py -q`.
**Commit:** `step-3: exact streaming aggregates`.

## Step 4: JSON and CSV Pipelines

**Goal:** Stable schema-versioned machine reports without stdout diagnostics.
**Time:** 1.5 hours.
**Context:** Architecture CLI output contract.
**Tasks:**
1. Create `src/nginx_lens/render.py` JSON/CSV serializers; connect file/stdin processing in `cli.py`.
2. Create `tests/test_exports.py` and `tests/fixtures/expected.json`, `tests/fixtures/expected.csv`; round-trip strings with quotes, commas, Unicode and control characters.
**Verification:** `python -m pytest tests/test_exports.py -q`; `nginx-lens --json tests/fixtures/combined.log`.
**Commit:** `step-4: deterministic machine exports`.

## Step 5: Rich Terminal Report

**Goal:** Default readable output including all metrics and skipped-line totals.
**Time:** 1 hour.
**Context:** Architecture text output and PRD terminal story.
**Tasks:**
1. Extend `src/nginx_lens/render.py` with Rich tables and escaped untrusted strings.
2. Create `tests/test_terminal.py` covering TTY color, --no-color, NO_COLOR, redirected output and hostile markup/control sequences.
**Verification:** `python -m pytest tests/test_terminal.py -q`; `nginx-lens --no-color tests/fixtures/combined.log`.
**Commit:** `step-5: terminal summary`.

## Step 6: Failure and Process Boundaries

**Goal:** Complete 0/1/2/3/4 behavior without misleading success output.
**Time:** 2 hours.
**Context:** Architecture exit codes and resource limits.
**Tasks:**
1. Update `src/nginx_lens/cli.py` and `reader.py` for input errors, output errors, broken pipes, SIGINT/SIGTERM and concise stderr errors.
2. Create `tests/test_process.py` with real subprocess checks for all exit codes, over-budget input, all-invalid success, partial read failure and interruption before EOF. Avoid timing-sensitive sleeps; synchronize the subprocess input explicitly.
**Verification:** `python -m pytest tests/test_process.py tests/test_cli.py -q`.
**Commit:** `step-6: complete failure contract`.

## Step 7: Performance and Full Correctness Gate

**Goal:** Measure the 1 GB/30-second target and preserve correctness under load.
**Time:** 3 hours.
**Context:** Architecture performance protocol and strategic DoD.
**Tasks:**
1. Create `benchmarks/run.py` and `tests/test_benchmark_corpus.py` for deterministic generation and reference-summary checks; never label generated logs as production data.
2. Run and profile the supported workload, including final sorting/rendering; capture environment, all timing runs and peak RSS in `benchmarks/RESULTS.md`. If the target fails, record it and block release.
3. Run full tests with branch coverage; optimize only measured hotspots.
**Verification:** `python -m pytest --cov=nginx_lens --cov-branch --cov-fail-under=90 -q`; `python benchmarks/run.py --bytes 1000000000 --runs 3 --formats text,json,csv`.
**Commit:** `step-7: measured performance and correctness`.

## Step 8: Local Release Readiness

**Goal:** Fresh-environment wheel installation works and docs describe implemented behavior.
**Time:** 2 hours.
**Context:** Strategic DoD, PRD release gate.
**Tasks:**
1. Add `LICENSE` with approved MIT terms; reconcile `README.md`, `CLAUDE.md` and usage examples against behavior.
2. Create `tests/test_distribution.py` to build a wheel, create a temporary Python 3.11 venv, install that wheel and run help/version/fixture tests outside the source tree.
3. Perform correctness/dependency review and record findings; handle external adversarial findings when supplied. Publishing, push and deployment require separate authorization and are excluded here.
**Verification:** `python -m pytest tests/test_distribution.py -q`; `python -m pytest --cov=nginx_lens --cov-branch --cov-fail-under=90 -q`; `python -m pip check`.
**Commit:** `step-8: local release readiness`.
