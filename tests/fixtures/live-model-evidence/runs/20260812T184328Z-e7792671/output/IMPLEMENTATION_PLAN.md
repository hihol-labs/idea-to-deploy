# Implementation Plan: nginx-insights

## 1. Delivery Rules

This plan implements [PRD.md](PRD.md) through the single-process design in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). Work in dependency order, keep one active step, and do not add a database, HTTP API, authentication, server, Docker, cloud, or Kubernetes assets. Each step ends only after its listed verification passes for the exact candidate.

The canonical exit-code contract for every step is:

| Code | Meaning |
|---:|---|
| `0` | Success |
| `1` | Operational/internal or stdout-write failure |
| `2` | Usage/options error |
| `3` | Input/read/decode/strict-parse failure |
| `4` | Unique-cardinality exhaustion |

Codes must never be omitted, remapped, or collapsed. Normal reports are absent on exits 1, 3, and 4.

## 2. Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml`, `src/`, and `tests/` skeleton | Establish import, console entry point, and quality commands | 1.0 h |
| 2 | Canonical dataclasses and exit taxonomy | Parser, pipeline, renderers, and tests need stable contracts | 1.5 h |
| 3 | Representative fixtures and golden-schema helpers | Prevent semantic drift before feature growth | 1.5 h |

There is intentionally no database, auth, API, deployment platform, or container runway.

## STEP 1: Freeze package, CLI, and test contracts

**Goal:** A pip-installable skeleton exposes help/version and the repository has executable quality gates.

**Time:** ~2 hours

**Context:** Architecture sections 2, 4, 6, and 10; PRD FR-01, FR-12, FR-13.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click/Rich dependencies, `nginx-insights = nginx_insights.cli:main`, build metadata, and dev tools.
2. Create `src/nginx_insights/__init__.py` with one package version source.
3. Create `src/nginx_insights/cli.py` with Click argument/option declarations and renderer exclusivity; feature bodies may initially delegate to typed placeholders that cannot report success.
4. Create `tests/integration/test_cli_contract.py` for help, version, mutually exclusive flags, and invalid `--max-unique`.
5. Create `tests/conftest.py` with isolated Click runner and stream helpers.

**Verification:**

- `python -m pip install -e '.[dev]'`
- `python -m ruff check .`
- `python -m mypy src`
- `python -m pytest tests/integration/test_cli_contract.py -q`
- `nginx-insights --help`

**Commit:** `step-1: freeze package and CLI contracts`

## STEP 2: Define domain models and failure taxonomy

**Goal:** All later components share immutable records/report types and the exact five-code mapping.

**Time:** ~2 hours

**Context:** Architecture sections 5 and CLI Interface; PRD sections 7–8.

**Tasks:**

1. Create `src/nginx_insights/models.py` with `AccessRecord`, `AggregateState`, `RankedItem`, `HourlyShare`, and `Report` dataclasses and invariants.
2. Create `src/nginx_insights/errors.py` with typed operational, input/parse, and cardinality exceptions mapped only to exits 1, 3, and 4; Click retains exit 2.
3. Create `tests/unit/test_models.py` to assert 24 buckets, nonnegative counts, deterministic serialization inputs, and zero-denominator semantics.
4. Extend `tests/integration/test_cli_contract.py` to exercise `0/1/2/3/4` without tracebacks or normal reports on failure.

**Verification:**

- `python -m pytest tests/unit/test_models.py tests/integration/test_cli_contract.py -q`
- `python -m mypy src tests`

**Commit:** `step-2: define domain and exit contracts`

## STEP 3: Implement and verify combined-log parsing

**Goal:** Valid combined lines become typed records and malformed/undecodable input produces structured rejection.

**Time:** ~3 hours

**Context:** Architecture sections 5 and 7; PRD Input Contract and US-6.

**Tasks:**

1. Create `src/nginx_insights/parser.py` with one compiled grammar, timestamp/status validation, quoted-field handling, and request-target extraction.
2. Create `tests/fixtures/combined_valid.log`, `tests/fixtures/combined_invalid.log`, and `tests/fixtures/combined_edge_cases.log` containing explicit synthetic test data.
3. Create `tests/unit/test_parser.py` for IPv4/IPv6 text, timezone offsets, quoted spaces, request `-`, bytes `-`, Unicode, and every malformed class.
4. Ensure parse diagnostics expose source and line number at the pipeline boundary but never echo the raw log record.

**Verification:**

- `python -m pytest tests/unit/test_parser.py -q`
- `python -m ruff check src/nginx_insights/parser.py tests/unit/test_parser.py`

**Commit:** `step-3: parse nginx combined logs`

## STEP 4: Build one-pass aggregation and cardinality guard

**Goal:** A lazy stream produces exact deterministic domain results for all four views.

**Time:** ~4 hours

**Context:** Architecture sections 5 and 8; PRD US-2, US-3, US-4, and US-7.

**Tasks:**

1. Create `src/nginx_insights/aggregate.py` to update IP, error-URL, 24-hour, and User-Agent trackers and finalize at most ten ranked items.
2. Create `src/nginx_insights/pipeline.py` to enumerate the input lazily, count/skips invalid lines, implement strict invalid mode, and return one immutable `Report`.
3. Enforce `--max-unique` separately on IPs, error URLs, and User-Agents before inserting a new key; raise the exit-4 domain error without approximation.
4. Create `tests/unit/test_aggregate.py` for status boundaries, ties, all hours, zero valid input, percentage formulas, and guard boundaries.
5. Create `tests/unit/test_pipeline.py` proving single iteration, default skip, strict failure, and no raw-record retention assumptions.

**Verification:**

- `python -m pytest tests/unit/test_aggregate.py tests/unit/test_pipeline.py -q`
- `python -m pytest tests/unit/test_aggregate.py -q -k 'hour or cardinality or tie'`
- `python -m mypy src/nginx_insights/aggregate.py src/nginx_insights/pipeline.py`

**Commit:** `step-4: aggregate reports in one pass`

## STEP 5: Add Rich terminal rendering

**Goal:** Default interactive output clearly presents every report field and invalid-line warning without markup injection.

**Time:** ~2.5 hours

**Context:** Architecture CLI Interface and Security and Privacy; PRD US-1 and NFR-07.

**Tasks:**

1. Create `src/nginx_insights/renderers/__init__.py` with renderer protocol/export definitions.
2. Create `src/nginx_insights/renderers/rich_text.py` with summary, ranked tables, 24 hourly rows, percentages, and explicit plain-text handling for untrusted values.
3. Wire TTY-aware `--color/--no-color` behavior in `src/nginx_insights/cli.py`.
4. Create `tests/integration/test_rich_output.py` for headings, empty input, invalid counts, color modes, narrow terminal, Unicode, and Rich-markup-like values.

**Verification:**

- `python -m pytest tests/integration/test_rich_output.py -q`
- `nginx-insights --no-color tests/fixtures/combined_valid.log`

**Commit:** `step-5: render terminal report`

## STEP 6: Add deterministic JSON and CSV rendering

**Goal:** Both pipeline formats expose the same report semantics with stable documented schemas.

**Time:** ~3 hours

**Context:** Architecture CLI Interface outputs; PRD US-5, FR-07–FR-09, NFR-06.

**Tasks:**

1. Create `src/nginx_insights/renderers/json_output.py` with the normative object shape, 24 ascending hours, six-decimal numeric rounding, and trailing newline.
2. Create `src/nginx_insights/renderers/csv_output.py` with the normalized header, section order, RFC 4180 quoting, and `\n` separators.
3. Connect renderer selection in `src/nginx_insights/cli.py` so JSON/CSV stdout contains no Rich output or diagnostics.
4. Create `tests/fixtures/expected/report.json` and `tests/fixtures/expected/report.csv` as reviewed golden files.
5. Create `tests/integration/test_structured_output.py` for golden equality, stdout/stderr separation, locale/TTY variation, CSV formula-like values, and empty reports.

**Verification:**

- `python -m pytest tests/integration/test_structured_output.py -q`
- `nginx-insights --json tests/fixtures/combined_valid.log | python -m json.tool >/dev/null`
- `nginx-insights --csv tests/fixtures/combined_valid.log | python -c "import csv,sys; list(csv.DictReader(sys.stdin))"`

**Commit:** `step-6: render stable JSON and CSV`

## STEP 7: Complete I/O boundaries and end-to-end fault behavior

**Goal:** File/stdin ownership, decoding, broken pipe, internal errors, malformed input, and cardinality failure honor the complete CLI contract.

**Time:** ~3 hours

**Context:** Architecture CLI Interface and Parsing and Error Strategy; PRD US-2, US-6, US-7, and Release Acceptance.

**Tasks:**

1. Finalize `src/nginx_insights/cli.py` buffered path/stdin handling, source labels, stderr diagnostics, and exception boundary.
2. Add `tests/integration/test_io_and_exit_codes.py` covering readable/unreadable paths, stdin, UTF-8 failure, invalid options, strict parse rejection, all three cardinality trackers, injected internal failure, and broken stdout.
3. Assert exact codes: success `0`, operational/internal `1`, usage `2`, input/parse `3`, and unique-cardinality exhaustion `4`.
4. Assert no traceback and no normal report for exits 1, 3, and 4.

**Verification:**

- `python -m pytest tests/integration/test_io_and_exit_codes.py -q`
- `python -m pytest -q`
- `python -m pytest --cov=nginx_insights --cov-report=term-missing --cov-fail-under=90`

**Commit:** `step-7: enforce IO and exit behavior`

## STEP 8: Benchmark, package, and release-check the CLI

**Goal:** The exact candidate is reproducibly verified, installable, documented, and ready for an open-source MVP release.

**Time:** ~4 hours

**Context:** Strategic Plan KPIs/Definition of Done; Architecture sections 8 and 10; PRD NFRs and Release Acceptance.

**Tasks:**

1. Create `tests/performance/generate_log.py` for a deterministic representative synthetic 1 GB combined-log fixture and document its distribution.
2. Create `tests/performance/run_benchmark.py` to record environment, byte size, elapsed time, peak RSS, output mode, and success threshold without shell parsing ambiguity.
3. Create `tests/integration/test_installed_package.py` or an equivalent clean-venv smoke procedure for wheel install, help, stdin, JSON, and CSV.
4. Update user documentation and CLI help from the normative contracts; do not introduce undocumented flags.
5. Build wheel and source distribution and run the full lint/type/test/coverage/benchmark gates against the frozen release candidate.

**Verification:**

- `python -m ruff format --check .`
- `python -m ruff check .`
- `python -m mypy src tests`
- `python -m pytest --cov=nginx_insights --cov-report=term-missing --cov-fail-under=90`
- `python -m build`
- `python tests/performance/run_benchmark.py --input tests/performance/fixtures/combined-1gb.log --max-seconds 30`
- `python -m pip install --force-reinstall dist/*.whl && nginx-insights --version`

**Commit:** `step-8: verify and package release candidate`

## 11. Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Freeze contracts and parse input | Friday evening–Saturday morning |
| Weekend block 2 | 4–6 | Complete all report semantics and formats | Saturday |
| Weekend block 3 | 7–8 | Fault handling, performance, and packaging | Sunday |

## 12. Dependency and Traceability Summary

```text
Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6 → Step 7 → Step 8
```

Parser work precedes aggregation; the renderer-neutral report precedes every renderer; fault integration follows all output paths; performance and packaging run last against the exact complete candidate. P0 stories US-1 through US-5 are delivered by Steps 3–6, while P1 hardening US-6 and US-7 is completed by Step 7. Step 8 proves the release criteria rather than adding product scope.
