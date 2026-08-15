# Implementation Plan: nginx-stream-report

## Planning Contract

This plan implements the specifications in `PRD.md` under the architecture in `PROJECT_ARCHITECTURE.md`. It contains no authorization to add a database, HTTP API, authentication, server, cloud resource, or Kubernetes. Keep one active step at a time and update specifications before changing user-visible behavior.

The stable exit-code contract applies throughout implementation and testing: `0` success, `1` input/I/O failure, `2` CLI usage error, `3` malformed log data in strict mode, and `4` unique-cardinality exhaustion. No step may omit, reuse, or remap code 4.

## Architectural Runway

Infrastructure and contracts that must exist before feature work:

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml`, `src/`, and `tests/` skeleton | Establishes import, packaging, and console entry-point boundaries | 1 hour |
| 2 | Typed records and error taxonomy | Prevents parser/renderer coupling and locks exit meanings | 1 hour |
| 3 | Golden fixtures and output schemas | Makes correctness machine-checkable before rendering grows | 1.5 hours |
| 4 | Benchmark protocol and deterministic fixture generator | Makes the 1 GB/30 s constraint reproducible | 1 hour |

Database schema, authentication, Docker, and CI/CD deployment infrastructure are intentionally absent because they contradict the local stateless CLI scope.

## Step 1: Package and Quality Skeleton

**Goal:** A clean Python 3.11 environment can install the project and invoke help/version.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Component Model, CLI Interface, Deployment.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click and Rich runtime dependencies, test/lint tooling, wheel configuration, and `nginx-stream-report` console script.
2. Create `src/nginx_stream_report/__init__.py`, `src/nginx_stream_report/__main__.py`, and `src/nginx_stream_report/cli.py`.
3. Create `tests/test_cli.py` for help, version, and mutually exclusive format options.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-report --help`
- `.venv/bin/pytest tests/test_cli.py -q`

**Commit:** `step-1: scaffold installable cli package`

## Step 2: Domain Models and Error Taxonomy

**Goal:** Typed report records and all five process outcomes have a single stable definition.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` — Data Contracts, Exit codes.

**Tasks:**

1. Create `src/nginx_stream_report/models.py` with `ParsedRequest`, `RankedCount`, `HourlyShare`, and `Report` dataclasses.
2. Create `src/nginx_stream_report/errors.py` with typed I/O, malformed-data, and cardinality-exhaustion errors plus constants for exit codes `0/1/2/3/4`.
3. Create `tests/test_models.py` and extend `tests/test_cli.py` to assert exact mappings, especially cardinality exhaustion to `4`.

**Verification:**

- `.venv/bin/pytest tests/test_models.py tests/test_cli.py -q`
- `.venv/bin/python -m mypy src`

**Commit:** `step-2: define report and failure contracts`

## Step 3: Combined-Log Parser

**Goal:** Valid nginx combined-format lines become compact records and malformed input is classified safely.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Input grammar, Security and Privacy.

**Tasks:**

1. Create `src/nginx_stream_report/parser.py` with one precompiled parser, status validation, local-hour extraction, and control-character-safe diagnostics.
2. Create `tests/fixtures/valid.log`, `tests/fixtures/mixed.log`, and `tests/fixtures/invalid-utf8.log` with documented synthetic test data.
3. Create `tests/test_parser.py` covering IPv4, IPv6, quoted fields, unknown values, error statuses, malformed lines, and invalid bytes.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py -q`
- `.venv/bin/ruff check src/nginx_stream_report/parser.py tests/test_parser.py`

**Commit:** `step-3: parse nginx combined logs`

## Step 4: One-Pass Aggregation and Cardinality Guard

**Goal:** All four exact metrics are produced without retaining input lines, and excessive distinct keys fail predictably.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` — State and memory bounds, Data Contracts.

**Tasks:**

1. Create `src/nginx_stream_report/aggregate.py` with IP counts, error-only URL counts, 24 hourly counts, and a unique User-Agent set.
2. Implement deterministic top-10 ordering and hourly percentages using `100 × hourly_request_count / total_valid_requests`.
3. Apply `--max-unique` independently to IPs, error URLs, and User-Agents; raise the typed exhaustion error before adding the excess value.
4. Create `tests/test_aggregate.py` covering ties, empty input, non-error exclusion, 24 rows, percentages summing to approximately 100 for nonempty input, and exhaustion in each category.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest tests/test_aggregate.py --cov=nginx_stream_report.aggregate --cov-branch --cov-fail-under=90`

**Commit:** `step-4: add bounded streaming aggregation`

## Step 5: Text Renderer

**Goal:** The default invocation emits a readable Rich report while redirected output remains clean.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Outputs, Error Handling.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/__init__.py` and `src/nginx_stream_report/renderers/text.py`.
2. Render top IPs, error URLs, 24-hour distribution, and unique User-Agent share with consistent percentage precision.
3. Honor terminal detection and `--no-color`; escape untrusted control sequences.
4. Create `tests/test_text_renderer.py` with normalized Rich snapshots for terminal, redirected, empty, and malicious-control-input cases.

**Verification:**

- `.venv/bin/pytest tests/test_text_renderer.py -q`
- `.venv/bin/nginx-stream-report --no-color tests/fixtures/valid.log`

**Commit:** `step-5: render safe terminal reports`

## Step 6: JSON and CSV Renderers

**Goal:** Pipelines receive deterministic, schema-conformant structured reports with no ANSI or prose contamination.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — JSON and CSV output contracts.

**Tasks:**

1. Create `src/nginx_stream_report/renderers/json.py` with the schema-versioned object defined by the architecture.
2. Create `src/nginx_stream_report/renderers/csv.py` with `section,key,count,percentage` long-form rows.
3. Create `tests/golden/report.json`, `tests/golden/report.csv`, and `tests/test_structured_renderers.py` for exact output and round-trip parsing.
4. Buffer each structured document until successful finalization so failures do not leak partial stdout.

**Verification:**

- `.venv/bin/pytest tests/test_structured_renderers.py -q`
- `.venv/bin/nginx-stream-report --json tests/fixtures/valid.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/nginx-stream-report --csv tests/fixtures/valid.log | .venv/bin/python -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: add stable json and csv reports`

## Step 7: End-to-End CLI and Failure Contract

**Goal:** File/stdin processing, malformed-line policy, diagnostics, and exact exit behavior work as one command.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — CLI Interface; `PRD.md` — P0 requirements.

**Tasks:**

1. Complete `src/nginx_stream_report/cli.py` to select input, stream records, finalize only on success, select the renderer, and handle broken pipes.
2. Create `tests/test_integration_cli.py` covering file and stdin parity, every output mode, skipped malformed records, strict malformed failure, unreadable input, usage errors, and forced exhaustion.
3. Assert the complete contract: success `0`, input/I/O `1`, usage `2`, strict malformed data `3`, unique-cardinality exhaustion `4`.
4. Assert JSON/CSV stdout is empty on all failure paths and diagnostics use stderr.

**Verification:**

- `.venv/bin/pytest tests/test_integration_cli.py -q`
- `sh tests/scripts/assert_exit_codes.sh`

**Commit:** `step-7: integrate streaming cli contracts`

## Step 8: Performance, Packaging, and Release Evidence

**Goal:** The installable artifact satisfies the complete correctness suite and the 1 GB/30 s acceptance gate.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Performance Strategy and Deployment; `STRATEGIC_PLAN.md` — Definition of Done.

**Tasks:**

1. Create `benchmarks/generate_fixture.py` to deterministically generate a representative 1 GB combined-format fixture outside version control.
2. Create `benchmarks/run.py` to measure wall time, throughput, and peak RSS while validating the report digest.
3. Create `tests/test_package.py` to inspect the wheel and smoke-test installation in a clean temporary environment.
4. Update `README.md` with measured reference hardware/results and release limitations; do not claim the target before running it.
5. Record executed checks and results in the project handoff state required by the Idea to Deploy harness.

**Verification:**

- `.venv/bin/pytest -q --cov=nginx_stream_report --cov-branch --cov-fail-under=90`
- `.venv/bin/ruff check . && .venv/bin/mypy src`
- `.venv/bin/python -m build && .venv/bin/pytest tests/test_package.py -q`
- `/usr/bin/time -v .venv/bin/python benchmarks/run.py --size-gib 1 --max-seconds 30`

**Commit:** `step-8: verify performance and release artifact`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Installable skeleton and reliable parsing | Saturday morning |
| Weekend block 2 | 4–5 | Exact bounded metrics and terminal experience | Saturday afternoon |
| Weekend block 3 | 6–7 | Pipeline formats and end-to-end contracts | Sunday morning |
| Weekend block 4 | 8 | Performance proof and release handoff | Sunday afternoon |

## Dependency and Scope Notes

Step order follows architectural dependencies rather than raw RICE scores. Gzip input and `--no-color` are P1: `--no-color` is included with the renderer because it is low-risk; gzip begins only after all P0 gates pass. Configurable log formats and approximate algorithms remain P2 and require PRD/architecture updates before implementation.

