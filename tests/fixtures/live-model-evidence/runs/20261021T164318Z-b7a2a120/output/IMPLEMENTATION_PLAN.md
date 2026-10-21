# Implementation Plan: nginx-stream-report

## Scope and Delivery Contract

This plan implements the approved MVP in [PRD.md](PRD.md) using the design in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). It contains eight dependency-ordered steps sized for one weekend. Product code is not part of the blueprint phase; every path below is a planned artifact.

Every implementation step must preserve the complete process contract: `0` success, `1` input/runtime I/O failure, `2` CLI usage error, `3` no valid records, and `4` unique-cardinality exhaustion. Hourly percentages must use `100 × hourly_request_count / total_valid_requests`.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml` package and console entry point | Makes every later slice installable and testable through the real command boundary | 0.5 h |
| 2 | Typed domain records and exception taxonomy | Prevents parser, aggregator, and CLI contracts from drifting | 0.5 h |
| 3 | Representative fixtures and benchmark generator | Gives correctness and performance work stable evidence | 1.0 h |
| 4 | Automated quality commands | Enables each subsequent step to prove its local behavior | 0.5 h |

No database schema, auth system, API scaffold, Docker setup, or CI deployment lane belongs in the runway because the product is a local stateless CLI.

## Step 1: Package Skeleton and Command Boundary

**Goal:** A Python 3.11 package installs with pip and exposes a callable `nginx-stream-report` command with help/version behavior.

**Time:** ~1 hour

**Context:** [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), sections “CLI Interface,” “Component Design,” and “Packaging and Deployment.”

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, pytest tooling, and the console entry point `nginx-stream-report = nginx_stream_report.cli:main`.
2. Create `src/nginx_stream_report/__init__.py` with the package version.
3. Create `src/nginx_stream_report/cli.py` with the Click command signature, mutually exclusive `--json`/`--csv`, positive `--max-unique-user-agents`, `--no-color`, `--version`, and file/stdin selection.
4. Create `tests/test_cli_contract.py` for help, version, option validation, and usage exit code `2`.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `nginx-stream-report --help`
- `python3.11 -m pytest tests/test_cli_contract.py -q`

**Commit:** `step-1: establish installable CLI contract`

## Step 2: Domain Models and Combined-Log Parser

**Goal:** Supported nginx combined-log lines become validated immutable records; malformed input is classified without throwing uncontrolled exceptions.

**Time:** ~2 hours

**Context:** [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), sections “Inputs,” “Component Design,” and “Security and Privacy.”

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with frozen `LogRecord`, ranking-entry, and `Report` dataclasses.
2. Create `src/nginx_stream_report/parser.py` with one precompiled grammar and `parse_line(line) -> LogRecord | None`.
3. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` covering IPv4, IPv6, query strings, escaped content, offset timestamps, status boundaries, missing User-Agent, empty lines, invalid UTF-8, and malformed request/status/timestamp fields.
4. Create `tests/test_parser.py` with field-level expectations and proof that log content is treated only as data.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_stream_report.parser --cov-branch --cov-fail-under=90`

**Commit:** `step-2: parse nginx combined log records`

## Step 3: One-Pass Aggregation and Exact Metrics

**Goal:** A stream of parsed records produces all four required metrics with deterministic rankings and bounded unique-cardinality behavior.

**Time:** ~2.5 hours

**Context:** [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), sections “Outputs,” “Streaming and Complexity,” and ADR-002; [PRD.md](PRD.md), FR-2 through FR-5.

**Tasks:**

1. Create `src/nginx_stream_report/aggregator.py` with counters for IPs/error URLs, 24 hourly buckets, valid/malformed totals, and a bounded exact User-Agent set.
2. Define `UniqueCardinalityExhausted` and raise it before the retained set exceeds the configured ceiling.
3. Finalize top lists by count descending and key ascending, limited to 10.
4. Calculate each hourly percentage with `100 × hourly_request_count / total_valid_requests` and calculate unique User-Agent share exactly as specified.
5. Create `tests/test_aggregator.py` for status edges, ties, empty error rankings, 24 buckets, percentage rounding, missing User-Agent, and exhaustion boundaries.

**Verification:**

- `python3.11 -m pytest tests/test_aggregator.py -q`
- `python3.11 -m pytest tests/test_aggregator.py --cov=nginx_stream_report.aggregator --cov-branch --cov-fail-under=90`

**Commit:** `step-3: add streaming report aggregation`

## Step 4: JSON and CSV Pipeline Outputs

**Goal:** Automation receives stable, ANSI-free, standards-parseable JSON and CSV reports.

**Time:** ~1.5 hours

**Context:** [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), “Outputs”; [PRD.md](PRD.md), FR-6.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/__init__.py` for renderer interfaces.
2. Create `src/nginx_stream_report/renderers/json.py` with the documented `schema_version: 1` object and numeric percentage fields.
3. Create `src/nginx_stream_report/renderers/csv.py` with the fixed `metric,rank,key,count,percentage` long-form schema using the standard `csv` module.
4. Create `tests/golden/report.json`, `tests/golden/report.csv`, and `tests/test_machine_renderers.py` to validate schemas, Unicode/quoting, deterministic output, and absence of ANSI escapes.

**Verification:**

- `python3.11 -m pytest tests/test_machine_renderers.py -q`
- `nginx-stream-report --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-4: add stable JSON and CSV reports`

## Step 5: Rich Terminal Report

**Goal:** Interactive users receive a readable colored summary while redirected output remains plain and color is never semantically required.

**Time:** ~1.5 hours

**Context:** [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), “Outputs”; [PRD.md](PRD.md), FR-6 and accessibility requirement.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/text.py` with summary, top-IP, top-error-URL, 24-hour, and unique-UA sections.
2. Use Rich-safe text objects so untrusted log fields cannot become markup.
3. Respect terminal detection, `NO_COLOR`, and `--no-color`; keep the same values and ordering with color disabled.
4. Create `tests/golden/report.txt` and `tests/test_text_renderer.py` for sections, escaping, terminal/plain modes, and long URL behavior.

**Verification:**

- `python3.11 -m pytest tests/test_text_renderer.py -q`
- `NO_COLOR=1 nginx-stream-report tests/fixtures/combined.log | python3.11 -c 'import sys; assert "\u001b[" not in sys.stdin.read()'`

**Commit:** `step-5: render accessible terminal report`

## Step 6: End-to-End CLI and Failure Semantics

**Goal:** File and stdin execution connect parsing, aggregation, and rendering with clean stdout/stderr separation and complete exit mapping.

**Time:** ~2 hours

**Context:** [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), “CLI Interface”; [PRD.md](PRD.md), FR-1, FR-6, and FR-7.

**Tasks:**

1. Complete `src/nginx_stream_report/cli.py` orchestration without materializing or rereading input.
2. Map success to `0`, input/runtime I/O failures to `1`, usage errors to `2`, zero valid records to `3`, and unique-cardinality exhaustion to `4`.
3. Ensure fatal paths do not emit partial reports and diagnostics are concise and content-safe on stderr.
4. Extend `tests/test_cli_contract.py` with file/stdin equivalence, all renderers, malformed counts, output-channel separation, broken/unreadable input, and every code in `0/1/2/3/4`.

**Verification:**

- `python3.11 -m pytest tests/test_cli_contract.py -q`
- `python3.11 -m pytest -q`

**Commit:** `step-6: integrate CLI and complete exit contract`

## Step 7: Performance and Resource Proof

**Goal:** The implementation demonstrates one-pass processing of a representative 1 GB log in under 30 seconds on the documented reference laptop.

**Time:** ~2 hours

**Context:** [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), “Streaming and Complexity”; [PRD.md](PRD.md), FR-8.

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically generate a representative fixture from recorded parameters without committing the 1 GB output.
2. Create `benchmarks/run.py` to invoke the installed CLI, validate its result, and record wall time and peak RSS with environment metadata.
3. Create `benchmarks/README.md` with exact generation/run commands, reference laptop details, fixture checksum, and acceptance threshold.
4. Profile only if the first measured run misses the target; optimize measured parser/aggregation hotspots without weakening semantics.

**Verification:**

- `python3.11 benchmarks/generate_log.py --size-gib 1 --output /tmp/nginx-stream-report-1g.log`
- `python3.11 benchmarks/run.py --max-seconds 30 /tmp/nginx-stream-report-1g.log`

**Commit:** `step-7: prove one-gigabyte performance target`

## Step 8: Release Documentation and Clean-Environment Validation

**Goal:** A new user can install and run the package in under 30 seconds, and release evidence agrees with all specifications.

**Time:** ~1.5 hours

**Context:** [README.md](README.md), [PRD.md](PRD.md), release acceptance, and this entire plan.

**Tasks:**

1. Update `README.md` from blueprint status to verified installation, examples, supported input grammar, schemas, formulas, limitations, and troubleshooting.
2. Create `CHANGELOG.md` with the initial release contract and create `LICENSE` with the selected open-source license.
3. Create `tests/test_docs_examples.py` to execute documented commands against fixtures where practical.
4. Build wheel/sdist, install the wheel into a clean Python 3.11 virtual environment, execute smoke tests, run the full suite, and rerun the benchmark.

**Verification:**

- `python3.11 -m pytest -q`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-stream-report-release-venv && /tmp/nginx-stream-report-release-venv/bin/pip install dist/*.whl && /tmp/nginx-stream-report-release-venv/bin/nginx-stream-report --version`
- `python3.11 benchmarks/run.py --max-seconds 30 /tmp/nginx-stream-report-1g.log`

**Commit:** `step-8: prepare verified local CLI release`

## Weekend Delivery Boundaries

| Block | Steps | Outcome |
|---|---|---|
| Saturday morning | 1–2 | Installable boundary and correct parser |
| Saturday afternoon | 3–4 | Complete metrics and machine outputs |
| Sunday morning | 5–6 | Human output and end-to-end failure semantics |
| Sunday afternoon | 7–8 | Performance proof and release validation |

## Final Verification Matrix

| Contract | Evidence |
|---|---|
| Functional metrics | Parser/aggregator unit tests and golden reports |
| Formula | Fixtures verify `100 × hourly_request_count / total_valid_requests` |
| Pipeline formats | JSON parser, CSV reader, ANSI absence tests |
| Exit codes | Integration matrix exercises `0/1/2/3/4` |
| Streaming | Code review plus memory/benchmark evidence |
| Performance | Recorded representative 1 GB run under 30 seconds |
| Packaging | Wheel installed and command run in clean Python 3.11 environment |

P1/P2 work must not begin until all P0 evidence passes. Gzip, configurable top-N, and custom log formats remain separate future units.
