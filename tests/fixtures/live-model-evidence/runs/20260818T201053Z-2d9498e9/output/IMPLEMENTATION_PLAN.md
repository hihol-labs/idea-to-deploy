# Implementation Plan: nginx-insights

## Scope and Delivery Rule

This is a planning document; it does not authorize implementation in the blueprint phase. When implementation starts, complete one step at a time, preserve the interfaces in `PROJECT_ARCHITECTURE.md`, and update `PRD.md` before changing behavior. The eight steps fit a focused one-weekend delivery.

Every implementation step preserves this complete exit-code contract: `0` success/help/version; `1` unexpected internal/runtime failure; `2` Click usage error; `3` input/parse failure, including unreadable input or zero valid records; `4` unique-cardinality exhaustion. Code `4` must never be omitted or remapped.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | PEP 621 package and console entry point | Every feature and test needs an installable import/command boundary | 1 hour |
| 2 | Domain/report dataclasses and typed errors | Parser, analyzer, CLI, and renderers need one shared contract | 1 hour |
| 3 | Quality and test configuration | Fast checks must exist before feature growth | 1 hour |
| 4 | Deterministic fixture conventions | Calculation and renderer tests need trustworthy inputs | 1 hour |

No database schema, migrations, authentication, Docker, server, or deployment infrastructure belongs in the runway.

## STEP 1: Package and CLI Skeleton

**Goal:** A clean Python 3.11 environment can install the project and run help/version through the `nginx-insights` console script.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3, 4, and `CLI Interface`.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click and Rich runtime dependencies, development extras, package discovery, and console entry point.
2. Create `src/nginx_insights/__init__.py` with a single version source.
3. Create `src/nginx_insights/cli.py` with the Click command, all approved options, mutual exclusion, and placeholder orchestration boundaries without metric logic.
4. Create `tests/test_cli.py` for help, version, invalid options, and JSON/CSV mutual exclusion.
5. Add Ruff, mypy, and pytest configuration to `pyproject.toml`.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `nginx-insights --help`
- `nginx-insights --version`
- `python3.11 -m pytest tests/test_cli.py -q`
- `python3.11 -m ruff check . && python3.11 -m mypy src`

**Commit:** `step-1: scaffold installable CLI package`

## STEP 2: Domain Models and Failure Contract

**Goal:** All layers share typed immutable input/report models and one explicit mapping for expected failures.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and `CLI Interface`; `PRD.md` reporting requirements.

**Tasks:**

1. Create `src/nginx_insights/models.py` with `AccessRecord`, ranked metric, hourly bucket, report metadata, and `AnalysisReport` dataclasses.
2. Create `src/nginx_insights/errors.py` with separate input, no-valid-record, and unique-cardinality exceptions carrying codes `3`, `3`, and `4` respectively.
3. Extend `tests/test_cli.py` to prove the complete exit mapping `0/1/2/3/4`, including that cardinality exhaustion remains code `4`.
4. Create `tests/test_models.py` to prove immutability and required report fields.

**Verification:**

- `python3.11 -m pytest tests/test_models.py tests/test_cli.py -q`
- `python3.11 -m mypy src`

**Commit:** `step-2: define models and exit semantics`

## STEP 3: Common and Combined Log Parser

**Goal:** Each supported nginx line becomes an `AccessRecord`, while malformed lines are rejected without stopping the stream.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` section 5; PRD functional requirements FR-01 and FR-02.

**Tasks:**

1. Create `src/nginx_insights/parser.py` with a parser protocol and precompiled common/combined patterns.
2. Create `tests/fixtures/sample_combined.log`, `tests/fixtures/sample_common.log`, and `tests/fixtures/malformed.log` with manually auditable cases.
3. Create `tests/test_parser.py` for IP variants, timestamps and offsets, request targets, statuses, escaped/quoted values, common-format null User-Agent, and malformed data.
4. Add a linear-time hostile-line regression test to discourage catastrophic backtracking.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`
- `python3.11 -m ruff check src/nginx_insights/parser.py tests/test_parser.py`

**Commit:** `step-3: parse nginx common and combined logs`

## STEP 4: Streaming Analysis and Required Metrics

**Goal:** One pass produces exact aggregates, deterministic top-10 lists, hourly percentages, and exact User-Agent share within its limit.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 8; PRD FR-03 through FR-07.

**Tasks:**

1. Create `src/nginx_insights/analyzer.py` with line iteration, valid/skipped accounting, counters, 24 buckets, User-Agent cap, and report finalization.
2. Create `tests/test_analyzer.py` with golden counts and tie ordering.
3. Prove every hourly percentage uses `100 × hourly_request_count / total_valid_requests` and all 24 buckets are present.
4. Prove the unique share denominator is `total_valid_requests`, and the next new User-Agent beyond the cap raises the code `4` failure.
5. Prove 4xx and 5xx are included while 1xx–3xx are excluded from error-URL ranking.

**Verification:**

- `python3.11 -m pytest tests/test_analyzer.py -q`
- `python3.11 -m pytest tests/test_analyzer.py --cov=nginx_insights.analyzer --cov-fail-under=95`

**Commit:** `step-4: implement streaming metrics`

## STEP 5: Terminal, JSON, and CSV Renderers

**Goal:** One report model renders as colored terminal text or stable, undecorated pipeline data.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface` outputs and report schema; PRD FR-08 through FR-10.

**Tasks:**

1. Create `src/nginx_insights/renderers/__init__.py` with the renderer selection boundary.
2. Create `src/nginx_insights/renderers/terminal.py` with Rich summaries and four metric sections.
3. Create `src/nginx_insights/renderers/json.py` with schema version `1` and numeric percentages.
4. Create `src/nginx_insights/renderers/csv.py` with `section,rank,key,count,percentage` rows.
5. Create `tests/test_renderers.py` that structurally parses JSON/CSV, compares all modes to one golden report, and checks ANSI/control-character safety.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py -q`
- `python3.11 -m pytest tests/test_renderers.py --cov=nginx_insights.renderers --cov-fail-under=90`

**Commit:** `step-5: add terminal json and csv reports`

## STEP 6: End-to-End CLI and Input Reliability

**Goal:** Files and stdin flow through the real parser/analyzer/renderer stack with clean stdout, stderr, and exit behavior.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface` and reliability boundary; all P0 stories in `PRD.md`.

**Tasks:**

1. Complete orchestration in `src/nginx_insights/cli.py` for no-path stdin, ordered paths, explicit `-`, and selected format.
2. Extend `tests/test_cli.py` for multiple files, stdin, unreadable paths, malformed-only input, mixed valid/invalid input, broken pipe, and cardinality exhaustion.
3. Assert JSON/CSV stdout contains no diagnostics or ANSI bytes and stderr contains concise failure/skipped information.
4. Add `tests/fixtures/expected_report.json` and `tests/fixtures/expected_report.csv` as reviewable end-to-end goldens.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-insights tests/fixtures/sample_combined.log --json | python3.11 -m json.tool >/dev/null`
- `nginx-insights tests/fixtures/sample_combined.log --csv | python3.11 -c 'import csv,sys; assert list(csv.DictReader(sys.stdin))'`

**Commit:** `step-6: integrate streaming CLI behavior`

## STEP 7: Performance and Quality Gate

**Goal:** The exact staged candidate proves the 1 GB/30 second target and passes all static/runtime checks.

**Time:** ~3 hours, excluding benchmark fixture generation

**Context:** `PROJECT_ARCHITECTURE.md` section 8; `STRATEGIC_PLAN.md` success metrics and Definition of Done.

**Tasks:**

1. Create `scripts/generate_benchmark_log.py` to deterministically generate a documented 1 GB combined-format fixture outside version control.
2. Create `tests/test_performance.py` with a `performance` marker, wall-time measurement, correctness checksum, and peak-memory capture.
3. Record reference laptop and run conditions in `docs/BENCHMARK.md`.
4. Add `.gitignore` entries for generated logs, environments, caches, coverage, and build outputs.
5. Profile before optimizing; retain the single-process architecture unless evidence requires a revised spec decision.

**Verification:**

- `python3.11 scripts/generate_benchmark_log.py --size-gib 1 --output .bench/access.log`
- `python3.11 -m pytest -m performance tests/test_performance.py -q`
- `python3.11 -m pytest --cov=nginx_insights --cov-fail-under=90`
- `python3.11 -m ruff format --check . && python3.11 -m ruff check . && python3.11 -m mypy src`

**Commit:** `step-7: prove performance and quality gates`

## STEP 8: Packaging and Release Readiness

**Goal:** Source and wheel artifacts install cleanly and reproduce the documented CLI contract.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; PRD release criteria.

**Tasks:**

1. Create `README.md` with a sub-30-second quick start, supported formats, metric definitions, examples, schemas, and exit codes.
2. Create `LICENSE` with the chosen permissive license and `CHANGELOG.md` with the initial contract.
3. Create `.github/workflows/ci.yml` for Python 3.11 lint, types, tests, coverage, and build; do not run the 1 GB benchmark on generic CI.
4. Build with `python -m build`, inspect with `twine check`, install the wheel into a fresh environment, and smoke-test terminal/JSON/CSV modes.

**Verification:**

- `python3.11 -m build && python3.11 -m twine check dist/*`
- `python3.11 -m venv .release-venv && .release-venv/bin/pip install dist/*.whl`
- `.release-venv/bin/nginx-insights tests/fixtures/sample_combined.log --json | python3.11 -m json.tool >/dev/null`
- `python3.11 -m pytest -q`

**Commit:** `step-8: prepare reproducible pip release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Weekend block 1 | 1–3 | Installable shell, contracts, and reliable parsing | Saturday morning |
| Weekend block 2 | 4–5 | Required metrics and all output modes | Saturday afternoon–Sunday morning |
| Weekend block 3 | 6–8 | Integration, performance evidence, and release artifacts | Sunday afternoon/evening |

## Final Acceptance Checklist

- [ ] All P0 criteria in `PRD.md` have passing automated evidence.
- [ ] `0/1/2/3/4` exit behavior is covered end to end, including code `4` for unique-cardinality exhaustion.
- [ ] The exact release candidate completes the recorded 1 GB benchmark in under 30 seconds.
- [ ] The wheel installs and all three output modes pass a clean-environment smoke test.
- [ ] No database, HTTP API, authentication, server, cloud, or Kubernetes component was introduced.

