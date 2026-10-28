# Implementation Plan: nginx-stream-report

## Planning Principles

The plan delivers the single-process streaming architecture in dependency order while using the RICE scores in `STRATEGIC_PLAN.md` within each layer. The product specification in `PRD.md` is the source of truth; no step adds a server, database, authentication, cloud service, or Kubernetes resource.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console entry point | Every test and feature needs an installable boundary | 1 hour |
| 2 | Canonical dataclasses and typed failures | Parser, aggregation, and renderers need one contract | 1 hour |
| 3 | Deterministic fixtures and benchmark generator | Correctness and performance need reproducible evidence | 2 hours |

The complete CLI exit-code contract for every implementation step is: `0` success, `1` unexpected internal failure, `2` usage/option error, `3` input/read/parse processing failure, and `4` unique-cardinality exhaustion. Code 4 must never be omitted, remapped, or converted into a partial successful report.

## Step 1: Scaffold the Installable Package

**Goal:** A clean Python 3.11 environment can install and invoke the command skeleton.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Package Structure,” “Packaging and Deployment,” and “CLI Interface.”

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, build metadata, optional test dependencies, and the `nginx-stream-report` console script.
2. Create `src/nginx_stream_report/__init__.py` and `src/nginx_stream_report/cli.py` with version/help wiring only.
3. Create `tests/test_cli.py` with install/invocation smoke tests.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`
- `.venv/bin/nginx-stream-report --help`
- `.venv/bin/pytest tests/test_cli.py -q`

**Commit:** `step-1: scaffold installable CLI package`

## Step 2: Define Domain Models and Failure Mapping

**Goal:** Parser, aggregator, and renderers share typed immutable contracts and all five exit meanings are testable.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Metric Semantics” and “Failure, Safety, and Observability.”

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with `AccessRecord`, ranked metric, hourly bucket, and `Report` dataclasses.
2. Create `src/nginx_stream_report/errors.py` with typed usage, processing, cardinality, and internal failure categories.
3. Extend `tests/test_cli.py` to assert exit codes `0/1/2/3/4` without exposing tracebacks for expected failures.

**Verification:**

- `.venv/bin/pytest tests/test_cli.py -q`
- `.venv/bin/python -m compileall -q src`

**Commit:** `step-2: define report and failure contracts`

## Step 3: Implement and Test Combined-Log Parsing

**Goal:** Supported nginx lines become accurate `AccessRecord` values and malformed lines are identified without retained input.

**Time:** ~3 hours

**Context:** `PRD.md` FR-01/FR-02 and `PROJECT_ARCHITECTURE.md` component/data-model sections.

**Tasks:**

1. Create `src/nginx_stream_report/parser.py` with once-compiled parsing logic and timestamp-offset handling.
2. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` with quoting, IPv4/IPv6, timezone, status, URL, and User-Agent cases.
3. Create `tests/test_parser.py` for valid fields, malformed lines, and no per-line state retention.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py -q`
- `.venv/bin/pytest tests/test_parser.py --cov=nginx_stream_report.parser --cov-fail-under=90`

**Commit:** `step-3: parse nginx combined access logs`

## Step 4: Build Streaming Aggregation and Safety Guard

**Goal:** One pass produces exact top-IP, error-URL, hourly, and User-Agent metrics with bounded uniqueness behavior.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Data Model and Metric Semantics”; `PRD.md` P0 acceptance criteria 1–4.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with counters, 24 buckets, valid/malformed totals, and deterministic ranking.
2. Compute hourly percentages with `100 × hourly_request_count / total_valid_requests` and two-decimal report values.
3. Add the exact User-Agent set and enforce the configured ceiling before insertion; raise the failure mapped to code 4.
4. Create `tests/test_aggregate.py` for ties, status boundaries, empty input, all-invalid input, formula totals, and ceiling exhaustion.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest tests/test_aggregate.py --cov=nginx_stream_report.aggregate --cov-fail-under=90`

**Commit:** `step-4: aggregate streaming nginx metrics`

## Step 5: Add JSON and CSV Pipeline Outputs

**Goal:** Automation consumers receive deterministic, ANSI-free, schema-stable structured results.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs” and “Output Schemas”; `PRD.md` FR-06/FR-08.

**Tasks:**

1. Create `src/nginx_stream_report/render_json.py` for schema version 1.
2. Create `src/nginx_stream_report/render_csv.py` with `section,key,count,percentage` rows and standard CSV quoting.
3. Create `tests/test_renderers.py` with golden semantic assertions, escaping cases, deterministic ordering, and no ANSI bytes.

**Verification:**

- `.venv/bin/pytest tests/test_renderers.py -q`
- `.venv/bin/nginx-stream-report --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-5: add stable JSON and CSV reports`

## Step 6: Add Rich Text Output and Complete CLI Wiring

**Goal:** Operators can run the full command with colored TTY text, safe redirection, stdin, and validated options.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “CLI Interface”; `PRD.md` P0 acceptance criteria 5–7.

**Tasks:**

1. Create `src/nginx_stream_report/render_text.py` with four metric sections plus valid/malformed summaries.
2. Complete `src/nginx_stream_report/cli.py` input opening, stdin flow, renderer selection, mutual exclusion, color detection, and failure mapping.
3. Expand `tests/test_cli.py` for file/stdin equivalence, redirection, all options, diagnostics, no partial fatal output, and exit codes `0/1/2/3/4`.

**Verification:**

- `.venv/bin/pytest tests/test_cli.py tests/test_renderers.py -q`
- `.venv/bin/nginx-stream-report tests/fixtures/combined.log`
- `.venv/bin/nginx-stream-report --csv tests/fixtures/combined.log | head -n 1`

**Commit:** `step-6: complete text UI and CLI contract`

## Step 7: Run Integration, Quality, and Privacy Checks

**Goal:** The package behaves consistently end-to-end and performs no unrequested persistence or network activity.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done and `PRD.md` quality requirements.

**Tasks:**

1. Add `tests/test_integration.py` to compare semantic values across all renderers and exercise malformed input.
2. Configure lint/type/test commands in `pyproject.toml` without runtime side effects.
3. Inspect dependencies and code paths for network, subprocess, and write operations; document intentional absence.

**Verification:**

- `.venv/bin/pytest -q --cov=nginx_stream_report --cov-fail-under=90`
- `.venv/bin/ruff check src tests`
- `.venv/bin/mypy src`

**Commit:** `step-7: verify correctness and local-only behavior`

## Step 8: Prove the Performance Target

**Goal:** Reproducible evidence shows the 1 GB target completes in under 30 seconds with acceptable peak memory.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Performance Design”; `PRD.md` quality requirements.

**Tasks:**

1. Create `tests/tools/generate_benchmark_log.py` to deterministically generate, not commit, a 1 GB valid fixture with controlled cardinality.
2. Create `tests/test_performance.py` for a small automated regression and document the opt-in 1 GB invocation.
3. Create `docs/PERFORMANCE.md` recording hardware, OS, Python version, command, wall time, peak RSS, and result.
4. Profile parser/aggregation hotspots only if the first run misses the target; preserve exact semantics.

**Verification:**

- `.venv/bin/python tests/tools/generate_benchmark_log.py --size 1GiB /tmp/nginx-stream-report-1g.log`
- `/usr/bin/time -v .venv/bin/nginx-stream-report --json /tmp/nginx-stream-report-1g.log >/dev/null`
- `.venv/bin/pytest tests/test_performance.py -q`

**Commit:** `step-8: validate one-gigabyte performance target`

## Step 9: Package and Release-Candidate Verification

**Goal:** A wheel installs cleanly and all documented behavior is replayable before any separately approved publication.

**Time:** ~2 hours

**Context:** all blueprint documents and the Definition of Done.

**Tasks:**

1. Update `README.md` with final install/use examples and exact supported format limitations.
2. Build wheel and source distribution into `dist/`.
3. Install the wheel into a fresh temporary Python 3.11 environment and run text/JSON/CSV smoke tests.
4. Record test and benchmark results; do not publish, push, or create a release without explicit human confirmation.

**Verification:**

- `.venv/bin/python -m build`
- `.venv/bin/twine check dist/*`
- `python3.11 -m venv /tmp/nginx-stream-report-release-venv && /tmp/nginx-stream-report-release-venv/bin/pip install dist/*.whl`
- `/tmp/nginx-stream-report-release-venv/bin/nginx-stream-report --json tests/fixtures/combined.log`

**Commit:** `step-9: prepare verified release candidate`

## Weekend Boundaries

| Block | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable boundary and correct parsing | ~5 hours |
| Saturday PM | 4–5 | Complete metrics and structured output | ~7 hours |
| Sunday AM | 6–7 | Human CLI and full correctness checks | ~5 hours |
| Sunday PM | 8–9 | Performance proof and installable candidate | ~5 hours |

## Completion Evidence

Implementation is complete only after the exact commands above have run successfully in the implementation session. Writing tests is not evidence that they pass. Any skipped platform-specific check must be recorded explicitly, and the release candidate must not be described as meeting the 1 GB target until the benchmark evidence exists.

