# Implementation Plan: nginx Stream Analytics CLI

This is an eight-step, dependency-ordered weekend plan. Product behavior comes from `PRD.md`; module boundaries and the CLI contract come from `PROJECT_ARCHITECTURE.md`. No step is complete until its listed checks pass for the exact candidate.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console entry point | Every test and feature needs an installable composition root | 0.5 h |
| 2 | Dataclass/report contracts | Parser, aggregation, and all renderers need one stable model | 0.5 h |
| 3 | Test fixtures and benchmark protocol | Correctness and performance must be measurable before feature work expands | 1 h |

No database schema, auth system, Docker setup, CI service, API, or deployment infrastructure belongs in the runway; the approved architecture is a local, stateless process.

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Installable skeleton, parser, streaming metrics | Saturday |
| Weekend block 2 | 4–6 | Stable terminal and pipeline outputs | Sunday morning |
| Weekend block 3 | 7–8 | Reliability, performance, packaging, handoff | Sunday afternoon |

## Step 1: Establish Package and Behavioral Contracts

**Goal:** A clean environment can install the project and invoke a placeholder-free CLI with approved options and model types.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Design,” “Data Contracts,” and “CLI Interface”; `PRD.md` P0 requirements.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, pytest tooling, and the `nginx-stream-report` console script.
2. Create `src/nginx_stream_analytics/__init__.py` and `src/nginx_stream_analytics/__main__.py`.
3. Create `src/nginx_stream_analytics/models.py` with `LogRecord`, `RankedItem`, `HourlyShare`, and `Report` dataclasses.
4. Create `src/nginx_stream_analytics/errors.py` with typed operational, empty-data, and cardinality exceptions.
5. Create `src/nginx_stream_analytics/cli.py` with Click argument/option declarations and mutual exclusion validation.
6. Create `tests/test_cli_contract.py` for help, version, option defaults, conflicts, and exit-code surface.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`
- `.venv/bin/nginx-stream-report --help`
- `.venv/bin/pytest tests/test_cli_contract.py -q`

**Commit:** `step-1: establish package and CLI contracts`

## Step 2: Implement the Combined-Log Parser and Input Boundary

**Goal:** File and stdin streams produce typed valid records while malformed lines and decoding failures remain explicit.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Input grammar” and “Failure and Malformed-Data Policy.”

**Tasks:**

1. Create `src/nginx_stream_analytics/input.py` with ownership-safe file/stdin opening and strict decoding.
2. Create `src/nginx_stream_analytics/parser.py` with one compiled combined-log grammar and timezone-aware timestamp parsing.
3. Create `tests/fixtures/combined_valid.log` and `tests/fixtures/combined_mixed.log` with small, auditable records.
4. Create `tests/test_parser.py` for quoting, IPv4/IPv6 strings, query targets, time offsets, statuses, User-Agent `-`, blank, and malformed lines.
5. Create `tests/test_input.py` for file, `-`, omitted stdin, missing file, and invalid encoding behavior.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py tests/test_input.py -q`
- `.venv/bin/python -m nginx_stream_analytics --json tests/fixtures/combined_valid.log`

**Commit:** `step-2: parse nginx combined logs as a stream`

## Step 3: Build Streaming Aggregation

**Goal:** One pass produces all four exact metrics with deterministic ordering and bounded cardinality.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “System Context and Data Flow,” “Data Contracts,” and “Performance and Resource Design.”

**Tasks:**

1. Create `src/nginx_stream_analytics/aggregate.py` with IP/error-URL counters, 24 hourly buckets, User-Agent set, total/malformed counts, and per-collection ceilings.
2. Calculate hourly percentage exactly as `100 × hourly_request_count / total_valid_requests` and round only at report finalization.
3. Calculate unique User-Agent share as a percentage and retain both unique count and share.
4. Implement descending-count/ascending-key tie breaking and top-10 truncation.
5. Raise the typed cardinality exception before inserting a key beyond `--max-unique`.
6. Create `tests/test_aggregate.py` covering all metrics, 4xx/5xx filtering, 24 buckets, ties, malformed counts, empty input, and every cardinality collection.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest -q`

**Commit:** `step-3: add bounded streaming metrics`

## Step 4: Render Rich Terminal Output

**Goal:** Default output is a readable four-section terminal report with safe color behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Output contracts” and `PRD.md` US-05.

**Tasks:**

1. Create `src/nginx_stream_analytics/render_text.py` with Rich tables for IPs, error URLs, hourly counts/percentages, and User-Agent summary.
2. Escape or disable markup for all log-derived strings.
3. Wire automatic TTY color and `--color/--no-color` in `src/nginx_stream_analytics/cli.py`.
4. Create `tests/test_render_text.py` with a deterministic no-color snapshot and malicious-markup values.
5. Extend `tests/test_cli_contract.py` to assert reports go to stdout and diagnostics to stderr.

**Verification:**

- `.venv/bin/pytest tests/test_render_text.py tests/test_cli_contract.py -q`
- `.venv/bin/nginx-stream-report --no-color tests/fixtures/combined_valid.log`

**Commit:** `step-4: render safe Rich terminal report`

## Step 5: Add Stable JSON Output

**Goal:** `--json` emits exactly one documented, ANSI-free JSON object suitable for pipelines.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` JSON contract and `PRD.md` US-06.

**Tasks:**

1. Create `src/nginx_stream_analytics/render_json.py` mapping `Report` to the documented top-level schema.
2. Wire `--json` only after successful aggregation so failures never produce partial JSON.
3. Create `tests/golden/report.json` and `tests/test_render_json.py` for schema, values, encoding, ordering, and absence of ANSI escapes.
4. Add a stdin pipeline integration test to `tests/test_cli_integration.py`.

**Verification:**

- `.venv/bin/pytest tests/test_render_json.py tests/test_cli_integration.py -q`
- `.venv/bin/nginx-stream-report --json tests/fixtures/combined_valid.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-5: add stable JSON pipeline output`

## Step 6: Add Stable CSV Output

**Goal:** `--csv` emits one RFC 4180-compatible long-form table with the same report semantics.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` CSV contract and `PRD.md` US-06.

**Tasks:**

1. Create `src/nginx_stream_analytics/render_csv.py` with header `section,key,count,percentage` using the standard `csv` module.
2. Wire `--csv` and preserve JSON/CSV mutual exclusion.
3. Create `tests/golden/report.csv` and `tests/test_render_csv.py` for quoting, newlines, UTF-8, values, and absence of ANSI escapes.
4. Add a CSV consumer round-trip to `tests/test_cli_integration.py`.

**Verification:**

- `.venv/bin/pytest tests/test_render_csv.py tests/test_cli_integration.py -q`
- `.venv/bin/nginx-stream-report --csv tests/fixtures/combined_valid.log | .venv/bin/python -c 'import csv,sys; rows=list(csv.DictReader(sys.stdin)); assert rows'`

**Commit:** `step-6: add stable CSV pipeline output`

## Step 7: Complete Failure Semantics and Resource Guards

**Goal:** Every expected failure follows the complete `0/1/2/3/4` contract and emits no corrupt machine output.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Exit-code contract,” “Failure and Malformed-Data Policy,” and “Security and Privacy.”

**Tasks:**

1. Centralize exception-to-exit mapping in `src/nginx_stream_analytics/cli.py` and `src/nginx_stream_analytics/errors.py`.
2. Ensure code `0` means success; `1` operational I/O/decoding failure; `2` Click usage error; `3` zero valid requests; `4` unique-cardinality exhaustion.
3. Handle downstream closed pipes quietly without masking prior data or resource errors.
4. Create `tests/test_exit_codes.py` that triggers and asserts all five codes.
5. Add hostile high-cardinality, malformed-only, invalid-byte, unsafe Rich-markup, and failing-writer cases.

**Verification:**

- `.venv/bin/pytest tests/test_exit_codes.py tests/test_cli_integration.py -q`
- `.venv/bin/pytest --cov=nginx_stream_analytics --cov-report=term-missing --cov-fail-under=90 -q`

**Commit:** `step-7: enforce exit and resource contracts`

## Step 8: Prove Performance and Prepare Distribution

**Goal:** The exact release candidate is installable, documented, and processes a declared 1 GB fixture in under 30 seconds on the recorded baseline.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PROJECT_ARCHITECTURE.md` “Performance and Resource Design” and “Packaging and Deployment.”

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically stream a grammar-valid fixture without checking generated data into source control.
2. Create `benchmarks/run.py` to record candidate identity, environment, bytes, elapsed time, throughput, peak RSS, and command.
3. Create `tests/test_package.py` to build a wheel, install it into a clean environment, and exercise the console entry point.
4. Finalize `README.md` with quick start, schemas, privacy, limits, and performance reproduction.
5. Run the full suite and repository Verification Loop against the frozen exact candidate, recording required evidence rather than relying on narration.

**Verification:**

- `.venv/bin/python benchmarks/generate_log.py --bytes 1073741824 --output /tmp/nginx-stream-benchmark.log`
- `.venv/bin/python benchmarks/run.py --input /tmp/nginx-stream-benchmark.log --max-seconds 30`
- `.venv/bin/python -m build && .venv/bin/pytest -q`

**Commit:** `step-8: validate performance and package release`

## Global Exit-Code Acceptance Contract

Every implementation step and renderer must preserve this mapping:

| Code | Required meaning |
|---:|---|
| 0 | Successful report/help/version |
| 1 | Operational input/output or decoding failure |
| 2 | Invalid CLI usage or options |
| 3 | No valid requests in completed input |
| 4 | Unique-cardinality exhaustion |

Code 4 must never be omitted, remapped, or collapsed into code 1. Tests must assert the process return code, stdout completeness/emptiness as applicable, and stderr diagnostic for each path.

## Release Acceptance

- All P0 stories and acceptance criteria in `PRD.md` pass.
- All output adapters derive from one `Report` and agree on values.
- The package installs and runs under Python 3.11 in a clean environment.
- Coverage and performance gates in the Definition of Done pass.
- The exact candidate is accepted only by current repository verification evidence.
- P1 gzip support may ship only after P0; P2 and Won't items do not delay MVP.
