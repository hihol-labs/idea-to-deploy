# Implementation Plan: Nginx Stream Analytics CLI

This is a planning artifact only; no product code is part of the blueprint. Steps are ordered by dependency while preserving the value ordering from `STRATEGIC_PLAN.md`.

## Architectural Runway

| # | Item | Why first | Effort |
|---:|---|---|---:|
| 1 | Python package and console entry point | Every test and feature needs an installable boundary | 1 hour |
| 2 | Domain dataclasses and typed errors | Parser, accumulator, renderers, and exit mapping share these contracts | 1 hour |
| 3 | Fixture corpus and test harness | Parser behavior must be frozen before aggregation | 1 hour |
| 4 | Repeatable performance fixture generator | The 1 GB target must be measurable before late optimization | 1 hour |

There is intentionally no database schema, auth system, Docker setup, server, or CI/CD deployment runway. These would contradict the CLI-only architecture.

## STEP 1: Package and CLI Skeleton

**Goal:** A clean Python 3.11 environment can install the package and invoke the documented command and help output.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and `CLI Interface`; `PRD.md` FR-01, FR-11.

**Tasks:**

1. Create `pyproject.toml` with Python `>=3.11,<4`, Click, Rich, build metadata, and the `nginx-stream-report` entry point.
2. Create `src/nginx_stream_analytics/__init__.py` with the package version.
3. Create `src/nginx_stream_analytics/cli.py` with the Click command, mutually exclusive format validation, and placeholders that fail explicitly until wired.
4. Create `tests/test_cli.py` for help, version, option validation, and the complete exit-code vocabulary.

**Verification:**

- `python3.11 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`
- `.venv/bin/nginx-stream-report --help`
- `.venv/bin/pytest tests/test_cli.py -q`

**Commit:** `step-1: establish package and CLI contracts`

## STEP 2: Models, Errors, and Fixtures

**Goal:** Shared record/snapshot types and representative log fixtures define the behavior boundary.

**Time:** ~1.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 8; `PRD.md` US-1 through US-7.

**Tasks:**

1. Create `src/nginx_stream_analytics/models.py` with `LogRecord`, metric row types, and immutable `ReportSnapshot` dataclasses.
2. Create `src/nginx_stream_analytics/errors.py` with input, parse, and unique-cardinality exceptions plus centralized mapping to `0/1/2/3/4`; code `4` means unique-cardinality exhaustion.
3. Create `tests/fixtures/valid.log`, `mixed.log`, `malformed.log`, `empty.log`, and `cardinality.log` with documented expected outcomes.
4. Extend `tests/test_cli.py` to assert `0` success, `1` I/O/runtime failure, `2` usage error, `3` parse failure, and `4` unique-cardinality exhaustion.

**Verification:**

- `.venv/bin/python -m compileall -q src tests`
- `.venv/bin/pytest tests/test_cli.py -q`

**Commit:** `step-2: define domain and failure contracts`

## STEP 3: Combined-Log Parser

**Goal:** Valid nginx combined records become typed records while malformed and encoding failures follow the approved policy.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 5 and 8; `PRD.md` FR-01, FR-02, FR-13.

**Tasks:**

1. Create `src/nginx_stream_analytics/parser.py` with compiled parsing logic, quoted-field escape handling, timezone-aware timestamp parsing, and field validation.
2. Create `tests/test_parser.py` covering IPv4, IPv6, escaped quotes, missing optional fields, invalid timestamps/status/request forms, and non-ASCII User-Agents.
3. Add one-shot iterator tests demonstrating that parsing does not seek or reread.

**Verification:**

- `.venv/bin/pytest tests/test_parser.py -q`
- `.venv/bin/pytest tests/test_parser.py --cov=nginx_stream_analytics.parser --cov-report=term-missing --cov-fail-under=90`

**Commit:** `step-3: parse nginx combined logs`

## STEP 4: One-Pass Metrics and Cardinality Guard

**Goal:** All four report families are computed exactly in one pass, with deterministic order and fail-closed unique cardinality.

**Time:** ~3 hours

**Context:** `PROJECT_ARCHITECTURE.md` sections 3, 5, and 9; `PRD.md` US-1 through US-4.

**Tasks:**

1. Create `src/nginx_stream_analytics/aggregate.py` with `MetricsAccumulator.consume(record)` and `snapshot(top_n)`.
2. Count all IPs, statuses 400–599 by request target, and 24 timestamp hours.
3. Calculate hourly percentages only as `100 × hourly_request_count / total_valid_requests`.
4. Track distinct non-null User-Agents exactly and raise the typed exhaustion failure before crossing `--max-unique-user-agents`.
5. Create `tests/test_aggregate.py` covering ties, zero input, mixed statuses, missing agents, timezone offsets, percentages summing to approximately 100 for nonempty input, and exhaustion.

**Verification:**

- `.venv/bin/pytest tests/test_aggregate.py -q`
- `.venv/bin/pytest tests/test_aggregate.py --cov=nginx_stream_analytics.aggregate --cov-report=term-missing --cov-fail-under=90`

**Commit:** `step-4: implement one-pass metric aggregation`

## STEP 5: Terminal Renderer

**Goal:** Default output is a clear Rich report whose colors never leak into redirected output.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface`; `PRD.md` FR-08, FR-10.

**Tasks:**

1. Create `src/nginx_stream_analytics/renderers/__init__.py` with renderer dispatch.
2. Create `src/nginx_stream_analytics/renderers/terminal.py` with summary, top-IP, error-URL, hourly, and User-Agent tables.
3. Extend `tests/test_renderers.py` with TTY/non-TTY and `--no-color` assertions using Rich's testable console configuration.

**Verification:**

- `.venv/bin/pytest tests/test_renderers.py -q -k terminal`
- `.venv/bin/nginx-stream-report tests/fixtures/valid.log --no-color`

**Commit:** `step-5: add terminal report renderer`

## STEP 6: JSON and CSV Renderers

**Goal:** Automation receives deterministic, ANSI-free JSON and CSV matching the documented schemas.

**Time:** ~2 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface`; `PRD.md` US-5 and FR-09.

**Tasks:**

1. Create `src/nginx_stream_analytics/renderers/json.py` with the versioned top-level object.
2. Create `src/nginx_stream_analytics/renderers/csv.py` with `report,key,count,percentage` rows via the standard library CSV writer.
3. Extend `tests/test_renderers.py` with schema, escaping, ordering, numeric type, empty-report, and no-ANSI assertions.

**Verification:**

- `.venv/bin/pytest tests/test_renderers.py -q -k 'json or csv'`
- `.venv/bin/nginx-stream-report --json tests/fixtures/valid.log | .venv/bin/python -m json.tool >/dev/null`

**Commit:** `step-6: add machine-readable renderers`

## STEP 7: End-to-End Orchestration and Failure Semantics

**Goal:** File and stdin workflows produce complete reports or concise diagnostics with no partial machine output.

**Time:** ~2.5 hours

**Context:** `PROJECT_ARCHITECTURE.md` `CLI Interface` and section 8; `PRD.md` US-5 through US-8.

**Tasks:**

1. Complete `src/nginx_stream_analytics/cli.py` to open input, stream parse/aggregate, freeze a snapshot, dispatch a renderer, and handle broken pipes.
2. Implement default tolerant malformed-line summary, `--strict`, `--top`, `--max-unique-user-agents`, and stdout/stderr separation.
3. Expand `tests/test_cli.py` with file/stdin equivalence, invalid UTF-8, nonexistent files, all-malformed input, strict mode, option conflicts, broken output, and no-partial-output assertions.
4. Assert the complete contract: `0` success, `1` I/O/runtime failure, `2` usage error, `3` parse failure, `4` unique-cardinality exhaustion.

**Verification:**

- `.venv/bin/pytest tests/test_cli.py -q`
- `.venv/bin/nginx-stream-report --json tests/fixtures/valid.log >/tmp/nginx-report.json`
- `printf '%s\n' 'not a log line' | .venv/bin/nginx-stream-report --strict -; test $? -eq 3`

**Commit:** `step-7: wire end-to-end CLI behavior`

## STEP 8: Quality, Packaging, and Performance Gate

**Goal:** The installable candidate meets correctness, clean-install, and 1 GB/30 s release criteria with recorded evidence.

**Time:** ~3 hours

**Context:** `STRATEGIC_PLAN.md` Definition of Done; `PRD.md` NFR-01 through NFR-06.

**Tasks:**

1. Create `tests/test_performance.py` and `scripts/generate_benchmark_log.py` for a deterministic representative fixture without committing the 1 GB artifact.
2. Add `README.md` examples and document supported format, metrics, schemas, performance methodology, and exit codes `0/1/2/3/4`; code `4` means unique-cardinality exhaustion.
3. Run profiling only if the baseline misses the target; optimize measured hot paths without changing output contracts.
4. Build wheel/sdist and install the wheel into a new Python 3.11 virtual environment.
5. Record laptop CPU, storage, Python version, fixture composition, peak RSS, and median of three wall-time runs.

**Verification:**

- `.venv/bin/pytest -q --cov=nginx_stream_analytics --cov-report=term-missing --cov-fail-under=90`
- `.venv/bin/python scripts/generate_benchmark_log.py --bytes 1000000000 --output /tmp/nginx-benchmark.log`
- `.venv/bin/pytest tests/test_performance.py -q --benchmark-input /tmp/nginx-benchmark.log`
- `.venv/bin/python -m build`
- `python3.11 -m venv /tmp/nginx-wheel-smoke && /tmp/nginx-wheel-smoke/bin/pip install dist/*.whl && /tmp/nginx-wheel-smoke/bin/nginx-stream-report --version`

**Commit:** `step-8: verify release and performance gates`

## Sprint Boundaries

The one-weekend schedule uses two short delivery blocks rather than multi-week sprints.

| Block | Steps | Goal | Duration |
|---|---|---|---|
| Saturday | 1–4 | Installable foundation, parser, exact aggregation | 1 day |
| Sunday | 5–8 | All renderers, integration, packaging, performance evidence | 1 day |

## Cross-Step Acceptance Protocol

After each step, run its focused commands and the accumulated test suite. Before release, freeze one candidate and run the full test, build, clean-install, and performance commands against that same candidate. A prose claim is not a substitute for command output.

The release exit-code contract is immutable across all steps: `0` complete success; `1` input/runtime I/O, encoding, or unexpected failure; `2` CLI usage error; `3` strict parse failure or non-empty input with zero valid records; `4` unique-cardinality exhaustion.

## Handoff

Start with Step 1. Do not begin a second step until the active step's focused verification passes. Use `CLAUDE_CODE_GUIDE.md` for implementation prompts and `PRD.md` acceptance criteria as the durable source of truth.
