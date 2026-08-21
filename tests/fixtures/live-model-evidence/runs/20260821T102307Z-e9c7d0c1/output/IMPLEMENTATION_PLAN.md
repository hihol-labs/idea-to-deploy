# Implementation Plan: Nginx Stream Analytics CLI

This plan covers one weekend, P0 scope only, and implements the single-process architecture in `PROJECT_ARCHITECTURE.md`. Steps follow dependency order; RICE priority orders work inside each layer. Product code is not part of this blueprint session.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package and console-entry structure | Every test and feature needs an importable/installable package | 1 hour |
| 2 | Domain and error contracts | Prevents parser, CLI, and renderer semantics from drifting | 1 hour |
| 3 | Fixture and benchmark specifications | Makes correctness and the 30-second gate measurable before optimization | 1 hour |

No database schema, authentication system, HTTP API, Docker environment, or CI deployment runway is needed. Adding one would violate the accepted architecture.

## STEP 1: Package and test foundation

**Goal:** A Python 3.11 package installs locally and exposes the CLI help/version surface.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3 and 8.

**Tasks:**

1. Create `pyproject.toml` with build metadata, Python constraint, Click/Rich dependencies, pytest configuration, and console script.
2. Create `src/nginx_stream_analytics/__init__.py` with package version.
3. Create `src/nginx_stream_analytics/cli.py` with the documented command/options but no analysis shortcuts.
4. Create `tests/test_cli.py` for help/version and invalid option combinations.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `nginx-stream-analytics --help`
- `python3.11 -m pytest tests/test_cli.py -q`

**Commit:** `step-1: establish package and CLI contracts`

## STEP 2: Domain, errors, and fixtures

**Goal:** Typed data contracts and representative fixtures make metric and failure semantics executable.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 7; `PRD.md` user stories.

**Tasks:**

1. Create `src/nginx_stream_analytics/models.py` with `ParsedRecord`, `RankedItem`, `HourlyItem`, and immutable `AnalysisResult` dataclasses.
2. Create `src/nginx_stream_analytics/errors.py` with input, no-valid-record, cardinality-exhaustion, and invariant errors.
3. Create `tests/fixtures/golden.log`, `mixed-malformed.log`, `all-malformed.log`, and `empty.log` with hand-calculated `tests/fixtures/golden.expected.json`.
4. Extend `tests/test_cli.py` with explicit cases for exit codes `0/1/2/3/4`; inject the internal-error path rather than relying on a real crash.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m json.tool tests/fixtures/golden.expected.json >/dev/null`

**Commit:** `step-2: define domain and failure contracts`

## STEP 3: Combined-log parser

**Goal:** Supported combined-format records parse incrementally into minimal typed records, with malformed lines identified.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 6.

**Tasks:**

1. Create `src/nginx_stream_analytics/parser.py` with a compiled bytes pattern, selective decoding, request-target extraction, and hour parsing.
2. Create `tests/test_parser.py` covering IPv4, IPv6, escapes, query strings, invalid bytes, status boundaries, missing tokens, and truncation.
3. Add a property-style fixture loop ensuring arbitrary malformed bytes never invoke a shell or leak an unhandled decoding exception.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_stream_analytics.parser --cov-fail-under=90`

**Commit:** `step-3: parse nginx combined logs`

## STEP 4: Streaming aggregation

**Goal:** One pass calculates top IPs, error URLs, all hourly buckets, exact unique User-Agent share, and scan counts.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 6; `PRD.md` US-1 through US-4 and US-6.

**Tasks:**

1. Create `src/nginx_stream_analytics/aggregate.py` with counter/set state and a single `analyze(lines, limit)` entry point.
2. Implement deterministic top-10 ordering and complete 24-hour output.
3. Calculate each hourly percentage as `100 × hourly_request_count / total_valid_requests` and UA share using its separately documented percentage formula.
4. Raise cardinality exhaustion immediately after the exact distinct count exceeds the configured ceiling; never return partial output.
5. Create `tests/test_aggregate.py` for status inclusion, ties, cutoff, zero hours, malformed accounting, and cardinality boundary/breach.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_stream_analytics.aggregate --cov-fail-under=90`

**Commit:** `step-4: aggregate four streaming metrics`

## STEP 5: Machine-readable renderers

**Goal:** JSON and normalized CSV output are stable, parseable, deterministic, and free of terminal decoration.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface` and ADR-003.

**Tasks:**

1. Create `src/nginx_stream_analytics/renderers/__init__.py` with the renderer protocol.
2. Create `src/nginx_stream_analytics/renderers/json_output.py` for schema version 1.
3. Create `src/nginx_stream_analytics/renderers/csv_output.py` for the normalized schema and formula-injection protection.
4. Create `tests/test_renderers.py` validating JSON types, CSV round trips, quoting, all 24 hours, stable ordering, and absence of ANSI escapes.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `nginx-stream-analytics --json tests/fixtures/golden.log | python3.11 -m json.tool >/dev/null`
- `nginx-stream-analytics --csv tests/fixtures/golden.log | python3.11 -c 'import csv,sys; assert list(csv.DictReader(sys.stdin))'`

**Commit:** `step-5: add deterministic JSON and CSV outputs`

## STEP 6: Rich terminal renderer

**Goal:** Default output provides readable colored tables without contaminating redirected or machine output.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface` outputs.

**Tasks:**

1. Create `src/nginx_stream_analytics/renderers/terminal.py` with four tables and scan summary.
2. Apply TTY-aware color and safe text rendering for untrusted log values.
3. Extend `tests/test_renderers.py` with terminal snapshots for color, no-color, long values, and escaping.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `nginx-stream-analytics --no-color tests/fixtures/golden.log`

**Commit:** `step-6: render safe Rich terminal reports`

## STEP 7: CLI integration and complete exit contract

**Goal:** File/stdin input, renderer selection, diagnostics, and all failures behave as one public command.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface` and section 7.

**Tasks:**

1. Complete `src/nginx_stream_analytics/cli.py` input opening, buffered iteration, output selection, stderr diagnostics, and domain-error mapping.
2. Enforce the complete contract: `0` success, `1` unexpected internal error, `2` usage/option/input-open error, `3` no valid records, `4` unique-cardinality exhaustion.
3. Extend `tests/test_cli.py` for stdin/file parity, mixed malformed input, output separation, invalid limits, mutual exclusion, unreadable input, and each code `0/1/2/3/4`.
4. Add `tests/test_end_to_end.py` comparing all outputs with the hand-calculated golden fixture.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py tests/test_end_to_end.py -q`
- `nginx-stream-analytics --json tests/fixtures/golden.log > /tmp/nginx-analysis.json`
- `python3.11 -m json.tool /tmp/nginx-analysis.json >/dev/null`

**Commit:** `step-7: integrate CLI and exit behavior`

## STEP 8: Performance profiling and hardening

**Goal:** The exact release candidate meets the 1 GB under 30 seconds target on a recorded reference laptop without correctness regressions.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 6; `PRD.md` quality attributes.

**Tasks:**

1. Create `tests/generate_benchmark_log.py` with deterministic seed/cardinality settings and exact byte-size reporting.
2. Create `tests/test_performance.py` as an opt-in benchmark assertion rather than a default unit test.
3. Create `scripts/benchmark.sh` to record environment, warm-up, three runs, median elapsed time, and peak RSS without excluding read/parse/aggregate work.
4. Profile the whole pipeline and optimize only measured hot paths; record any design change back in `PROJECT_ARCHITECTURE.md` before code changes.
5. Run correctness, coverage, package-build, and benchmark gates against the same staged candidate.

**Verification:**

- `python3.11 tests/generate_benchmark_log.py --size-gib 1 --output /tmp/nginx-benchmark.log`
- `scripts/benchmark.sh /tmp/nginx-benchmark.log`
- `python3.11 -m pytest -q --cov=nginx_stream_analytics --cov-fail-under=90`
- `python3.11 -m build`

**Commit:** `step-8: validate performance and release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable contracts and correct parsing | ~4.5 hours |
| Saturday PM | 4–5 | All metrics and machine outputs | ~4.5 hours |
| Sunday AM | 6–7 | Human output and full CLI integration | ~3.5 hours |
| Sunday PM | 8 | Performance, regression, packaging, documentation | ~3 hours |

## Completion Gate

Do not mark the implementation complete unless the same candidate passes all test commands, the hand-calculated golden fixture, packaging, and the documented performance protocol. The complete `0/1/2/3/4` contract must be exercised, including code `4` for unique-cardinality exhaustion. No P1/P2 work starts before all P0 gates pass.

