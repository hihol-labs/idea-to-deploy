# Implementation Plan: nginx-log-report

## Plan Principles

This is a one-weekend, WIP=1 plan. Steps are dependency-ordered, then guided by the RICE priorities in `STRATEGIC_PLAN.md`. Each step must finish its checks before the next begins. Product behavior comes from `PRD.md`; module boundaries and output schemas come from `PROJECT_ARCHITECTURE.md`.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` package, console entry point, and Python 3.11 metadata | Every executable test and module depends on import/install behavior | 1 h |
| 2 | Representative combined-log fixtures and benchmark generator | Parser correctness and the 1 GB target need reproducible evidence from the start | 1 h |
| 3 | Error and output contracts | Prevents renderer/CLI branches from inventing incompatible behavior | 0.5 h |

There is no database schema, auth system, Docker environment, or CI/CD deployment runway because the approved architecture is a local stateless CLI.

## Step 1: Establish the Installable CLI Skeleton

**Goal:** A clean environment can install the project and run help/version without consuming input.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Boundaries,” “CLI Interface,” and “Packaging and Deployment.”

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, build metadata, and the `nginx-log-report` console entry point.
2. Create `src/nginx_log_report/__init__.py` and `src/nginx_log_report/__main__.py` with a single version source.
3. Create `src/nginx_log_report/cli.py` containing only the Click command surface and placeholder orchestration boundaries defined by the architecture.
4. Create `tests/test_cli.py` for help, version, mutually exclusive modes, and no-input invocation wiring.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- `.venv/bin/nginx-log-report --help`
- `.venv/bin/nginx-log-report --version`
- `.venv/bin/pytest tests/test_cli.py -q`

**Commit:** `step-1: establish installable CLI skeleton`

## Step 2: Implement Input and Combined-Log Parsing

**Goal:** Files and stdin yield validated `AccessRecord` objects one line at a time with traceable parse failures.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Supported Input Format,” “Data Model and Algorithms,” and “Error Handling and Observability.”

**Tasks:**

1. Create `src/nginx_log_report/io.py` for 64 KiB-bounded file/stdin iteration, source labels, strict UTF-8 decoding, overlong-line draining, and resource ownership.
2. Create `src/nginx_log_report/parser.py` with the frozen `AccessRecord` dataclass, precompiled combined-format parser, request-target extraction, and timestamp/status validation.
3. Create `src/nginx_log_report/errors.py` with input, parse, and internal error classes plus exit-code metadata.
4. Create `tests/fixtures/access_combined.log` and `tests/fixtures/access_malformed.log` with synthetic non-sensitive cases.
5. Create `tests/test_io.py` and `tests/test_parser.py` covering the edge cases named in the architecture.
6. Create `benchmarks/generate_log.py` and the phase-timing foundation in `benchmarks/run_benchmark.py` so the Step 3 hot-path gate is runnable before renderers.

**Verification:**

- `.venv/bin/pytest tests/test_io.py tests/test_parser.py -q`
- `.venv/bin/python -m pytest tests/test_parser.py -q --disable-warnings`

**Commit:** `step-2: stream and parse combined nginx logs`

## Step 3: Build the Streaming Aggregator

**Goal:** One pass produces exact source counts and all four report metrics without retaining records.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section “Data Model and Algorithms”; `PRD.md` P0 metric requirements.

**Tasks:**

1. Create `src/nginx_log_report/aggregate.py` with `StreamingStats`, immutable report dataclasses, error-status filtering, 24 hourly buckets, and the defined User-Agent denominator.
2. Create `tests/test_aggregate.py` for empty input, status 399/400/599, ties, repeated/distinct/missing User-Agents, all hours, and rank limits.
3. Add an iterator-consumption test proving the aggregator does not request a second pass or retain source records.
4. Generate the realistic 1 GB fixture and run an early hot-path spike that records decode, parse, aggregation, total time, and peak RSS before renderer work begins; stop for profiling/ADR review if projected total time is 30 seconds or more.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest tests/test_aggregate.py --cov=nginx_log_report.aggregate --cov-fail-under=95 -q`
- `.venv/bin/python benchmarks/run_benchmark.py --runs 1 --phases /tmp/nginx-access-1g.log`

**Commit:** `step-3: compute exact streaming metrics`

## Step 4: Add JSON and CSV Pipeline Contracts

**Goal:** Machine consumers receive stable, color-free, parseable output with no stdout contamination.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “JSON output,” “CSV output,” and “Exit codes”; `PRD.md` pipeline stories.

**Tasks:**

1. Create `src/nginx_log_report/render/__init__.py` and `src/nginx_log_report/render/json.py` implementing schema version 1.
2. Create `src/nginx_log_report/render/csv.py` implementing the five-column normalized schema and RFC 4180 quoting.
3. Create `tests/test_render_json.py` and `tests/test_render_csv.py` using structural parsing rather than string-only snapshots.
4. Extend `tests/test_cli.py` to prove diagnostics remain on stderr and mode flags are mutually exclusive.

**Verification:**

- `.venv/bin/pytest tests/test_render_json.py tests/test_render_csv.py tests/test_cli.py -q`
- `.venv/bin/nginx-log-report --json tests/fixtures/access_combined.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/nginx-log-report --csv tests/fixtures/access_combined.log | .venv/bin/python -c 'import csv,sys; rows=list(csv.reader(sys.stdin)); assert rows[0] == ["metric","rank","key","value","unit"]'`

**Commit:** `step-4: add stable JSON and CSV reports`

## Step 5: Add the Rich Terminal Report

**Goal:** Default execution shows a readable colored report and remains plain when output is redirected or `--no-color` is used.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Text output” and “Security and Privacy.”

**Tasks:**

1. Create `src/nginx_log_report/render/text.py` with the processing summary, two ranked tables, 24-hour table, and User-Agent summary.
2. Escape or disable Rich markup for every log-derived value.
3. Create `tests/test_render_text.py` for empty sections, unsafe markup-like values, TTY color, redirected output, and `--no-color`.
4. Wire the renderer choice into `src/nginx_log_report/cli.py` without placing Rich calls in the per-line loop.

**Verification:**

- `.venv/bin/pytest tests/test_render_text.py tests/test_cli.py -q`
- `.venv/bin/nginx-log-report --no-color tests/fixtures/access_combined.log | tee /tmp/nginx-log-report.txt`
- `test -s /tmp/nginx-log-report.txt`

**Commit:** `step-5: render safe Rich terminal report`

## Step 6: Complete Failure and Interruption Semantics

**Goal:** All documented input, parsing, usage, internal, and interruption paths produce the promised exit code and output separation.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “CLI Interface” and “Error Handling and Observability”; `PRD.md` reliability criteria.

**Tasks:**

1. Complete orchestration and typed exception mapping in `src/nginx_log_report/cli.py` and `src/nginx_log_report/errors.py`.
2. Add default skip/count and `--strict` stop behavior without exposing complete sensitive lines.
3. Add tests for unreadable paths, invalid codecs, malformed lines, broken input, unexpected errors, and keyboard interruption.
4. Verify that JSON/CSV failures never leave a syntactically valid-looking partial result.

**Verification:**

- `.venv/bin/pytest tests/test_cli.py tests/test_io.py -q`
- `.venv/bin/nginx-log-report --strict tests/fixtures/access_malformed.log >/tmp/out.json 2>/tmp/err.txt; test $? -eq 4`
- `test ! -s /tmp/out.json && test -s /tmp/err.txt`

**Commit:** `step-6: enforce CLI failure contracts`

## Step 7: Prove Performance and Resource Behavior

**Goal:** Reproducible evidence shows whether the 1 GB/30 s target and memory expectations are met.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Performance Strategy”; `STRATEGIC_PLAN.md` KPIs and risks.

**Tasks:**

1. Extend `benchmarks/generate_log.py` to deterministically generate realistic and boundary-cardinality 1 GB combined-format fixtures without checking generated files into source control.
2. Complete `benchmarks/run_benchmark.py` to record fixture hash/profile, Python/OS/CPU, decode/parse/aggregation/total time, and peak RSS for at least three runs over both fixtures.
3. Create `tests/test_streaming_contract.py` with a guarded memory/cardinality sanity test suitable for normal CI.
4. Profile parser allocations if the median exceeds 30 seconds; record any architecture-affecting change in `PROJECT_ARCHITECTURE.md` before implementation.

**Verification:**

- `.venv/bin/python benchmarks/generate_log.py --size-gib 1 --output /tmp/nginx-access-1g.log`
- `.venv/bin/python benchmarks/run_benchmark.py --runs 3 /tmp/nginx-access-1g.log`
- `.venv/bin/pytest tests/test_streaming_contract.py -q`

**Commit:** `step-7: verify gigabyte-scale performance`

## Step 8: Release-Quality Verification and Documentation

**Goal:** The source and built artifacts satisfy all acceptance criteria in a clean environment.

**Time:** ~2 hours

**Context:** All blueprint documents; especially `STRATEGIC_PLAN.md` Definition of Done and `PRD.md` release criteria.

**Tasks:**

1. Update `README.md` with actual installation, examples, schemas, limitations, privacy, and benchmark results.
2. Create `CHANGELOG.md` with the initial release contract and `LICENSE` with the selected open-source license.
3. Finalize `tests/test_end_to_end.py` for file/stdin and text/JSON/CSV golden flows.
4. Build wheel and sdist, install the wheel into a clean temporary environment, and run all smoke cases.
5. Run lint, type checks, tests with coverage, security review, and the Idea to Deploy Verification Loop against the exact candidate.

**Verification:**

- `.venv/bin/ruff check src tests benchmarks`
- `.venv/bin/mypy src`
- `.venv/bin/pytest --cov=nginx_log_report --cov-fail-under=85 -q`
- `.venv/bin/python -m build`
- `python3.11 -m venv /tmp/nginx-log-report-release-venv && /tmp/nginx-log-report-release-venv/bin/pip install dist/*.whl && printf '' | /tmp/nginx-log-report-release-venv/bin/nginx-log-report --json`

**Commit:** `step-8: complete release verification`

## Weekend Boundary

Saturday covers Steps 1–4; Sunday covers Steps 5–8. If Step 7 demonstrates the performance target cannot be met without an architectural change, release stops for an explicit scope/architecture decision. Could features (`--follow`, custom formats, compressed input) never displace P0 verification.

## Completion Evidence

The implementation is complete only when every P0 acceptance criterion in `PRD.md`, the Definition of Done in `STRATEGIC_PLAN.md`, and the current `.itd/VERIFICATION_CONTRACT.json` are backed by current evidence for the exact candidate. A successful narrative or standalone benchmark number is insufficient.
