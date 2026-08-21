# Implementation Plan: Nginx Stream Insights

This is a documentation-only plan; no product code is part of the blueprint
session. Steps are dependency-ordered, with RICE value used inside those
constraints. Total estimated effort is approximately 14–17 focused hours.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and quality configuration | Every feature and check needs an installable import/CLI boundary | 1.5 h |
| 2 | Shared dataclasses and typed failures | Parser, aggregator, renderers, and CLI must share one contract | 1 h |
| 3 | Representative log fixtures | Exact parser/output behavior needs executable examples before feature work | 1 h |
| 4 | Benchmark protocol and generator design | The 1 GB target must be measured consistently, not asserted late | 0.5 h |

No schema, migration, authentication, Docker, HTTP, cloud, or Kubernetes runway
exists because the approved architecture has none.

## Exit-Code Contract Used by Every Step

| Code | Meaning |
|---:|---|
| `0` | Successful report/help/version |
| `1` | Input/output operating error |
| `2` | Usage or invalid option combination |
| `3` | No valid records in finite input |
| `4` | Unique-cardinality exhaustion |

Code 4 is reserved for the exact User-Agent cardinality guard and must never be
omitted, remapped, or converted to a successful approximate report.

## Step 1: Establish the installable package and quality gates

**Goal:** A Python 3.11 virtual environment can install the project and invoke
an empty Click command with version/help behavior.

**Time:** 1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Packaging and Deployment, CLI Interface.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, a `src/`
   package layout, the `nginx-insights` entry point, and test/lint/type extras.
2. Create `src/nginx_stream_insights/__init__.py` and
   `src/nginx_stream_insights/cli.py` with version/help scaffolding only.
3. Create `tests/test_cli.py` for help, version, and invalid-option exit 2.
4. Configure the chosen formatter, linter, type checker, pytest, and coverage
   in `pyproject.toml` without adding runtime services.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-insights --help`
- `.venv/bin/pytest tests/test_cli.py -q`

**Commit:** `step-1: establish python package and CLI contract`

## Step 2: Define domain models, errors, and fixtures

**Goal:** Every later component shares typed immutable-enough records, report
shapes, and error categories.

**Time:** 1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Component Design, Data and Streaming Model.

**Tasks:**

1. Create `src/nginx_stream_insights/models.py` with dataclasses for
   `AccessRecord`, ranked rows, hourly rows, and `Report`.
2. Create `src/nginx_stream_insights/errors.py` with errors that the CLI maps
   to operating code 1, data code 3, and cardinality code 4.
3. Create `tests/fixtures/valid_combined.log`, `mixed_combined.log`, and
   `malformed_only.log` covering IPv4, IPv6, offset hours, 4xx/5xx, quoted
   fields, empty User-Agent, and malformed records.
4. Create `tests/test_models.py` to lock construction and invariants.

**Verification:**

- `.venv/bin/pytest tests/test_models.py -q`
- `.venv/bin/python -m ruff check src tests`
- `.venv/bin/python -m mypy src`

**Commit:** `step-2: define report models and fixture corpus`

## Step 3: Implement the streaming combined-log parser and input reader

**Goal:** A file or stdin yields validated `AccessRecord` values one at a time,
with malformed lines counted safely.

**Time:** 2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — Data and Streaming Model; `PRD.md` — US-1.

**Tasks:**

1. Create `src/nginx_stream_insights/parser.py` with one compiled
   combined-format grammar, timestamp/status validation, and request-token
   extraction.
2. Create `src/nginx_stream_insights/input.py` with buffered file/stdin line
   iteration and line-number tracking.
3. Create `tests/test_parser.py` for every valid and invalid fixture dimension.
4. Create `tests/test_input.py` for finite files, stdin, UTF-8 decode failures,
   unreadable paths, and proof that iteration is lazy.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py tests/test_input.py -q`
- `.venv/bin/python -m ruff check src tests`
- `.venv/bin/python -m mypy src`

**Commit:** `step-3: stream and parse nginx combined logs`

## Step 4: Implement exact aggregation and cardinality protection

**Goal:** One pass produces all four exact metric families with deterministic
rankings and an honest bounded failure for User-Agent cardinality.

**Time:** 2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — ADR-002, Data and Streaming Model;
`PRD.md` — US-2 through US-5.

**Tasks:**

1. Create `src/nginx_stream_insights/aggregate.py` with IP/error-URL counters,
   24 hourly counters, valid/malformed totals, and a guarded exact UA set.
2. Compute hourly percentages only with
   `100 × hourly_request_count / total_valid_requests`.
3. Implement stable descending-count/ascending-key top-10 finalization.
4. Raise the typed cardinality error before inserting value limit+1 and map it
   later to code 4; never return an approximate result.
5. Create `tests/test_aggregate.py` for status boundaries, ties, percentage
   sums, empty UA values, zero-valid data, and success/failure around the exact
   UA limit.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest tests/test_aggregate.py --cov=nginx_stream_insights.aggregate --cov-fail-under=95`

**Commit:** `step-4: aggregate exact streaming metrics`

## Step 5: Build terminal, JSON, and CSV renderers

**Goal:** The same `Report` produces readable terminal output and stable
pipeline schemas without metric recomputation.

**Time:** 2 hours

**Context:** `PROJECT_ARCHITECTURE.md` — ADR-003, CLI Interface; `PRD.md` — US-6.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/__init__.py` and
   `terminal.py` for four Rich sections and TTY-aware color.
2. Create `src/nginx_stream_insights/renderers/json_output.py` with schema
   version 1 and all 24 hour objects.
3. Create `src/nginx_stream_insights/renderers/csv_output.py` with the exact
   five-column RFC 4180 schema.
4. Create `tests/test_renderers.py` to compare semantic values across modes,
   assert stable ties/rounding, and forbid ANSI in machine output.

**Verification:**

- `.venv/bin/pytest tests/test_renderers.py -q`
- `.venv/bin/python -m ruff check src tests`
- `.venv/bin/python -m mypy src`

**Commit:** `step-5: render terminal JSON and CSV reports`

## Step 6: Integrate the complete finite-stream CLI contract

**Goal:** End users can analyze files/stdin with all options, stdout/stderr
separation, and the complete `0/1/2/3/4` exit behavior.

**Time:** 2 hours

**Context:** `PROJECT_ARCHITECTURE.md` — CLI Interface; `PRD.md` — FR-01 through FR-10.

**Tasks:**

1. Complete `src/nginx_stream_insights/cli.py` with `INPUT`, `--json`, `--csv`,
   `--max-unique-user-agents`, and `--color/--no-color`.
2. Enforce positive limits and mutually exclusive formats as usage errors (2).
3. Map operating errors to 1, zero-valid finite input to 3, and unique
   cardinality exhaustion to 4; leave success at 0.
4. Ensure error paths never claim a complete JSON/CSV report and diagnostics
   never echo full raw records.
5. Extend `tests/test_cli.py` with file/stdin golden flows and explicit tests
   for codes 0, 1, 2, 3, and 4.

**Verification:**

- `.venv/bin/pytest tests/test_cli.py -q`
- `.venv/bin/nginx-insights --json tests/fixtures/valid_combined.log | .venv/bin/python -m json.tool >/dev/null`
- `.venv/bin/nginx-insights --csv tests/fixtures/valid_combined.log | awk -F, 'NR==1 {exit !($1=="metric" && NF==5)}'`

**Commit:** `step-6: integrate finite-stream CLI and exit codes`

## Step 7: Add follow mode as the P1 capability

**Goal:** A named regular file can be followed without busy spinning or
weakening finite-input behavior.

**Time:** 1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` — CLI Interface; `PRD.md` — US-7.

**Tasks:**

1. Extend `src/nginx_stream_insights/input.py` with complete-line follow logic
   and a bounded polling interval.
2. Extend `src/nginx_stream_insights/cli.py` with `--follow/-f`, reject stdin
   with code 2, and document termination semantics in help.
3. Add `tests/test_follow.py` with temporary-file append, partial-line,
   no-busy-spin, and controlled termination cases.

**Verification:**

- `.venv/bin/pytest tests/test_follow.py tests/test_cli.py -q`
- `.venv/bin/python -m ruff check src tests`
- `.venv/bin/python -m mypy src`

**Commit:** `step-7: follow growing nginx log files`

## Step 8: Prove correctness, privacy, and performance

**Goal:** The release candidate has recorded functional, quality, security,
and 1 GB performance evidence.

**Time:** 2 hours plus benchmark runtime

**Context:** `PROJECT_ARCHITECTURE.md` — Performance Strategy, Security and
Privacy, Test Architecture; `STRATEGIC_PLAN.md` — Definition of Done.

**Tasks:**

1. Create `tests/test_contract.py` to assert JSON/CSV schema, 24 hourly buckets,
   denominator semantics, tie ordering, stdout/stderr separation, and all exit
   codes `0/1/2/3/4`.
2. Create `tools/generate_benchmark_log.py` for a deterministic representative
   fixture; keep generated 1 GB data out of version control.
3. Create `docs/BENCHMARK.md` with hardware, storage, OS, Python, generator
   parameters, command, wall time, CPU time, and peak RSS fields.
4. Inspect diagnostics for raw-line/token leakage and scan dependencies with
   the project's selected audit command.

**Verification:**

- `.venv/bin/pytest -q --cov=nginx_stream_insights --cov-report=term-missing --cov-fail-under=90`
- `.venv/bin/python -m ruff check src tests tools && .venv/bin/python -m mypy src`
- `/usr/bin/time -v .venv/bin/nginx-insights --json .bench/combined-1gb.log >/dev/null`

**Commit:** `step-8: verify contracts privacy and performance`

## Step 9: Package and document the release candidate

**Goal:** A clean Python 3.11 environment can build, install, and use the wheel
with documentation matching every implemented contract.

**Time:** 1.5 hours

**Context:** all blueprint documents, especially `PRD.md` — Release Acceptance.

**Tasks:**

1. Update `README.md` with actual package name, examples, schemas, supported
   nginx format, limitations, and exit codes.
2. Update `CHANGELOG.md` and create `LICENSE` using the chosen open-source
   license before publication.
3. Build sdist/wheel into `dist/`; do not add Docker, server, database, cloud,
   or Kubernetes artifacts.
4. Install the wheel in a fresh temporary environment and run terminal, JSON,
   CSV, empty-data, I/O-error, usage-error, and cardinality-exhaustion checks.

**Verification:**

- `.venv/bin/python -m build`
- `.venv/bin/python -m twine check dist/*`
- `python3.11 -m venv .release-venv && .release-venv/bin/pip install dist/*.whl && .release-venv/bin/nginx-insights --version`
- `.release-venv/bin/python -m pytest -q`

**Commit:** `step-9: package documented release candidate`

## Sprint Boundaries

For a one-weekend delivery, “sprint” means a focused half-day timebox.

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable foundation and reliable streaming parser | Half day |
| Saturday PM | 4–5 | Exact metrics and all renderers | Half day |
| Sunday AM | 6–7 | Complete CLI and follow capability | Half day |
| Sunday PM | 8–9 | Evidence, packaging, and handoff | Half day |

## Dependency and Scope Rules

WIP remains one implementation step at a time. A step advances only after its
verification commands pass and evidence is recorded. P2 gzip/custom formats
begin only after P0/P1 release acceptance. Any proposal for persistence,
network service, authentication, cloud, or Kubernetes requires a new product
decision and updates to the PRD and architecture before code changes.

