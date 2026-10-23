# Implementation Plan: nginx-top

This plan implements the contracts in `PROJECT_ARCHITECTURE.md` and the P0/P1 requirements in `PRD.md`. It contains eight dependency-ordered steps sized for one weekend. Product code is not part of this blueprint.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Package metadata and `src/` layout | Enables imports, console entry point, and isolated install checks | 0.5 h |
| 2 | Domain models and typed public errors | Prevents parser, aggregator, and renderers from inventing incompatible contracts | 0.5 h |
| 3 | Representative fixtures and benchmark generator | Gives correctness and performance work reproducible inputs | 0.5 h |
| 4 | CI-quality local commands | Establishes formatting, typing, tests, and coverage before feature work grows | 0.5 h |

No schema, migrations, auth, Docker, or deployment pipeline is runway work because the approved architecture has no database, identity boundary, container, or service deployment.

## STEP 1: Package Skeleton and CLI Contract

**Goal:** A pip-installable Python 3.11 package exposes `nginx-top`, help/version output, validated options, and the public exit-code constants.

**Time:** ~1 hour

**Context:** `PROJECT_ARCHITECTURE.md` sections “System Components,” “CLI Interface,” and “Packaging and Deployment.”

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click and Rich runtime dependencies, test/lint/type extras, and the `nginx-top` console script.
2. Create `src/nginx_top/__init__.py` with the package version contract.
3. Create `src/nginx_top/errors.py` with typed operational errors and constants for the complete `0/1/2/3/4` contract: success, I/O, usage, strict malformed input, and unique-cardinality exhaustion.
4. Create `src/nginx_top/cli.py` with Click arguments/options, mutual exclusion validation, and placeholder orchestration boundaries without metric logic.
5. Create `tests/integration/test_cli_contract.py` covering help, version, invalid option combinations, stdin/file validation, and exit 2.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `python3.11 -m pytest tests/integration/test_cli_contract.py -q`
- `nginx-top --help`

**Commit:** `step-1: establish package and CLI contract`

## STEP 2: Domain Models and Combined-Log Parser

**Goal:** Supported nginx combined-format lines become minimal, typed records; malformed lines carry source and line context without exposing full log contents.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections “Data Model and Streaming State” and “Supported Input Contract”; `PRD.md` FR-001 and FR-002.

**Tasks:**

1. Create `src/nginx_top/models.py` with frozen/slots dataclasses for `LogRecord`, `RankedCount`, `HourlyBucket`, `Diagnostics`, and `AnalysisResult`.
2. Create `src/nginx_top/parser.py` with a precompiled combined-format parser, timezone-aware timestamp parsing, request-target extraction, and a typed malformed-line result/error.
3. Create `tests/fixtures/combined.log` and `tests/fixtures/malformed.log` with synthetic non-sensitive samples.
4. Create `tests/unit/test_parser.py` for quoted fields, IPv4/IPv6 text, `-` request fields, status boundaries, timezone offsets, blank lines, and malformed data.

**Verification:**

- `python3.11 -m pytest tests/unit/test_parser.py -q`
- `python3.11 -m mypy src/nginx_top/models.py src/nginx_top/parser.py`

**Commit:** `step-2: parse nginx combined records`

## STEP 3: Streaming Input and Core Aggregation

**Goal:** Files and stdin are consumed once, producing deterministic top IP, top error URL, and 24-hour distribution results without retaining records.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` processing flow, state invariants, and performance design; `PRD.md` FR-003 through FR-006.

**Tasks:**

1. Create `src/nginx_top/input.py` for sequential path/stdin iteration, UTF-8 replacement decoding, source labels, and typed I/O errors.
2. Create `src/nginx_top/aggregate.py` with one-pass counters, deterministic count-descending/key-ascending ranking, 400–599 filtering, and all 24 hourly buckets.
3. Calculate each hourly percentage with exactly `100 × hourly_request_count / total_valid_requests`, using zero for an empty valid dataset.
4. Extend `tests/unit/test_aggregate.py` for ranking ties, fewer than 10 values, status boundaries, multiple sources, timezone-local hour bucketing, malformed skip behavior, and empty input.
5. Create `tests/integration/test_streaming_sources.py` proving file and stdin results agree and multiple files form one dataset.

**Verification:**

- `python3.11 -m pytest tests/unit/test_aggregate.py tests/integration/test_streaming_sources.py -q`
- `python3.11 -m pytest -q --cov=nginx_top --cov-report=term-missing`

**Commit:** `step-3: aggregate core metrics in one pass`

## STEP 4: Exact User-Agent Metric and Resource Guard

**Goal:** The result includes exact unique User-Agent count/share within a configured ceiling and fails safely with code 4 beyond it.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` data model, resource design, and exit codes; `PRD.md` FR-007 and FR-008.

**Tasks:**

1. Extend `src/nginx_top/aggregate.py` with a `set[str]`, positive ceiling enforcement, and `CardinalityExhaustedError` raised before an incomplete result can render.
2. Compute User-Agent share as `100 × unique_user_agent_count / total_valid_requests` and define empty input as `0.0`.
3. Map the error in `src/nginx_top/cli.py` to stderr and exit 4.
4. Extend `tests/unit/test_aggregate.py` for repeated/empty User-Agents, exact-boundary behavior, and first-over-limit failure.
5. Extend `tests/integration/test_cli_contract.py` to prove unique-cardinality exhaustion exits 4 and stdout contains no partial report.

**Verification:**

- `python3.11 -m pytest tests/unit/test_aggregate.py tests/integration/test_cli_contract.py -q`
- `bash -o pipefail -c "nginx-top --max-unique-user-agents 1 tests/fixtures/combined.log >/tmp/nginx-top.out; test $? -eq 4 && test ! -s /tmp/nginx-top.out"`

**Commit:** `step-4: guard exact user-agent cardinality`

## STEP 5: Rich Terminal Renderer

**Goal:** Default output presents the complete analysis clearly, uses color only when appropriate, and safely handles untrusted strings.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` outputs and security/privacy; `PRD.md` FR-009.

**Tasks:**

1. Create `src/nginx_top/renderers/__init__.py` with the renderer protocol/interface.
2. Create `src/nginx_top/renderers/text.py` with four Rich sections, diagnostics, fixed percentage formatting, markup-safe values, and `--color/--no-color` handling.
3. Wire the default renderer in `src/nginx_top/cli.py`.
4. Create `tests/unit/renderers/test_text.py` with a non-color snapshot and control/markup-like input cases.
5. Extend `tests/integration/test_cli_contract.py` for stdout/stderr separation and successful empty input.

**Verification:**

- `python3.11 -m pytest tests/unit/renderers/test_text.py tests/integration/test_cli_contract.py -q`
- `nginx-top --no-color tests/fixtures/combined.log`

**Commit:** `step-5: render safe rich terminal report`

## STEP 6: JSON and CSV Renderers

**Goal:** `--json` and `--csv` emit stable, deterministic, pipeline-safe representations of the same `AnalysisResult`.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` output contract/schema; `PRD.md` FR-010 and FR-011.

**Tasks:**

1. Create `src/nginx_top/renderers/json.py` with the documented top-level keys and six-decimal numeric percentage policy.
2. Create `src/nginx_top/renderers/csv.py` with `metric,rank,key,count,percentage`, standard quoting, formula-trigger neutralization, and deterministic row order.
3. Select renderers in `src/nginx_top/cli.py` without allowing mixed formats.
4. Create `tests/unit/renderers/test_json.py` for schema, types, order, and parseability.
5. Create `tests/unit/renderers/test_csv.py` for schema, row order, quoting, empty cells, and formula injection.
6. Create `tests/integration/test_pipeline_outputs.py` to parse real CLI stdout with `json` and `csv` standard-library readers.

**Verification:**

- `python3.11 -m pytest tests/unit/renderers tests/integration/test_pipeline_outputs.py -q`
- `nginx-top --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-6: add deterministic json and csv outputs`

## STEP 7: Failure Semantics and Full Quality Gate

**Goal:** Every known failure maps to the documented complete exit contract and the full suite/static checks pass at the required coverage.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` exit codes/error handling; all P0 acceptance criteria in `PRD.md`.

**Tasks:**

1. Complete `src/nginx_top/cli.py` exception boundaries for the `0/1/2/3/4` contract, where 4 always means unique-cardinality exhaustion.
2. Add strict-mode line/source diagnostics without printing full raw records.
3. Add integration cases for unreadable input (1), usage error (2), malformed strict input (3), cardinality exhaustion (4), and successful/empty input (0).
4. Add `tests/unit/test_invariants.py` for cross-renderer metric equivalence and percentage totals subject to rounding.
5. Configure Ruff, mypy, pytest, and ≥90% coverage thresholds in `pyproject.toml`.

**Verification:**

- `python3.11 -m ruff check src tests`
- `python3.11 -m mypy src`
- `python3.11 -m pytest -q --cov=nginx_top --cov-report=term-missing --cov-fail-under=90`

**Commit:** `step-7: enforce quality and exit semantics`

## STEP 8: Benchmark, Packaging, and Release Documentation

**Goal:** The install artifact works in a clean environment, the 1 GB target has measured evidence, and operators can use the command safely.

**Time:** ~2 hours plus benchmark runtime

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PROJECT_ARCHITECTURE.md` performance, privacy, and packaging; `README.md`.

**Tasks:**

1. Create `tests/perf/generate_log.py` to deterministically generate representative synthetic combined logs without checking a 1 GB artifact into Git.
2. Create `tests/perf/benchmark_1gb.py` to record input bytes, valid lines, Python version, platform/CPU, wall time, and peak RSS.
3. Update `README.md` with quick start, supported format, examples, output/exit contract, performance methodology, and privacy warning.
4. Build wheel/sdist, install the wheel into a clean virtual environment, and smoke-test file/stdin plus all three formats.
5. Record the named reference-laptop benchmark result in a release checklist only after an actual run; do not substitute an estimate.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m pytest -q --cov=nginx_top --cov-fail-under=90`
- `python3.11 tests/perf/generate_log.py --bytes 1073741824 /tmp/nginx-top-1gb.log`
- `/usr/bin/time -v nginx-top --json /tmp/nginx-top-1gb.log >/tmp/nginx-top-result.json`
- `python3.11 -m json.tool /tmp/nginx-top-result.json >/dev/null`

**Commit:** `step-8: verify performance and release artifacts`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–2 | Package contract and parser | 3 hours |
| Saturday PM | 3–4 | Complete one-pass metric engine and cardinality safety | 4 hours |
| Sunday AM | 5–6 | Human and pipeline output formats | 3.5 hours |
| Sunday PM | 7–8 | Quality gates, benchmark, and release readiness | 3.5+ hours |

## Completion Gate

Do not call implementation complete unless every verification command relevant to the current step has actually run and passed. The 1 GB/<30 s claim requires recorded benchmark evidence from the reference laptop; until then it remains an acceptance target. A red test, lint, typing, packaging, or benchmark gate blocks completion rather than being converted into narrative success.

