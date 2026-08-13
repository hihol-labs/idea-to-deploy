# Implementation Plan: nginx-top

## Delivery Rules

This plan implements the P0 contract in `PRD.md` using the architecture in `PROJECT_ARCHITECTURE.md`. Work is dependency-ordered while preserving the RICE priorities from `STRATEGIC_PLAN.md`. Each step ends with executable evidence and a small commit; do not begin a later feature while the current step is failing.

Every step must preserve the complete exit-code contract: `0` success/help/version; `1` operational input/output failure; `2` usage/configuration error; `3` malformed-log threshold exceeded or no valid requests; `4` unique-cardinality exhaustion. Code `4` must never be omitted, remapped, or converted into a partial-success report.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console entry point | Every test and feature needs an installable import/CLI boundary | 1 hour |
| 2 | Renderer-neutral dataclasses and typed failures | Prevent output concerns from leaking into parsing and metrics | 1 hour |
| 3 | Deterministic fixtures and golden expectations | Makes correctness measurable before performance tuning | 1 hour |
| 4 | Benchmark generator outside product runtime | Establishes the performance oracle without checking in 1 GB | 1 hour |

No database schema, migrations, authentication, API, Docker, cloud, or Kubernetes runway is needed or permitted.

## Step 1: Package Skeleton and CLI Contract

**Goal:** A pip-installable Python 3.11 package exposes `nginx-top`, help/version behavior, option validation, and placeholder-free typed interfaces without implementing log analysis.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Components and Source Layout,” “CLI Interface,” and “Packaging and Deployment.”

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click and Rich dependencies, build metadata, pytest configuration, and `nginx-top = nginx_top.cli:main`.
2. Create `src/nginx_top/__init__.py` with a single version source.
3. Create `src/nginx_top/cli.py` with the `INPUT`, `--json`, `--csv`, `--color/--no-color`, `--max-parse-errors`, `--max-unique`, help, and version contracts.
4. Create `src/nginx_top/errors.py` with application error categories mapped to `0/1/2/3/4`, including `4` for unique-cardinality exhaustion.
5. Create `tests/test_cli.py` for help, version, mutual exclusion, and numeric option validation.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-top --help`

**Commit:** `step-1: establish package and CLI contract`

## Step 2: Domain Models and Combined-Log Parser

**Goal:** Valid combined-format lines become immutable typed requests; malformed lines return bounded, non-sensitive diagnostics.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Streaming Algorithm” and “Supported Log Format”; `PRD.md` FR-2.

**Tasks:**

1. Create `src/nginx_top/models.py` with frozen `ParsedRequest`, ranked-item, hourly-bucket, and `Report` dataclasses.
2. Create `src/nginx_top/parser.py` with one compiled bytes regex and validation for status, timestamp hour, and request token.
3. Create representative valid, IPv6, quoted-field, missing-UA, malformed, and blank fixtures under `tests/fixtures/`.
4. Create `tests/test_parser.py` covering accepted boundaries and safe diagnostic reasons without echoing full log lines.
5. Ensure parser exceptions are internal data failures and cannot leak as exit `1`, `2`, or `4`; CLI mapping to `3` occurs only at threshold/empty-input policy boundaries.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_top.parser --cov-fail-under=90 -q`

**Commit:** `step-2: parse nginx combined logs`

## Step 3: Streaming Aggregation and Cardinality Guard

**Goal:** One pass produces exact counters for all four required metrics with deterministic top-10 selection and safe uniqueness limits.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Data Model and Streaming Algorithm” and “Output Correctness and Determinism”; `PRD.md` US-1 through US-4.

**Tasks:**

1. Create `src/nginx_top/aggregate.py` with IP and 4xx/5xx URL dictionaries, a 24-item hour array, and an exact User-Agent set.
2. Enforce the combined distinct-key ceiling before inserting a new IP, error URL, or User-Agent.
3. Raise the typed unique-cardinality error that maps only to exit `4`; never return an approximate or partial report.
4. Finalize deterministic top-10 entries by count descending/key ascending.
5. Compute every hourly percentage with `100 × hourly_request_count / total_valid_requests` and User-Agent share with the PRD formula.
6. Create `tests/test_aggregate.py` for boundaries, ties, statuses, 24 buckets, percentages, missing User-Agents, and exact limit exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_top.aggregate --cov-fail-under=90 -q`

**Commit:** `step-3: aggregate required metrics in one pass`

## Step 4: Terminal Renderer

**Goal:** Humans receive a readable Rich report with four metric sections and safe, TTY-aware color.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs,” “Security and Privacy”; `PRD.md` FR-5.

**Tasks:**

1. Create `src/nginx_top/renderers/__init__.py` with renderer protocol/type aliases.
2. Create `src/nginx_top/renderers/terminal.py` with summary, IP, error URL, hourly, and User-Agent tables.
3. Escape Rich markup and terminal control content from all log-derived strings.
4. Implement auto-color for TTY stdout and explicit `--color/--no-color` behavior.
5. Add terminal golden and malicious-markup cases to `tests/test_renderers.py`.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -k terminal -q`
- `python3.11 -m pytest tests/test_renderers.py -k 'color or markup' -q`

**Commit:** `step-4: render safe Rich terminal reports`

## Step 5: JSON and CSV Renderers

**Goal:** Pipelines receive stable, ANSI-free JSON or long-form CSV generated from the same report object.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` JSON/CSV schemas under “CLI Interface”; `PRD.md` US-5.

**Tasks:**

1. Create `src/nginx_top/renderers/json.py` using the standard JSON encoder and the exact documented field names.
2. Create `src/nginx_top/renderers/csv.py` using the standard `csv` module and one `record_type,rank,key,count,percentage` header.
3. Add schema, newline, quoting, Unicode, no-ANSI, and cross-renderer semantic-equivalence tests to `tests/test_renderers.py`.
4. Verify percentages are rounded only during serialization and remain numeric in JSON.
5. Keep renderer write errors mapped to exit `1`; `--json --csv` remains usage exit `2`; cardinality failure remains exit `4` before rendering.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -k 'json or csv or equivalence' -q`
- `python3.11 -m pytest tests/test_renderers.py --cov=nginx_top.renderers --cov-fail-under=90 -q`

**Commit:** `step-5: add stable JSON and CSV outputs`

## Step 6: End-to-End Streaming CLI and Failure Semantics

**Goal:** File and stdin inputs flow through parser, aggregator, and selected renderer with exact diagnostics and exit behavior.

**Time:** ~4 hours

**Context:** Entire `PROJECT_ARCHITECTURE.md` “CLI Interface”; `PRD.md` US-6 and US-7.

**Tasks:**

1. Complete `src/nginx_top/cli.py` stream ownership, binary line iteration, parse-threshold policy, renderer selection, and stderr diagnostics.
2. Stop before rendering when no valid requests exist or parse errors exceed the limit; exit `3`.
3. Map open/read/write operational failures to `1` and Click validation to `2`.
4. Map uniqueness exhaustion exclusively to `4`, including file and stdin paths.
5. Handle expected downstream broken-pipe closure without a traceback.
6. Expand `tests/test_cli.py` to cover regular file, non-seekable stdin, tolerated errors, empty input, each error exit, no partial output, and stdout/stderr isolation.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m pytest tests/test_cli.py -k 'exit or stdin or partial' -q`
- `nginx-top --json tests/fixtures/sample.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-6: integrate streaming CLI and exit semantics`

## Step 7: Full Correctness, Packaging, and Security Checks

**Goal:** The complete P0 behavior is reproducible from a clean install and resistant to malicious log text.

**Time:** ~3 hours

**Context:** `PRD.md` release acceptance and `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Add a renderer-neutral golden report fixture under `tests/fixtures/expected_report.json`.
2. Add cross-format end-to-end cases for commas, quotes, Unicode, IPv6, query strings, and terminal control sequences.
3. Add explicit table-driven tests for exit codes `0`, `1`, `2`, `3`, and `4`, where `4` means unique-cardinality exhaustion.
4. Build a wheel and install it into a fresh temporary Python 3.11 virtual environment.
5. Run dependency and source security checks appropriate to a local offline CLI.

**Verification:**

- `python3.11 -m pytest --cov=nginx_top --cov-report=term-missing --cov-fail-under=90 -q`
- `python3.11 -m build`
- `python3.11 -m pip check`
- `python3.11 -m bandit -r src/nginx_top`

**Commit:** `step-7: lock correctness and package quality`

## Step 8: Performance Benchmark and Focused Optimization

**Goal:** A documented run proves a representative 1 GB log completes in under 30 seconds without violating correctness or memory guards.

**Time:** ~4 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Performance Validation”; `PRD.md` NFR-1 and NFR-2.

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically generate a representative combined-format file with controlled cardinality.
2. Create `tests/test_performance.py` for a small CI-safe streaming regression; mark the 1 GB acceptance run as explicit/local.
3. Record Python, OS, CPU, storage, input size, line count, wall time, and peak RSS in `BENCHMARK.md`.
4. Profile compiled parsing, decoding, dictionary updates, and finalization; optimize only measured hotspots.
5. Rerun correctness tests after each optimization and confirm the uniqueness guard still exits `4` at its boundary.

**Verification:**

- `python3.11 benchmarks/generate_log.py --bytes 1000000000 --output /tmp/nginx-top-benchmark.log`
- `/usr/bin/time -v nginx-top --json /tmp/nginx-top-benchmark.log >/dev/null`
- `python3.11 -m pytest -q`

**Commit:** `step-8: verify one-gigabyte performance target`

## Step 9: User Documentation and Release Handoff

**Goal:** A new user can install and run the CLI in under 30 seconds, while maintainers can reproduce every acceptance check.

**Time:** ~2 hours

**Context:** `README.md`, `CLAUDE.md`, `CLAUDE_CODE_GUIDE.md`, and all release criteria in `PRD.md`.

**Tasks:**

1. Update `README.md` with actual installation, file/stdin examples, JSON/CSV schemas, supported log format, privacy warning, limitations, and troubleshooting.
2. Reconcile `CLAUDE.md` status rows with evidence and preserve the specification-first workflow.
3. Confirm all option help text matches `PROJECT_ARCHITECTURE.md`.
4. Confirm every implementation guide documents `0/1/2/3/4`, with `4` as unique-cardinality exhaustion.
5. Build final source and wheel distributions; do not publish without explicit repository/credential authorization.

**Verification:**

- `python3.11 -m pytest -q`
- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `nginx-top --help`

**Commit:** `step-9: finalize documentation and release handoff`

## Sprint Boundaries

The “sprints” are weekend delivery blocks, not multi-week iterations.

| Block | Steps | Goal | Duration |
|---|---|---|---:|
| Block 1 | 1–3 | Installable core, parsing, all metric semantics | ~9 hours |
| Block 2 | 4–6 | Three outputs and complete CLI integration | ~9 hours |
| Block 3 | 7–9 | Quality gate, performance evidence, handoff | ~9 hours |

## Final Verification Checklist

- [ ] Python 3.11 clean install succeeds and `nginx-top --version` exits `0`.
- [ ] Parser, aggregation, renderer, and CLI tests pass at the documented coverage floor.
- [ ] Golden semantic results match across terminal, JSON, and CSV.
- [ ] Hourly output uses `100 × hourly_request_count / total_valid_requests`.
- [ ] Exit codes `0/1/2/3/4` are each exercised; code `4` proves unique-cardinality exhaustion and no partial report.
- [ ] A recorded 1 GB run is under 30 seconds on the named reference laptop.
- [ ] Wheel and source distribution pass package checks.
- [ ] No product code introduces a database, API, server, authentication, cloud, or Kubernetes.
