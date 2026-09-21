# Implementation Plan: nginx-stream-report

## Scope and Ordering

This plan implements the MVP specified by `PRD.md` on the selected single-process architecture in `PROJECT_ARCHITECTURE.md`. It contains nine dependency-ordered steps suitable for one weekend. Product code is not part of this blueprint session.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package metadata and console entry point | Every CLI and clean-install check depends on it | 0.5 h |
| 2 | Typed records, typed errors, output schemas | Prevents parser, aggregator, and renderer contract drift | 0.5 h |
| 3 | Representative fixtures and benchmark generator | Enables correctness and performance evidence from the start | 1 h |

No database schema, authentication system, Docker setup, API scaffold, or CI deployment runway is needed; those would contradict the approved architecture.

## STEP 1: Package and CLI Skeleton

**Goal:** A Python 3.11 package installs locally and exposes `nginx-stream-report --help` and `--version`.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Repository Layout” and “CLI Interface”.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click and Rich runtime dependencies, pytest tooling, and the console script.
2. Create `src/nginx_stream_report/__init__.py` with a single package version source.
3. Create `src/nginx_stream_report/cli.py` with Click argument/option declarations and mutual-exclusion validation only.
4. Create `tests/test_cli.py` for help, version, defaults, and invalid option combinations.

**Verification:**

- `python3.11 -m pip install -e .`
- `nginx-stream-report --help`
- `python3.11 -m pytest tests/test_cli.py -q`

**Commit:** `step-1: scaffold installable CLI package`

## STEP 2: Domain Models and Exit Semantics

**Goal:** Parser input, aggregate output, and expected failures have explicit typed contracts.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Algorithms” and “Exit Codes”.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with frozen `AccessRecord`, ranked-item, hourly-bucket, summary, and report dataclasses.
2. Create `src/nginx_stream_report/errors.py` with typed I/O, log-data, and cardinality exceptions.
3. Extend `tests/test_cli.py` to prove the complete mapping: `0` success, `1` I/O, `2` usage, `3` log-data failure, `4` unique-cardinality exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m compileall -q src tests`

**Commit:** `step-2: define report and failure contracts`

## STEP 3: Streaming Input and nginx Parser

**Goal:** Common and combined log lines from a file or stdin become `AccessRecord` values without retaining the stream.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Inputs” and “Data Model and Algorithms”.

**Tasks:**

1. Create `src/nginx_stream_report/inputs.py` with context-managed file/stdin iteration and future-safe follow iteration.
2. Create `src/nginx_stream_report/parser.py` with a compiled parser for supported common and combined fields.
3. Add `tests/fixtures/common.log`, `tests/fixtures/combined.log`, and `tests/fixtures/malformed.log` containing synthetic, non-sensitive examples.
4. Create `tests/test_parser.py` for quoted fields, timezone offsets, missing User-Agent, malformed status/timestamp, empty lines, and Unicode replacement behavior.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_cli.py -q`

**Commit:** `step-3: parse nginx streams`

## STEP 4: Core Streaming Aggregation

**Goal:** One pass computes top IPs, top error URLs, 24 hourly percentages, and exact unique User-Agent share.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “Data Model and Algorithms”; `PRD.md` FR-2 through FR-5.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with counters, hourly buckets, the guarded User-Agent set, and deterministic top-10 selection.
2. Calculate each hourly percentage with `100 × hourly_request_count / total_valid_requests` and unique share with its documented percentage formula.
3. Create `tests/test_aggregate.py` for ties, status boundaries 399/400/599/600, query handling, 24 zero-filled buckets, missing User-Agents, and cardinality exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_parser.py tests/test_aggregate.py -q`

**Commit:** `step-4: compute streaming report metrics`

## STEP 5: Rich Terminal Renderer

**Goal:** Default output is readable colored terminal text without corrupting redirected output.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Outputs” and “Security and Privacy”.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/__init__.py` with renderer selection interfaces.
2. Create `src/nginx_stream_report/renderers/terminal.py` with summary and four Rich tables.
3. Escape untrusted IP/URL/User-Agent display values and implement auto/forced/disabled color behavior.
4. Create terminal cases in `tests/test_renderers.py`, including no ANSI escapes when output is not a TTY.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q -k terminal`
- `nginx-stream-report tests/fixtures/combined.log --no-color`

**Commit:** `step-5: render terminal report`

## STEP 6: JSON and CSV Renderers

**Goal:** Pipeline outputs match stable machine-readable schemas and never contain ANSI escapes.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “Outputs”; `PRD.md` FR-7.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/json_output.py` with one JSON object per completed report.
2. Create `src/nginx_stream_report/renderers/csv_output.py` with `section,rank,key,count,percentage` rows and standard CSV quoting.
3. Add golden JSON/CSV assertions and hostile cell values to `tests/test_renderers.py`.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `nginx-stream-report --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-stream-report --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: add structured output renderers`

## STEP 7: End-to-End CLI and Follow Mode

**Goal:** The coordinator streams input, handles malformed lines, selects a renderer, maps every failure, and optionally follows a file.

**Time:** ~2 hours

**Context:** Entire `PROJECT_ARCHITECTURE.md` “CLI Interface”.

**Tasks:**

1. Complete `src/nginx_stream_report/cli.py` orchestration without retaining records.
2. Complete follow behavior in `src/nginx_stream_report/inputs.py`, including partial-line buffering and interrupt behavior.
3. Expand `tests/test_cli.py` for file/stdin equivalence, strict/default malformed handling, query options, broken output, follow restrictions, and all renderers.
4. Assert the full `0/1/2/3/4` exit-code contract; code `4` remains unique-cardinality exhaustion and is never remapped.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `cat tests/fixtures/combined.log | nginx-stream-report --json -`

**Commit:** `step-7: integrate CLI processing pipeline`

## STEP 8: Correctness, Security, and Packaging Gate

**Goal:** The complete product is reproducible, well tested, and installable from a built artifact.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` “Definition of Done” and `PROJECT_ARCHITECTURE.md` “Security and Privacy”.

**Tasks:**

1. Add boundary/property-style cases to `tests/test_parser.py` and `tests/test_aggregate.py` without adding an unnecessary runtime dependency.
2. Add full golden CLI cases to `tests/test_cli.py` for text, JSON, CSV, malformed data, and all exit codes.
3. Configure coverage and build checks in `pyproject.toml`.
4. Verify a wheel in a clean temporary virtual environment and check no secrets or generated log data enter the distribution.

**Verification:**

- `python3.11 -m pytest --cov=nginx_stream_report --cov-report=term-missing --cov-fail-under=90`
- `python3.11 -m build`
- `python3.11 -m pip check`

**Commit:** `step-8: harden tests and package build`

## STEP 9: Performance Acceptance and Release Documentation

**Goal:** The 1 GB / 30 s claim has reproducible evidence and operator-facing contracts are synchronized.

**Time:** ~2 hours plus benchmark runtime

**Context:** `PROJECT_ARCHITECTURE.md` “Performance and Resource Contract”; `STRATEGIC_PLAN.md` KPIs.

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` to deterministically generate representative, non-sensitive combined-format data to a requested byte size.
2. Create `tests/test_performance.py` with a small automated smoke case and a separately marked 1 GB acceptance case.
3. Record the laptop, Python version, dataset parameters, elapsed time, peak RSS, and exact command in project release notes.
4. Reconcile `PRD.md`, `PROJECT_ARCHITECTURE.md`, CLI help, and user documentation if measured behavior differs; never relax the target silently.

**Verification:**

- `python3.11 scripts/generate_benchmark_log.py --size 1GB --output /tmp/nginx-stream-report-1gb.log`
- `/usr/bin/time -v nginx-stream-report --json /tmp/nginx-stream-report-1gb.log >/tmp/nginx-stream-report.json`
- `python3.11 -m pytest -q`

**Commit:** `step-9: validate performance and release readiness`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Architectural runway and trustworthy parsing | 4 hours |
| Saturday PM | 4–5 | Required metrics and default terminal experience | 4 hours |
| Sunday AM | 6–7 | Pipeline formats and complete CLI behavior | 4 hours |
| Sunday PM | 8–9 | Quality, packaging, and measured performance | 4 hours plus benchmark |

## Release Gate

Release is permitted only when all step checks pass, the 90% coverage floor holds, a clean wheel installation works, structured outputs validate, and the documented 1 GB run completes in under 30 seconds on the reference laptop. The complete exit-code interface in every implementation artifact is `0/1/2/3/4`: success, I/O failure, usage error, log-data failure, and unique-cardinality exhaustion respectively.

