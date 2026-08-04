# Implementation Plan: nginx-stream-report

This is a planning guide only. Execute one step at a time and retain the exact verification output. The complete exit-code contract is: `0` success, `1` runtime/I/O failure, `2` usage error, `3` strict input-format failure, and `4` unique-cardinality exhaustion. Code 4 must never be omitted or remapped.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console entry point | Every behavior needs an installable execution boundary | 1 hour |
| 2 | Golden combined-log fixtures and output schemas | Freezes semantics before aggregation code | 1 hour |
| 3 | Ruff, mypy, pytest, coverage configuration | Provides feedback before feature growth | 1 hour |
| 4 | 1 GiB fixture generator and benchmark protocol | Makes the performance target reproducible early | 1 hour |

No database schema, authentication, API, Docker, cloud, or Kubernetes runway is needed.

## STEP 1: Package and CLI Contract

**Goal:** An installable command exposes all approved options and canonical exit-code constants.  
**Time:** ~2 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Design” and “CLI Interface”.  
**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, test tooling, and the console entry point.
2. Create `src/nginx_stream_report/{__init__,cli,errors}.py` with option validation and exit mappings `0/1/2/3/4`.
3. Create `tests/test_cli_contract.py` for help, version, mutual exclusion, option bounds, and exit meanings.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `nginx-stream-report --help`
- `pytest -q tests/test_cli_contract.py`

**Commit:** `step-1: establish package and CLI contract`

## STEP 2: Combined-Log Parser

**Goal:** Valid records become typed dataclasses; malformed and decoding failures remain distinguishable.  
**Time:** ~3 hours  
**Context:** `PROJECT_ARCHITECTURE.md` “Data Model and Streaming State”; `PRD.md` FR-1.  
**Tasks:**

1. Create `src/nginx_stream_report/models.py` with `AccessRecord`.
2. Create `src/nginx_stream_report/parser.py` with one compiled parser and timestamp/status validation.
3. Create `tests/fixtures/access.log` and `tests/test_parser.py` for quoting, missing markers, malformed fields, and final unterminated lines.

**Verification:**

- `pytest -q tests/test_parser.py`
- `ruff check src/nginx_stream_report/parser.py tests/test_parser.py`

**Commit:** `step-2: parse nginx combined logs`

## STEP 3: Streaming Aggregation and Safety Limit

**Goal:** One pass computes every required metric and fails atomically on cardinality exhaustion.  
**Time:** ~4 hours  
**Context:** `PROJECT_ARCHITECTURE.md` “Data Model and Streaming State”; `PRD.md` US-2 through US-5.  
**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with `AggregateState`, size-10 deterministic selection, 24 hourly buckets, and both percentage formulas.
2. Preflight each record across `--max-unique` and the shared conservative `--max-key-bytes` estimate before any mutation; raise the typed error mapped only to exit 4.
3. Create `tests/test_aggregate.py` covering ties, 400/599 boundaries, empty input, formulas, each exhausted key space, byte-budget exhaustion, and all-or-nothing state.

**Verification:**

- `pytest -q tests/test_aggregate.py`
- `mypy src/nginx_stream_report`

**Commit:** `step-3: add bounded streaming aggregations`

## STEP 4: Input and End-to-End Processing

**Goal:** Paths and stdin stream through parser and aggregation with permissive/strict policies.  
**Time:** ~3 hours  
**Context:** `PROJECT_ARCHITECTURE.md` “CLI Interface” inputs and exits; `PRD.md` US-1.  
**Tasks:**

1. Create `src/nginx_stream_report/input.py` with a bounded binary line iterator for path/stdin ownership; invalid UTF-8 and overlong lines follow malformed-record policy.
2. Wire `src/nginx_stream_report/cli.py` so I/O maps to 1, usage to 2, strict malformed input to 3, and cardinality exhaustion to 4.
3. Create `tests/test_processing.py` for identical path/stdin results, empty streams, malformed skips, strict failure, and no partial result on exit 4.

**Verification:**

- `pytest -q tests/test_processing.py`
- `printf '%s\n' 'malformed' | nginx-stream-report --strict -; test $? -eq 3`

**Commit:** `step-4: connect streaming input pipeline`

## STEP 5: Text, JSON, and CSV Renderers

**Goal:** All formats express equivalent data and obey stdout/stderr and ANSI contracts.  
**Time:** ~4 hours  
**Context:** `PROJECT_ARCHITECTURE.md` “CLI Interface” outputs; `PRD.md` US-6 and US-7.  
**Tasks:**

1. Create `src/nginx_stream_report/render.py` with shared visible control/bidi escaping, escaped Rich tables, JSON schema version 1, and normalized CSV columns.
2. Add `tests/golden/report.json`, `tests/golden/report.csv`, and `tests/test_render.py`.
3. Add `tests/test_cli_output.py` for TTY policy, `NO_COLOR`, stderr diagnostics, deterministic ties, and broken pipes.

**Verification:**

- `pytest -q tests/test_render.py tests/test_cli_output.py`
- `nginx-stream-report --json tests/fixtures/access.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: render stable text json and csv reports`

## STEP 6: Optional gzip Input (P1)

**Goal:** gzip archives stream through the identical parser without changing report semantics.  
**Time:** ~2 hours  
**Context:** `PRD.md` US-8.  
**Tasks:**

1. Extend `src/nginx_stream_report/input.py` to select `gzip.open` for `.gz` paths.
2. Add `tests/fixtures/access.log.gz` and cases in `tests/test_input.py` for equivalence and corruption.
3. Confirm corrupt archives map to exit 1 and do not produce partial stdout.

**Verification:**

- `pytest -q tests/test_input.py`
- `diff <(nginx-stream-report --csv tests/fixtures/access.log) <(nginx-stream-report --csv tests/fixtures/access.log.gz)`

**Commit:** `step-6: stream gzip access logs`

## STEP 7: Quality and Performance Gate

**Goal:** Correctness, typing, coverage, and the 1 GiB/30 s target have recorded evidence.  
**Time:** ~4 hours  
**Context:** `STRATEGIC_PLAN.md` KPIs and Definition of Done; `PROJECT_ARCHITECTURE.md` “Performance Contract”.  
**Tasks:**

1. Create `bench/generate_log.py` and `bench/README.md` implementing the architecture's fixed i7-1165G7 baseline, seed/cardinalities, warm-cache policy, three-run median, and worst-RSS record.
2. Fill edge-case gaps in `tests/` without weakening assertions.
3. Profile only if the initial run fails; preserve before/after measurements for any optimization.

**Verification:**

- `ruff check . && mypy src/nginx_stream_report`
- `pytest --cov=nginx_stream_report --cov-branch --cov-fail-under=90`
- `/usr/bin/time -f 'elapsed=%e maxrss=%M' nginx-stream-report --json bench/access-1g.log >/dev/null`

**Commit:** `step-7: prove quality and performance targets`

## STEP 8: Packaging and Release Readiness

**Goal:** Clean Python 3.11 environments can build, install, run, and verify the release artifact.  
**Time:** ~3 hours  
**Context:** `PROJECT_ARCHITECTURE.md` “Packaging and Deployment”; all P0 release criteria in `PRD.md`.  
**Tasks:**

1. Finalize `README.md`, `CHANGELOG.md`, and package metadata in `pyproject.toml`.
2. Create `tests/test_wheel.py` or an equivalent isolated wheel smoke-test script.
3. Record the complete exit-code contract in user documentation: 0 success, 1 runtime/I/O, 2 usage, 3 strict format, 4 unique-cardinality exhaustion.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `pytest -q && nginx-stream-report --version`

**Commit:** `step-8: prepare reproducible pip release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Contract, packaging, parser | 4–5 hours |
| Saturday PM | 3–4 | Safe streaming core | 6–7 hours |
| Sunday AM | 5–6 | Output formats and gzip | 5–6 hours |
| Sunday PM | 7–8 | Evidence and release readiness | 6–7 hours |

## Scope Guard

Do not implement P2 live follow until every P0 criterion passes. Do not add a database, API, server, authentication, Docker, cloud, or Kubernetes. If the 30-second target fails, profile the current pipeline before revisiting architecture.
