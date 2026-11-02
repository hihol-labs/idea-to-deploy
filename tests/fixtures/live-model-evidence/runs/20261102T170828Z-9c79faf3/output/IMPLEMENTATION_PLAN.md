# Implementation Plan: nginx-stream-insights

This is a planning artifact only. Each future step is independently verifiable and must preserve the specifications in `PRD.md` and `PROJECT_ARCHITECTURE.md`.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and test layout | Every implementation and check needs importable boundaries | 1 hour |
| 2 | Canonical dataclasses and CLI schema | Prevents three renderers from inventing different semantics | 1 hour |
| 3 | Benchmark protocol/fixture generator | Makes the performance target measurable before optimization | 1 hour |

No database schema, migrations, auth system, HTTP service, Docker setup, cloud, or Kubernetes work belongs in the runway.

## Step 1: Package Skeleton and Contracts

**Goal:** A Python 3.11 package builds, installs, and exposes an empty command boundary.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 7; `PRD.md` FR-01 and FR-08.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<3.12`, Click, Rich, build metadata, and the `nginx-stream-insights` console script.
2. Create `src/nginx_stream_insights/__init__.py`, `src/nginx_stream_insights/__main__.py`, and `src/nginx_stream_insights/cli.py`.
3. Create `tests/test_cli.py` with help/version and initial command-boundary tests.

**Verification:**

- `python3.11 -m pip install -e '.[test]'`
- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-stream-insights --help`

**Commit:** `step-1: scaffold installable CLI package`

## Step 2: Domain Models and nginx Parser

**Goal:** Common/combined log lines become validated `AccessEvent` values without output side effects.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 6; `PRD.md` FR-02.

**Tasks:**

1. Create `src/nginx_stream_insights/models.py` with `AccessEvent`, ranked result, hourly bucket, and `Report` dataclasses.
2. Create `src/nginx_stream_insights/parser.py` with explicit common/combined parsers and a typed malformed-line result.
3. Create `tests/fixtures/access.log` with non-sensitive handcrafted edge cases.
4. Create `tests/test_parser.py` for IPv4/IPv6, quoting, timestamps, status bounds, request targets, placeholders, and invalid UTF-8/structure behavior.

**Verification:**

- `python3.11 -m pytest tests/test_parser.py -q`

**Commit:** `step-2: add validated nginx parser`

## Step 3: Streaming Input and Aggregation

**Goal:** One pass computes exact counts, rankings, percentages, malformed counts, and the cardinality guard.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4–6; `PRD.md` FR-01 and FR-03 through FR-05.

**Tasks:**

1. Create `src/nginx_stream_insights/input.py` for file/stdin iteration and source errors.
2. Create `src/nginx_stream_insights/aggregator.py` for IP/error URL counters, 24 hour buckets, exact User-Agent set, ceiling, and deterministic finalization.
3. Create `tests/test_input.py` and `tests/test_aggregator.py` covering empty input, ties, 4xx/5xx boundaries, formulas, missing User-Agent, malformed records, and ceiling exhaustion.

**Verification:**

- `python3.11 -m pytest tests/test_input.py tests/test_aggregator.py -q`
- `python3.11 -m pytest --cov=nginx_stream_insights --cov-report=term-missing -q`

**Commit:** `step-3: implement streaming metrics core`

## Step 4: Terminal Renderer and CLI Orchestration

**Goal:** Default execution produces readable Rich output and maps failures to the public contract.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` → `CLI Interface`; `PRD.md` FR-06 through FR-08.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/__init__.py` and `renderers/text.py`.
2. Complete `cli.py` options, input selection, orchestration, stdout/stderr separation, TTY color detection, and exit mapping.
3. Extend `tests/test_cli.py` to cover text output, `--no-color`, malformed policy, missing files, invalid options, and codes 0–4.

**Verification:**

- `python3.11 -m pytest tests/test_cli.py -q`
- `nginx-stream-insights tests/fixtures/access.log --no-color`

**Commit:** `step-4: deliver terminal analytics command`

## Step 5: JSON and CSV Renderers

**Goal:** Pipelines receive stable schemas derived from the same canonical report.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` → `CLI Interface` outputs; `PRD.md` P0 acceptance criteria 4.

**Tasks:**

1. Create `src/nginx_stream_insights/renderers/json.py` with schema version and numeric percentages.
2. Create `src/nginx_stream_insights/renderers/csv.py` with the normalized five-column schema.
3. Create `tests/golden/report.json`, `tests/golden/report.csv`, and `tests/test_renderers.py` for exact schema, ordering, escaping, and semantic parity.
4. Add Click mutual exclusion for `--json` and `--csv`.

**Verification:**

- `python3.11 -m pytest tests/test_renderers.py tests/test_cli.py -q`
- `nginx-stream-insights --json tests/fixtures/access.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-5: add stable JSON and CSV output`

## Step 6: Follow Mode and Operational Edge Cases

**Goal:** Regular files can be followed safely while invalid source/option combinations remain deterministic.

**Time:** ~2 hours

**Context:** `PRD.md` FR-09 through FR-11; `PROJECT_ARCHITECTURE.md` error model.

**Tasks:**

1. Extend `input.py` with interruptible regular-file follow behavior without busy-spinning.
2. Extend `cli.py` with `--top`, `--max-unique-user-agents`, and `--follow` validation.
3. Add `tests/test_follow.py` using a temporary file, bounded waits, appended lines, and clean interruption.

**Verification:**

- `python3.11 -m pytest tests/test_follow.py tests/test_cli.py -q`

**Commit:** `step-6: add bounded controls and follow mode`

## Step 7: Performance and Quality Gate

**Goal:** Correctness, memory, and the 1 GB/30-second target are evidenced on a named environment.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 8 and 10; `PRD.md` quality attributes.

**Tasks:**

1. Create `benchmarks/generate_log.py` to deterministically generate non-sensitive combined-format records to a requested byte size.
2. Create `benchmarks/run.sh` to record Python version, OS/machine, command, wall time, peak RSS, and output counts.
3. Create `tests/test_end_to_end.py` for cross-renderer golden flow and every exit code.
4. Profile failures before changing architecture; record benchmark assumptions in `benchmarks/README.md`.

**Verification:**

- `python3.11 -m pytest --cov=nginx_stream_insights --cov-fail-under=90 -q`
- `python3.11 benchmarks/generate_log.py --size 1GB --output /tmp/nginx-stream-insights-1gb.log`
- `bash benchmarks/run.sh /tmp/nginx-stream-insights-1gb.log`

**Commit:** `step-7: verify correctness and performance budget`

## Step 8: Packaging and Release Readiness

**Goal:** A clean Python 3.11 environment can install the wheel and reproduce documented behavior.

**Time:** ~2 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; all P0 requirements in `PRD.md`.

**Tasks:**

1. Finalize `README.md` quick start, supported formats, formulas, schemas, examples, and limitations.
2. Add `LICENSE`, `CHANGELOG.md`, and build configuration as needed.
3. Create `tests/test_wheel_smoke.py` or `scripts/smoke-wheel.sh` to install the built wheel into a temporary virtual environment.
4. Run the complete suite and benchmark; prepare but do not publish a release without explicit human approval.

**Verification:**

- `python3.11 -m build`
- `python3.11 -m pytest --cov=nginx_stream_insights --cov-fail-under=90 -q`
- `bash scripts/smoke-wheel.sh dist/*.whl`
- `bash benchmarks/run.sh /tmp/nginx-stream-insights-1gb.log`

**Commit:** `step-8: prepare verified pip release`

## Sprint Boundaries

| Sprint | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Installable package, parser, canonical streaming core | Half day |
| Saturday PM | 4–5 | Human and pipeline output | Half day |
| Sunday AM | 6–7 | Operational controls, full correctness/performance evidence | Half day |
| Sunday PM | 8 | Packaging, documentation, release readiness | Half day |

## Complete Exit-code Contract

Every step that touches CLI behavior must preserve: `0` success (including empty input), `1` input/unexpected runtime I/O failure, `2` CLI usage/configuration error, `3` non-empty input with no valid records, and `4` unique-cardinality exhaustion. Code 4 must never be remapped to a generic runtime or parse failure.

## Delivery Rules

- Implement one step at a time and run its verification commands before committing.
- Change the PRD/architecture first when behavior changes; generated code follows the specification.
- Never publish, push, or deploy without explicit human confirmation.
- Do not add a database, HTTP API, server, auth, cloud, Docker runtime, or Kubernetes artifact to satisfy generic templates.
