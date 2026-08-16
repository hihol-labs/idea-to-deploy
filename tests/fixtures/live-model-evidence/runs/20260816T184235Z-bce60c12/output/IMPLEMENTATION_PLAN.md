# Implementation Plan: nginx-stream-stats

## Plan Contract

This is a nine-step, one-weekend plan. It creates product code only in a later implementation session; this blueprint session creates documentation only. Dependencies precede feature RICE order. [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) is the technical source of truth and [PRD.md](PRD.md) is the behavioral source of truth.

Every step must preserve the complete exit-code contract:

| Code | Contract |
|---:|---|
| `0` | Successful report/help/version |
| `1` | Operational I/O or unexpected internal failure |
| `2` | Invalid CLI invocation |
| `3` | Log data/format failure, including zero valid records or strict malformed input |
| `4` | Unique-cardinality exhaustion |

Code 4 must remain distinct; it cannot be omitted, approximated, or remapped.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml` and `src/` package | Enables repeatable install and console entry point | 0.5 h |
| 2 | Dataclass and error contracts | Prevents parser, aggregator, and renderers from diverging | 0.5 h |
| 3 | Test configuration and fixtures | Gives every feature an executable acceptance path | 0.5 h |
| 4 | Benchmark generator design | Exposes performance risk before polish | 0.5 h |

No database schema, auth system, Docker setup, or CI deployment is runway because those components are explicitly outside scope.

## Step 1: Package and Verification Skeleton

**Goal:** A Python 3.11 package installs in a clean environment and exposes a placeholder-free Click command surface ready for subsequent behavior.

**Time:** ~1.5 hours

**Context:** Architecture sections 6–8; PRD packaging and CLI requirements.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, the `nginx-stream-stats` console script, and test/lint/type-check extras.
2. Create `src/nginx_stream_stats/__init__.py` with package version metadata and `src/nginx_stream_stats/cli.py` with the declared option signatures.
3. Create `tests/conftest.py` and tool configuration for pytest, coverage, linting, and typing.
4. Create `tests/integration/test_cli.py` cases for help/version and Click usage failures.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `nginx-stream-stats --help`
- `python3.11 -m pytest tests/integration/test_cli.py -q`

**Commit:** `step-1: scaffold installable CLI package`

## Step 2: Domain and Error Contracts

**Goal:** Typed immutable results and unambiguous error categories exist before parsing or output logic.

**Time:** ~1 hour

**Context:** Architecture data model and CLI exit table.

**Tasks:**

1. Create `src/nginx_stream_stats/models.py` with `AccessRecord`, `RankedCount`, `HourlyBucket`, `UniqueAgentSummary`, and `AnalysisReport` dataclasses.
2. Create `src/nginx_stream_stats/errors.py` with `LogParseError`, `NoValidRecordsError`, `InputDataError`, and `CardinalityLimitError`.
3. Create `tests/unit/test_models.py` to verify invariants, immutability, and 24-bucket reports.
4. Add exit mapping tests to `tests/integration/test_cli.py` for codes `0/1/2/3/4`.

**Verification:**

- `python3.11 -m pytest tests/unit/test_models.py tests/integration/test_cli.py -q`
- `python3.11 -m mypy src/nginx_stream_stats`

**Commit:** `step-2: define report and failure contracts`

## Step 3: Streaming Combined-Log Parser

**Goal:** Individual nginx combined lines become typed records without retaining the input stream.

**Time:** ~2 hours

**Context:** Architecture parsing decisions; PRD FR-01 and FR-02.

**Tasks:**

1. Create `src/nginx_stream_stats/parser.py` with one compiled anchored expression, escaped-field handling, bounded request parsing, status validation, and timezone-aware timestamps.
2. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` with IPv4/IPv6, escaped quotes, query strings, 4xx/5xx, blank, malformed, and invalid cases.
3. Create `tests/unit/test_parser.py` for valid records, malformed records, strict UTF-8 expectations, and logged-hour semantics.
4. Add a streaming spy test proving no unbounded `read()`/`readlines()` call occurs.

**Verification:**

- `python3.11 -m pytest tests/unit/test_parser.py -q`
- `python3.11 -m ruff check src/nginx_stream_stats/parser.py tests/unit/test_parser.py`

**Commit:** `step-3: parse combined logs incrementally`

## Step 4: Core Aggregations and Percentages

**Goal:** One pass produces deterministic top IPs, error URLs, and all hourly percentages.

**Time:** ~2 hours

**Context:** Architecture complexity model; PRD FR-03 through FR-05.

**Tasks:**

1. Create `src/nginx_stream_stats/aggregator.py` with IP/error `Counter` objects, 24 hourly counters, valid/invalid totals, deterministic tie-breaking, and finalization.
2. Compute every hourly percentage using the literal formula `100 × hourly_request_count / total_valid_requests` and round only at rendering boundaries.
3. Create `tests/unit/test_aggregator.py` with hand-calculated mixed-status fixtures, ties, 24 buckets, and percentage sum tolerance.
4. Verify URLs count only status 400–599 and top lists default to ten.

**Verification:**

- `python3.11 -m pytest tests/unit/test_aggregator.py -q`
- `python3.11 -m pytest tests/unit/test_aggregator.py --cov=nginx_stream_stats.aggregator --cov-fail-under=95`

**Commit:** `step-4: calculate ranked and hourly metrics`

## Step 5: Exact User-Agent Cardinality Guard

**Goal:** Exact User-Agent share works within a bound and fails predictably beyond it.

**Time:** ~1 hour

**Context:** Architecture cardinality decision; PRD FR-06 and exit code 4.

**Tasks:**

1. Extend `src/nginx_stream_stats/aggregator.py` with an exact User-Agent set and positive configured cap.
2. Calculate `100 × unique_user_agent_count / total_valid_requests` during finalization.
3. Raise `CardinalityLimitError` before adding a new value beyond the cap; do not emit partial or approximate output.
4. Extend `tests/unit/test_aggregator.py` for duplicates, empty User-Agent field, exact limit, and limit + 1; extend CLI integration tests for exit 4.

**Verification:**

- `python3.11 -m pytest tests/unit/test_aggregator.py -q -k 'user_agent or cardinality'`
- `python3.11 -m pytest tests/integration/test_cli.py -q -k cardinality`

**Commit:** `step-5: bound exact user-agent cardinality`

## Step 6: Terminal, JSON, and CSV Renderers

**Goal:** All three modes serialize the same report without changing metrics.

**Time:** ~2 hours

**Context:** Architecture output schemas; PRD FR-07 through FR-09.

**Tasks:**

1. Create `src/nginx_stream_stats/renderers/__init__.py` and `terminal.py` with escaped Rich tables, TTY-aware color, and `--no-color` behavior.
2. Create `json_output.py` with the stable JSON keys and six-decimal numeric percentages.
3. Create `csv_output.py` with the single tidy header, all metric row types, standard quoting, and trailing newline.
4. Create `tests/integration/test_output_contracts.py` to compare semantic counts across modes, parse JSON/CSV, and reject ANSI sequences in machine output.

**Verification:**

- `python3.11 -m pytest tests/integration/test_output_contracts.py -q`
- `python3.11 -m pytest tests/integration/test_output_contracts.py -q -k 'json or csv or color'`

**Commit:** `step-6: render terminal json and csv reports`

## Step 7: Wire CLI, Streams, and Failures

**Goal:** The console command fulfills the complete input/output/diagnostic and exit contract.

**Time:** ~1.5 hours

**Context:** Exact `## CLI Interface` in architecture; all P0 PRD criteria.

**Tasks:**

1. Complete `src/nginx_stream_stats/cli.py` to open a file or stdin once, select one renderer, and keep diagnostics on stderr.
2. Map success to 0, operational/internal failures to 1, Click invocation errors to 2, data/format failures to 3, and `CardinalityLimitError` to 4.
3. Implement lenient invalid-line counting and strict first-error termination.
4. Extend `tests/integration/test_cli.py` for stdin/path equivalence, mode exclusion, missing/unreadable files, empty input, invalid UTF-8, strict/lenient behavior, broken output, and all `0/1/2/3/4` codes.

**Verification:**

- `python3.11 -m pytest tests/integration/test_cli.py -q`
- `nginx-stream-stats --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-7: complete CLI and exit semantics`

## Step 8: Performance and Memory Gate

**Goal:** Evidence demonstrates the 1 GB/30-second target and bounded-cardinality behavior on a named laptop.

**Time:** ~1.5 hours

**Context:** Architecture quality attributes; strategic success metrics.

**Tasks:**

1. Create `tests/performance/generate_log.py` to deterministically generate exactly 1 GB of valid combined log data with documented cardinalities.
2. Create `tests/performance/test_benchmark.py` as an opt-in smoke benchmark that checks line-by-line processing and report validity.
3. Record the benchmark machine, Python version, input parameters, command, wall time, and peak RSS in `README.md` without claiming results from another machine.
4. Profile only if the gate fails; preserve behavior while removing measured hotspots.

**Verification:**

- `python3.11 tests/performance/generate_log.py --bytes 1000000000 --output /tmp/nginx-stream-stats-1gb.log`
- `/usr/bin/time -v nginx-stream-stats --json /tmp/nginx-stream-stats-1gb.log >/tmp/nginx-stream-stats-report.json`
- `python3.11 -m pytest tests/performance/test_benchmark.py -q`

**Commit:** `step-8: prove streaming performance envelope`

## Step 9: Release Documentation and Artifact Check

**Goal:** A clean Python 3.11 environment can install the wheel and reach a correct report in under 30 seconds of user setup.

**Time:** ~1.5 hours

**Context:** Strategic Definition of Done; PRD release criteria; README Quick Start.

**Tasks:**

1. Update `README.md` with real installation, input examples, output schemas, all exit codes, limits, and benchmark reproduction.
2. Update `CLAUDE.md` and `CLAUDE_CODE_GUIDE.md` only if implementation discoveries require specification changes; change specs before code behavior.
3. Build sdist/wheel and inspect metadata; install the wheel into a clean virtual environment.
4. Run the full unit/integration suite, coverage gate, lint, typing, and CLI smoke test.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_stream_stats --cov-fail-under=90`
- `python3.11 -m ruff check . && python3.11 -m mypy src/nginx_stream_stats`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `nginx-stream-stats --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-9: verify releasable python package`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Runway, contracts, parser | 5 hours |
| Weekend block 2 | 4–5 | Exact core analytics | 3 hours |
| Weekend block 3 | 6–7 | Renderers and complete CLI | 3.5 hours |
| Weekend block 4 | 8–9 | Performance and release evidence | 3 hours |

WIP remains one step: start the next step only after the current verification commands pass and evidence is recorded.
