# Implementation Plan: nginx-insight

This is a planning artifact only. It orders work by dependency and then RICE value, preserves a single-process streaming architecture, and assumes one developer over one weekend. `PROJECT_ARCHITECTURE.md` is the technical source of truth and `PRD.md` is the behavior source of truth.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `src/` package and console entry point | Every test and feature needs an importable/installable boundary | 0.5 h |
| 2 | Canonical dataclasses and domain errors | Parser, accumulator, CLI, and renderers must share stable contracts | 0.5 h |
| 3 | Fixture strategy and quality commands | Enables red/green work before feature logic | 0.5 h |

There is no database schema, authentication runway, Docker setup, server, or CI/CD deployment target because those would contradict the approved local CLI architecture.

## STEP 1: Package and Contract Skeleton

**Goal:** A clean Python 3.11 environment can install the package and invoke the Click command skeleton.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Component Boundaries,” “Packaging and Deployment,” and “CLI Interface.”

**Tasks:**

1. Create `pyproject.toml` with `src/` packaging, Python 3.11 constraint, Click/Rich dependencies, dev extras, and `nginx-insight` console entry point.
2. Create `src/nginx_insight/__init__.py` and `src/nginx_insight/__main__.py` with one version source and CLI delegation.
3. Create `src/nginx_insight/cli.py` containing only the initial command/options contract.
4. Create `tests/test_cli.py` covering help, version, and mutually exclusive `--json`/`--csv` usage.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m nginx_insight --help`
- `pytest -q tests/test_cli.py`

**Commit:** `step-1: establish installable CLI contract`

## STEP 2: Domain Models and Exit Semantics

**Goal:** The project has framework-independent dataclasses, invariant checks, and a single error-to-exit mapping.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and State” and “Exit Codes.”

**Tasks:**

1. Create `src/nginx_insight/models.py` with `AccessRecord`, `RankedCount`, `HourlyBucket`, `UserAgentSummary`, and `Report`.
2. Create `src/nginx_insight/errors.py` with typed processing, input, and unique-cardinality exceptions.
3. Extend `src/nginx_insight/cli.py` so domain errors map exactly once to exits `0/1/2/3/4`.
4. Create `tests/test_models.py` and `tests/test_exit_codes.py` for invariants and all five statuses.

**Verification:**

- `pytest -q tests/test_models.py tests/test_exit_codes.py`
- `python3.11 -m nginx_insight --max-unique-user-agents 0 >/dev/null; test $? -eq 2`

**Commit:** `step-2: define report and error contracts`

## STEP 3: Streaming Input and Combined-Log Parser

**Goal:** Files and stdin produce valid `AccessRecord` objects line-by-line with classified malformed and I/O failures.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Parsing Contract,” “Inputs,” and “Error and Security Boundaries”; `PRD.md` FR-1 and FR-2.

**Tasks:**

1. Create `src/nginx_insight/input.py` for ordered file/stdin iteration, UTF-8 decoding, and source/line context.
2. Create `src/nginx_insight/parser.py` for the supported nginx combined format with one compiled pattern.
3. Create `tests/fixtures/combined.log`, `tests/fixtures/malformed.log`, and `tests/fixtures/invalid-utf8.log` with minimal deterministic cases.
4. Create `tests/test_input.py` and `tests/test_parser.py` for files, stdin, timestamps, `-` bytes, query strings, malformed lines, and decoding failures.

**Verification:**

- `pytest -q tests/test_input.py tests/test_parser.py`
- `python3.11 -m nginx_insight tests/fixtures/missing.log >/dev/null; test $? -eq 3`

**Commit:** `step-3: stream and parse combined logs`

## STEP 4: Exact Streaming Aggregation

**Goal:** One pass calculates top IPs, top 4xx/5xx URLs, all 24 hourly percentages, and exact unique User-Agent share.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and State” and “Performance and Capacity”; `PRD.md` FR-3 through FR-6.

**Tasks:**

1. Create `src/nginx_insight/aggregate.py` with `ReportAccumulator.update()` and `finalize()`.
2. Implement deterministic top-10 tie-breaking and error-only URL counting.
3. Implement all 24 hour buckets with `100 × hourly_request_count / total_valid_requests` and zero-valid-input behavior.
4. Implement unique User-Agent share and the configured cardinality guard that raises the exit-4 domain error before approximation.
5. Create `tests/test_aggregate.py` for rankings, ties, 4xx/5xx selection, denominators, rounding inputs, empty reports, and cardinality exhaustion.

**Verification:**

- `pytest -q tests/test_aggregate.py`
- `pytest -q tests/test_aggregate.py -k 'hourly or cardinality or tie'`

**Commit:** `step-4: calculate exact streaming metrics`

## STEP 5: Terminal, JSON, and CSV Renderers

**Goal:** One canonical report is rendered as colored terminal text or pipeline-safe JSON/CSV without metric drift.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Outputs” and ADR-003; `PRD.md` FR-7 through FR-9.

**Tasks:**

1. Create `src/nginx_insight/renderers/__init__.py` with renderer selection.
2. Create `src/nginx_insight/renderers/terminal.py` with four Rich report sections and safe text handling.
3. Create `src/nginx_insight/renderers/json.py` with the schema-versioned object contract.
4. Create `src/nginx_insight/renderers/csv.py` with the normalized column contract.
5. Create `tests/test_renderers.py` with golden structural assertions and cross-format count/percentage reconciliation.

**Verification:**

- `pytest -q tests/test_renderers.py`
- `python3.11 -m nginx_insight --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: add terminal and pipeline renderers`

## STEP 6: End-to-End CLI and Failure Atomicity

**Goal:** The installed command satisfies input selection, stdout/stderr separation, strict mode, option validation, and complete exit behavior.

**Time:** ~2 hours

**Context:** Entire `PROJECT_ARCHITECTURE.md` “CLI Interface”; `PRD.md` FR-10 and acceptance criteria.

**Tasks:**

1. Complete `src/nginx_insight/cli.py` orchestration without adding parsing or aggregation logic to the CLI layer.
2. Extend `tests/test_cli.py` for stdin, multiple files, empty input, strict/non-strict malformed input, non-TTY mode, and mutually exclusive formats.
3. Extend `tests/test_exit_codes.py` to assert `0` success, `1` processing failure, `2` usage failure, `3` input failure, and `4` unique-cardinality exhaustion.
4. Assert nonzero JSON/CSV runs emit no partial stdout and place diagnostics only on stderr.

**Verification:**

- `pytest -q tests/test_cli.py tests/test_exit_codes.py`
- `python3.11 -m nginx_insight --json tests/fixtures/combined.log >/tmp/nginx-insight.json`
- `python3.11 -m nginx_insight --csv tests/fixtures/combined.log >/tmp/nginx-insight.csv`

**Commit:** `step-6: integrate CLI and atomic failures`

## STEP 7: Quality, Security, and Performance Evidence

**Goal:** Correctness, safety, and the 1 GB / 30 s target have reproducible evidence on a named reference laptop.

**Time:** ~3 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done and risks; `PROJECT_ARCHITECTURE.md` “Performance and Capacity.”

**Tasks:**

1. Create `tests/test_security.py` for control characters, Rich markup, CSV injection-like prefixes, and non-echoed sensitive malformed lines.
2. Create `benchmarks/generate_log.py` to deterministically generate a representative fixture locally without committing a 1 GB artifact.
3. Create `benchmarks/run.sh` to record command, environment, wall time, and peak RSS without including renderer cost.
4. Configure formatter, linter, type checker, pytest, and coverage in `pyproject.toml`.
5. Record actual benchmark conditions and measurements in `benchmarks/RESULTS.md`; do not claim the target before running it.

**Verification:**

- `ruff check . && ruff format --check .`
- `mypy src`
- `pytest --cov=nginx_insight --cov-report=term-missing --cov-fail-under=90`
- `bash benchmarks/run.sh`

**Commit:** `step-7: establish quality and performance evidence`

## STEP 8: Package and Release Readiness

**Goal:** The wheel installs cleanly and all user-facing documentation matches tested behavior.

**Time:** ~1 hour

**Context:** `README.md`, `CLAUDE_CODE_GUIDE.md`, and all acceptance criteria in `PRD.md`.

**Tasks:**

1. Update `README.md` only with commands verified against the installed wheel.
2. Add `LICENSE` using the selected open-source license before public release.
3. Build sdist/wheel into `dist/` and inspect metadata.
4. Install the wheel into a clean Python 3.11 virtual environment and run help, version, and a fixture analysis.
5. Reconcile implementation status in `CLAUDE.md` and retain exit codes `0/1/2/3/4` unchanged.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m twine check dist/*`
- `pytest -q`
- `python3.11 -m venv /tmp/nginx-insight-release-venv && /tmp/nginx-insight-release-venv/bin/pip install dist/*.whl && /tmp/nginx-insight-release-venv/bin/nginx-insight --help`

**Commit:** `step-8: prepare installable release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable boundary, contracts, and parsing | ~4 h |
| Saturday PM | 4–5 | Metrics and all renderers | ~4 h |
| Sunday AM | 6–7 | End-to-end behavior and quality evidence | ~5 h |
| Sunday PM | 8 | Clean package and documentation handoff | ~1 h |

## Complete Exit-Code Contract

Every step must preserve the same contract: `0` success; `1` processing/data failure; `2` CLI usage failure; `3` input I/O or UTF-8 decoding failure; `4` unique-cardinality exhaustion. Code `4` specifically means the exact distinct User-Agent set would exceed `--max-unique-user-agents`. No step may omit, remap, or silently downgrade it.

## Plan Acceptance

The implementation is not complete merely because these steps are documented. Completion requires the commands and evidence named in each step, the Definition of Done in `STRATEGIC_PLAN.md`, and all P0 acceptance criteria in `PRD.md`. No product code was produced by this blueprint.

