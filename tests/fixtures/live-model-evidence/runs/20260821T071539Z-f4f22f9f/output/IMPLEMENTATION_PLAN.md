# Implementation Plan: Nginx Stream Analyzer

This eight-step, one-weekend plan is ordered by dependency and adjusted RICE value. It produces product code only when executed later; this blueprint session creates documentation only.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package/console-entry skeleton | All CLI and tests need import/install boundaries | 1 h |
| 2 | Canonical fixtures and contracts | Prevents output and parsing drift | 1 h |
| 3 | Benchmark corpus generator | Makes the performance goal measurable early | 1 h |
| 4 | Test/lint configuration | Gives every feature an immediate machine check | 1 h |

No database schema, migrations, auth system, API scaffold, Docker setup, or CI deployment pipeline belongs in the runway.

## Step 1: Package Skeleton and CLI Contract

**Goal:** A pip-installable Python 3.11 package exposes the command, options, help, and version with no analysis implementation.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface,” “Deployment and Packaging.”

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, build metadata, and `nginx-stream-analyzer` console script.
2. Create `src/nginx_stream_analyzer/__init__.py`, `__main__.py`, and `cli.py`.
3. Create `src/nginx_stream_analyzer/errors.py` with typed I/O, no-valid-data, and cardinality exceptions.
4. Create `tests/test_cli_contract.py` for help, version, options, mutual exclusion, and stdin/file selection.

**Verification:**

- `python3.11 -m pip install -e .`
- `python3.11 -m pytest tests/test_cli_contract.py`
- `nginx-stream-analyzer --help`

**Commit:** `step-1: establish package and cli contract`

## Step 2: Parsing Domain Model

**Goal:** Supported common/combined lines convert deterministically to typed records; malformed lines are rejected without leaking content.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model,” “Parsing Contract.”

**Tasks:**

1. Create `src/nginx_stream_analyzer/models.py` with `AccessRecord` and result dataclasses.
2. Create `src/nginx_stream_analyzer/parser.py` with a pure single-line parser.
3. Create `tests/fixtures/common.log`, `combined.log`, and `malformed.log` with synthetic non-sensitive data.
4. Create `tests/test_parser.py` covering IPv4/IPv6, timestamps/offsets, request triples, status boundaries, sentinel values, quotes, and malformed fields.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py`
- `python3.11 -m ruff check src/nginx_stream_analyzer/parser.py src/nginx_stream_analyzer/models.py`

**Commit:** `step-2: implement nginx record parser contract`

## Step 3: Streaming Input and Core Aggregation

**Goal:** File/stdin records flow through one pass into exact counters without retaining requests.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Streaming and Performance,” “Component Design.”

**Tasks:**

1. Create `src/nginx_stream_analyzer/input.py` for buffered file/stdin iteration and strict decoding.
2. Create `src/nginx_stream_analyzer/aggregate.py` for valid/malformed totals, IP counts, error-URL counts, 24 hour buckets, and exact User-Agent set.
3. Enforce `--max-unique-user-agents`; raise the cardinality exception immediately when exceeded.
4. Create `tests/test_input.py` and `tests/test_aggregate.py` for streaming behavior, sorting ties, percentage math, malformed mixes, empty input, and the cap boundary.

**Verification:**

- `python3.11 -m pytest tests/test_input.py tests/test_aggregate.py`
- `python3.11 -m pytest tests/test_aggregate.py -k cardinality`

**Commit:** `step-3: add streaming aggregation and safety limit`

## Step 4: Terminal Renderer

**Goal:** Default output presents all reports clearly with TTY-aware color and safely escaped untrusted fields.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Outputs,” “Security and Privacy.”

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/__init__.py` and `terminal.py`.
2. Render labeled top-IP, error-URL, hourly, User-Agent, and processing-summary tables.
3. Implement auto/forced/disabled color without interpreting log fields as Rich markup.
4. Create `tests/test_terminal_renderer.py` with snapshots and control-character/markup fixtures.

**Verification:**

- `python3.11 -m pytest tests/test_terminal_renderer.py`
- `nginx-stream-analyzer --no-color tests/fixtures/combined.log`

**Commit:** `step-4: render safe rich terminal report`

## Step 5: JSON and CSV Renderers

**Goal:** Pipeline users receive stable, undecorated structured output with metric parity.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “CLI Interface / Outputs”; `PRD.md` US-6.

**Tasks:**

1. Create `src/nginx_stream_analyzer/renderers/json_output.py` matching the documented JSON shape.
2. Create `src/nginx_stream_analyzer/renderers/csv_output.py` matching the documented five-column schema.
3. Wire renderer selection in `cli.py`; send diagnostics only to stderr.
4. Create `tests/test_json_renderer.py`, `tests/test_csv_renderer.py`, and parity assertions across renderers.

**Verification:**

- `python3.11 -m pytest tests/test_json_renderer.py tests/test_csv_renderer.py`
- `nginx-stream-analyzer --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-stream-analyzer --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-5: add stable json and csv outputs`

## Step 6: End-to-End Failures and Exit Codes

**Goal:** The entire command obeys one tested automation contract: `0/1/2/3/4`.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “CLI Interface / Exit Codes.”

**Tasks:**

1. Map successful analysis to 0; input I/O/decoding failures to 1; Click usage errors to 2; no valid records to 3; unique-cardinality exhaustion to 4.
2. Buffer report emission until successful EOF so nonzero outcomes cannot leak partial stdout.
3. Add `tests/test_exit_codes.py` covering every code and stdout/stderr invariant.
4. Add end-to-end tests comparing stdin and file results.

**Verification:**

- `python3.11 -m pytest tests/test_exit_codes.py tests/test_cli_contract.py`
- `python3.11 -m pytest`

**Commit:** `step-6: enforce complete cli failure contract`

## Step 7: Performance and Robustness Gate

**Goal:** A reproducible representative 1 GB run completes in under 30 seconds with measured peak memory and no semantic regression.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “Streaming and Performance”; `PRD.md` NFR-1/NFR-2.

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically stream a representative corpus without committing the 1 GB artifact.
2. Create `benchmarks/run.sh` to record hardware, Python version, wall time, peak RSS, arguments, and corpus parameters.
3. Profile parser and counter hot paths; optimize only measured bottlenecks without changing output contracts.
4. Create `tests/test_adversarial_input.py` for long fields, high cardinality, Unicode, control characters, and malformed-heavy streams.

**Verification:**

- `python3.11 -m pytest`
- `python3.11 benchmarks/generate_log.py --bytes 1073741824 | benchmarks/run.sh --stdin`
- `python3.11 -m pytest tests/test_adversarial_input.py`

**Commit:** `step-7: validate throughput memory and robustness`

## Step 8: Packaging and Release Documentation

**Goal:** A clean environment can build, install, run, and understand the MVP.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `README.md`; `CLAUDE.md` status protocol.

**Tasks:**

1. Finalize `README.md` examples, schemas, supported formats, limitations, and `0/1/2/3/4` exit codes.
2. Add `LICENSE`, `CHANGELOG.md`, and package metadata appropriate for an open-source release.
3. Add `tests/test_packaging.py` or a clean-venv smoke script for wheel installation and console invocation.
4. Record benchmark evidence and reconcile implementation status in `CLAUDE.md` without marking deferred P1/P2 items complete.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m pytest`
- `python3.11 -m pip install --force-reinstall dist/*.whl && nginx-stream-analyzer --version`

**Commit:** `step-8: prepare tested pip release`

## Weekend Boundaries

| Block | Steps | Goal | Duration |
|---|---|---|---|
| Friday | 1–2 | Contracts and parsing foundation | ~5 h |
| Saturday | 3–5 | All metrics and three output formats | ~9 h |
| Sunday | 6–8 | Error contract, benchmark, release | ~8 h |

WIP remains one step at a time. A step advances only after its listed checks pass; failed performance returns Step 7 to active rather than being narrated as complete.

## Deferred Work

Gzip input (P1), custom `log_format` (P2), and approximate-cardinality research (P2) begin only after MVP release acceptance. Database, HTTP API, auth, server, cloud, and Kubernetes remain out of scope.

