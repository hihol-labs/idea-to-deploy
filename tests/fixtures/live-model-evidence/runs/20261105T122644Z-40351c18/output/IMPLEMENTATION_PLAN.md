# Implementation Plan: Nginx Lens

This is a future implementation plan, not completed work. Scope and priorities come from [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) and [PRD.md](PRD.md). [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) defines the executable behavior. Eight steps total approximately 16 engineering hours; keep WIP=1. Proposed verification commands below become runnable when their corresponding files exist. No tests or benchmarks of product code have run during blueprint generation.

## Contract Carried Through Every Step

Keep Python 3.11, Click, Rich and dataclasses, one process, file/stdin streaming and no persistence/services. Every implementation must retain the complete exit-code contract 0/1/2/3/4: 0 successful analysis (also empty/help/version), 1 report with malformed lines skipped, 2 invalid CLI usage, 3 I/O/resource/interruption failure, 4 unique-cardinality exhaustion. Fatal 3/4 override pending 1; code 4 emits no report. Do not let Click silently substitute another code for interruption or broken pipe.

Hourly distribution is a percentage: `100 × hourly_request_count / total_valid_requests`. All 24 buckets are UTC hours-of-day. User-Agent share uses distinct nonmissing agents divided by all valid requests, multiplied by 100. Preserve exactness with shared entry/key-byte quotas; never approximate counts to pass a benchmark.

## Architectural Runway

| Item | Why first | Effort within steps |
|---|---|---|
| Package layout and local pytest harness | All following work must run in a clean environment | Step 1, 1 hour |
| Dataclass and failure contracts | Parser, counters and renderers must agree | Steps 1–2, 1 hour |
| Synthetic golden fixtures and quota cases | Verify correctness without sensitive production logs | Steps 1–3, 1 hour |

No database schema, auth, Docker, hosted CI or deployment runway is required. The highest RICE bundle (guards/installability) starts first and is validated again at the end. Remaining feature order follows RICE with parser dependencies respected. P1 gzip and P2 drilldowns are deferred.

## Step 1: Package and Freeze Behavior

**Goal:** Installable package skeleton, typed contracts and deterministic local tests.

**Time:** ~2 hours, Saturday.

**Context:** Architecture: Data Flow, CLI Interface; PRD P0 requirements.

**Tasks:**
1. Create `pyproject.toml`, `src/nginx_lens/__init__.py`, `src/nginx_lens/cli.py` and `src/nginx_lens/models.py`; define entry point, dependencies, schema and domain failure types.
2. Create `tests/conftest.py`, `tests/test_contracts.py`, `tests/fixtures/combined.log` and `tests/fixtures/expected.json`; hand-calculate expected metrics.
3. Create `LICENSE` with MIT text and `tests/test_install.py` for entry-point metadata.

**Verification:** `python -m pip install -e '.[dev]'`; `python -m pytest tests/test_contracts.py tests/test_install.py`.

**Proposed commit:** `step-1: establish package and CLI contracts` (commit only after green tests).

## Step 2: Streaming Reader and Combined Parser

**Goal:** Produce valid RequestRecord instances without buffering the source.

**Time:** ~3 hours, Saturday.

**Context:** Architecture: Input Grammar and Validity, Exactness and Resource Limits.

**Tasks:**
1. Create `src/nginx_lens/reader.py` with 64 KiB bounded reads, oversized-line draining, strict UTF-8 and source ownership.
2. Create `src/nginx_lens/parser.py` with anchored grammar, nginx escapes, canonical IPs, locale-independent dates and field validation.
3. Create `tests/test_reader.py` and `tests/test_parser.py` covering CRLF, no final newline, IPv6, invalid dates/status/escapes/encoding and oversized records.

**Verification:** `python -m pytest tests/test_reader.py tests/test_parser.py`.

**Proposed commit:** `step-2: parse bounded nginx combined streams`.

## Step 3: Exact Rankings and Quota Guards

**Goal:** Count IPs and combined 4xx/5xx error URLs with deterministic ties and safe exhaustion.

**Time:** ~2 hours, Saturday.

**Context:** Architecture: Metric Contract, Exactness and Resource Limits.

**Tasks:**
1. Create `src/nginx_lens/aggregate.py`; count all IP requests, count raw request-target errors only for 400–599, maintain UA set and shared quotas.
2. Extend `src/nginx_lens/models.py` with state and frozen report records; validate all new keys before mutating a record's state.
3. Create `tests/test_rankings.py` and `tests/test_limits.py`: test ties, >10 keys, URL query distinction, duplicate reuse, namespace accounting, exact limits and one-over failures.

**Verification:** `python -m pytest tests/test_rankings.py tests/test_limits.py`.

**Proposed commit:** `step-3: add exact rankings and cardinality guards`.

## Step 4: Percentages and Early Performance Probe

**Goal:** Correct UTC hourly and User-Agent metrics, plus early throughput evidence.

**Time:** ~1 hour, Saturday.

**Context:** Architecture: Metric Contract, Performance and Verification.

**Tasks:**
1. Extend `src/nginx_lens/aggregate.py` for 24 UTC buckets, missing-UA semantics, zero denominators and unrounded internal calculations.
2. Create `tests/test_metrics.py` with timezone rollover, multiple days, duplicate/missing agents and empty/all-invalid inputs.
3. Create `benchmarks/generate.py` and `benchmarks/probe.py` to generate deterministic combined logs and measure parse/aggregate time. This probe does not substitute for final end-to-end measurement.

**Verification:** `python -m pytest tests/test_metrics.py`; `python benchmarks/probe.py --bytes 100000000`.

**Proposed commit:** `step-4: define exact percentages and probe throughput`.

## Step 5: CLI and Terminal Report

**Goal:** A useful local text command with reliable diagnostics and exit mapping.

**Time:** ~2 hours, Sunday.

**Context:** Architecture: CLI Interface, Input Grammar and Validity.

**Tasks:**
1. Complete `src/nginx_lens/cli.py`: file/stdin, options, EOF finalization, stderr-only diagnostics and codes 0/1/2/3/4.
2. Create `src/nginx_lens/render.py` with Rich tables, TTY-aware color, --no-color and escaped untrusted strings.
3. Create `tests/test_cli.py` and `tests/test_terminal.py`; exercise malformed input, fatal-over-partial precedence, terminal controls, interruption and input ownership.

**Verification:** `python -m pytest tests/test_cli.py tests/test_terminal.py`; `nginx-lens --no-color tests/fixtures/combined.log`.

**Proposed commit:** `step-5: wire safe terminal CLI and exit contract`.

## Step 6: JSON and CSV Exports

**Goal:** Stable schema-versioned output equivalent to the terminal report.

**Time:** ~2 hours, Sunday.

**Context:** Architecture: CLI Interface / Outputs.

**Tasks:**
1. Extend `src/nginx_lens/render.py` with complete JSON schema and normalized CSV, six-place percentages, deterministic order and correct quoting.
2. Extend `src/nginx_lens/cli.py` to reject simultaneous --json/--csv before reading input.
3. Create `tests/test_exports.py` to parse serialized output independently, compare metrics, exercise commas/quotes/newlines and ensure no ANSI or diagnostic pollution.

**Verification:** `python -m pytest tests/test_exports.py`; `nginx-lens --json tests/fixtures/combined.log`.

**Proposed commit:** `step-6: support stable JSON and CSV pipelines`.

## Step 7: End-to-End Hardening and Benchmark

**Goal:** Measured performance and verified failure behavior for the assembled command.

**Time:** ~3 hours, Sunday.

**Context:** Architecture: Performance and Verification; PRD nonfunctional acceptance.

**Tasks:**
1. Create `tests/test_end_to_end.py` and `tests/test_failures.py` for stdin/file equivalence, codes 0/1/2/3/4, quota exhaustion, broken pipe and unreadable inputs.
2. Create `benchmarks/run.py` to invoke the installed CLI, record elapsed time, peak RSS, platform/dependency versions and cache conditions in `benchmarks/results.md`.
3. Profile and adjust only `reader.py`, `parser.py`, `aggregate.py` hot paths when evidence requires it; rerun correctness after each change.

**Verification:** `python -m pytest --cov=nginx_lens --cov-branch`; `python benchmarks/generate.py --bytes 1000000000 --output /tmp/nginx-lens-benchmark.log`; `python benchmarks/run.py --input /tmp/nginx-lens-benchmark.log --runs 3 --format json`.

**Proposed commit:** `step-7: verify failure paths and performance budget`.

## Step 8: Clean Install and Handoff

**Goal:** A locally reviewable wheel and truthful usage documentation.

**Time:** ~1 hour, Sunday.

**Context:** Strategic Definition of Done; architecture CLI contract.

**Tasks:**
1. Finalize `README.md`, `CLAUDE.md`, `pyproject.toml` and `tests/test_install.py`; confirm documented commands, MIT/dependency licenses and scope.
2. Build a wheel, install into a fresh `/tmp/nginx-lens-smoke` virtual environment, inspect help/version and analyze the golden fixture.
3. Record all results and remaining issues in `.itd-memory/continuity/nginx-lens-implementation.md`; obtain independent code review before any release. Publishing remains a separate human-confirmed action.

**Verification:** `python -m pytest`; `python -m build`; `python -m venv /tmp/nginx-lens-smoke`; `/tmp/nginx-lens-smoke/bin/python -m pip install --no-index --find-links dist --find-links /tmp/nginx-lens-wheelhouse nginx-lens`; `/tmp/nginx-lens-smoke/bin/nginx-lens --json tests/fixtures/combined.log`.

Prepare the dependency wheelhouse locally before the offline smoke install; it is a test prerequisite, not a runtime service. If the performance budget fails, record failure and follow PRD kill criteria rather than marking the step done.

**Proposed commit:** `step-8: package and document local release candidate`.

## Completion Boundary

No deployment or publication is part of implementation acceptance. Require passing checks and recorded measurements, then review the local candidate. Use [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) for step prompts and save continuity after significant work. Eight steps do not require a multi-sprint cadence.
