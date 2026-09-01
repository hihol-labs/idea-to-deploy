# Implementation Plan: nginx-stream-insights

## Delivery Rules

This plan is for a one-weekend implementation after blueprint approval. Preserve WIP=1: complete and verify one step before beginning the next. `PRD.md` is the behavioral source of truth and `PROJECT_ARCHITECTURE.md` is the technical source of truth. No step may introduce authentication, a database, an HTTP API, a server, cloud infrastructure, Docker as a runtime requirement, or Kubernetes.

The complete process exit contract is fixed for every step: `0` success, `1` input/read/runtime failure, `2` CLI usage error, `3` no valid requests, and `4` unique-cardinality exhaustion. It is always the `0/1/2/3/4` contract; code 4 must never be omitted or remapped.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | `pyproject.toml`, `src/`, and test harness | Every feature needs an installable package and repeatable tests | 1 hour |
| 2 | Typed records and error taxonomy | Parser, aggregator, CLI, and renderers share these contracts | 1 hour |
| 3 | Representative fixtures and benchmark generator | Correctness and the 1 GB gate need stable evidence before optimization | 1.5 hours |

## Step 1: Package and Verification Skeleton

**Goal:** A clean Python 3.11 environment can install the project and invoke help/version while tests and quality gates are available.

**Time:** ~1.5 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections Package and File Layout, Testing Strategy.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click and Rich runtime dependencies, pytest/coverage/ruff/mypy development extras, and the `nginx-stream-insights` console entry point.
2. Create `src/nginx_stream_insights/__init__.py` with package version and `src/nginx_stream_insights/cli.py` with help/version-only scaffolding.
3. Create `tests/test_cli.py` for installation-facing help and version behavior.
4. Configure coverage and static checks in `pyproject.toml`; do not add application behavior yet.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/nginx-stream-insights --help`

**Commit:** `step-1: establish installable CLI and test skeleton`

## Step 2: Domain Models and Error Contract

**Goal:** Shared immutable records and typed failures encode the documented invariants and fixed exit mapping.

**Time:** ~1 hour  
**Context:** `PROJECT_ARCHITECTURE.md` sections Data Model, Exit-code contract, Error Handling.

**Tasks:**

1. Create `src/nginx_stream_insights/models.py` with frozen `AccessRecord`, `RankedCount`, and `AnalysisResult` dataclasses.
2. Create `src/nginx_stream_insights/errors.py` with typed input and unique-cardinality errors.
3. Extend `tests/test_models.py` to assert 24 buckets, non-negative counts, and result invariants.
4. Add exit mapping tests for all `0/1/2/3/4` outcomes, explicitly including code 4.

**Verification:**

- `.venv/bin/python -m pytest tests/test_models.py tests/test_cli.py -q`
- `.venv/bin/python -m mypy src`

**Commit:** `step-2: define domain and failure contracts`

## Step 3: Streaming Combined-Log Parser

**Goal:** Each physical line is converted into one valid record or one explicit malformed result without retaining input.

**Time:** ~3 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections Input contract, Parsing and Aggregation Invariants.

**Tasks:**

1. Create `src/nginx_stream_insights/parser.py` with parser state compiled once and a maximum physical-line-length guard.
2. Create `tests/fixtures/valid.log`, `tests/fixtures/mixed.log`, and focused synthetic fixture helpers.
3. Create `tests/test_parser.py` for IPv4, IPv6, timezone offsets, quoting, status boundaries, `-` User-Agent, malformed syntax, invalid UTF-8 boundary behavior, and overlong lines.
4. Keep file opening in the CLI boundary; the parser accepts a single string and line number.

**Verification:**

- `.venv/bin/python -m pytest tests/test_parser.py -q`
- `.venv/bin/python -m ruff check src/nginx_stream_insights/parser.py tests/test_parser.py`

**Commit:** `step-3: parse nginx combined logs safely`

## Step 4: One-Pass Aggregation

**Goal:** One iterator pass produces deterministic top IPs, top error URLs, hourly percentages, and exact bounded User-Agent share.

**Time:** ~3 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections Data Model, Parsing and Aggregation Invariants; `PRD.md` Metric Definitions.

**Tasks:**

1. Create `src/nginx_stream_insights/aggregator.py` with scalar counters, two `Counter` instances, 24 hourly counters, and a bounded User-Agent set.
2. Finalize top 10 results with count-descending and key-ascending ordering.
3. Calculate hourly values with `100 × hourly_request_count / total_valid_requests`, never as an unscaled fraction.
4. Raise the typed exhaustion error before the exact User-Agent set exceeds its ceiling.
5. Create `tests/test_aggregator.py` for mixed statuses, all hours, deterministic ties, empty input, repeated agents, and exhaustion.

**Verification:**

- `.venv/bin/python -m pytest tests/test_aggregator.py -q`
- `.venv/bin/python -m pytest tests/test_aggregator.py --cov=nginx_stream_insights.aggregator --cov-fail-under=95`

**Commit:** `step-4: aggregate required metrics in one pass`

## Step 5: Terminal Renderer

**Goal:** Default output is a concise Rich report that remains readable and ANSI-free when color is disabled or stdout is not a TTY.

**Time:** ~2 hours  
**Context:** `PROJECT_ARCHITECTURE.md` Output contract; `PRD.md` Output Requirements.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/__init__.py` and `renderers/terminal.py`.
2. Render summary, both top-10 lists, all 24 hourly percentages, and unique User-Agent count/share.
3. Create `tests/test_renderers.py` and a terminal golden fixture with color forced off.
4. Verify empty/error sections remain explicit rather than disappearing.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py -k terminal -q`
- `.venv/bin/python -m ruff check src/nginx_stream_insights/renderers/terminal.py`

**Commit:** `step-5: render default Rich terminal report`

## Step 6: JSON and CSV Renderers

**Goal:** Pipeline modes emit deterministic, ANSI-free data using the documented schemas.

**Time:** ~2.5 hours  
**Context:** `PROJECT_ARCHITECTURE.md` Output contract and ADR-003; `PRD.md` JSON and CSV requirements.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/json.py` with the fixed top-level object contract.
2. Create `src/nginx_stream_insights/renderers/csv.py` with `metric,rank,key,count,percentage` rows and formula-injection mitigation.
3. Add JSON and CSV golden files under `tests/fixtures/expected/`.
4. Extend `tests/test_renderers.py` for parseability, stable ordering, two-decimal serialization, quoting, hostile cell prefixes, and absence of ANSI escapes.

**Verification:**

- `.venv/bin/python -m pytest tests/test_renderers.py -k 'json or csv' -q`
- `.venv/bin/python -m pytest tests/test_renderers.py --cov=nginx_stream_insights.renderers --cov-fail-under=95`

**Commit:** `step-6: add stable JSON and CSV output`

## Step 7: Complete CLI Orchestration

**Goal:** File and stdin inputs drive the full pipeline with mutually exclusive modes, separated stdout/stderr, and exact exit behavior.

**Time:** ~2.5 hours  
**Context:** `PROJECT_ARCHITECTURE.md` section CLI Interface; `PRD.md` FR-01 and FR-07 through FR-10.

**Tasks:**

1. Complete `src/nginx_stream_insights/cli.py` to open UTF-8 files incrementally or use stdin without closing it.
2. Add Click options `--json`, `--csv`, `--no-color`, and `--max-unique-user-agents` with validation.
3. Select exactly one renderer and map typed outcomes to `0/1/2/3/4` centrally.
4. Extend `tests/test_cli.py` for file/stdin parity, conflicting flags, missing files, mixed/empty/malformed input, diagnostics separation, and exhaustion code 4.

**Verification:**

- `.venv/bin/python -m pytest tests/test_cli.py -q`
- `.venv/bin/nginx-stream-insights --json tests/fixtures/valid.log | .venv/bin/python -m json.tool >/dev/null`
- `test "$(printf 'bad\n' | .venv/bin/nginx-stream-insights --json - >/dev/null; echo $?)" -eq 3`

**Commit:** `step-7: wire input output and exit contracts`

## Step 8: Performance Gate and Profiling

**Goal:** The release candidate processes a representative 1 GB log in under 30 seconds with documented peak memory, without weakening correctness.

**Time:** ~3 hours  
**Context:** `PROJECT_ARCHITECTURE.md` Performance Architecture; `PRD.md` NFR-01 through NFR-03.

**Tasks:**

1. Create `tests/perf/generate_log.py` to reproducibly generate representative high/low-cardinality input outside the committed repository.
2. Create `tests/test_performance.py` for a small CI budget and `scripts/benchmark.sh` for the explicit 1 GB local gate.
3. Record CPU, storage, OS, Python version, fixture parameters, three wall-time runs, slowest result, and peak RSS in `BENCHMARK.md`.
4. Profile only if the gate fails; optimize measured hotspots without changing schemas or metric definitions.

**Verification:**

- `.venv/bin/python -m pytest tests/test_performance.py -q`
- `sh scripts/benchmark.sh --size 1GB --runs 3`
- `.venv/bin/python -m pytest -q`

**Commit:** `step-8: enforce throughput and memory gates`

## Step 9: Packaging, Documentation, and Release Check

**Goal:** A clean Python 3.11 environment installs the artifact and every documented contract is verified end to end.

**Time:** ~2 hours  
**Context:** All blueprint documents and Definition of Done in `STRATEGIC_PLAN.md`.

**Tasks:**

1. Create `README.md` with installation, supported format, examples for terminal/JSON/CSV/stdin, metric formulas, security note, and all exit codes.
2. Add `LICENSE` using the selected open-source license and `CHANGELOG.md` for the initial contract.
3. Build wheel and sdist, install the wheel into a new clean Python 3.11 environment, and run smoke tests.
4. Run unit, integration, coverage, static, golden, and benchmark gates; reconcile docs before tagging.

**Verification:**

- `.venv/bin/python -m pytest --cov=nginx_stream_insights --cov-fail-under=90 -q`
- `.venv/bin/python -m ruff check . && .venv/bin/python -m mypy src`
- `.venv/bin/python -m build && python3.11 -m venv /tmp/nginx-stream-insights-smoke && /tmp/nginx-stream-insights-smoke/bin/pip install dist/*.whl && /tmp/nginx-stream-insights-smoke/bin/nginx-stream-insights --version`
- `sh scripts/benchmark.sh --size 1GB --runs 3`

**Commit:** `step-9: prepare verified pip release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable foundation and correct parsing | ~5.5 hours |
| Saturday PM | 4–5 | Complete metrics and terminal experience | ~5 hours |
| Sunday AM | 6–7 | Pipeline formats and CLI contract | ~5 hours |
| Sunday PM | 8–9 | Performance evidence and clean release | ~5 hours |

## Dependency and Scope Checkpoints

- Step 3 cannot begin until Step 2 contracts pass.
- Renderers consume finalized `AnalysisResult`; they do not receive mutable aggregators.
- CLI integration begins only after all three renderers pass their own tests.
- Performance optimization may change internals but not parsing semantics, formulas, schemas, or exit codes.
- Gzip input and configurable top-N remain P1/P2 and are not allowed to displace the release gates.
