# Implementation Plan: nginx-logtop

This is a documentation-only execution plan. Product code is intentionally not implemented by the blueprint workflow. Steps follow dependencies first and RICE order where dependencies permit. Total expected effort is one weekend (approximately 14–18 focused hours).

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package, lint, test, and console-entry skeleton | Every later step needs imports and repeatable commands | 1.5 h |
| 2 | Combined-format fixtures and schema fixtures | Fixes behavior before implementation | 1.0 h |
| 3 | Performance fixture protocol | Prevents late discovery that the architecture misses the main constraint | 0.5 h |

No database schema, auth system, API scaffold, Docker setup, or CI deployment runway is required because the accepted architecture is a local, stateless CLI.

## Step 1: Establish Packaging and Quality Gates

**Goal:** A Python 3.11 source-layout package builds and exposes a placeholder console entry without implementing product behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Component Boundaries and Deployment and Packaging.

**Files:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, the `nginx-logtop` entry point, and development test/static dependencies.
2. Create `src/nginx_logtop/__init__.py` and `src/nginx_logtop/__main__.py` for version and module execution.
3. Create empty test package `tests/__init__.py` and tool configuration in `pyproject.toml`.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/python -m build`
- `.venv/bin/nginx-logtop --help`

**Commit:** `step-1: establish package and quality gates`

## Step 2: Lock CLI, Error, and Data Contracts

**Goal:** Typed contracts and Click validation encode the documented interface and complete exit-code map before parsing logic.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections CLI Interface and Output Schemas; `PRD.md` FR-01 and FR-09.

**Files:**

1. Create `src/nginx_logtop/models.py` with slotted dataclasses for parsed records, ranked rows, hourly rows, unique-UA summary, and final report.
2. Create `src/nginx_logtop/errors.py` with domain failures mapped to `0/1/2/3/4`: `0` success, `1` unexpected internal error, `2` CLI usage error, `3` input/data error, and `4` unique-cardinality exhaustion.
3. Create `src/nginx_logtop/cli.py` with options, mutual-exclusion validation, stdin rules, renderer selection, and one top-level exit mapping.
4. Create `tests/test_cli_contract.py` covering help, version, conflicts, invalid ceilings, and stdin/path combinations.

**Verification:**

- `.venv/bin/pytest tests/test_cli_contract.py -q`
- `.venv/bin/nginx-logtop --json --csv </dev/null; test $? -eq 2`

**Commit:** `step-2: lock cli and exit contracts`

## Step 3: Implement Input Streaming and Combined-Format Parsing

**Goal:** Files and stdin yield validated records line by line with explicit lenient and strict malformed-line behavior.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections Data Flow and Log Format Contract; `PRD.md` US-6.

**Files:**

1. Create `src/nginx_logtop/inputs.py` for UTF-8 line iteration, source labels, ordered multi-file handling, and typed read/decode failures.
2. Create `src/nginx_logtop/parser.py` with one compiled combined-format parser and timestamp, status, and request validation.
3. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` with small, non-sensitive deterministic records.
4. Create `tests/test_inputs.py` and `tests/test_parser.py` for files, stdin, IPv4/IPv6, quotes, offsets, missing User-Agent, decoding failure, and malformed lines.

**Verification:**

- `.venv/bin/pytest tests/test_inputs.py tests/test_parser.py -q`
- `.venv/bin/ruff check src/nginx_logtop/inputs.py src/nginx_logtop/parser.py tests/test_inputs.py tests/test_parser.py`

**Commit:** `step-3: stream and parse combined logs`

## Step 4: Implement Streaming Aggregation

**Goal:** One pass computes all required metrics without retaining parsed requests.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` Metric Definitions and Performance Design; `PRD.md` US-1 through US-4.

**Files:**

1. Create `src/nginx_logtop/aggregate.py` with per-IP counters, error-only URL counters and 4xx/5xx splits, 24 hour counters, and exact User-Agent set.
2. Enforce `--max-unique-user-agents` before adding a new value; raise the domain failure that exits `4` and never finalize partial output.
3. Implement deterministic top-10 sorting and percentage finalization, including `100 × hourly_request_count / total_valid_requests`.
4. Create `tests/test_aggregate.py` for ties, fewer/more than ten keys, 4xx/5xx boundaries, 24 buckets, missing UAs, zero valid input, and ceiling exhaustion.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest tests/test_aggregate.py --cov=nginx_logtop.aggregate --cov-branch --cov-fail-under=90`

**Commit:** `step-4: implement streaming metrics`

## Step 5: Add Terminal Renderer

**Goal:** Default output is a readable Rich report with identical values and deterministic order.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Outputs and Security and Privacy; `PRD.md` US-7.

**Files:**

1. Create `src/nginx_logtop/render_terminal.py` with summary, top-IP, error-URL, 24-hour, and unique-UA tables.
2. Treat log-derived values as literal text rather than Rich markup and implement auto/forced color behavior.
3. Create `tests/test_render_terminal.py` with no-color golden output and markup-injection fixtures.

**Verification:**

- `.venv/bin/pytest tests/test_render_terminal.py -q`
- `NO_COLOR=1 .venv/bin/nginx-logtop --no-color tests/fixtures/combined.log`

**Commit:** `step-5: render terminal report`

## Step 6: Add JSON and CSV Renderers

**Goal:** Pipeline formats conform exactly to schema version 1 and contain no ANSI styling.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` Output Schemas; `PRD.md` US-5.

**Files:**

1. Create `src/nginx_logtop/render_json.py` using the standard JSON serializer and one trailing newline.
2. Create `src/nginx_logtop/render_csv.py` using `csv.DictWriter` and the documented long-form header.
3. Create `tests/fixtures/expected.json` and `tests/fixtures/expected.csv` as reviewed schema fixtures.
4. Create `tests/test_render_json.py` and `tests/test_render_csv.py` for schema, escaping, numeric values, and cross-format semantic equivalence.

**Verification:**

- `.venv/bin/pytest tests/test_render_json.py tests/test_render_csv.py -q`
- `.venv/bin/nginx-logtop --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-6: add pipeline renderers`

## Step 7: Complete End-to-End Failure and Success Coverage

**Goal:** The installed command behaves atomically across inputs, modes, and every exit code.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` CLI Interface and Error Handling; all P0 acceptance criteria in `PRD.md`.

**Files:**

1. Create `tests/test_e2e.py` covering file, multiple files, stdin, lenient/strict parsing, empty input, unreadable input, and all output modes.
2. Add controlled injection fixtures or monkeypatches for unexpected internal failure and exact unique-cardinality exhaustion.
3. Assert the complete contract in every mode: `0` success, `1` unexpected internal error, `2` CLI usage error, `3` input/data error, `4` unique-cardinality exhaustion.
4. Assert stdout is empty for exits `3` and `4`, and diagnostics stay on stderr.

**Verification:**

- `.venv/bin/pytest tests/test_e2e.py -q`
- `.venv/bin/pytest --cov=nginx_logtop --cov-branch --cov-report=term-missing --cov-fail-under=90`

**Commit:** `step-7: prove end-to-end contracts`

## Step 8: Benchmark and Optimize the Frozen Hot Path

**Goal:** The fixed 1 GB fixture processes in under 30 seconds on the named reference laptop without request retention.

**Time:** ~2 hours, plus fixture generation time

**Context:** `PROJECT_ARCHITECTURE.md` Performance Design; `PRD.md` NFR-01 and NFR-02.

**Files:**

1. Create `benchmarks/generate_fixture.py` to deterministically generate representative, non-sensitive combined-format data outside Git.
2. Create `benchmarks/run.py` to record input bytes, line count, wall time, peak RSS, CPU, Python version, and package version.
3. Create `benchmarks/README.md` with the exact reference-laptop specification and command.
4. Profile `parser.py` and `aggregate.py`; change only measured hot paths while keeping golden tests green.

**Verification:**

- `.venv/bin/python benchmarks/generate_fixture.py --bytes 1000000000 --output /tmp/nginx-logtop-1gb.log`
- `.venv/bin/python benchmarks/run.py --max-seconds 30 /tmp/nginx-logtop-1gb.log`
- `.venv/bin/pytest -q`

**Commit:** `step-8: meet one-gigabyte benchmark`

## Step 9: Package and Release-Readiness Verification

**Goal:** A clean Python 3.11 environment can install the built artifact and reproduce documented behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` Deployment and Packaging; `PRD.md` Release Acceptance.

**Files:**

1. Update `README.md` with real installation, command examples, schema links, limitations, and exit codes.
2. Create `CHANGELOG.md` with schema version 1 and MVP behavior.
3. Create `LICENSE` with the selected permissive open-source license.
4. Finalize package metadata in `pyproject.toml` and ensure source distributions include required files.

**Verification:**

- `.venv/bin/ruff check . && .venv/bin/pytest --cov=nginx_logtop --cov-branch --cov-fail-under=90`
- `.venv/bin/python -m build && .venv/bin/python -m twine check dist/*`
- `python3.11 -m venv /tmp/nginx-logtop-smoke && /tmp/nginx-logtop-smoke/bin/pip install dist/*.whl && /tmp/nginx-logtop-smoke/bin/nginx-logtop --version`

**Commit:** `step-9: verify release artifact`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Contracts, package runway, and correct input parsing | 4–5 h |
| Saturday PM | 4–5 | All aggregates and default terminal experience | 4–5 h |
| Sunday AM | 6–7 | Stable machine formats and complete behavior coverage | 4 h |
| Sunday PM | 8–9 | Performance proof and installable release candidate | 3–4 h |

## Verification and Handoff Rule

Do not accept a step from prose alone. Freeze the exact candidate, run the step commands against that candidate, preserve the named evidence, and apply the repository's current Idea to Deploy Verification Loop and risk-tier checker. Completion requires a current revalidated adjudication receipt where the project contract demands one. The exit-code contract must remain exactly `0/1/2/3/4`; code `4` always means unique-cardinality exhaustion.
