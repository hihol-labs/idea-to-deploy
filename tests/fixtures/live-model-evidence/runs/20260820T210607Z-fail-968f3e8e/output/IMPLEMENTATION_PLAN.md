# Implementation Plan: nginx-stream-report

## Planning Rules

This is a documentation-only plan; it does not authorize product-code changes in the current session. Delivery preserves WIP=1: complete and verify one step before starting the next. Behavioral truth comes from [PRD.md](PRD.md), and technical contracts come from [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

Every step must preserve and, where relevant, test the complete exit-code contract: **0 success, 1 operational failure, 2 usage error, 3 data-quality failure/no valid requests, 4 unique-cardinality exhaustion**. Code 4 must never be folded into code 1 or 3.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package layout and tool configuration | Every module and test depends on import/entry-point conventions | 1 hour |
| 2 | Stable domain and error contracts | Parser, accumulator, renderers, and CLI must agree before parallel format work | 1 hour |
| 3 | Golden combined-log fixtures | Correctness needs reviewed examples before feature implementation | 1 hour |
| 4 | Performance benchmark protocol | Prevents late discovery that the core parser design misses the target | 1 hour |

No database, authentication, API, Docker, CI service, or deployment infrastructure is runway for this local CLI.

## Step 1: Establish Package and Contract Tests

**Goal:** A pip-installable skeleton exposes the intended command and encodes the interface before business logic.

**Time:** ~2 hours

**Context:** Architecture sections Technology Stack, Module Boundaries, and CLI Interface.

**Files:**

1. Create `pyproject.toml` with Python `>=3.11`, Click/Rich runtime dependencies, development extras, and `nginx-stream-report = nginx_stream_report.cli:main`.
2. Create `src/nginx_stream_report/__init__.py` with the version surface.
3. Create `src/nginx_stream_report/cli.py` with Click command/options and placeholder composition boundaries only as needed by tests.
4. Create `tests/test_cli.py` for help, version, mutual exclusion, stdin selection, and stdout/stderr rules.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-stream-report --help`

**Commit:** `step-1: establish package and CLI contract`

## Step 2: Define Models, Errors, and Fixtures

**Goal:** All later modules share typed, immutable-enough domain results and explicit error categories.

**Time:** ~2 hours

**Context:** Architecture sections Data Model and Metric Semantics, Error Handling and Trust Boundaries.

**Files:**

1. Create `src/nginx_stream_report/models.py` with `ParsedEntry`, `RankedItem`, `HourBucket`, and `AnalysisReport` dataclasses.
2. Create `src/nginx_stream_report/errors.py` with operational, data-quality, and unique-cardinality exception types.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, and `tests/fixtures/ties.log` with small reviewed examples.
4. Extend `tests/test_cli.py` with parameterized assertions for exits `0/1/2/3/4` at the CLI error-mapping seam.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m compileall -q src tests`

**Commit:** `step-2: define report and error contracts`

## Step 3: Implement and Validate the Combined-Log Parser

**Goal:** Valid lines become `ParsedEntry` objects and invalid lines fail atomically with source position.

**Time:** ~3 hours

**Context:** Architecture Data Model and Error Handling; PRD FR-1 and Data Quality Requirements.

**Files:**

1. Create `src/nginx_stream_report/parser.py` with a compiled combined-format grammar, quoted-field unescaping, timestamp parsing, request-target extraction, and validation.
2. Create `tests/test_parser.py` covering IPv4/IPv6 text, escaped quotes/backslashes, `-`, all status boundaries, query strings, malformed timestamps, malformed requests, and control characters.
3. Extend fixtures only with minimal reviewed cases needed by parser tests.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m pytest tests/test_parser.py --cov=nginx_stream_report.parser --cov-branch --cov-fail-under=90 -q`

**Commit:** `step-3: parse nginx combined logs`

## Step 4: Build the Streaming Accumulator

**Goal:** One-pass analysis returns exact rankings, hourly percentages, and guarded User-Agent diversity.

**Time:** ~4 hours

**Context:** Architecture Streaming and Resource Model; PRD US-2 through US-5.

**Files:**

1. Create `src/nginx_stream_report/aggregate.py` with counters, fixed hourly buckets, deterministic top-10 extraction, shared rounding, and the unique limit check-before-insert.
2. Create `tests/test_aggregate.py` for ties, fewer-than-10 values, status `399/400/599/600`, 24 hours, empty error lists, duplicate User-Agents, the `-` value, and the limit boundary.
3. Ensure cardinality exhaustion raises the dedicated exception mapped to exit 4 and returns no report.

**Verification:**

- `python3.11 -m pytest tests/test_aggregate.py -q`
- `python3.11 -m pytest tests/test_aggregate.py --cov=nginx_stream_report.aggregate --cov-branch --cov-fail-under=90 -q`

**Commit:** `step-4: add streaming metrics and cardinality guard`

## Step 5: Add Terminal, JSON, and CSV Renderers

**Goal:** One report model produces three semantically equivalent, deterministic representations.

**Time:** ~3 hours

**Context:** Architecture CLI Interface and Data Model; PRD US-6 and US-7.

**Files:**

1. Create `src/nginx_stream_report/renderers.py` with separate terminal, JSON, and CSV functions.
2. Create `tests/test_renderers.py` with JSON structure assertions, CSV header/row order/quoting, terminal snapshots without forced ANSI, TTY color tests, and hostile-value escaping.
3. Store expected JSON/CSV snapshots under `tests/fixtures/expected/` only where structural assertions would be less readable.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `python3.11 -m pytest tests/test_renderers.py --cov=nginx_stream_report.renderers --cov-branch -q`

**Commit:** `step-5: render terminal JSON and CSV reports`

## Step 6: Integrate Inputs, Modes, and Exit Semantics

**Goal:** The installed command handles paths/stdin, permissive/strict modes, diagnostics, and every terminal condition end to end.

**Time:** ~3 hours

**Context:** Architecture CLI Interface and Error Handling; PRD FR-7 through FR-9.

**Files:**

1. Complete `src/nginx_stream_report/cli.py` to own streams, compose parsing/aggregation/rendering, map failures, handle broken pipes, and prevent partial reports.
2. Expand `tests/test_cli.py` for multiple paths, repeated stdin rejection, missing/unreadable files, invalid options, malformed lines, zero-valid input, strict mode, broken output, and cardinality exhaustion.
3. Add golden assertions that exit codes remain exactly `0/1/2/3/4`, where 4 means unique-cardinality exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m pytest -q`
- `printf '%s\n' 'invalid' | nginx-stream-report --json; test $? -eq 3`

**Commit:** `step-6: integrate streaming CLI and exit contract`

## Step 7: Prove Performance and Resource Boundaries

**Goal:** The selected single-process architecture is measured against the 1 GB target and cardinality failure remains controlled.

**Time:** ~3 hours

**Context:** Strategic Success Metrics; Architecture Streaming and Resource Model; PRD NFR-1 through NFR-3.

**Files:**

1. Create `tests/test_performance.py` with opt-in markers for representative scan and cardinality stress cases.
2. Create `scripts/generate_benchmark_log.py` as a deterministic local fixture generator; it must label generated data as synthetic and never commit the 1 GB output.
3. Create `docs/PERFORMANCE.md` documenting machine CPU/RAM/storage, Python version, fixture parameters, cache condition, command, elapsed time, and peak RSS.
4. Update `.gitignore` for generated benchmark files and build artifacts.

**Verification:**

- `python3.11 scripts/generate_benchmark_log.py --bytes 1000000000 --output .bench/combined-1gb.log`
- `/usr/bin/time -v nginx-stream-report --json .bench/combined-1gb.log > /dev/null`
- `python3.11 -m pytest -m performance tests/test_performance.py -q`

The recorded elapsed time must be below 30 seconds. If it is not, profile and revise the parser/aggregation design before Step 8; do not waive the requirement in prose.

**Commit:** `step-7: verify performance and memory boundaries`

## Step 8: Package, Document, and Validate the Release Candidate

**Goal:** A clean Python 3.11 environment can install the built wheel and complete all golden flows.

**Time:** ~3 hours

**Context:** Strategic Definition of Done; PRD Release Acceptance; Architecture Deployment.

**Files:**

1. Finalize `README.md` usage and schema examples against actual `--help` output.
2. Add `LICENSE` with the selected open-source license and ensure `pyproject.toml` metadata matches.
3. Add `CHANGELOG.md` with the initial contract and known limitations.
4. Update `CLAUDE.md` step status and evidence links; preserve the complete `0/1/2/3/4` exit contract.

**Verification:**

- `python3.11 -m pytest --cov=nginx_stream_report --cov-branch -q`
- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `python3.11 -m venv .release-venv && .release-venv/bin/pip install dist/*.whl && .release-venv/bin/nginx-stream-report --help`
- `.release-venv/bin/nginx-stream-report --json tests/fixtures/combined.log`
- `.release-venv/bin/nginx-stream-report --csv tests/fixtures/combined.log`

Do not publish a package or create a remote release without separate authorization.

**Commit:** `step-8: validate installable release candidate`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Package contract and correct parsing | Half day |
| Saturday PM | 4–5 | Metrics and all output formats | Half day |
| Sunday AM | 6–7 | End-to-end behavior and measured performance | Half day |
| Sunday PM | 8 | Clean install, documentation, release candidate | Half day |

## Dependency and Priority Rationale

RICE orders user value, but dependency order governs execution: parsing unlocks every metric; a stable report model unlocks formats; integrated CLI behavior unlocks performance and packaging acceptance. P1 gzip support is not scheduled in the eight-step MVP. Strict mode is included because it shares error handling and has low incremental effort; it is the first cut if the weekend capacity is exceeded.

## Completion Evidence

Each step records its exact commands and results in the project’s Idea to Deploy state/evidence mechanism when implementation begins. Completion requires current executable evidence, not this plan or a standalone claim. No implementation or runtime evidence is asserted by this blueprint.
