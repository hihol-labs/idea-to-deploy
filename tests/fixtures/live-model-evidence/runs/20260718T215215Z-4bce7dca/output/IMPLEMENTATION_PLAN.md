# Implementation Plan: nginx-stream-report

No product code is created by this blueprint. The eight steps below fit the approved one-weekend delivery and are ordered by dependency; RICE order is applied within those constraints.

## Architectural Runway

| # | Item | Why first | Effort |
|---|---|---|---:|
| 1 | Package skeleton and CLI contract | Every test and module needs import/entry-point stability | 1 h |
| 2 | Representative fixtures and benchmark protocol | Correctness/performance need an oracle before features | 1.5 h |
| 3 | Shared dataclasses and error/exit taxonomy | Parser, aggregator, and renderers share these contracts | 1 h |

There is intentionally no database schema, auth, Docker, or CI/CD deployment runway: none is part of this local CLI architecture.

## Step 1: Package and executable contract

**Goal:** A Python 3.11 wheel exposes a Click command with help, version, options, and validated format/source combinations.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§4, 7, 9.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, console script, build, lint, typing, and test configuration.
2. Create `src/nginx_stream_report/__init__.py` with the version contract.
3. Create `src/nginx_stream_report/cli.py` with option declarations and exit taxonomy, initially delegating analysis.
4. Create `tests/test_cli.py` for help, conflicts, stdin/follow rejection, and error exits.

**Verification:**

- `python3.11 -m pip wheel . --no-deps -w dist`
- `python3.11 -m pytest tests/test_cli.py -q`

**Commit:** `step-1: establish package and CLI contract`

## Step 2: Fixtures, models, and benchmark harness

**Goal:** Domain contracts, correctness fixtures, and reproducible performance inputs exist before parser implementation.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§5–6, 10; `PRD.md` §§5, 9.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with `AccessRecord`, `ParseIssue`, ranked item, report, and summary dataclasses.
2. Create sanitized files under `tests/fixtures/` for common, combined, malformed, empty, ties, Unicode, and formula-like CSV values.
3. Create `tests/test_models.py` for invariants and immutable report shape.
4. Create `benchmarks/calibrate_memory.py` to measure worst-case permitted map/set/string overhead and lock defaults to the 192 MiB projected envelope.
5. Create `benchmarks/generate_log.py` and `benchmarks/run_1gb.sh` with deterministic seed/checksum and environment capture.

**Verification:**

- `python3.11 -m pytest tests/test_models.py -q`
- `python3.11 benchmarks/calibrate_memory.py --sample-keys 10000`
- `python3.11 benchmarks/generate_log.py --size 1M --output /tmp/nginx-report-smoke.log`

**Commit:** `step-2: define models fixtures and benchmark protocol`

## Step 3: Streaming input and nginx parser

**Goal:** File and stdin iterators produce equivalent records from supported nginx formats without loading the full input.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§3, 5; `PRD.md` FR-1, US-1, US-3.

**Tasks:**

1. Create `src/nginx_stream_report/sources.py` with bounded binary file/stdin iterators and source labels.
2. Create `src/nginx_stream_report/parser.py` with once-compiled traditional common/combined grammar, explicit UTF-8 replacement decoding, minimal slotted hot-path records, and structured parse issues.
3. Create `tests/test_parser.py` for every fixture, 64-KiB line/key limits, invalid UTF-8, unsupported escapes, and boundary tokens.
4. Add a generator-consumption test that detects `read()`/`readlines()` full-file use.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m mypy src/nginx_stream_report/parser.py src/nginx_stream_report/sources.py`

**Commit:** `step-3: parse nginx streams`

## Step 4: Aggregation and safety limits

**Goal:** One-pass aggregation returns exact, deterministic four-metric reports and fails visibly at configured cardinality limits.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` §6; `PRD.md` US-1, US-2, FR-2, FR-6.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with IP/error-URL counters, 24-hour array, distinct-UA set, totals, and deterministic top 10 selection.
2. Implement separate calibrated per-map cardinality guards and structured overflow errors.
3. Create `tests/test_aggregate.py` with an independent oracle, ties, status boundaries, offsets, empty input, and overflow.
4. Add randomized small-stream equivalence tests against the oracle.
5. Create `benchmarks/run_core.py` to drive only sources, parser, and aggregator; run a representative 100–250 MB throughput/RSS gate before renderer work and stop for profiling below 34 MiB/s or above 256 MiB RSS.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_stream_report.aggregate --cov-branch --cov-fail-under=90`
- `/usr/bin/time -v python3.11 benchmarks/run_core.py /tmp/nginx-report-250mb.log`

**Commit:** `step-4: implement bounded streaming metrics`

## Step 5: JSON and CSV renderers

**Goal:** Pipeline formats are parseable, schema-versioned, deterministic, safe, and equivalent.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` §8; `PRD.md` US-3.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/json.py` for the schema-versioned object.
2. Create `src/nginx_stream_report/renderers/csv.py` for the lossless rectangular discriminator schema; document rather than silently mutate spreadsheet-formula-like keys.
3. Create `src/nginx_stream_report/renderers/__init__.py` for renderer selection.
4. Create `tests/test_renderers.py` to parse both formats and compare semantic reports.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `nginx-stream-report --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: add stable pipeline renderers`

## Step 6: Rich terminal report and CLI integration

**Goal:** The default command produces an accessible TTY-aware report; all source, parser, aggregator, renderer, diagnostic, and exit-code paths are connected.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` §§3, 7–8; `PRD.md` FR-3–FR-5.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/terminal.py` with Rich summary and metric tables.
2. Complete `src/nginx_stream_report/cli.py` orchestration and stderr diagnostics.
3. Extend `tests/test_cli.py` for file/stdin equivalence, TTY/no-TTY color, invalid thresholds, unreadable files, and cardinality exits.
4. Add golden semantic assertions without snapshotting environment-specific ANSI layout.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py tests/test_renderers.py -q`
- `nginx-stream-report --no-color tests/fixtures/combined.log`

**Commit:** `step-6: integrate terminal and command workflow`

## Step 7: Follow mode and resilience

**Goal:** A growing regular file can be monitored with correct partial-line and interrupt behavior.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` §7; `PRD.md` US-4, US-5.

**Tasks:**

1. Extend `src/nginx_stream_report/sources.py` with polling follow iteration that waits for a complete newline.
2. Extend `src/nginx_stream_report/cli.py` and terminal renderer with configurable Rich Live refresh and interrupt/final-snapshot behavior; reject machine/non-TTY modes.
3. Create `tests/test_follow.py` using bounded polling and temporary files, including append, partial line, refresh, incompatible modes, rotation limitation, and Ctrl-C seams.
4. Document that log rotation reopening is deferred unless explicitly implemented and tested.

**Verification:**

- `python3.11 -m pytest tests/test_follow.py -q`
- `python3.11 -m pytest -q`

**Commit:** `step-7: support live file following`

## Step 8: Quality, performance, packaging, and release docs

**Goal:** The release candidate meets static, runtime, performance, install, security, and documentation gates.

**Time:** ~3 hours

**Context:** `STRATEGIC_PLAN.md` §§8, 12–13; `PRD.md` §§7, 9–10.

**Tasks:**

1. Complete `README.md` with install, examples, schemas, privacy, supported formats, and limits.
2. Create `CHANGELOG.md` and license metadata; confirm dependency licenses.
3. Run the full 1 GB benchmark and save reproducible results under `benchmarks/results/`.
4. Build wheel/sdist, install the wheel into a fresh environment, and exercise terminal/JSON/CSV.
5. Run lint, type, test, coverage, and dependency/security checks; record deviations as blockers.

**Verification:**

- `python3.11 -m ruff check . && python3.11 -m mypy src && python3.11 -m pytest --cov=nginx_stream_report --cov-branch --cov-fail-under=90`
- `bash benchmarks/run_1gb.sh`
- `python3.11 -m build && python3.11 -m pip install --force-reinstall dist/*.whl && nginx-stream-report --version`

**Commit:** `step-8: verify and package release candidate`

## Sprint boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Executable contract and correct streaming parse | ~6.5 h |
| Saturday PM | 4–5 | Exact metrics and pipeline formats | ~5 h |
| Sunday AM | 6–7 | Interactive/live workflow and resilience | ~4.5 h |
| Sunday PM | 8 | Evidence and release readiness | ~3 h |

## Dependency and handoff rules

Only one step is active at a time. Each step starts from its referenced specifications and ends only after its verification commands run. A failure updates the plan/state as recovery work; it is never narrated as complete. Any schema or metric change begins in `PRD.md`/`PROJECT_ARCHITECTURE.md`, then propagates to code and tests.
