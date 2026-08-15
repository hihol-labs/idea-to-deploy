# Implementation Plan: nginx-insight

## Delivery Boundary

This plan covers the one-weekend MVP specified by `PRD.md` and the approved single-process design in `PROJECT_ARCHITECTURE.md`. It creates product code only when a later implementation session executes the plan; this blueprint session creates documentation only.

All steps preserve the complete exit-code contract:

- `0` success, including an intentional downstream pipe close.
- `1` operational, I/O, output, or unexpected internal failure.
- `2` Click usage or option-validation error.
- `3` input-data failure: no valid requests, or malformed input under `--fail-on-invalid`.
- `4` unique-cardinality exhaustion after the configured distinct User-Agent ceiling is exceeded.

No step may omit, remap, or reuse code 4, and no failure may emit a partial report.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` package layout, Python 3.11 metadata, console entry point | Every feature and test needs an installable package | 0.5 h |
| 2 | Typed report and record dataclasses | Parser, aggregator, and renderers need one shared contract | 0.5 h |
| 3 | Test fixtures and golden-output conventions | Enables incremental verification before feature expansion | 0.5 h |
| 4 | Performance harness design and reference-machine record | Prevents a late, unverifiable performance claim | 0.5 h |

There is no database schema, authentication layer, API framework, Docker setup, or CI deployment runway because those components are explicitly outside the architecture.

## Step 1: Package Skeleton and Domain Contracts

**Goal:** `nginx-insight --help` and `nginx-insight --version` run from an isolated Python 3.11 environment, and typed report models are importable.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface,” “Package and Component Design,” and “Core Dataclasses.”

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click and Rich runtime dependencies, pytest tooling, package discovery, and the `nginx-insight = nginx_insight.cli:main` entry point.
2. Create `src/nginx_insight/__init__.py` with the package version export.
3. Create `src/nginx_insight/models.py` with frozen/slot dataclasses and invariants for access records, stats, ranked values, hourly buckets, User-Agent summary, and the report.
4. Create `src/nginx_insight/cli.py` with the Click group/command shell and version/help paths only.
5. Create `tests/test_models.py` and initial `tests/test_cli.py` assertions.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`
- `.venv/bin/nginx-insight --help`
- `.venv/bin/nginx-insight --version`
- `.venv/bin/pytest -q tests/test_models.py tests/test_cli.py`

**Commit:** `step-1: establish package and domain contracts`

## Step 2: Streaming Input and nginx Parser

**Goal:** Common and combined nginx lines become validated `AccessRecord` objects without buffering a file.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Metric Contracts,” “Streaming, Memory, and Performance,” and “Error Handling and Security Boundaries.”

**Tasks:**

1. Create `src/nginx_insight/input.py` with sequential path/stdin iteration, `-` validation hooks, UTF-8 replacement decoding, and context-managed file closing.
2. Create `src/nginx_insight/parser.py` with one compiled parsing strategy for common/combined layouts and explicit valid/invalid outcomes.
3. Add `tests/fixtures/common.log`, `tests/fixtures/combined.log`, and `tests/fixtures/malformed.log` with synthetic non-sensitive records.
4. Create `tests/test_input.py` for multiple paths, stdin, line numbers, unreadable input, and bounded iteration.
5. Create `tests/test_parser.py` for timestamps, IPv4/IPv6 tokens, quoted request targets, status boundaries, missing User-Agent values, escapes, blank lines, and malformed records.

**Verification:**

- `.venv/bin/pytest -q tests/test_input.py tests/test_parser.py`
- `.venv/bin/python -m pytest -q tests/test_parser.py --cov=nginx_insight.parser --cov-fail-under=90`

**Commit:** `step-2: parse nginx streams into validated records`

## Step 3: Core Traffic and Error Aggregation

**Goal:** Exact top IPs, top error URLs, and all 24 hourly buckets are produced with deterministic ties and correct percentages.

**Time:** ~1.5 hours

**Context:** `PRD.md` functional requirements FR-1 through FR-4 and `PROJECT_ARCHITECTURE.md` “Metric Contracts.”

**Tasks:**

1. Create `src/nginx_insight/aggregate.py` with IP and 4xx/5xx URL counters plus a fixed 24-slot hourly counter.
2. Implement top-10 finalization using descending counts and ascending string tie-breakers.
3. Implement hourly percentages using exactly `100 × hourly_request_count / total_valid_requests`, rounding only at the report boundary.
4. Create `tests/test_aggregate.py` covering mixed statuses, ties, 24 buckets, time-zone preservation, zero hours, and percentage sum tolerance.

**Verification:**

- `.venv/bin/pytest -q tests/test_aggregate.py -k 'ip or error or hourly'`
- `.venv/bin/python -m pytest -q tests/test_aggregate.py --cov=nginx_insight.aggregate --cov-fail-under=90`

**Commit:** `step-3: aggregate traffic errors and hourly distribution`

## Step 4: Exact User-Agent Share and Cardinality Guard

**Goal:** The report includes exact distinct User-Agent share within a configured bound and fails closed with exit code 4 beyond it.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Metric Contracts” and “Streaming, Memory, and Performance”; `PRD.md` FR-5 and FR-9.

**Tasks:**

1. Extend `src/nginx_insight/aggregate.py` with the exact nonempty User-Agent set and a domain-specific cardinality exception.
2. Compute `100 × distinct_nonempty_user_agent_count / total_valid_requests` only after successful stream completion.
3. Extend `tests/test_aggregate.py` for repeated, missing, empty, and ceiling-crossing User-Agents and for no partial report on exhaustion.
4. Extend `src/nginx_insight/models.py` invariants for `UserAgentSummary`.

**Verification:**

- `.venv/bin/pytest -q tests/test_aggregate.py -k 'user_agent or cardinality'`
- `.venv/bin/pytest -q tests/test_models.py tests/test_aggregate.py`

**Commit:** `step-4: bound exact user-agent cardinality`

## Step 5: Colored Terminal Renderer

**Goal:** Default output is a readable Rich report with four sections, TTY-aware color, stable ordering, and escaped input values.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs” and `PRD.md` FR-6.

**Tasks:**

1. Create `src/nginx_insight/render/__init__.py` with renderer protocol exports.
2. Create `src/nginx_insight/render/terminal.py` with Rich tables for top IPs, error URLs, hourly distribution, and User-Agent summary.
3. Add fixed-width/non-interactive capture fixtures under `tests/golden/terminal.txt` without ANSI escapes.
4. Extend `tests/test_renderers.py` for labels, ordering, two-decimal percentages, markup escaping, TTY color, and `--no-color` behavior.

**Verification:**

- `.venv/bin/pytest -q tests/test_renderers.py -k terminal`
- `.venv/bin/python -m pytest -q tests/test_renderers.py --cov=nginx_insight.render.terminal --cov-fail-under=90`

**Commit:** `step-5: render safe rich terminal report`

## Step 6: JSON and CSV Pipeline Renderers

**Goal:** `--json` and `--csv` serialize the same report model into deterministic, ANSI-free pipeline contracts.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` “Outputs,” “Determinism and Compatibility,” and `PRD.md` FR-7.

**Tasks:**

1. Create `src/nginx_insight/render/json.py` with the schema-version-1 object.
2. Create `src/nginx_insight/render/csv.py` with header `section,key,count,percentage` and RFC 4180-compatible quoting.
3. Add `tests/golden/report.json` and `tests/golden/report.csv` based on one shared fixture.
4. Extend `tests/test_renderers.py` to parse both outputs, reject ANSI escapes, verify special-character escaping, and compare all metric values with the shared report model.

**Verification:**

- `.venv/bin/pytest -q tests/test_renderers.py -k 'json or csv'`
- `.venv/bin/python -m json.tool tests/golden/report.json >/dev/null`

**Commit:** `step-6: add deterministic pipeline formats`

## Step 7: End-to-End CLI and Exit-Code Contract

**Goal:** The command integrates input, parser, aggregator, and renderer while enforcing every option, stdout/stderr, and exit behavior.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` complete “CLI Interface” and `PRD.md` FR-8 through FR-10.

**Tasks:**

1. Complete `src/nginx_insight/cli.py` with `analyze`, path/stdin rules, mutually exclusive formats, positive cardinality validation, `--fail-on-invalid`, and renderer selection.
2. Map success to 0, operational failures to 1, Click usage failures to 2, input-data failures to 3, and unique-cardinality exhaustion to 4.
3. Handle downstream `BrokenPipeError` as success without a traceback and keep every diagnostic on stderr.
4. Extend `tests/test_cli.py` with subprocess-level assertions for codes `0/1/2/3/4`, byte-clean stdout, multiple files, stdin, malformed policies, no valid records, and no partial report on failure.

**Verification:**

- `.venv/bin/pytest -q tests/test_cli.py`
- `.venv/bin/nginx-insight analyze --json tests/fixtures/combined.log | .venv/bin/python -m json.tool >/dev/null`
- `test "$(.venv/bin/python -m pytest -q tests/test_cli.py -k exit_code | tail -n 1 | sed -n 's/.*\([0-9][0-9]* passed\).*/\1/p')" != ""`

**Commit:** `step-7: enforce cli and exit contracts`

## Step 8: Performance, Packaging, and Release Readiness

**Goal:** The complete package satisfies correctness, coverage, installation, documentation, and the measured 1 GB performance acceptance criterion.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done and KPIs; `PROJECT_ARCHITECTURE.md` “Streaming, Memory, and Performance.”

**Tasks:**

1. Create `tests/generate_performance_fixture.py` for deterministic synthetic combined-log generation with documented distributions and no production data.
2. Create `tests/test_performance.py` to run the installed CLI, suppress report output, record wall time and peak RSS, and enforce the reference-machine target only when explicitly enabled.
3. Complete `README.md` with installation, command examples, schemas, limitations, and reproducible benchmark instructions.
4. Add `LICENSE`, `CHANGELOG.md`, and packaging metadata required to build source and wheel distributions.
5. Run the full suite, coverage, build, clean-environment install, and 1 GB benchmark; record the machine profile with the result.

**Verification:**

- `.venv/bin/pytest -q --cov=nginx_insight --cov-report=term-missing --cov-fail-under=90`
- `.venv/bin/python -m build && .venv/bin/python -m twine check dist/*`
- `NGINX_INSIGHT_PERF=1 .venv/bin/pytest -q tests/test_performance.py --maxfail=1`
- `tmpdir=$(mktemp -d) && python3.11 -m venv "$tmpdir/venv" && "$tmpdir/venv/bin/pip" install dist/*.whl && "$tmpdir/venv/bin/nginx-insight" --help`

**Commit:** `step-8: verify performance and release package`

## Weekend Execution Sequence

| Block | Steps | Goal |
|---|---|---|
| Saturday morning | 1–2 | Installable shell and trustworthy streaming parser |
| Saturday afternoon | 3–4 | Exact metrics and bounded User-Agent cardinality |
| Sunday morning | 5–7 | All output modes and complete CLI behavior |
| Sunday afternoon | 8 | Full verification, benchmark, and handoff |

## Plan Acceptance

Implementation is acceptable only when all step-specific checks and the final exact-candidate project verification gate pass. A prose claim or standalone passing message is not evidence. Gzip input remains Should priority and may be delivered only after all P0 acceptance criteria pass without extending the weekend boundary.

