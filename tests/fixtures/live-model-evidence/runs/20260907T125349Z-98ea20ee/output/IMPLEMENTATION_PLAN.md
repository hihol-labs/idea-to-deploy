# Implementation Plan: nginx-stream-insights

This plan implements the P0 scope from `PRD.md` in dependency order informed by the RICE ranking in `STRATEGIC_PLAN.md`. It has nine steps, sized for one focused weekend. No product code is part of this blueprint.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package and console-entry scaffold | Every test and feature needs an importable package | 1 h |
| 2 | Domain/output contracts | Prevents parser, aggregator, and renderers from drifting | 1 h |
| 3 | Test fixtures and quality commands | Enables fast red-green work from the first behavior | 1 h |
| 4 | Performance harness metadata | Makes the 1 GB target measurable rather than anecdotal | 1 h |

Database, authentication, API, Docker, and CI/CD deployment runway are intentionally absent because the architecture is a local, stateless CLI. A lightweight CI test matrix is introduced only as release verification.

## Step 1: Package and CLI Contract

**Goal:** A clean Python 3.11 environment can install the package and invoke help/version with the documented options.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface,” “Packaging and Deployment,” and “Repository Layout.”

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, and the `nginx-stream-insights` console script.
2. Create `src/nginx_stream_insights/__init__.py` with a single version source.
3. Create `src/nginx_stream_insights/cli.py` with Click argument/option declarations but no parsing logic yet.
4. Create `tests/test_cli.py` for help, version, mutually exclusive formats, numeric option bounds, and code 2 usage failures.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-stream-insights --help`

**Commit:** `step-1: scaffold package and CLI contract`

## Step 2: Domain Models and Golden Fixtures

**Goal:** Shared dataclasses and representative inputs make metric/output contracts explicit.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Component Design” and `PRD.md` “Output Definitions.”

**Tasks:**

1. Create `src/nginx_stream_insights/models.py` with immutable `LogRecord`, configuration, ranked row, hourly row, User-Agent summary, and complete result dataclasses.
2. Create `tests/fixtures/combined.log`, `tests/fixtures/common.log`, `tests/fixtures/malformed.log`, and expected JSON/CSV fixture documents.
3. Add fixture invariants for errors, all tie cases, missing User-Agents, timezone offsets, query strings, Unicode, and control characters.

**Verification:**

- `python3.11 -m pytest tests/test_models.py -q`
- `python3.11 -m compileall -q src tests`

**Commit:** `step-2: define domain contracts and fixtures`

## Step 3: Streaming nginx Parser

**Goal:** Combined/common lines are parsed into `LogRecord` instances one at a time with clear malformed accounting.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Inputs,” “Processing and Complexity,” and “Reliability and Security.”

**Tasks:**

1. Create `src/nginx_stream_insights/parser.py` with precompiled combined/common patterns and field conversion.
2. Create `tests/test_parser.py` for valid profiles, timestamps, request-target extraction, status bounds, Unicode, missing fields, oversized lines, and malformed rows.
3. Ensure parsed log strings are treated only as data and never evaluated or sent to a shell.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m ruff check src/nginx_stream_insights/parser.py tests/test_parser.py`

**Commit:** `step-3: implement streaming nginx parser`

## Step 4: Aggregation and Cardinality Guard

**Goal:** One pass produces exact counters, hourly percentages, deterministic rankings, and a bounded User-Agent failure.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Processing and Complexity” and `PRD.md` FR-2 through FR-5.

**Tasks:**

1. Create `src/nginx_stream_insights/aggregator.py` with `consume`, malformed accounting, and `snapshot` operations.
2. Implement top ordering by count descending then key ascending.
3. Calculate hourly percentages with `100 × hourly_request_count / total_valid_requests` and emit all 24 buckets.
4. Enforce `--max-unique-user-agents` before adding a new value and raise a typed exhaustion error.
5. Create `tests/test_aggregator.py` for all formulas, boundaries, ties, missing User-Agents, and accounting invariants.

**Verification:**

- `python3.11 -m pytest tests/test_aggregator.py -q`
- `python3.11 -m pytest tests/test_aggregator.py --cov=nginx_stream_insights.aggregator --cov-fail-under=90`

**Commit:** `step-4: aggregate metrics with bounded cardinality`

## Step 5: Text, JSON, and CSV Renderers

**Goal:** A completed result renders correctly for terminals and pipelines without contaminating stdout.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs” and `PRD.md` FR-6.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/__init__.py` with renderer selection.
2. Create `src/nginx_stream_insights/renderers/text.py` with Rich summary/tables, two-decimal percentages, TTY-aware color, and escaped values.
3. Create `src/nginx_stream_insights/renderers/json.py` with `schema_version: 1` and deterministic keys/arrays.
4. Create `src/nginx_stream_insights/renderers/csv.py` with the fixed long-form header and standard-library quoting.
5. Create `tests/test_renderers.py` with JSON parsing, CSV round-trip, snapshots, Unicode/control text, and absence of ANSI in structured modes.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `python3.11 -m ruff check src/nginx_stream_insights/renderers tests/test_renderers.py`

**Commit:** `step-5: add deterministic output renderers`

## Step 6: End-to-End CLI and Exit Codes

**Goal:** File/stdin processing, diagnostics, and the full process contract operate as one command.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “CLI Interface” and `PRD.md` FR-1 and FR-7.

**Tasks:**

1. Complete `src/nginx_stream_insights/cli.py` to own/close file streams, preserve stdin ownership, stream rows, choose a renderer, and map typed failures.
2. Extend `tests/test_cli.py` to compare file/stdin output, check stdout/stderr separation, handle zero-valid input and interruption, and assert every exit code.
3. Implement the contract exactly: `0` success; `1` input I/O/interruption; `2` usage/configuration; `3` zero valid requests; `4` unique-cardinality exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-stream-insights --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- `python3.11 -m pytest -q`

**Commit:** `step-6: integrate CLI and complete exit contract`

## Step 7: Performance and Memory Acceptance

**Goal:** The implementation has reproducible evidence for the 1 GB under 30 seconds target and cardinality behavior.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Processing and Complexity” and `PRD.md` FR-8.

**Tasks:**

1. Create `benchmarks/generate_log.py` for a deterministic 1 GB representative dataset without checking the generated file into source control.
2. Create `benchmarks/run_benchmark.py` to record environment, elapsed time, throughput, peak RSS, input profile, and three runs.
3. Create `tests/test_performance.py` with a small CI-safe streaming smoke test; keep the 1 GB test as an explicit local acceptance marker.
4. Profile parser/aggregation hot paths and make only measured optimizations that preserve the specification.

**Verification:**

- `python3.11 benchmarks/generate_log.py --size-gb 1 --output /tmp/nginx-stream-insights-1gb.log`
- `python3.11 benchmarks/run_benchmark.py /tmp/nginx-stream-insights-1gb.log --runs 3`
- `python3.11 -m pytest tests/test_performance.py -q`

**Commit:** `step-7: verify throughput and memory behavior`

## Step 8: Packaging, CI, and Documentation

**Goal:** A clean environment can build, install, test, and use the CLI from documented examples.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Packaging and Deployment,” `README.md`, and `CLAUDE_CODE_GUIDE.md`.

**Tasks:**

1. Create `.github/workflows/ci.yml` for Python 3.11 lint, type, unit, and integration checks without services.
2. Finalize `README.md` with install, file/stdin, text/JSON/CSV, format, limit, and exit-code examples.
3. Add `LICENSE`, packaging include rules, and wheel/sdist metadata.
4. Test the built wheel in a new virtual environment.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m pytest -q`

**Commit:** `step-8: package and document release candidate`

## Step 9: Release-Candidate Verification

**Goal:** Freeze and adjudicate one exact candidate with all functional, quality, and performance evidence current.

**Time:** ~2 hours plus benchmark

**Context:** `STRATEGIC_PLAN.md` “Definition of Done,” `PRD.md` “Release Criteria,” and `.itd/VERIFICATION_CONTRACT.json`.

**Tasks:**

1. Run all static, test, build, install, and CLI smoke checks on the exact staged candidate.
2. Run the documented 1 GB benchmark on the reference laptop and attach environment/results.
3. Verify the exit contract `0/1/2/3/4`, structured schemas, fixture accounting, and no network/persistence behavior.
4. Apply the project risk-tier checker and accept only a current Idea to Deploy adjudication receipt.

**Verification:**

- `python3.11 -m ruff check . && python3.11 -m mypy src && python3.11 -m pytest --cov=nginx_stream_insights --cov-fail-under=90`
- `python3.11 -m build && python3.11 -m twine check dist/*`
- `nginx-stream-insights --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`
- Run the repository Verification Loop against the exact staged candidate according to `.itd/VERIFICATION_CONTRACT.json`.

**Commit:** `step-9: verify release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Installable contract and parser | Friday evening–Saturday morning |
| Weekend block 2 | 4–6 | Metrics, formats, integrated CLI | Saturday afternoon–evening |
| Weekend block 3 | 7–9 | Performance, packaging, acceptance | Sunday |

## Dependency and Scope Rules

- Complete only one step at a time and record verification before moving on.
- `PROJECT_ARCHITECTURE.md` is authoritative for process boundaries and public interfaces; `PRD.md` is authoritative for behavior.
- Changes to formulas, schemas, or exit codes require updating the documents before code.
- P1/P2 work begins only after every P0 release criterion passes.
- Database, authentication, HTTP API, server, cloud, and Kubernetes changes are forbidden without an explicit new scope decision.

