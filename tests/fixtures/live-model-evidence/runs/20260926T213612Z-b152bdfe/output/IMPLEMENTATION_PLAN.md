# Implementation Plan: Nginx Stream Analyzer

## 1. Delivery Rules

This is a one-weekend, WIP=1 sequence. Complete and verify each step before starting the next. `PROJECT_ARCHITECTURE.md` is the technical source of truth and `PRD.md` owns product acceptance. No product code exists at blueprint time; all paths below are planned artifacts.

The complete exit-code contract applies throughout implementation: `0` success, `1` operational failure, `2` usage/option error, `3` malformed log input, and `4` unique-cardinality exhaustion. Code 4 must never be collapsed into code 1 or 3.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Packaging and module boundaries | Tests and later features need importable stable locations | 1 hour |
| 2 | Representative known-answer fixtures | Parser and aggregation need executable truth before optimization | 1 hour |
| 3 | CLI/output contracts frozen in tests | Prevents format and exit-code drift | 1 hour |

No database, auth system, server, Docker setup, or CI deployment is part of the runway because this is a local stateless CLI.

## STEP 1: Package Skeleton and Contract Tests

**Goal:** The project installs in editable mode and exposes a Click command whose help/version and option validation follow the contract.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3, 7, and 9; `PRD.md` FR-07/FR-08 and NFR-05.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, dev dependencies, `src` discovery, and console script.
2. Create `src/nginx_stream_analyzer/__init__.py` with the package version.
3. Create `src/nginx_stream_analyzer/cli.py` with the command signature and mutually exclusive output validation.
4. Create `tests/test_cli.py` for help, version, missing path, conflicting formats, and positive cardinality validation.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-stream-analyzer --help`

**Commit:** `step-1: scaffold package and freeze CLI contract`

## STEP 2: Combined-Log Parser

**Goal:** Supported combined-format lines become typed immutable records; malformed variants have stable classifications.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4–5; `PRD.md` FR-02.

**Tasks:**

1. Create `src/nginx_stream_analyzer/models.py` with `ParsedRequest`, `RankedCount`, `HourlyShare`, and `Report` dataclasses.
2. Create `src/nginx_stream_analyzer/parser.py` with compiled parsing machinery, timezone-aware timestamp parsing, and `ParseError`.
3. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` with IPv4, IPv6, escaping, 2xx/4xx/5xx, Unicode, and malformed cases.
4. Create `tests/test_parser.py` with known expected fields and malformed classifications.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_stream_analyzer.parser --cov-fail-under=90`

**Commit:** `step-2: parse nginx combined logs`

## STEP 3: Streaming Input and Error Policy

**Goal:** Files and non-seekable stdin feed records incrementally, with skip/count and fail-fast behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5–8; `PRD.md` FR-01, FR-09, and FR-10.

**Tasks:**

1. Create `src/nginx_stream_analyzer/inputs.py` to open paths or borrow stdin without closing caller-owned streams.
2. Extend `src/nginx_stream_analyzer/cli.py` to enumerate lines and translate open/read failures to code 1.
3. Add `tests/test_inputs.py` for path, `-`, non-seekable input, invalid UTF-8 replacement, unreadable path, and read failure.
4. Extend `tests/test_cli.py` for malformed skip/count and `--fail-fast`, both returning code 3.

**Verification:**

- `python3.11 -m pytest tests/test_inputs.py tests/test_cli.py -q`
- `printf '%s\n' 'not a log line' | nginx-stream-analyzer --fail-fast -; test $? -eq 3`

**Commit:** `step-3: stream inputs and classify malformed data`

## STEP 4: Core Aggregation

**Goal:** One pass produces deterministic IP/error top tens and 24 hourly percentages.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 6; `PRD.md` FR-03–FR-05.

**Tasks:**

1. Create `src/nginx_stream_analyzer/aggregate.py` with invocation-local counters and 24 fixed buckets.
2. Implement error status selection for 400–599 and deterministic `(-count, value)` ordering.
3. Implement hourly percentage as `100 × hourly_request_count / total_valid_requests`, with an empty-input zero branch.
4. Create `tests/test_aggregate.py` for top-k truncation, ties, query strings, error boundaries, 24-hour completeness, and empty input.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_stream_analyzer.aggregate --cov-fail-under=90`

**Commit:** `step-4: aggregate core traffic and error metrics`

## STEP 5: Exact User-Agent Metric and Safety Guard

**Goal:** Exact unique User-Agent count/share works within a configured limit and fails explicitly when exhausted.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 7; `PRD.md` FR-06.

**Tasks:**

1. Extend `src/nginx_stream_analyzer/aggregate.py` with the exact set, percentage finalization, and `CardinalityLimitExceeded`.
2. Extend `src/nginx_stream_analyzer/cli.py` to map that exception only to exit code 4.
3. Add high-cardinality, duplicate, empty, and boundary cases to `tests/test_aggregate.py`.
4. Add a CLI regression proving code 4 is distinct from codes 0/1/2/3.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py tests/test_cli.py -q`
- `nginx-stream-analyzer --max-unique-user-agents 1 tests/fixtures/two-user-agents.log; test $? -eq 4`

**Commit:** `step-5: guard exact user-agent cardinality`

## STEP 6: Terminal, JSON, and CSV Renderers

**Goal:** All three output modes implement stable schemas with correct stream and color behavior.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 7; `PRD.md` FR-07/FR-08.

**Tasks:**

1. Create `src/nginx_stream_analyzer/outputs/__init__.py` with renderer selection.
2. Create `src/nginx_stream_analyzer/outputs/terminal.py` with four Rich sections, safe plain-text log values, and `--no-color`.
3. Create `src/nginx_stream_analyzer/outputs/json_output.py` with the documented JSON schema.
4. Create `src/nginx_stream_analyzer/outputs/csv_output.py` with `section,key,count,percentage` rows using `csv.writer`.
5. Create `tests/test_outputs.py` for schemas, order, quoting, Unicode, numeric types, ANSI absence, and stdout/stderr separation.

**Verification:**

- `python3.11 -m pytest tests/test_outputs.py tests/test_cli.py -q`
- `nginx-stream-analyzer --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-stream-analyzer --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: add stable terminal json and csv output`

## STEP 7: End-to-End and Performance Gates

**Goal:** Correctness, memory, and the 1 GB / 30 second target are demonstrated on a documented reference laptop.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 11; `PRD.md` NFR-01–NFR-04.

**Tasks:**

1. Create `tests/test_end_to_end.py` to compare file/stdin and all formats against known answers.
2. Create `tests/test_exit_codes.py` covering the complete 0/1/2/3/4 contract and precedence.
3. Create `scripts/generate_benchmark_log.py` to reproducibly write a 1 GB fixture outside version control.
4. Create `tests/test_performance.py` as an opt-in benchmark assertion and document reference hardware metadata.
5. Profile and optimize only measured hotspots without changing schemas or error semantics.

**Verification:**

- `python3.11 -m pytest -q`
- `python3.11 scripts/generate_benchmark_log.py --bytes 1073741824 /tmp/nginx-stream-analyzer-1gb.log`
- `/usr/bin/time -v nginx-stream-analyzer --json /tmp/nginx-stream-analyzer-1gb.log >/dev/null`
- `python3.11 -m pytest tests/test_performance.py -m performance -q`

**Commit:** `step-7: prove end-to-end correctness and performance`

## STEP 8: Packaging and Release Documentation

**Goal:** A clean environment can build, install, use, and verify the local CLI from the documented instructions.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `README.md`; `CLAUDE_CODE_GUIDE.md`.

**Tasks:**

1. Finalize `README.md` with supported format, examples, schemas, exit codes, limitations, and benchmark environment.
2. Add `LICENSE` after confirming the planned permissive license.
3. Add `CHANGELOG.md` with the initial release contract.
4. Validate `pyproject.toml` metadata and build both wheel and source distribution.
5. Install the wheel in a fresh virtual environment and run terminal/JSON/CSV smoke tests.

**Verification:**

- `python3.11 -m pytest -q`
- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-stream-analyzer-release-venv && /tmp/nginx-stream-analyzer-release-venv/bin/pip install dist/*.whl && /tmp/nginx-stream-analyzer-release-venv/bin/nginx-stream-analyzer --version`

**Commit:** `step-8: prepare verified pip release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable skeleton and trustworthy parser | 4 hours |
| Saturday PM | 3–5 | Streaming aggregation and explicit safety failures | 5.5 hours |
| Sunday AM | 6 | Complete user and pipeline interface | 3 hours |
| Sunday PM | 7–8 | Performance evidence and releasable package | 5 hours |

## Completion Evidence

The release handoff must record the full pytest result, coverage for parser/aggregation, a clean-wheel smoke test, known-answer output comparisons, and reference-hardware benchmark time/peak RSS. A narrated “works” statement is not acceptance evidence.

