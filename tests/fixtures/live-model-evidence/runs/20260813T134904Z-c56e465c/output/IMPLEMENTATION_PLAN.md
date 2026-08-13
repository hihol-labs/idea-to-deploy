# Implementation Plan: Nginx Stream Insights

## Planning Contract

This is an eight-step, one-weekend plan for the architecture in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) and P0 requirements in [PRD.md](PRD.md). WIP is one step: do not begin the next step until the current verification passes. Change the specifications first if behavior changes.

The complete process exit-code contract applies to every step and verification fixture: `0` success, `1` unexpected internal error, `2` CLI usage/input I/O/encoding error, `3` log-data failure, and `4` unique-cardinality exhaustion. Code `4` must never be omitted, remapped, or collapsed into a generic failure.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package metadata and `src/` layout | Enables clean imports, tests, and pip entry point | 0.5 h |
| 2 | Typed data and error contracts | Keeps parser, aggregator, renderers, and CLI decoupled | 0.5 h |
| 3 | Representative fixtures and benchmark generator | Establishes correctness and performance evidence before optimization | 0.75 h |

No database schema, authentication system, API scaffold, Docker setup, or CI/CD infrastructure belongs in the runway. The product has no such runtime components.

## STEP 1: Scaffold the Installable CLI

**Goal:** A Python 3.11 package installs locally, exposes `nginx-stream-insights`, and validates the approved option surface.

**Time:** ~1.5 hours

**Context:** [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), sections “CLI Interface,” “Packaging, Configuration, and Deployment,” and “Repository Layout.”

**Files:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, optional pytest tooling, and the console entry point.
2. Create `src/nginx_stream_insights/__init__.py` with a single version source.
3. Create `src/nginx_stream_insights/cli.py` with Click arguments/options, mutual exclusion for `--json`/`--csv`, input stream ownership, and placeholder-free help.
4. Create `tests/test_cli.py` for help, version, defaults, invalid `--top`, invalid `--max-unique`, and format conflicts.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-insights --help`
- `.venv/bin/python -m pytest tests/test_cli.py -q`

**Commit:** `step-1: scaffold installable CLI contract`

## STEP 2: Define Models, Errors, and Fixtures

**Goal:** All component boundaries share typed, immutable records and the test corpus defines accepted nginx combined input.

**Time:** ~1.5 hours

**Context:** Architecture sections “Streaming Data Model,” “Parser and Error Policy,” and “Test Architecture.”

**Files:**

1. Create `src/nginx_stream_insights/models.py` with `AccessRecord`, `RankedItem`, `HourlyBucket`, and `Report` dataclasses.
2. Create `src/nginx_stream_insights/errors.py` with domain exceptions and the full `0/1/2/3/4` mapping, including `CardinalityError -> 4`.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, and `tests/fixtures/ties.log` with documented expected totals.
4. Add model and error-contract assertions to `tests/test_cli.py` or a focused `tests/test_models.py`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_models.py tests/test_cli.py -q`
- `.venv/bin/python -c "from nginx_stream_insights.errors import EXIT_CARDINALITY; assert EXIT_CARDINALITY == 4"`

**Commit:** `step-2: define domain and failure contracts`

## STEP 3: Implement and Validate the Streaming Parser

**Goal:** The tool converts accepted UTF-8 combined-log lines into `AccessRecord` values without retaining raw lines.

**Time:** ~2.5 hours

**Context:** Architecture sections “Streaming Data Model” and “Parser and Error Policy”; PRD FR-1 and FR-2.

**Files:**

1. Create `src/nginx_stream_insights/parser.py` with one compiled grammar and field validators.
2. Create `tests/test_parser.py` covering IPv4/IPv6 strings, timezone offsets, quoted fields, `-` markers, status boundaries, malformed requests, and line-numbered errors.
3. Add an invalid-UTF-8 fixture or byte-stream integration case to `tests/test_cli.py`.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py tests/test_cli.py -q`
- `.venv/bin/python -m pytest tests/test_parser.py --cov=nginx_stream_insights.parser --cov-branch --cov-fail-under=90`

**Commit:** `step-3: parse nginx combined logs`

## STEP 4: Build Bounded Aggregation and Metrics

**Goal:** One pass produces deterministic top lists, 24 hourly percentages, User-Agent share, and controlled exhaustion behavior.

**Time:** ~3 hours

**Context:** Architecture sections “Streaming Data Model” and “Performance and Resource Design”; PRD FR-3 through FR-7.

**Files:**

1. Create `src/nginx_stream_insights/aggregate.py` with counters, a combined distinct-key budget, `consume`, and `finalize`.
2. Create `tests/test_aggregate.py` for top-IP and error-URL ordering, status range 400–599, `--top`, exact tie rules, and zero totals.
3. Add hourly tests using the required percentage formula `100 × hourly_request_count / total_valid_requests`.
4. Add User-Agent exact-match and boundary tests plus cardinality limit-at/exceeded cases proving exit code `4` at the CLI boundary.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregate.py tests/test_cli.py -q`
- `.venv/bin/python -m pytest tests/test_aggregate.py --cov=nginx_stream_insights.aggregate --cov-branch --cov-fail-under=90`

**Commit:** `step-4: add bounded streaming metrics`

## STEP 5: Add Deterministic Text, JSON, and CSV Output

**Goal:** A finalized report renders in exactly one selected format with stdout/stderr separation.

**Time:** ~3 hours

**Context:** Architecture “CLI Interface” outputs and PRD FR-8 through FR-10.

**Files:**

1. Create `src/nginx_stream_insights/render_text.py` with Rich tables and TTY-aware color.
2. Create `src/nginx_stream_insights/render_json.py` with the versioned object schema.
3. Create `src/nginx_stream_insights/render_csv.py` with the long-form schema and spreadsheet-formula mitigation.
4. Create `tests/test_renderers.py` with no-color text, parsed JSON, parsed CSV, tie-order, escaping, and golden-output tests.
5. Update `src/nginx_stream_insights/cli.py` to select one renderer only after successful finalization.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py tests/test_cli.py -q`
- `.venv/bin/nginx-stream-insights --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-5: render terminal JSON and CSV reports`

## STEP 6: Integrate Failure Semantics and Pipeline Behavior

**Goal:** File/stdin runs expose the exact public behavior, including strict parsing and all five exit codes.

**Time:** ~2 hours

**Context:** Architecture “CLI Interface” exit codes; PRD FR-11 and FR-12.

**Files:**

1. Complete `src/nginx_stream_insights/cli.py` stream lifecycle, diagnostics, empty/non-empty invalid input distinction, and exception mapping.
2. Expand `tests/test_cli.py` with file/stdin parity, redirects, no partial JSON/CSV on failure, and assertions for codes `0/1/2/3/4`.
3. Add `tests/fixtures/empty.log` and a generated cardinality-exhaustion input.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py -q`
- Run the exit matrix documented in `CLAUDE_CODE_GUIDE.md` and confirm stdout/stderr independently.

**Commit:** `step-6: enforce complete CLI failure contract`

## STEP 7: Prove Correctness and Performance

**Goal:** Automated evidence demonstrates count conservation, parser/renderer correctness, memory guard behavior, and the 1 GB target.

**Time:** ~2.5 hours plus benchmark runtime

**Context:** Architecture “Performance and Resource Design” and “Test Architecture”; strategic KPIs and Definition of Done.

**Files:**

1. Create `scripts/generate_benchmark_log.py` to deterministically create a representative fixture with controlled cardinality outside timed setup.
2. Create `tests/test_performance.py` as an opt-in benchmark harness that records environment, elapsed time, input bytes, throughput, valid records, and peak RSS.
3. Add property/generated tests to `tests/test_aggregate.py` for count conservation and hourly-percentage totals.
4. Record the named reference machine and three-run results in a “Performance” section of `README.md` after measurement.

**Verification:**

- `.venv/bin/python -m pytest -q --cov=nginx_stream_insights --cov-branch --cov-fail-under=90`
- `.venv/bin/python scripts/generate_benchmark_log.py --bytes 1073741824 --output /tmp/nginx-stream-insights-1gb.log`
- `/usr/bin/time -v .venv/bin/nginx-stream-insights --json /tmp/nginx-stream-insights-1gb.log > /tmp/nginx-stream-insights-report.json` repeated three times; median must be under 30 seconds and JSON must parse

**Commit:** `step-7: verify correctness and performance`

## STEP 8: Package and Perform Clean-Environment Acceptance

**Goal:** The release candidate installs through pip and its documentation matches observed behavior.

**Time:** ~2 hours

**Context:** All architecture sections, all P0 acceptance criteria, [README.md](README.md), and [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md).

**Files:**

1. Finalize `pyproject.toml` metadata, license declaration, classifiers, wheel settings, and console script.
2. Finalize `README.md` quick start, schemas, examples, privacy note, limitations, and measured benchmark.
3. Add distribution smoke cases to `tests/test_cli.py` or `tests/test_distribution.py`.
4. Update this plan and `CLAUDE.md` status only from actual test evidence.

**Verification:**

- `.venv/bin/python -m build`
- Create a fresh temporary Python 3.11 virtual environment, install the built wheel with pip, and run help plus text/JSON/CSV smoke tests.
- `.venv/bin/python -m pytest -q`
- Confirm `git diff --check` when the project is under Git.

**Commit:** `step-8: package release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable shell, contracts, and validated parser | ~5.5 h |
| Saturday PM | 4–5 | Core metrics and all output formats | ~6 h |
| Sunday | 6–8 | Failure semantics, evidence, packaging, and handoff | ~6.5 h plus benchmark |

## Dependency and Release Gates

```text
Step 1 -> Step 2 -> Step 3 -> Step 4 -> Step 5 -> Step 6 -> Step 7 -> Step 8
```

A failed verification keeps the active step open. Release requires the clean-wheel smoke test, full test suite, branch-coverage threshold, all P0 acceptance criteria, complete `0/1/2/3/4` exit behavior, and a measured sub-30-second median for the 1 GB fixture. A performance miss triggers profiling and scoped revision; it does not justify deleting safety checks or adding unapproved infrastructure.
