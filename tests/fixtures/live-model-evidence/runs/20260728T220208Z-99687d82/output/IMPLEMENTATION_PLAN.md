# Implementation Plan: Nginx Log Lens

## Planning Basis

This is a one-weekend, documentation-only delivery plan for the product
specified in `PRD.md` and `PROJECT_ARCHITECTURE.md`. Steps follow dependency
order while preserving the RICE priorities in `STRATEGIC_PLAN.md`. Only one
step is active at a time (WIP=1).

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package and CLI contract | Every test and feature needs an installable command | 1.0 h |
| 2 | Domain dataclasses and error taxonomy | Parser, aggregation, and renderers share these contracts | 1.0 h |
| 3 | Deterministic fixtures and benchmark protocol | Correctness and performance need reproducible evidence | 1.0 h |

No database schema, authentication system, API, Docker environment, or CI/CD
deployment pipeline is runway work because those components are explicitly
out of scope.

## STEP 1: Freeze Package and CLI Contracts

**Goal:** A pip-installable Python 3.11 skeleton exposes
`nginx-log-lens --help` with the approved options and no product logic.

**Time:** ~1 hour  
**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface” and
“Database, API, and Deployment”.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click, Rich, build
   metadata, and the `nginx-log-lens` console entry point.
2. Create `src/nginx_log_lens/__init__.py` with version metadata.
3. Create `src/nginx_log_lens/cli.py` with the command, `INPUT`, mutually
   exclusive `--json`/`--csv`, color validation, and help text.
4. Create `tests/test_cli_contract.py` for help, version, option conflicts,
   and Click’s exit code 2.

**Verification:**

- `python -m pip install -e '.[test]'`
- `nginx-log-lens --help`
- `pytest -q tests/test_cli_contract.py`

**Commit:** `step-1: freeze package and CLI contracts`

## STEP 2: Define Domain Models and Failures

**Goal:** Typed, renderer-independent records, state, reports, and error
categories make metric semantics explicit.

**Time:** ~1 hour  
**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model” and “Error
Handling and Observability”.

**Tasks:**

1. Create `src/nginx_log_lens/models.py` with `AccessRecord`,
   `AnalysisState`, ranked-entry dataclasses, and immutable `AnalysisReport`.
2. Create `src/nginx_log_lens/errors.py` with usage-independent input,
   data, and internal failure classes mapped to exit codes 3, 4, and 1.
3. Create `tests/test_models.py` for invariants, zero-request UA share, and
   immutability.

**Verification:**

- `pytest -q tests/test_models.py`
- `python -m compileall -q src`

**Commit:** `step-2: define report and error models`

## STEP 3: Implement Streaming Input and Combined-Log Parser

**Goal:** A file or stdin is consumed line by line and each standard combined
record becomes an `AccessRecord` or a counted parse failure.

**Time:** ~2.5 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections “Parsing Contract” and
“Performance Strategy”.

**Tasks:**

1. Create `src/nginx_log_lens/input.py` with local path/stdin handling,
   a 64 KiB chunk reader, 1 MiB physical-line limit, discard-to-newline
   recovery, incremental decoding, and read-error translation.
2. Create `src/nginx_log_lens/parser.py` with the specified linear state
   machine, exact escape/full-consumption rules, and timezone-aware timestamp
   conversion.
3. Create `tests/fixtures/combined.log` and
   `tests/fixtures/malformed.log` with documented expected counts.
4. Create `tests/test_input.py` and `tests/test_parser.py` for file/stdin,
   chunk boundaries, CRLF, overlong lines, quoted/escaped values, timezones,
   trailing tokens, and invalid bytes.
5. Create `benchmarks/generate_log.py` now, with deterministic representative
   and near-unique 1 GB profiles, seed, exact byte target, cardinalities, and
   fixture SHA-256 output, so the architecture risk can be gated immediately
   after aggregation exists.

**Verification:**

- `pytest -q tests/test_input.py tests/test_parser.py`
- `pytest -q tests/test_parser.py --durations=10`
- `python benchmarks/generate_log.py --help`

**Commit:** `step-3: stream and parse combined logs`

## STEP 4: Build Exact Aggregations

**Goal:** One pass produces exact top IPs, top 4xx/5xx URLs, all 24 hourly
buckets, and the defined User-Agent diversity share.

**Time:** ~2 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model” and “Performance
Strategy”; `PRD.md` requirements P0-3 through P0-6.

**Tasks:**

1. Create `src/nginx_log_lens/aggregate.py` with `consume(record)` and
   deterministic `finalize()` functions.
2. Enforce status boundaries 400–599, count-desc/key-asc tie ordering, exact
   top-10 truncation, and a fixed 24-bucket hour array.
3. Create `tests/test_aggregate.py` covering boundary statuses, ties, more
   than 10 keys, mixed timezones, missing UAs, and no valid records.
4. Create the minimal `benchmarks/run.sh` hot-loop harness and execute the
   early gate before starting any renderer: representative 1 GB median under
   30 seconds and peak RSS under 256 MB, plus a recorded near-unique 1 GB run.

**Verification:**

- `pytest -q tests/test_aggregate.py`
- `pytest -q tests/test_aggregate.py --cov=nginx_log_lens.aggregate --cov-fail-under=95`
- `bash benchmarks/run.sh --gate`

**Commit:** `step-4: implement exact report aggregations`

## STEP 5: Add Rich Terminal Rendering

**Goal:** Default output presents all metrics clearly, uses color only when
appropriate, and safely renders untrusted log values.

**Time:** ~1.5 hours  
**Context:** `PROJECT_ARCHITECTURE.md` “CLI Interface” outputs and “Security
and Privacy”.

**Tasks:**

1. Create `src/nginx_log_lens/renderers/__init__.py`.
2. Create `src/nginx_log_lens/renderers/text.py` with Rich tables for the four
   reports and summary counts.
3. Create `tests/golden/text.txt` and `tests/test_text_renderer.py` for stable
   no-color output, empty sections, markup escaping, and forced color.

**Verification:**

- `pytest -q tests/test_text_renderer.py`
- `NO_COLOR=1 nginx-log-lens tests/fixtures/combined.log`

**Commit:** `step-5: render safe Rich terminal report`

## STEP 6: Add JSON and CSV Pipeline Formats

**Goal:** JSON and CSV stdout conform exactly to their versioned schemas and
contain no styling or diagnostic text.

**Time:** ~1.5 hours  
**Context:** `PROJECT_ARCHITECTURE.md` “CLI Interface” outputs.

**Tasks:**

1. Create `src/nginx_log_lens/renderers/json.py` for `schema_version: 1`.
2. Create `src/nginx_log_lens/renderers/csv.py` for the normalized
   `section,key,count,value` schema.
3. Create `tests/golden/report.json`, `tests/golden/report.csv`, and
   `tests/test_machine_renderers.py` for schema, ordering, quoting, precision,
   and trailing newline.

**Verification:**

- `pytest -q tests/test_machine_renderers.py`
- `nginx-log-lens --json tests/fixtures/combined.log | python -m json.tool >/dev/null`

**Commit:** `step-6: add stable JSON and CSV renderers`

## STEP 7: Integrate End-to-End CLI Behavior

**Goal:** File and pipe workflows select a renderer, preserve stdout/stderr
separation, and implement all exit codes.

**Time:** ~1.5 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections “CLI Interface” and “Error
Handling and Observability”.

**Tasks:**

1. Update `src/nginx_log_lens/cli.py` to connect input, parser, aggregator,
   final report, renderer, and exception mapping.
2. Create `tests/test_cli_e2e.py` for path/stdin equivalence, empty input,
   partially malformed input, all-malformed input, unreadable input, renderer
   selection, diagnostics, and broken pipe.
3. Ensure line contents and tracebacks never appear in expected error output.

**Verification:**

- `pytest -q tests/test_cli_e2e.py`
- `nginx-log-lens --json tests/fixtures/combined.log > /tmp/nginx-log-lens-report.json`

**Commit:** `step-7: integrate end-to-end CLI analysis`

## STEP 8: Validate Performance and Robustness

**Goal:** Reproducible evidence establishes whether the 1 GB / 30-second
target and memory expectations hold on the reference laptop.

**Time:** ~2 hours  
**Context:** `PROJECT_ARCHITECTURE.md` “Performance Strategy” and
`STRATEGIC_PLAN.md` KPIs.

**Tasks:**

1. Extend `benchmarks/generate_log.py` only if profiling revealed a missing
   representative or near-unique data shape; preserve seed compatibility.
2. Extend `benchmarks/run.sh` to record the full environment, three timed
   runs, median wall time, and peak RSS without fixture generation.
3. Create `tests/test_robustness.py` for bounded random input, overlong
   physical records, and regression
   cases discovered during profiling.
4. Re-run and record both profiles in `benchmarks/RESULTS.md`; if the
   representative target fails or the adversarial process is killed/errors,
   keep the evidence and re-open architecture acceptance.

**Verification:**

- `pytest -q tests/test_robustness.py`
- `bash benchmarks/run.sh`

**Commit:** `step-8: record performance and robustness evidence`

## STEP 9: Package and Release-Readiness Check

**Goal:** Source and wheel artifacts install cleanly in Python 3.11 and the
documented workflows pass from an isolated environment.

**Time:** ~2 hours  
**Context:** `PRD.md` release acceptance and `README.md` Quick Start.

**Tasks:**

1. Complete `README.md` with install, examples, schemas, exit codes,
   performance caveat, and privacy statement.
2. Add `LICENSE`, `CHANGELOG.md`, and packaging include/exclude rules.
3. Create `tests/test_packaging.py` or a release script that installs the
   built wheel into a clean environment and runs smoke commands.
4. Reconcile `CLAUDE.md` status and preserve verification evidence.

**Verification:**

- `pytest -q --cov=nginx_log_lens --cov-fail-under=90`
- `python -m build && python -m twine check dist/*`
- `python -m pip install --force-reinstall dist/*.whl && nginx-log-lens --version`

**Commit:** `step-9: verify package release readiness`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Contracts and reliable parsing | Saturday morning |
| Weekend block 2 | 4–6 | Metrics and all output modes | Saturday afternoon/Sunday morning |
| Weekend block 3 | 7–9 | Integration, benchmarks, and release proof | Sunday afternoon |

## Dependency and Rollback Rules

- Execute steps in order; do not begin a later step while an earlier step is
  unverified.
- Each step is independently reviewable and has a named commit boundary.
- A failed performance target does not authorize an architecture switch; it
  opens a measured profiling/replanning decision.
- Should features (gzip and custom formats) begin only after all P0 acceptance
  criteria and the release check pass.

## Final Acceptance

All P0 criteria in `PRD.md`, the complete test suite, isolated wheel smoke
test, and the documented benchmark must pass. A narrative “works” statement
is not evidence.
