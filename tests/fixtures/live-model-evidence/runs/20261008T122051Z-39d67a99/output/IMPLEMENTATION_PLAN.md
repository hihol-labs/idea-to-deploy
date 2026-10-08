# Implementation Plan: `nginx-top`

## 1. Delivery Rules

This plan is a one-weekend, WIP=1 sequence. Complete and verify one step before starting the next. `PROJECT_ARCHITECTURE.md` is the architecture source of truth; `PRD.md` supplies acceptance criteria. Product code is not part of the blueprint session.

Every implementation step must preserve the complete exit-code contract: `0` success, `1` operational/internal failure, `2` usage error, `3` non-empty input with zero valid records, and `4` unique-cardinality exhaustion.

## 2. Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml` package and console entry point | Every test and command needs an installable import/CLI boundary | 1 hour |
| 2 | Typed records and exception taxonomy | Parser, aggregator, renderer, and exit mapping need stable contracts | 1 hour |
| 3 | Deterministic fixture corpus and golden conventions | Behavior needs executable evidence before feature expansion | 1 hour |
| 4 | Performance harness design | The 1 GB / 30 second constraint must be measured consistently | 1 hour |

No database schema, auth system, API scaffolding, Docker setup, or CI deployment infrastructure belongs in the runway because the accepted architecture is local and stateless.

## STEP 1: Package, CLI shell, and contract tests

**Goal:** A pip-installable Python 3.11 package exposes `nginx-top` with help/version and stable option validation.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4, 6, and 9; `PRD.md` FR-01, FR-09.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, and `nginx-top = nginx_top.cli:main`.
2. Create `src/nginx_top/__init__.py` with package version exposure.
3. Create `src/nginx_top/cli.py` with the `INPUT`, `--json`, `--csv`, `--color/--no-color`, and `--max-unique` declarations.
4. Create `tests/integration/test_cli_contract.py` for help, version, flag conflicts, missing input, and positive limit validation.

**Verification:**

- `python3.11 -m pip install -e .`
- `python3.11 -m pytest tests/integration/test_cli_contract.py -q`
- `nginx-top --help`

**Commit:** `step-1: establish package and CLI contract`

## STEP 2: Domain models, errors, and fixtures

**Goal:** Typed immutable records and failure categories encode the architecture without parsing or rendering concerns.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4–6.

**Tasks:**

1. Create `src/nginx_top/models.py` with frozen `LogRecord`, `RankedItem`, and `ReportSnapshot` dataclasses.
2. Create `src/nginx_top/errors.py` with operational, data, and cardinality exhaustion exceptions.
3. Create `tests/fixtures/combined_valid.log`, `combined_mixed.log`, `combined_invalid.log`, and `empty.log` with documented provenance as test fixtures.
4. Create `tests/unit/test_models.py` for invariants and immutable value behavior.

**Verification:**

- `python3.11 -m pytest tests/unit/test_models.py -q`
- `python3.11 -m compileall -q src/nginx_top`

**Commit:** `step-2: define domain and failure models`

## STEP 3: Streaming input and combined-log parser

**Goal:** Files and stdin yield valid typed records or exact invalid-line diagnostics without whole-file buffering.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 7; `PRD.md` streaming and parsing acceptance criteria.

**Tasks:**

1. Create `src/nginx_top/input.py` for UTF-8 line iteration from a path or stdin and normalized I/O failures.
2. Create `src/nginx_top/parser.py` with one precompiled combined-log parser and timezone-aware timestamps.
3. Create `tests/unit/test_parser.py` for IPv4, IPv6, missing fields, escapes, status boundaries, timestamps, and malformed lines.
4. Create `tests/integration/test_input_sources.py` to prove file/stdin parity and streaming iteration.

**Verification:**

- `python3.11 -m pytest tests/unit/test_parser.py tests/integration/test_input_sources.py -q`

**Commit:** `step-3: stream and parse combined logs`

## STEP 4: Streaming aggregation and cardinality guard

**Goal:** One pass computes all four summaries with deterministic ranking and bounded distinct-key growth.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 7; `PRD.md` ranking, hourly, and User-Agent criteria.

**Tasks:**

1. Create `src/nginx_top/aggregate.py` with IP/error-URL counters, 24 hourly buckets, exact User-Agent set, and pre-insert limits.
2. Create `src/nginx_top/report.py` with top-10 tie-breaking and percentage calculations.
3. Create `tests/unit/test_aggregate.py` covering status 400/599 inclusion, 399/600 exclusion, ties, missing User-Agent, zero records, and formula precision.
4. Add adversarial low-limit cases proving each guarded collection maps to the cardinality exception.

**Verification:**

- `python3.11 -m pytest tests/unit/test_aggregate.py -q`

**Commit:** `step-4: aggregate metrics with cardinality bounds`

## STEP 5: JSON renderer

**Goal:** `--json` emits the complete stable schema without terminal escapes.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` JSON schema and CLI interface; `PRD.md` output criteria.

**Tasks:**

1. Create `src/nginx_top/renderers/__init__.py` with the renderer protocol.
2. Create `src/nginx_top/renderers/json.py` using the standard JSON encoder and schema version.
3. Create `tests/unit/test_json_renderer.py` for keys, types, precision, ordering, diagnostics, and Unicode.
4. Add `tests/golden/report.json` as the reviewed machine-contract fixture.

**Verification:**

- `python3.11 -m pytest tests/unit/test_json_renderer.py -q`
- `nginx-top --json tests/fixtures/combined_valid.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: add stable JSON output`

## STEP 6: CSV renderer

**Goal:** `--csv` emits every report through the normalized six-column schema.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CSV schema and CLI interface; `PRD.md` output criteria.

**Tasks:**

1. Create `src/nginx_top/renderers/csv.py` with standard-library CSV quoting and ordered report rows.
2. Create `tests/unit/test_csv_renderer.py` for header, discriminators, quoting, empty cells, row order, and Unicode.
3. Add `tests/golden/report.csv` as the reviewed machine-contract fixture.
4. Add a parser round-trip test proving every emitted row has six fields.

**Verification:**

- `python3.11 -m pytest tests/unit/test_csv_renderer.py -q`

**Commit:** `step-6: add normalized CSV output`

## STEP 7: Rich terminal renderer

**Goal:** Default output is readable, safely escaped, and colored only under the documented policy.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI interface and security section; `PRD.md` terminal criteria.

**Tasks:**

1. Create `src/nginx_top/renderers/terminal.py` with summary, top-IP, top-error-URL, hourly, and User-Agent sections.
2. Escape untrusted labels before Rich rendering and implement TTY/forced color behavior.
3. Create `tests/unit/test_terminal_renderer.py` for layout, control/markup injection, no-color, empty reports, and all-hour display.
4. Add `tests/golden/report.txt` for non-color output.

**Verification:**

- `python3.11 -m pytest tests/unit/test_terminal_renderer.py -q`

**Commit:** `step-7: add safe Rich terminal report`

## STEP 8: End-to-end orchestration and exit codes

**Goal:** The Click command connects the pipeline and implements every success/failure path exactly.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI interface; `PRD.md` output/error contract.

**Tasks:**

1. Update `src/nginx_top/cli.py` to select one renderer, stream input, aggregate, and write stdout/stderr separately.
2. Map success to `0`, operational/internal failures to `1`, usage failures to `2`, non-empty all-invalid input to `3`, and unique-cardinality exhaustion to `4`.
3. Treat expected downstream broken-pipe closure as success without a traceback.
4. Expand `tests/integration/test_cli_contract.py` to cover file/stdin parity, all output modes, mixed invalid data, empty data, all-invalid data, I/O failure, broken pipe, and all five exit codes.

**Verification:**

- `python3.11 -m pytest tests/integration/test_cli_contract.py -q`

**Commit:** `step-8: integrate pipeline and exit semantics`

## STEP 9: Quality, security, and performance gates

**Goal:** The exact candidate meets correctness, memory, security, and 1 GB throughput requirements.

**Time:** ~3 hours plus benchmark runtime

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` NFR-01–NFR-07.

**Tasks:**

1. Create `tests/performance/generate_fixture.py` for a deterministic 1 GB fixture and checksum manifest.
2. Create `tests/performance/test_one_gb.py` to record laptop specification, elapsed time, peak RSS, and result checksum.
3. Add control-character, large-line, malformed-quote, and cardinality-bomb fixtures to integration tests.
4. Configure formatter, linter, type checker, pytest, and coverage gates in `pyproject.toml`.

**Verification:**

- `python3.11 -m pytest -q --cov=nginx_top --cov-fail-under=90`
- `python3.11 -m ruff check src tests`
- `python3.11 -m mypy src/nginx_top`
- `python3.11 -m pytest tests/performance/test_one_gb.py -m performance -q`

**Commit:** `step-9: enforce quality and performance gates`

## STEP 10: Packaging and user documentation

**Goal:** Releasable artifacts install cleanly and document exact supported behavior.

**Time:** ~2 hours

**Context:** All blueprint documents, especially release criteria in `PRD.md`.

**Tasks:**

1. Create `README.md` with sub-30-second quick start, supported grammar, examples for text/JSON/CSV, formulas, limits, and `0/1/2/3/4` exits.
2. Create `LICENSE` using the chosen open-source license and `CHANGELOG.md` with the initial contract.
3. Create `tests/integration/test_installed_wheel.py` to install and exercise the wheel in an isolated Python 3.11 environment.
4. Build sdist/wheel and verify their contents exclude fixtures, logs, and local artifacts.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m pytest tests/integration/test_installed_wheel.py -q`
- `python3.11 -m twine check dist/*`

**Commit:** `step-10: prepare verified release artifacts`

## 3. Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable shell and trusted streaming parser | 4–6 hours |
| Saturday PM | 4–6 | Complete metrics and machine formats | 5–6 hours |
| Sunday AM | 7–8 | Human output and end-to-end semantics | 4–5 hours |
| Sunday PM | 9–10 | Evidence, hardening, packaging, documentation | 5–6 hours |

## 4. Dependency and Handoff Map

Steps 1–4 form the core pipeline. Steps 5–7 may proceed only after the snapshot contract is stable. Step 8 integrates all renderers. Step 9 freezes and tests the exact candidate; Step 10 packages that same accepted behavior. Handoff requires test logs, benchmark environment/results, machine-output goldens, and an explicit next action.

