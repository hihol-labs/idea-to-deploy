# Implementation Plan: nginx-insight

## Planning Rules

This is an execution plan, not product code. Work is WIP=1: complete and verify one step before beginning the next. [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) is the technical source of truth; [PRD.md](PRD.md) owns behavior and acceptance criteria. If behavior changes, update those specifications first.

Every implementation step must preserve the complete exit-code contract: `0` complete success, `1` input/output operational failure, `2` usage/configuration error, `3` partial-data report after malformed records are skipped, and `4` unique-cardinality exhaustion with no report. Code 4 must never be omitted, remapped, or collapsed into code 1.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package and quality-tool skeleton | All later modules and checks need stable paths | 1 hour |
| 2 | Golden fixtures and output schemas | Fixes behavior before implementation | 1.5 hours |
| 3 | Parser/aggregate boundaries and typed errors | Prevents UI and format logic from entering the hot path | 1 hour |
| 4 | Reproducible benchmark harness | Allows early performance checks, not end-of-project guesses | 1.5 hours |

There is intentionally no database schema, authentication system, HTTP API, Docker setup, or CI/CD deployment runway.

## STEP 1: Package Skeleton and CLI Surface

**Goal:** An installable Python 3.11 package exposes `nginx-insight --help` and validates the public options without processing input.

**Time:** ~1 hour

**Context:** Architecture Sections 4 and `CLI Interface`; PRD FR-001 and NFR-006.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, the `nginx-insight` console entry point, and test/lint/type-check extras.
2. Create `src/nginx_insight/__init__.py`, `src/nginx_insight/__main__.py`, and `src/nginx_insight/cli.py`.
3. Create `tests/test_cli.py` to pin help, version, mutually exclusive formats, stdin/path rules, and positive `--max-unique` validation.
4. Map invalid invocation to exit code 2; keep the full `0/1/2/3/4` contract visible in command help.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- `.venv/bin/nginx-insight --help`
- `.venv/bin/pytest -q tests/test_cli.py`

**Commit:** `step-1: establish package and CLI contract`

## STEP 2: Golden Fixtures and Contract Oracles

**Goal:** Representative logs and expected normalized results make metric semantics executable before parser work.

**Time:** ~1.5 hours

**Context:** Architecture `Input grammar`, `Metric semantics`, and `Outputs`; all P0 acceptance criteria.

**Tasks:**

1. Create `tests/fixtures/combined.log` with repeated IPs, 2xx/4xx/5xx statuses, ties, query strings, missing User-Agents, and timezone-bearing timestamps.
2. Create `tests/fixtures/malformed.log` with mixed valid/invalid records and invalid UTF-8 bytes where the test framework permits a binary fixture.
3. Create `tests/fixtures/expected_report.json` as the canonical schema-v1 oracle.
4. Create `tests/test_contract_fixtures.py` to independently assert fixture counts, the formula `100 × hourly_request_count / total_valid_requests`, tie ordering, and UA numerator/denominator.

**Verification:**

- `.venv/bin/pytest -q tests/test_contract_fixtures.py`
- `.venv/bin/python -m json.tool tests/fixtures/expected_report.json >/dev/null`

**Commit:** `step-2: freeze report fixtures and metric oracle`

## STEP 3: Combined-Log Parser and Input Reader

**Goal:** Files and stdin yield validated `ParsedRecord` values one at a time with source-aware malformed-line diagnostics.

**Time:** ~2.5 hours

**Context:** Architecture Sections 3, 4, `Input grammar`, and 8; PRD FR-002 and FR-008.

**Tasks:**

1. Create `src/nginx_insight/models.py` with the specified dataclasses.
2. Create `src/nginx_insight/errors.py` with parse, operational, configuration, and cardinality exception types.
3. Create `src/nginx_insight/input.py` for buffered binary iteration over ordered paths or stdin.
4. Create `src/nginx_insight/parser.py` with a compiled combined-format grammar, timestamp/status validation, raw request-target extraction, and missing-UA normalization.
5. Create `tests/test_parser.py` and `tests/test_input.py` for valid, malformed, huge, escaped/control-character, invalid-byte, multi-file, and I/O cases.

**Verification:**

- `.venv/bin/pytest -q tests/test_parser.py tests/test_input.py`
- `.venv/bin/mypy src/nginx_insight/parser.py src/nginx_insight/input.py src/nginx_insight/models.py`

**Commit:** `step-3: parse combined logs as a stream`

## STEP 4: Exact Streaming Aggregation

**Goal:** One pass produces exact counters for all four required views without retaining raw records.

**Time:** ~3 hours

**Context:** Architecture Sections 3, 6, ADR-002, and `Metric semantics`; PRD FR-003 through FR-007.

**Tasks:**

1. Create `src/nginx_insight/aggregate.py` with IP counts, 4xx/5xx URL counts, 24 buckets, valid/invalid totals, and the exact non-missing UA set.
2. Enforce `--max-unique` independently before inserting a new IP, error URL, or User-Agent; raise the typed exhaustion error without finalizing partial output.
3. Implement deterministic top-10 selection by descending count and ascending key.
4. Implement six-decimal percentages and the documented hourly display adjustment.
5. Create `tests/test_aggregate.py`, including empty input, ties, status boundaries, missing UAs, cap-at-limit, and cap-plus-one.

**Verification:**

- `.venv/bin/pytest -q tests/test_aggregate.py`
- `.venv/bin/pytest -q tests/test_aggregate.py -k 'cardinality or hourly or tie'`

**Commit:** `step-4: implement bounded exact aggregations`

## STEP 5: JSON and CSV Renderers

**Goal:** Automation receives deterministic, decoration-free schema-v1 JSON and CSV generated from the same report.

**Time:** ~2 hours

**Context:** Architecture `Outputs` and ADR-003; PRD FR-010 and FR-011.

**Tasks:**

1. Create `src/nginx_insight/renderers/__init__.py` and `src/nginx_insight/renderers/json.py`.
2. Create `src/nginx_insight/renderers/csv.py` with columns `schema_version,metric,rank,key,count,total,percentage`.
3. Create `tests/test_json_renderer.py` and `tests/test_csv_renderer.py` against the golden oracle, including quotes, commas, newlines, Unicode, and spreadsheet-formula-shaped keys.
4. Assert byte-stable ordering and absence of ANSI escapes.

**Verification:**

- `.venv/bin/pytest -q tests/test_json_renderer.py tests/test_csv_renderer.py`
- `.venv/bin/python -m json.tool tests/fixtures/expected_report.json >/dev/null`

**Commit:** `step-5: add deterministic pipeline renderers`

## STEP 6: Rich Terminal Renderer

**Goal:** Default output is a concise colored terminal report with four views and summary counts.

**Time:** ~1.5 hours

**Context:** Architecture `Outputs`; PRD FR-009.

**Tasks:**

1. Create `src/nginx_insight/renderers/rich.py` with accessible headings, aligned counts, percentages, and explicit empty-state text.
2. Respect TTY detection, `NO_COLOR` convention where compatible with Rich, and the explicit `--no-color` override.
3. Create `tests/test_rich_renderer.py` using fixed console width and forced color/no-color configurations.

**Verification:**

- `.venv/bin/pytest -q tests/test_rich_renderer.py`
- `.venv/bin/python -m nginx_insight tests/fixtures/combined.log --no-color | .venv/bin/python -c 'import sys; assert "\033[" not in sys.stdin.read()'`

**Commit:** `step-6: render human-readable terminal report`

## STEP 7: End-to-End Error and Exit Behavior

**Goal:** The command wires reader, parser, aggregate, and renderers with clean stdout/stderr separation and exact automation semantics.

**Time:** ~2 hours

**Context:** Architecture `Exit codes` and Section 8; PRD FR-008 and FR-012.

**Tasks:**

1. Update `src/nginx_insight/cli.py` to select the renderer and process inputs in order.
2. Map outcomes exactly: success `0`, operational I/O `1`, usage/configuration `2`, partial-data report `3`, unique-cardinality exhaustion `4`.
3. Ensure code 4 means unique-cardinality exhaustion and emits no report; never omit or remap it.
4. Handle normal pipe closure and Ctrl-C without tracebacks.
5. Create `tests/test_end_to_end.py` parametrized across terminal/JSON/CSV and all five exit codes.

**Verification:**

- `.venv/bin/pytest -q tests/test_end_to_end.py`
- `.venv/bin/pytest -q tests/test_end_to_end.py -k 'exit_code'`

**Commit:** `step-7: wire CLI and complete exit contract`

## STEP 8: Performance and Memory Gate

**Goal:** The installed CLI proves the 1 GB/30 s target and predictable cap behavior on a reproducible benchmark.

**Time:** ~2.5 hours

**Context:** Architecture Section 9; PRD NFR-001 through NFR-003.

**Tasks:**

1. Create `benchmarks/generate_log.py` with a fixed seed, documented distribution, byte-size target, and expected aggregate summary.
2. Create `benchmarks/run_benchmark.py` to capture hardware, OS, Python, input hash/size, three timed runs, median, peak RSS, result correctness, and command line.
3. Create `tests/test_benchmark_tools.py` for deterministic small-fixture generation and oracle verification.
4. Profile only after a failing baseline; optimize parser/allocation hot spots without changing schemas.
5. Run a high-cardinality case that deterministically exits 4 before uncontrolled memory growth.

**Verification:**

- `.venv/bin/pytest -q tests/test_benchmark_tools.py`
- `.venv/bin/python benchmarks/generate_log.py --size-gib 1 --output .bench/nginx-1g.log`
- `.venv/bin/python benchmarks/run_benchmark.py --input .bench/nginx-1g.log --max-seconds 30`

**Commit:** `step-8: prove throughput and cardinality guard`

## STEP 9: Quality, Security, and Compatibility Gate

**Goal:** The full candidate is statically clean, thoroughly tested, and robust to hostile log values.

**Time:** ~2 hours

**Context:** Architecture Section 8; Strategic Plan Definition of Done.

**Tasks:**

1. Complete `tests/test_security_inputs.py` for terminal controls, serialized formula-shaped cells, pathological line length, and no raw-line diagnostic leakage.
2. Add configuration for Ruff, mypy, and coverage in `pyproject.toml`.
3. Run the suite on Python 3.11 in a clean environment and review every warning.
4. Record evidence under the repository’s verification workflow without weakening tests or thresholds.

**Verification:**

- `.venv/bin/ruff check src tests benchmarks`
- `.venv/bin/mypy src/nginx_insight`
- `.venv/bin/pytest --cov=nginx_insight --cov-report=term-missing --cov-fail-under=90`
- `.venv/bin/pip check`

**Commit:** `step-9: pass quality and security gates`

## STEP 10: Packaging and Release Documentation

**Goal:** A clean Python 3.11 environment can build, install, invoke, and understand the release artifact.

**Time:** ~1.5 hours

**Context:** Architecture `Deployment`; PRD NFR-006; [README.md](README.md).

**Tasks:**

1. Finalize `README.md` with installation, examples, schema links, supported grammar, performance baseline, limitations, and exit codes `0/1/2/3/4`.
2. Add `LICENSE` with the selected OSI-approved license and finalize metadata in `pyproject.toml`.
3. Build wheel and source distribution into `dist/`; inspect metadata and contents.
4. Install the wheel into a new temporary virtual environment and run the golden file/stdin checks in all formats.
5. Re-run the repository’s exact-candidate verification/adjudication route before tagging.

**Verification:**

- `.venv/bin/python -m build`
- `.venv/bin/python -m twine check dist/*`
- `python3.11 -m venv .release-venv && .release-venv/bin/pip install dist/*.whl && .release-venv/bin/nginx-insight --version`
- `.release-venv/bin/nginx-insight --json tests/fixtures/combined.log | .release-venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-10: prepare verified release artifact`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Contracts, fixtures, and streaming parser | ~5 hours |
| Saturday PM | 4–5 | Exact metrics and pipeline outputs | ~5 hours |
| Sunday AM | 6–8 | Human UX, integration, and performance | ~6 hours |
| Sunday PM | 9–10 | Quality gate and release artifact | ~3.5 hours |

## Final Acceptance

Completion requires all P0 criteria in [PRD.md](PRD.md), recorded benchmark evidence, clean install from the built wheel, and a current adjudication receipt under `.itd/VERIFICATION_CONTRACT.json`. A standalone “tests passed” statement is insufficient.

