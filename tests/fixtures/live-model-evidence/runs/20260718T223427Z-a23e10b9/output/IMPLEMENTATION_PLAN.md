# Implementation Plan: nginx-log-report

## Planning rules

This is a dependency-ordered, one-weekend plan for the P0 product in [PRD.md](PRD.md). It creates product code only when a later implementation workflow is explicitly started; this blueprint itself creates documentation only. Maintain one active step at a time, update the durable specifications before changing behavior, and record the verification output named by each step.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console-entry contract | Every test and module import depends on a valid installable layout | 1 hour |
| 2 | Canonical dataclasses and output schema version | Aggregators and all renderers need one stable internal contract | 1 hour |
| 3 | Representative parser fixtures and benchmark generator | Correctness and performance need reproducible evidence from the start | 1.5 hours |
| 4 | Test/lint/type-check configuration | Each feature needs an executable quality gate | 1 hour |

No database schema, authentication system, Docker setup, or CI deployment runway is needed because the approved architecture is a local, stateless CLI.

## Step 1: Package skeleton and CLI surface

**Goal:** A Python 3.11 wheel exposes `nginx-log-report`, validates output-mode options, and prints help/version without implementing report logic.  
**Time:** ~1.5 hours  
**Context:** [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), Sections 4, 8, and 12.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click/Rich dependencies, pytest tooling, and the `nginx-log-report = nginx_log_report.cli:main` entry point.
2. Create `src/nginx_log_report/__init__.py` with package version exposure.
3. Create `src/nginx_log_report/cli.py` with `INPUT`, `--json`, `--csv`, `--no-color`, `--max-diagnostic-lines`, `--max-distinct-values`, `--help`, and `--version`; enforce JSON/CSV mutual exclusion.
4. Create `tests/test_cli.py` covering help, version, invalid option combinations, and stdin/file argument selection.

**Verification:**

- `python3.11 -m pip install -e .`
- `nginx-log-report --help`
- `python3.11 -m pytest tests/test_cli.py -q`

**Commit:** `step-1: scaffold package and CLI contract`

## Step 2: Canonical records and error model

**Goal:** Typed records define the only contract shared by parser, aggregation, and renderers; user-visible failures map deterministically to exit codes.  
**Time:** ~1 hour  
**Context:** Architecture Sections 5, 6, and 8.

**Tasks:**

1. Create `src/nginx_log_report/models.py` with frozen/slotted `AccessRecord`, `RankedCount`, `ReportMeta`, and `Report` dataclasses and invariant checks.
2. Create `src/nginx_log_report/errors.py` with input, no-valid-record, resource, and internal error categories plus the approved exit-code constants.
3. Create `tests/test_models.py` for 24-bucket, top-10, count, timestamp, and percentage invariants.

**Verification:**

- `python3.11 -m pytest tests/test_models.py -q`
- `python3.11 -m compileall -q src`

**Commit:** `step-2: define report and failure contracts`

## Step 3: Nginx line parser

**Goal:** Combined/common nginx records are parsed into one `AccessRecord` at a time with documented malformed-line behavior.  
**Time:** ~3 hours  
**Context:** Architecture Sections 3 and 7; PRD stories US-1 and US-6.

**Tasks:**

1. Create `src/nginx_log_report/parser.py` with the specified byte-state-machine grammar, nginx escape handling, field/record limits, timezone-aware timestamps, request-target extraction, and optional User-Agent extraction.
2. Create `tests/fixtures/combined.log`, `tests/fixtures/common.log`, and `tests/fixtures/mixed-invalid.log` with small, non-sensitive deterministic cases.
3. Create `tests/test_parser.py` for IPv4/IPv6, every supported escape, extra fields, `-` requests, missing User-Agent, invalid status/timestamp/request, invalid UTF-8 collision semantics, oversized records/fields, and reason-only bounded diagnostics.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_log_report.parser --cov-fail-under=90`

**Commit:** `step-3: parse supported nginx access records`

## Step 4: Streaming aggregations

**Goal:** One pass produces exact top IPs, error URLs, 24 hourly counts, and User-Agent share with deterministic ordering.  
**Time:** ~2.5 hours  
**Context:** Architecture Sections 3, 6, and 13; PRD stories US-2 through US-5.

**Tasks:**

1. Create `src/nginx_log_report/aggregate.py` with counters, fixed hourly buckets, User-Agent set/denominator, summed distinct-key pre-insertion guard, and `finalize()`.
2. Ensure URLs are included only for 400–599 responses and equal-count ranking ties use lexical key order.
3. Create `tests/test_aggregate.py` for empty/mixed data, top-10 truncation, ties, status boundaries, timestamp hours, missing User-Agent, exact share calculation, and deterministic pre-exhaustion failure at a small configured distinct limit.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_log_report.aggregate --cov-fail-under=90`

**Commit:** `step-4: add exact streaming report aggregation`

## Step 5: Versioned JSON and normalized CSV

**Goal:** Pipeline users receive stable, ANSI-free, UTF-8 structured output matching Architecture Section 9.  
**Time:** ~2 hours  
**Context:** Architecture Section 9; PRD story US-7.

**Tasks:**

1. Create `src/nginx_log_report/renderers/__init__.py` with the renderer protocol/selection boundary.
2. Create `src/nginx_log_report/renderers/json.py` with schema version 1, fixed keys, and two-decimal serialized share.
3. Create `src/nginx_log_report/renderers/csv.py` using the standard `csv` module and the fixed six-column normalized schema.
4. Create `tests/golden/report.json`, `tests/golden/report.csv`, `tests/test_render_json.py`, and `tests/test_render_csv.py` for byte-level contract checks, the complete ordered seven-column CSV mapping, escaping, Unicode, and absence of ANSI escapes.

**Verification:**

- `python3.11 -m pytest tests/test_render_json.py tests/test_render_csv.py -q`
- `python3.11 -m pytest tests/test_render_json.py tests/test_render_csv.py --cov=nginx_log_report.renderers --cov-fail-under=90`

**Commit:** `step-5: add stable JSON and CSV outputs`

## Step 6: Rich terminal report

**Goal:** Interactive users get a readable colored report while redirected/default text remains plain and parseable by humans.  
**Time:** ~1.5 hours  
**Context:** Architecture Section 9; PRD story US-8.

**Tasks:**

1. Create `src/nginx_log_report/renderers/text.py` with metadata, ranked tables, hourly distribution, and User-Agent summary.
2. Add the shared display sanitizer for controls, ANSI/OSC, newlines, bidi formatting, and 200-character display truncation; honor TTY detection and `--no-color`.
3. Create `tests/test_render_text.py` with fixed console width, color/no-color, hostile control sequences, safe truncation, zero denominator, and section-label checks.

**Verification:**

- `python3.11 -m pytest tests/test_render_text.py -q`
- `NO_COLOR=1 python3.11 -m pytest tests/test_render_text.py -q`

**Commit:** `step-6: render safe Rich terminal report`

## Step 7: End-to-end CLI integration and failure behavior

**Goal:** File and stdin runs connect parsing, aggregation, rendering, diagnostics, and exit codes without cross-stream contamination.  
**Time:** ~2.5 hours  
**Context:** Architecture Sections 7, 8, and 14; all P0 PRD stories.

**Tasks:**

1. Update `src/nginx_log_report/cli.py` to open buffered input, stream records, bound stderr samples, finalize a report, and invoke one renderer.
2. Map unreadable/late input, zero-valid-record input, resource-limit failure, write/flush failure, quiet broken pipe, and unexpected defects to the documented exits.
3. Extend `tests/test_cli.py` with file/stdin, mixed malformed records, empty input, JSON/CSV stdout purity, broken/late-failing input, failing output doubles, quiet broken pipe, and deterministic repeat-run checks.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-log-report --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `nginx-log-report --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; rows=list(csv.reader(sys.stdin)); assert rows[0] == ["schema_version","section","rank","key","value","count","share_percent"]'`

**Commit:** `step-7: integrate streaming CLI and error handling`

## Step 8: Real 1 GB performance gate

**Goal:** Runtime and memory are measured on a deterministic 1 GB log; the under-30-second requirement is proven on documented hardware.  
**Time:** ~3 hours including profiling/optimization  
**Context:** Architecture Section 13; Strategic Plan KPI and kill criteria.

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` to generate exactly 1,073,741,824 bytes from a fixed seed and documented line-length/status/hour/IP/URL/User-Agent cardinality distributions and malformed ratio.
2. Create `tests/test_performance.py` for a small CI-scale streaming regression and correctness checksum; keep the real 1 GB gate separately marked.
3. Create `BENCHMARK.md` recording generator version/seed/distributions, input hash/size, CPU, cores, RAM, storage, OS/kernel, Python/package versions, warm-up/cache policy, five measured commands/results, median, and peak RSS; add parser-only and high-cardinality microbenchmarks.
4. Profile the real command and optimize only measured parser/aggregation hotspots without changing output contracts.

**Verification:**

- `python3.11 scripts/generate_benchmark_log.py --size-bytes 1073741824 /tmp/nginx-log-report-1g.log`
- Run `/usr/bin/time -v nginx-log-report --json /tmp/nginx-log-report-1g.log >/tmp/nginx-log-report-1g.json` once as warm-up and then five measured times.
- `python3.11 -m pytest tests/test_performance.py -m 'not large' -q`
- Manually record evidence that the five-run median is `<30.0 s`, every run is `<33.0 s`, maximum RSS is `<524288 KB`, and JSON metadata matches the generated record count.

**Commit:** `step-8: prove and tune one-gigabyte performance`

## Step 9: Release-candidate verification and handoff

**Goal:** A clean Python 3.11 environment can install artifacts and produce all three output modes; specifications and package metadata agree.  
**Time:** ~2 hours  
**Context:** All blueprint documents and Strategic Plan Definition of Done.

**Tasks:**

1. Finalize `README.md` with supported formats, exact metric definitions, examples, exit codes, benchmark reference, and limitations.
2. Add `CHANGELOG.md` entry for version `0.1.0` and ensure license/classifiers in `pyproject.toml` reflect the chosen open-source license.
3. Build wheel/sdist, install the wheel in a clean environment, and run text/JSON/CSV smoke tests.
4. Reconcile `PRD.md`, `PROJECT_ARCHITECTURE.md`, `CLAUDE.md`, benchmark evidence, and test results before tagging a release candidate.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_log_report --cov-fail-under=90`
- `python3.11 -m build`
- `python3.11 -m venv /tmp/nginx-log-report-smoke && /tmp/nginx-log-report-smoke/bin/pip install dist/*.whl && /tmp/nginx-log-report-smoke/bin/nginx-log-report --json tests/fixtures/combined.log`
- `python3.11 -m pip check`

**Commit:** `step-9: validate release candidate and handoff`

## Sprint boundaries

These are weekend execution blocks rather than multi-week sprints.

| Block | Steps | Goal | Duration |
|---|---|---|---|
| Saturday foundation | 1–3 | Installable surface, contracts, and correct parsing | ~5.5 hours |
| Saturday/Sunday core | 4–7 | Exact metrics and all output modes integrated | ~8.5 hours |
| Sunday release gate | 8–9 | Performance evidence and clean-install handoff | ~5 hours |

## Final dependency gate

Do not claim implementation completion from unit tests alone. Steps 1–7 must be green before the 1 GB run; Step 8 must contain measured runtime/RSS evidence before Step 9; and Step 9 must install the built wheel, not the editable source tree.
