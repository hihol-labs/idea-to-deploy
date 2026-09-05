# Implementation Plan: nginx-log-report

This is a planning artifact; it does not authorize product code in the blueprint session. Implementation is nine dependency-ordered steps, sized for one weekend. Every step must preserve the complete exit-code contract: `0` success, `1` unexpected internal error, `2` CLI usage/input I/O error, `3` unusable/strict-invalid data, and `4` unique-cardinality exhaustion. Code 4 must never be caught and remapped to code 1.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml` and `src/` package boundary | Enables clean imports, console entry point, and isolated installation tests | 0.5 h |
| 2 | Domain dataclasses and typed errors | Stabilizes the single report model and `0/1/2/3/4` mapping before feature work | 0.75 h |
| 3 | Representative fixtures and benchmark generator design | Makes correctness and the 1 GB target measurable from the start | 0.75 h |

No database schema, auth system, API, Docker setup, or CI/CD deployment runway is needed because this is a local stateless CLI.

## STEP 1: Package and CLI Skeleton

**Goal:** A clean Python 3.11 environment can install the package and invoke help/version.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections 3, 6, and 8.

**Tasks:**

1. Create `pyproject.toml` with Python 3.11 requirement, Click/Rich runtime dependencies, development extras, `src` discovery, and the `nginx-log-report` console entry point.
2. Create `src/nginx_log_report/__init__.py` with package version and `src/nginx_log_report/cli.py` with the Click option surface only.
3. Create `tests/test_cli.py` covering help, version, mutually exclusive formats, and invalid cardinality values.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-log-report --help`
- `.venv/bin/pytest -q tests/test_cli.py`

**Commit:** `step-1: scaffold installable CLI contract`

## STEP 2: Domain Models and Failure Mapping

**Goal:** Data and failure semantics exist independently of parsing and presentation.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 6; `PRD.md` FR-8.

**Tasks:**

1. Create `src/nginx_log_report/models.py` with `AccessRecord`, `CountEntry`, `HourEntry`, and immutable `Report` dataclasses.
2. Create `src/nginx_log_report/errors.py` with typed input, data, cardinality, and internal failure boundaries.
3. Extend `tests/test_cli.py` to assert the full `0/1/2/3/4` mapping, including code 4 for unique-cardinality exhaustion.

**Verification:**

- `.venv/bin/pytest -q tests/test_cli.py`
- `.venv/bin/python -m mypy src/nginx_log_report`

**Commit:** `step-2: define report and exit contracts`

## STEP 3: Combined-Log Parser

**Goal:** One conventional combined-log line becomes a typed record or classified parse failure.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 5; `PRD.md` FR-2.

**Tasks:**

1. Create `src/nginx_log_report/parser.py` with a compiled grammar and explicit request/timestamp/status conversion.
2. Create `tests/fixtures/combined.log` with small, hand-auditable valid and malformed records without real personal data.
3. Create `tests/test_parser.py` covering IPv4, IPv6, escapes, offsets, missing User-Agent normalization, malformed requests, timestamps, and statuses.

**Verification:**

- `.venv/bin/pytest -q tests/test_parser.py`
- `.venv/bin/ruff check src/nginx_log_report/parser.py tests/test_parser.py`

**Commit:** `step-3: parse nginx combined logs`

## STEP 4: Streaming Inputs

**Goal:** stdin, plain files, gzip files, and multiple paths yield lines without whole-file buffering.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface and section 7; `PRD.md` FR-1.

**Tasks:**

1. Create `src/nginx_log_report/input.py` with context-managed stdin/plain/gzip iterators and UTF-8 replacement decoding.
2. Create `tests/test_input.py` covering `-`, multiple-file order, unreadable input, corrupt gzip, and an iterator that rejects unbounded reads.
3. Wire input errors to exit 2 without writing partial stdout.

**Verification:**

- `.venv/bin/pytest -q tests/test_input.py tests/test_cli.py`
- `.venv/bin/python -c "from nginx_log_report.input import iter_lines; print(sum(1 for _ in iter_lines(('tests/fixtures/combined.log',))))"`

**Commit:** `step-4: stream stdin plain and gzip inputs`

## STEP 5: Exact Aggregation and Limits

**Goal:** A single pass computes all metrics with deterministic top tens and bounded cardinality.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 7; `PRD.md` FR-3 through FR-6.

**Tasks:**

1. Create `src/nginx_log_report/aggregate.py` with counters, the 24-slot hour array, User-Agent set, total reconciliation, and report finalization.
2. Apply `--max-cardinality` before insertion into each distinct-key collection and raise the typed code-4 failure rather than returning partial or approximate output.
3. Create `tests/test_aggregate.py` for error status selection, deterministic ties, all 24 buckets, `100 × hourly_request_count / total_valid_requests`, User-Agent share, and limit boundaries.

**Verification:**

- `.venv/bin/pytest -q tests/test_aggregate.py`
- `.venv/bin/pytest -q tests/test_aggregate.py -k cardinality`

**Commit:** `step-5: aggregate exact bounded metrics`

## STEP 6: Terminal Renderer

**Goal:** The default command displays a clear Rich summary and four metric sections.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface; `PRD.md` FR-7.

**Tasks:**

1. Create `src/nginx_log_report/renderers.py` with a terminal renderer that consumes only `Report`.
2. Implement TTY color detection plus `--color/--no-color`, escaping untrusted displayed values.
3. Create `tests/test_render_terminal.py` with fixed-width semantic assertions and ANSI/no-ANSI cases.

**Verification:**

- `.venv/bin/pytest -q tests/test_render_terminal.py`
- `.venv/bin/nginx-log-report --no-color tests/fixtures/combined.log`

**Commit:** `step-6: render rich terminal report`

## STEP 7: JSON and CSV Renderers

**Goal:** Pipelines receive deterministic, ANSI-free JSON or CSV with the documented schema.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface outputs; `PRD.md` FR-7.

**Tasks:**

1. Add JSON and normalized CSV renderers to `src/nginx_log_report/renderers.py` using standard serializers.
2. Create `tests/golden/report.json` and `tests/golden/report.csv` from a hand-verified fixture.
3. Create `tests/test_render_machine.py` to validate schema, RFC 4180 parsing, ordering, percentage scale, and absence of ANSI escapes.

**Verification:**

- `.venv/bin/pytest -q tests/test_render_machine.py`
- `.venv/bin/nginx-log-report --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-7: add stable JSON and CSV output`

## STEP 8: End-to-End Correctness and Hardening

**Goal:** All paths satisfy the public contract and protect stdout/privacy on failures.

**Time:** ~2 hours

**Context:** All P0 requirements in `PRD.md`; `PROJECT_ARCHITECTURE.md` sections 6, 7, and 9.

**Tasks:**

1. Create `tests/test_e2e.py` for stdin/files/gzip, invalid mixtures, strict mode, broken pipe, redacted diagnostics, and no partial output.
2. Add property-based or generated-case checks for count reconciliation, deterministic ordering, and hourly percentages.
3. Configure Ruff, mypy, pytest coverage, and dependency/license audit commands in `pyproject.toml`.

**Verification:**

- `.venv/bin/pytest -q --cov=nginx_log_report --cov-branch --cov-fail-under=90`
- `.venv/bin/ruff check . && .venv/bin/mypy src/nginx_log_report`
- `.venv/bin/pip check`

**Commit:** `step-8: harden complete CLI behavior`

## STEP 9: Performance, Packaging, and Release Evidence

**Goal:** The exact candidate proves the 1 GB target and installs from built artifacts.

**Time:** ~2 hours plus benchmark runtime

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` FR-9.

**Tasks:**

1. Create `tools/generate_benchmark_log.py` to deterministically stream-generate a representative synthetic 1 GB corpus outside version control.
2. Create `tests/test_performance_smoke.py` for a CI-sized regression and document the reference benchmark command/hardware in `docs/BENCHMARK.md`.
3. Build wheel/sdist, install the wheel in a clean temporary virtual environment, run all output modes, and record elapsed time plus peak RSS.
4. Freeze the exact candidate and use the repository’s verification/adjudication workflow before accepting release readiness.

**Verification:**

- `.venv/bin/python tools/generate_benchmark_log.py --bytes 1073741824 --output /tmp/nginx-log-report-1g.log`
- `/usr/bin/time -v .venv/bin/nginx-log-report --json /tmp/nginx-log-report-1g.log >/tmp/nginx-log-report.json`
- `.venv/bin/python -m build && .venv/bin/twine check dist/*`
- `.venv/bin/pytest -q`

**Commit:** `step-9: verify performance and release artifacts`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Installable contract and correct parser | Saturday morning |
| Weekend block 2 | 4–5 | Streaming inputs and exact aggregation | Saturday afternoon |
| Weekend block 3 | 6–7 | Human and machine output | Sunday morning |
| Weekend block 4 | 8–9 | Hardening, benchmark, and release evidence | Sunday afternoon |

## Final Acceptance

Completion requires the Definition of Done in `STRATEGIC_PLAN.md`, every P0 acceptance criterion in `PRD.md`, and a current verification receipt for the exact candidate. A narrated result, a standalone `PASSED`, or an estimated benchmark is insufficient.

