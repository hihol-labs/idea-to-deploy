# Implementation Plan: nginx-stream-report

This plan implements the approved P0 scope in ten dependency-ordered steps. It creates product code only when executed later; this blueprint session creates documentation only. `PROJECT_ARCHITECTURE.md` is the technical source of truth and `PRD.md` is the behavior source of truth.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console-entry skeleton | Every test and feature needs an installable import/CLI boundary | 1.0 h |
| 2 | Domain dataclasses and typed failures | Parser, aggregator, renderers, and CLI share these contracts | 1.0 h |
| 3 | Representative log fixtures and test helpers | Correctness must be testable before aggregation is expanded | 1.0 h |
| 4 | Benchmark generator outside release artifacts | Performance assumptions need reproducible evidence | 0.5 h |

No database, auth system, HTTP API, Docker setup, or CI deployment infrastructure belongs in the runway.

## STEP 1: Package and CLI Skeleton

**Goal:** A fresh Python 3.11 environment can install the project and invoke help/version.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 9.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click and Rich runtime dependencies, development extras, build metadata, and the `nginx-stream-report` entry point.
2. Create `src/nginx_stream_report/__init__.py` with a single package version source.
3. Create `src/nginx_stream_report/cli.py` with Click help, `--version`, the optional `INPUT`, and placeholder-free option declarations.
4. Create `tests/integration/test_cli_basics.py` for help, version, and invalid-option behavior.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `nginx-stream-report --help`
- `pytest -q tests/integration/test_cli_basics.py`

**Commit:** `step-1: scaffold installable CLI package`

## STEP 2: Domain Models and Failure Mapping

**Goal:** The product has explicit immutable report contracts and typed error-to-exit mappings.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 6.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with `ParsedRequest`, `RankedItem`, `HourBucket`, `UserAgentStats`, and `Report` dataclasses.
2. Create `src/nginx_stream_report/errors.py` with usage-independent domain exceptions for no-valid-data, cardinality exhaustion, and runtime input/output failure.
3. Create `tests/unit/test_models.py` and `tests/unit/test_errors.py` for invariants and code mapping.
4. Keep the complete contract centralized: `0` success, `1` I/O runtime failure, `2` CLI usage error, `3` no valid records, and `4` unique-cardinality exhaustion.

**Verification:**

- `pytest -q tests/unit/test_models.py tests/unit/test_errors.py`
- `mypy src/nginx_stream_report/models.py src/nginx_stream_report/errors.py`

**Commit:** `step-2: define report and error contracts`

## STEP 3: Supported-Format Parser

**Goal:** Common and combined nginx byte lines become validated `ParsedRequest` objects without whole-file reads.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 7; `PRD.md` US-1.

**Tasks:**

1. Create `src/nginx_stream_report/parser.py` with a compiled bytes parser for the published grammar.
2. Add `tests/fixtures/common.log`, `tests/fixtures/combined.log`, and `tests/fixtures/mixed.log` containing small synthetic test records clearly labeled as fixtures.
3. Create `tests/unit/test_parser.py` for IPv4/IPv6 text, timezone offsets, query strings, missing User-Agent, status limits, invalid UTF-8 replacement, and malformed records.
4. Confirm the parser extracts the local log hour and performs no timezone conversion.

**Verification:**

- `pytest -q tests/unit/test_parser.py`
- `ruff check src/nginx_stream_report/parser.py tests/unit/test_parser.py`

**Commit:** `step-3: parse supported nginx formats`

## STEP 4: Bounded Streaming Aggregator

**Goal:** One pass over parsed records yields exact bounded counters and an immutable report.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 6 and 7; `PRD.md` US-2, US-3, US-4, and US-6.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with IP/error-URL counters, 24 hour counts, exact User-Agent set, and scalar totals.
2. Enforce `--max-unique-values` separately for IP, error URL, and User-Agent dimensions before atomic per-record mutation.
3. Implement deterministic top-10 selection by descending count then ascending UTF-8 key.
4. Implement hour percentages with `100 × hourly_request_count / total_valid_requests` and exact User-Agent share semantics.
5. Create `tests/unit/test_aggregate.py`, including every metric, tie handling, zero-UA behavior, and each cardinality boundary.

**Verification:**

- `pytest -q tests/unit/test_aggregate.py`
- `pytest -q tests/unit/test_aggregate.py -k cardinality`

**Commit:** `step-4: aggregate exact bounded metrics`

## STEP 5: JSON and CSV Renderers

**Goal:** Successful reports serialize to deterministic ANSI-free pipeline formats.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface outputs; `PRD.md` US-5.

**Tasks:**

1. Create `src/nginx_stream_report/render/__init__.py` for renderer exports.
2. Create `src/nginx_stream_report/render/json.py` for the fixed `schema_version: 1` object.
3. Create `src/nginx_stream_report/render/csv.py` for `section,rank,key,count,total,percentage` long-form rows.
4. Create `tests/unit/test_render_json.py`, `tests/unit/test_render_csv.py`, and golden files under `tests/fixtures/expected/`.
5. Assert deterministic newlines, null/blank zero-denominator behavior, escaping, and no ANSI bytes.

**Verification:**

- `pytest -q tests/unit/test_render_json.py tests/unit/test_render_csv.py`
- `python -m json.tool tests/fixtures/expected/report.json >/dev/null`

**Commit:** `step-5: add deterministic structured renderers`

## STEP 6: Rich Text Renderer

**Goal:** Default output is readable terminal text whose meaning does not depend on color.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface; `PRD.md` US-5 and US-8.

**Tasks:**

1. Create `src/nginx_stream_report/render/text.py` with summary, top-IP, top-error-URL, hourly, and User-Agent sections.
2. Escape untrusted values as data rather than Rich markup.
3. Honor TTY detection and explicit `--no-color`; keep all labels available without styling.
4. Create `tests/unit/test_render_text.py` for colored and plain snapshots, long keys, and `N/A` User-Agent percentage.

**Verification:**

- `pytest -q tests/unit/test_render_text.py`
- `pytest -q tests/unit/test_render_text.py -k 'color or markup'`

**Commit:** `step-6: render accessible terminal report`

## STEP 7: End-to-End CLI and Exit Codes

**Goal:** File/stdin ingestion, options, diagnostics, output routing, and all exit codes work together.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface; `PRD.md` FR-01 through FR-10.

**Tasks:**

1. Complete `src/nginx_stream_report/cli.py` to stream binary input through parser and aggregator and invoke exactly one renderer after EOF.
2. Map all expected conditions to the complete contract `0/1/2/3/4`: success, I/O runtime failure, usage error, no valid records, and unique-cardinality exhaustion.
3. Ensure code `4` is never collapsed into generic code `1`, and structured stdout stays empty on every nonzero result.
4. Create `tests/integration/test_cli_end_to_end.py` and `tests/integration/test_exit_codes.py` covering file and stdin paths, option conflict, unreadable input, empty/malformed data, output failure, and cardinality exhaustion.

**Verification:**

- `pytest -q tests/integration/test_cli_end_to_end.py tests/integration/test_exit_codes.py`
- `nginx-stream-report --json tests/fixtures/combined.log | python -m json.tool >/dev/null`

**Commit:** `step-7: integrate CLI and complete exit contract`

## STEP 8: Full Quality Gate

**Goal:** Static analysis, tests, coverage, and fresh-install behavior satisfy the release baseline.

**Time:** ~1.5 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done.

**Tasks:**

1. Add any missing edge-case tests under `tests/unit/` and `tests/integration/` without weakening assertions.
2. Configure Ruff, mypy, pytest, and branch coverage in `pyproject.toml`.
3. Create `tests/integration/test_packaging.py` only if packaging validation cannot be expressed cleanly as a release command.
4. Confirm tests exercise codes `0`, `1`, `2`, `3`, and `4` by process result, not only exception mapping.

**Verification:**

- `ruff check .`
- `mypy src`
- `pytest --cov=nginx_stream_report --cov-branch --cov-fail-under=90`
- `python -m build`
- `python -m twine check dist/*`

**Commit:** `step-8: enforce release quality gates`

## STEP 9: Reproducible Performance Gate

**Goal:** Measured evidence establishes whether the single-process architecture meets the 1 GB target.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 10; `PRD.md` US-7.

**Tasks:**

1. Create `tests/performance/generate_log.py` to deterministically generate a non-committed 1 GB fixture with declared IP, URL, error, and User-Agent cardinalities.
2. Create `tests/performance/benchmark.py` to run the installed command, verify totals, capture wall time and peak resident memory, and record hardware/Python context.
3. Create `docs/PERFORMANCE.md` with exact reproduction commands and the measured result; never present generated fixture data as production data.
4. Profile only if the first valid measurement misses 30 seconds; make optimizations in parser/aggregation code only with before/after evidence.

**Verification:**

- `python tests/performance/generate_log.py --size-gib 1 --output /tmp/nginx-stream-report-benchmark.log`
- `python tests/performance/benchmark.py --input /tmp/nginx-stream-report-benchmark.log --max-seconds 30 --max-memory-mib 256`

**Commit:** `step-9: prove performance and memory targets`

## STEP 10: Documentation and Release Candidate

**Goal:** A new user can install, run, automate, and troubleshoot the exact accepted behavior.

**Time:** ~1.5 hours

**Context:** All blueprint documents and the Definition of Done.

**Tasks:**

1. Update `README.md` with final installation, examples, schemas, privacy note, limits, and decompression-through-stdin example.
2. Create `CHANGELOG.md` with the initial release scope and known non-goals.
3. Verify `nginx-stream-report --help` matches `PROJECT_ARCHITECTURE.md` and no placeholder text remains.
4. Build artifacts in a clean environment and rerun the complete quality and performance gates.

**Verification:**

- `python -m build && python -m twine check dist/*`
- `pytest --cov=nginx_stream_report --cov-branch --cov-fail-under=90`
- `rg -n 'TODO|TBD|Lorem ipsum' README.md CHANGELOG.md src tests && exit 1 || true`
- `nginx-stream-report --help`

**Commit:** `step-10: prepare documented release candidate`

## Sprint Boundaries

For the approved one-weekend delivery, “sprints” are short execution blocks rather than multi-week ceremonies.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable foundation and validated parser | ~4 h |
| Saturday PM | 4–5 | Exact aggregation and pipeline formats | ~5 h |
| Sunday AM | 6–8 | Terminal UX, CLI integration, quality gate | ~5.5 h |
| Sunday PM | 9–10 | Performance evidence and release handoff | ~3.5 h |

## Plan Acceptance

Do not mark a step complete from narration. Record the named verification commands and their outcomes. A failed gate keeps the active step in progress; WIP remains one. The release candidate is acceptable only after Step 10 revalidates the exact candidate produced by Steps 1–9.

