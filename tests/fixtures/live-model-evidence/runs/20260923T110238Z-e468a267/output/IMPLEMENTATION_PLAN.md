# Implementation Plan: nginx-stream-insights

This Full-mode plan covers one weekend and eight dependency-ordered steps. It implements `PRD.md` through the component boundaries in `PROJECT_ARCHITECTURE.md`; it does not introduce a database, API, service, container, cloud resource, or Kubernetes asset.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` package, pip entry point, and dependency pins | Every test and feature needs an installable command | 1 hour |
| 2 | Domain dataclasses and typed public failures | Parser, aggregator, renderers, and exit mapping share these contracts | 1 hour |
| 3 | Representative fixtures and output schemas | Prevents implementation from inventing ambiguous behavior | 1 hour |
| 4 | Benchmark generator and measurement protocol | Makes the 1 GB / 30 s constraint measurable before optimization | 1 hour |

No database schema, authentication system, API scaffold, Docker setup, or deployment pipeline belongs in the runway because the product is a local stateless CLI.

## Step 1: Establish the Installable CLI and Contracts

**Goal:** A Python 3.11 virtual environment can install the project, invoke `nginx-insights --help`, and import stable domain/error types.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Model,” “CLI Interface,” and “Packaging and Deployment.”

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11`, Click, Rich, pytest tooling, `src` discovery, and the `nginx-insights = nginx_stream_insights.cli:main` entry point.
2. Create `src/nginx_stream_insights/__init__.py` with package version metadata.
3. Create `src/nginx_stream_insights/models.py` with frozen/slot-based `AccessRecord`, `RankedCount`, `HourlyBucket`, and `AnalysisResult` dataclasses.
4. Create `src/nginx_stream_insights/errors.py` with expected input and cardinality exceptions.
5. Create `src/nginx_stream_insights/cli.py` with Click option declarations and explicit mutual-exclusion validation, initially delegating analysis through typed boundaries.
6. Create `tests/test_cli_contract.py` to pin help text, option defaults, option conflicts, and version behavior.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-insights --help`
- `.venv/bin/python -m pytest tests/test_cli_contract.py -q`

**Commit:** `step-1: establish package and CLI contracts`

## Step 2: Implement Streaming Input and Combined-Log Parsing

**Goal:** Files and stdin are read lazily, and valid combined-log lines become typed records while malformed lines remain recoverable diagnostics.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Algorithms,” “CLI Interface / Inputs,” and “Error Handling and Resource Limits.”

**Tasks:**

1. Create `src/nginx_stream_insights/input.py` with context-managed iteration over stdin and sequential files without corpus buffering.
2. Create `src/nginx_stream_insights/parser.py` with one compiled combined-log pattern, timestamp parsing, request-target extraction, and status validation.
3. Create `tests/fixtures/combined.log` containing IPv4, IPv6, escaped quoted fields, multiple timezone offsets, missing User-Agent values, and 2xx/4xx/5xx records.
4. Create `tests/fixtures/malformed.log` containing blank, truncated, invalid-timestamp, and invalid-status lines.
5. Create `tests/test_input.py` and `tests/test_parser.py` for lazy iteration, file ordering, stdin, gzip deferral, decoding failures, and parser boundaries.

**Verification:**

- `.venv/bin/python -m pytest tests/test_input.py tests/test_parser.py -q`
- `.venv/bin/python -c "from nginx_stream_insights.parser import parse_line; print(parse_line(open('tests/fixtures/combined.log', encoding='utf-8').readline()))"`

**Commit:** `step-2: add streaming input and nginx parser`

## Step 3: Build Exact Core Aggregation

**Goal:** A single pass computes top IPs, top error URLs, and 24 hourly percentages deterministically.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Streaming state” and “Performance Design”; `PRD.md` FR-02 through FR-04.

**Tasks:**

1. Create `src/nginx_stream_insights/aggregate.py` with counters, fixed 24-hour storage, valid/malformed totals, and a finalization boundary.
2. Implement deterministic top-10 ordering by descending count then ascending key.
3. Count URL errors only for statuses 400–599 and preserve query strings in targets.
4. Calculate every hourly percentage with `100 × hourly_request_count / total_valid_requests`, returning all 24 buckets.
5. Create `tests/test_aggregate.py` for status boundaries, ties, fewer/more than ten keys, empty hours, multiple sources, and percentage totals.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate.py -k 'top or hourly' -q`

**Commit:** `step-3: implement exact streaming metrics`

## Step 4: Add User-Agent Cardinality Safety and Exit Semantics

**Goal:** Unique User-Agent share is exact within a configured bound, and every expected outcome maps to the documented exit code.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Algorithms,” “Exit codes,” and ADR-003; `PRD.md` FR-05 and FR-09.

**Tasks:**

1. Extend `src/nginx_stream_insights/aggregate.py` with the exact non-missing User-Agent set and pre-insertion limit check.
2. Extend `src/nginx_stream_insights/cli.py` to map typed failures and prevent any partial stdout on failure.
3. Add `tests/test_cardinality.py` for boundary-equal, boundary-exceeded, repeated-agent, and missing-agent behavior.
4. Extend `tests/test_cli_contract.py` to cover the complete `0/1/2/3/4` exit-code contract.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cardinality.py tests/test_cli_contract.py -q`
- `set +e; .venv/bin/nginx-insights --max-unique-user-agents 1 tests/fixtures/combined.log >/tmp/nginx-insights.out; test $? -eq 4 && test ! -s /tmp/nginx-insights.out`

**Commit:** `step-4: enforce cardinality and exit contracts`

## Step 5: Render Safe Colored Terminal Output

**Goal:** Default output is a readable Rich report with no unsafe markup interpretation and a reliable plain-text mode.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface / Outputs” and “Security and Privacy”; `PRD.md` FR-06.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers.py` with Rich title, summary, top-IP, error-URL, hourly, and User-Agent sections.
2. Escape all untrusted fields and configure automatic terminal color detection.
3. Wire `--no-color` and terminal rendering in `src/nginx_stream_insights/cli.py`.
4. Create `tests/test_terminal_output.py` with plain snapshots and adversarial Rich-markup values.

**Verification:**

- `.venv/bin/python -m pytest tests/test_terminal_output.py -q`
- `.venv/bin/nginx-insights --no-color tests/fixtures/combined.log`

**Commit:** `step-5: add safe terminal report`

## Step 6: Implement JSON and CSV Pipeline Contracts

**Goal:** `--json` and `--csv` emit stable, parseable, styling-free stdout while diagnostics remain on stderr.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “CLI Interface / Outputs”; `PRD.md` FR-07 and FR-08.

**Tasks:**

1. Add JSON schema-versioned serialization to `src/nginx_stream_insights/renderers.py`.
2. Add normalized `metric,rank,key,count,percentage` CSV serialization with standard quoting and spreadsheet-formula mitigation.
3. Wire mutually exclusive format selection in `src/nginx_stream_insights/cli.py`.
4. Create `tests/test_json_output.py`, `tests/test_csv_output.py`, and snapshots under `tests/snapshots/`.
5. Verify neither machine format contains ANSI escapes, warnings, or locale-dependent numbers.

**Verification:**

- `.venv/bin/python -m pytest tests/test_json_output.py tests/test_csv_output.py -q`
- `.venv/bin/nginx-insights --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/nginx-insights --csv tests/fixtures/combined.log | .venv/bin/python -c "import csv,sys; rows=list(csv.DictReader(sys.stdin)); assert rows"`

**Commit:** `step-6: add JSON and CSV output contracts`

## Step 7: Complete Input Robustness and P1 Gzip Support

**Goal:** Multi-file, encoding, broken gzip, malformed-only, and mixed-quality inputs behave exactly as documented.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface / Inputs” and “Error Handling and Resource Limits”; `PRD.md` FR-01, FR-09, and FR-10.

**Tasks:**

1. Extend `src/nginx_stream_insights/input.py` with `.gz` text streaming while preserving one-file-at-a-time behavior.
2. Finish encoding validation and source-context diagnostics in `src/nginx_stream_insights/cli.py`.
3. Create compressed and invalid-encoding fixtures under `tests/fixtures/`.
4. Create `tests/test_end_to_end.py` for stdin, ordered files, gzip, mixed malformed lines, no valid records, unreadable files, and stdout write failures.

**Verification:**

- `.venv/bin/python -m pytest tests/test_input.py tests/test_end_to_end.py -q`
- `gzip -c tests/fixtures/combined.log >/tmp/nginx-insights-combined.log.gz && .venv/bin/nginx-insights --json /tmp/nginx-insights-combined.log.gz | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-7: harden inputs and add gzip streaming`

## Step 8: Prove Performance, Package, and Release Readiness

**Goal:** The exact candidate passes all behavior gates, processes the representative 1 GB fixture in under 30 seconds on the recorded laptop, and installs from a built wheel.

**Time:** ~4 hours

**Context:** `STRATEGIC_PLAN.md` sections “KPIs” and “Definition of Done”; `PROJECT_ARCHITECTURE.md` sections “Performance Design,” “Packaging and Deployment,” and “Test Boundaries.”

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically generate a representative combined-log corpus with recorded parameters.
2. Create `benchmarks/run.py` to record wall time, peak RSS, byte/line counts, Python version, CPU model, and input checksum.
3. Profile and optimize only measured hot paths in `src/nginx_stream_insights/parser.py` and `aggregate.py` without changing public contracts.
4. Complete `README.md` with installation, examples, schemas, privacy note, scope, and exit codes.
5. Build a wheel/sdist, install the wheel into a clean environment, and run terminal/JSON/CSV smoke tests.
6. Run the full suite, coverage gate, static checks, and the representative 1 GB benchmark.

**Verification:**

- `.venv/bin/python -m pytest --cov=nginx_stream_insights --cov-fail-under=90 -q`
- `.venv/bin/python -m ruff check src tests benchmarks`
- `.venv/bin/python -m build`
- `.venv/bin/python benchmarks/generate_log.py --size-gib 1 --output /tmp/nginx-insights-1g.log`
- `.venv/bin/python benchmarks/run.py /tmp/nginx-insights-1g.log --max-seconds 30`
- `python3.11 -m venv /tmp/nginx-insights-release-venv && /tmp/nginx-insights-release-venv/bin/python -m pip install dist/*.whl && /tmp/nginx-insights-release-venv/bin/nginx-insights --json tests/fixtures/combined.log`

**Commit:** `step-8: validate performance and release package`

## Exit-Code Acceptance Contract

Every implementation step must preserve this complete public contract:

| Code | Required meaning |
|---:|---|
| `0` | Successful help/version or completed analysis with valid records |
| `1` | Unexpected internal/runtime or output-write failure |
| `2` | CLI usage or configuration error |
| `3` | Input/read/decode/gzip failure or zero valid records |
| `4` | Unique-cardinality exhaustion |

Codes must not be remapped, collapsed, or inferred from diagnostic text.

## Weekend Boundaries

| Block | Steps | Outcome |
|---|---|---|
| Saturday morning | 1–2 | Installable CLI, typed contracts, and streaming parser |
| Saturday afternoon | 3–4 | Exact metrics, cardinality guard, and exit semantics |
| Sunday morning | 5–7 | All output modes and robust inputs |
| Sunday afternoon | 8 | Performance evidence and releasable package |

## Completion Gate

Completion requires the Definition of Done in `STRATEGIC_PLAN.md`, all P0 acceptance criteria in `PRD.md`, the exact output/exit contracts in `PROJECT_ARCHITECTURE.md`, and a current benchmark result tied to the tested package candidate. Narrative confidence alone is not evidence.
