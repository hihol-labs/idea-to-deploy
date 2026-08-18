# Implementation Plan: Nginx Stream Insights

This is a documentation-only plan; no product code is included. Steps follow dependency order, informed by the RICE ranking in `STRATEGIC_PLAN.md`. The weekend time-box assumes one engineer.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console entry point | Every CLI and test depends on installability | 1 h |
| 2 | Domain/output and exit-code contracts | Prevents renderer and failure semantics from diverging | 1 h |
| 3 | Representative fixtures and benchmark protocol | Makes correctness and performance measurable before feature work | 1.5 h |

No database, auth, Docker, API, or deployment pipeline runway is needed for this local CLI.

## Step 1: Package and Contract Skeleton

**Goal:** A clean Python 3.11 environment can install the package and invoke the documented command.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface” and “Packaging and Planned Structure”.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, pytest/tool configuration, and `nginx-stream-insights` entry point.
2. Create `src/nginx_stream_insights/__init__.py`, `cli.py`, and `errors.py` with version exposure and typed error/exit mapping.
3. Create `tests/integration/test_install_and_help.py` for installed `--help`/`--version` behavior.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`
- `.venv/bin/nginx-stream-insights --help`
- `.venv/bin/pytest tests/integration/test_install_and_help.py -q`

**Commit:** `step-1: establish package and CLI contracts`

## Step 2: Dataclasses and Combined-Log Parser

**Goal:** Lines are lazily converted into validated domain records or explicit malformed results.

**Time:** ~2 hours

**Context:** Architecture sections “Domain and Data Model” and “Parsing and Metric Semantics”.

**Tasks:**

1. Create `src/nginx_stream_insights/models.py` with `AccessRecord`, report, ranking, hourly, and User-Agent dataclasses.
2. Create `src/nginx_stream_insights/parser.py` with a compiled combined-format parser and timezone-aware timestamp conversion.
3. Create `tests/unit/test_parser.py` and fixtures covering quotes, IPv4/IPv6 text, `-`, timezones, statuses, malformed lines, and request-target extraction.

**Verification:**

- `.venv/bin/pytest tests/unit/test_parser.py -q`
- `.venv/bin/python -m compileall -q src`

**Commit:** `step-2: parse nginx combined records`

## Step 3: Streaming Inputs and Core Aggregation

**Goal:** Files/stdin are processed once and produce all four correct metric families.

**Time:** ~3 hours

**Context:** Architecture “System Components”, “Parsing and Metric Semantics”, and PRD FR-1–FR-6.

**Tasks:**

1. Create `src/nginx_stream_insights/input.py` for lazy files/stdin and ordered multi-file input.
2. Create `src/nginx_stream_insights/aggregate.py` with IP/error counters, 24 hourly buckets, exact User-Agent set, totals, and deterministic top-10 finalization.
3. Create `tests/unit/test_aggregate.py` and `tests/integration/test_inputs.py`, including tie, zero-valid, malformed, and multiple-source cases.

**Verification:**

- `.venv/bin/pytest tests/unit/test_aggregate.py tests/integration/test_inputs.py -q`
- `.venv/bin/python -m pytest --cov=nginx_stream_insights.aggregate --cov=nginx_stream_insights.parser --cov-fail-under=90`

**Commit:** `step-3: stream and aggregate nginx metrics`

## Step 4: Rich Terminal Renderer

**Goal:** Default CLI output is a readable human report without corrupting redirected output.

**Time:** ~1.5 hours

**Context:** Architecture “CLI Interface / Outputs” and PRD US-5.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/__init__.py` and `text.py`.
2. Wire default rendering and `--no-color` in `src/nginx_stream_insights/cli.py`.
3. Create `tests/integration/test_text_output.py` for sections, empty buckets, TTY/color policy, and stderr isolation.

**Verification:**

- `.venv/bin/pytest tests/integration/test_text_output.py -q`
- `.venv/bin/nginx-stream-insights --no-color tests/fixtures/sample.log`

**Commit:** `step-4: render terminal report`

## Step 5: JSON and CSV Renderers

**Goal:** Pipelines receive deterministic, styling-free JSON or CSV with the same report semantics.

**Time:** ~2 hours

**Context:** Architecture “CLI Interface / Outputs”, PRD “Output Schemas”, US-6.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/json.py` and `csv.py`.
2. Add mutually exclusive `--json`/`--csv` Click options in `cli.py`.
3. Create `tests/integration/test_json_output.py`, `test_csv_output.py`, and golden files under `tests/fixtures/expected/`.

**Verification:**

- `.venv/bin/pytest tests/integration/test_json_output.py tests/integration/test_csv_output.py -q`
- `.venv/bin/nginx-stream-insights --json tests/fixtures/sample.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-5: add pipeline output formats`

## Step 6: Failure and Cardinality Boundaries

**Goal:** All failures obey `0/1/2/3/4`, and code 4 specifically signals unique-cardinality exhaustion.

**Time:** ~2 hours

**Context:** Architecture “CLI Interface / Exit codes”, PRD “Exit and Error Requirements”.

**Tasks:**

1. Add `--cardinality-limit` validation and pre-insertion checks to `cli.py` and `aggregate.py`.
2. Complete typed exception mapping in `errors.py` for internal, usage, input, and cardinality failures.
3. Create `tests/integration/test_exit_codes.py` covering codes 0, 1, 2, 3, and 4 plus empty stdout on failed JSON/CSV.

**Verification:**

- `.venv/bin/pytest tests/integration/test_exit_codes.py -q`
- `.venv/bin/nginx-stream-insights --cardinality-limit 1 tests/fixtures/two_user_agents.log; test $? -eq 4`

**Commit:** `step-6: enforce exit and cardinality contracts`

## Step 7: Performance Gate and Profiling

**Goal:** A representative 1 GB fixture completes under 30 seconds with documented peak memory.

**Time:** ~2 hours

**Context:** Architecture “Performance and Resource Strategy”, PRD NFR-1/NFR-2.

**Tasks:**

1. Create `tests/performance/generate_fixture.py` with deterministic, non-sensitive synthetic records.
2. Create `tests/performance/benchmark.py` to record file/line count, wall time, peak RSS, CPU/OS/storage/Python metadata.
3. Profile parser/aggregation hot paths and make only evidence-backed optimizations without changing schemas.

**Verification:**

- `.venv/bin/python tests/performance/generate_fixture.py --size-gib 1 --output /tmp/nginx-stream-insights-1gb.log`
- `.venv/bin/python tests/performance/benchmark.py /tmp/nginx-stream-insights-1gb.log --max-seconds 30`

**Commit:** `step-7: verify one-gigabyte performance`

## Step 8: Packaging, Documentation, and Release Candidate

**Goal:** The exact candidate is installable, documented, tested, and handoff-ready.

**Time:** ~2 hours

**Context:** All blueprint documents and `.itd/VERIFICATION_CONTRACT.json`.

**Tasks:**

1. Update `README.md` with verified installation, examples, schemas, exit contract, and performance environment.
2. Add `LICENSE`, build metadata, and `tests/integration/test_wheel.py`; build sdist/wheel.
3. Run lint/type/test/security/package checks, freeze the exact staged candidate, and obtain the required current adjudication receipt before release acceptance.

**Verification:**

- `.venv/bin/python -m build && .venv/bin/twine check dist/*`
- `.venv/bin/pytest -q && .venv/bin/python -m compileall -q src`
- Run the repository's Verification Loop commands for the frozen candidate as defined by the then-current `.itd/VERIFICATION_CONTRACT.json`.

**Commit:** `step-8: prepare verified release candidate`

## Optional Step 9: Gzip Input (P1)

**Goal:** Archived `.gz` logs stream through identical metric and failure contracts.

**Time:** ~1 hour, only if the MVP gates already pass.

**Context:** PRD US-8 / FR-10.

**Tasks:**

1. Extend `src/nginx_stream_insights/input.py` with suffix/magic-aware gzip streaming.
2. Add gzip and corrupt-archive fixtures to `tests/integration/test_inputs.py`.
3. Document gzip behavior in `README.md`.

**Verification:**

- `.venv/bin/pytest tests/integration/test_inputs.py -q -k gzip`
- `.venv/bin/nginx-stream-insights --json tests/fixtures/sample.log.gz | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-9: stream gzip input`

## Weekend Boundaries

| Block | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Installable parser foundation | 3 h |
| Saturday PM | 3–4 | Complete metrics and human output | 4.5 h |
| Sunday AM | 5–6 | Pipeline formats and failure contracts | 4 h |
| Sunday PM | 7–8; 9 only if green | Performance and release evidence | 4–5 h |

## Global Acceptance Checklist

- [ ] Metrics and formulae match `PRD.md`.
- [ ] Text, JSON, and CSV are semantically consistent.
- [ ] Complete exit contract `0/1/2/3/4` passes; code 4 means unique-cardinality exhaustion.
- [ ] 1 GB benchmark is under 30 seconds on the documented laptop.
- [ ] No authentication, database, HTTP API, server, cloud, or Kubernetes capability was introduced.
- [ ] Exact-candidate verification and risk-tier review evidence is current before completion is claimed.
