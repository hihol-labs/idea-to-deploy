# Implementation Plan: nginx-insight

This plan implements the approved architecture in dependency order over one weekend. It is planning only; no product code is included here.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package, console entry point, and quality configuration | Every feature needs an installable and testable boundary | 1 hour |
| 2 | Immutable domain and error contracts | Parser, aggregator, renderers, and CLI must agree | 1 hour |
| 3 | Representative fixtures and benchmark protocol | Correctness and speed need reproducible evidence before optimization | 1 hour |

No database, authentication, Docker, API, or deployment infrastructure belongs in the runway.

## STEP 1: Package and CLI Contract

**Goal:** A pip-installable Python 3.11 package exposes `nginx-insight` with validated help and options.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3 and `CLI Interface`; `PRD.md` FR-1 and FR-5.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, build metadata, and console entry point.
2. Create `src/nginx_insight/__init__.py`, `src/nginx_insight/cli.py`, and `src/nginx_insight/errors.py`.
3. Create `tests/test_cli.py` for help, version, option exclusivity, and usage errors.

**Verification:**

- `python -m pytest tests/test_cli.py -q`
- Build a wheel, install it in a clean Python 3.11 environment, and run `nginx-insight --help`.

**Commit:** `step-1: establish package and CLI contract`

## STEP 2: Domain Models and Combined-Log Parser

**Goal:** Standard combined-format lines become typed records with explicit rejection reasons.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 6; `PRD.md` FR-2.

**Tasks:**

1. Create `src/nginx_insight/models.py` with `ParsedRecord`, `ParseStats`, and snapshot dataclasses.
2. Create `src/nginx_insight/parser.py` with one compiled format parser and explicit conversions.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, and `tests/test_parser.py` covering escapes, offsets, malformed request lines, and statuses.

**Verification:**

- `python -m pytest tests/test_parser.py -q`
- Run focused tests proving timestamp offsets and request targets are preserved.

**Commit:** `step-2: parse nginx combined logs`

## STEP 3: Streaming Inputs and Diagnostics

**Goal:** Files and stdin are iterated sequentially without whole-file reads, with bounded diagnostics.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 6 and 8; `PRD.md` FR-1 and FR-2.

**Tasks:**

1. Create `src/nginx_insight/inputs.py` for buffered UTF-8 iteration over paths and stdin.
2. Extend `src/nginx_insight/cli.py` to combine inputs, count malformed records, and implement `--strict`.
3. Create `tests/test_inputs.py` for ordering, stdin, unreadable paths, decoding failure, and bounded diagnostic samples.

**Verification:**

- `python -m pytest tests/test_inputs.py tests/test_cli.py -q`
- Pipe a fixture into the installed command and confirm report data and diagnostics use separate streams.

**Commit:** `step-3: stream files and stdin safely`

## STEP 4: Exact Aggregates and Cardinality Guard

**Goal:** One pass computes all four required views and fails safely at the unique-key ceiling.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 4; `PRD.md` FR-3 and user stories 1–4.

**Tasks:**

1. Create `src/nginx_insight/aggregate.py` with IP/error counters, 24 hourly buckets, User-Agent set, and deterministic top-ten finalization.
2. Enforce `--max-unique` before adding a new stored key and map exhaustion to exit 4.
3. Create `tests/test_aggregate.py` for status bounds, ties, empty hours, timestamp offsets, percentage formulas, and cardinality exhaustion.

**Verification:**

- `python -m pytest tests/test_aggregate.py -q`
- Use a tiny ceiling to prove exit 4 occurs before any report bytes are written.

**Commit:** `step-4: compute bounded exact aggregates`

## STEP 5: Rich Terminal Renderer

**Goal:** The default report clearly presents all metrics with safe color behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface` and section 9; `PRD.md` FR-4.

**Tasks:**

1. Create `src/nginx_insight/renderers/__init__.py` and `src/nginx_insight/renderers/terminal.py`.
2. Add four report sections, summary diagnostics, `--no-color`, non-TTY handling, and safe treatment of log-derived strings.
3. Create `tests/test_terminal_output.py` with normalized snapshots for TTY and redirected output.

**Verification:**

- `python -m pytest tests/test_terminal_output.py -q`
- Run the fixture report in a terminal and redirected to a file; confirm no ANSI bytes in redirected output.

**Commit:** `step-5: render terminal report`

## STEP 6: JSON and CSV Renderers

**Goal:** Pipeline users receive stable, decoration-free, schema-versioned output.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface`; `PRD.md` FR-4 and user story 5.

**Tasks:**

1. Create `src/nginx_insight/renderers/json.py` using the standard JSON encoder.
2. Create `src/nginx_insight/renderers/csv.py` using `csv.writer` and the normalized row schema.
3. Create `tests/test_json_output.py` and `tests/test_csv_output.py` for schemas, values, escaping, all 24 hours, and absence of ANSI sequences.

**Verification:**

- `python -m pytest tests/test_json_output.py tests/test_csv_output.py -q`
- Validate JSON with `python -m json.tool` and parse CSV back with Python's `csv` module.

**Commit:** `step-6: add stable JSON and CSV reports`

## STEP 7: End-to-End Failure and Acceptance Contract

**Goal:** Installed CLI behavior matches all P0 scenarios and the complete process contract.

**Time:** ~2 hours

**Context:** `PRD.md` section 6 and `PROJECT_ARCHITECTURE.md` `CLI Interface`.

**Tasks:**

1. Create `tests/test_acceptance.py` to compare terminal, JSON, and CSV semantics from a golden fixture.
2. Test the complete exit-code contract: `0/1/2/3/4` means success, input/I/O failure, usage error, log-data failure, and unique-cardinality exhaustion.
3. Assert failures never emit partial machine output and diagnostics never contaminate stdout.

**Verification:**

- `python -m pytest tests/test_acceptance.py -q`
- Run the built wheel against success, unreadable, conflicting-option, malformed-strict, and cardinality fixtures and assert codes `0`, `1`, `2`, `3`, and `4` respectively.

**Commit:** `step-7: enforce end-to-end CLI contract`

## STEP 8: Performance, Packaging, and Handoff

**Goal:** A frozen release candidate is installable, documented, and meets the 1 GB target.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 7 and 10; `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Create `benchmarks/generate_log.py` and `benchmarks/run.py` with fixture generation outside the timed region and environment metadata capture.
2. Create or update `README.md` with installation, examples, schemas, supported format, limitations, and exit codes.
3. Run profiling, optimize measured hot paths without changing contracts, build wheel/sdist, and record benchmark evidence.
4. Freeze the exact staged candidate, run the project machine oracle, and apply the risk-tier checker before acceptance.

**Verification:**

- Run the full lint, type, and `python -m pytest -q` suite against the staged candidate.
- Install the built wheel in a clean Python 3.11 environment and run all output-mode smoke tests.
- Run the documented 1 GB benchmark and confirm elapsed time is under 30 seconds on the reference laptop.

**Commit:** `step-8: verify performance and release artifact`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Installable CLI, parser, and streaming input | Friday evening–Saturday morning |
| Weekend block 2 | 4–6 | Correct aggregates and all renderers | Saturday |
| Weekend block 3 | 7–8 | Acceptance, performance, packaging, and handoff | Sunday |

## Cross-Cutting Verification Contract

All implementation steps preserve the exit-code contract `0/1/2/3/4`; code 4 always means unique-cardinality exhaustion. Completion requires current evidence for the exact candidate, not a prose assertion: tests, clean-install smoke checks, benchmark evidence, and the applicable Idea to Deploy adjudication receipt must be recorded.
