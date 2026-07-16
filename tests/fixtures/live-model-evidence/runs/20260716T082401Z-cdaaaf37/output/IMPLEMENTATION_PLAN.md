# Implementation Plan: Nginx Stream Insights

## Architectural Runway

| # | Item | Why first | Effort |
|---|---|---|---:|
| 1 | Python package skeleton and console entry point | Every test and feature needs an installable command | 1 h |
| 2 | Domain/output contracts and golden fixtures | Prevents parser, aggregation, and renderers from drifting | 1 h |
| 3 | Test, lint, and benchmark commands | Evidence must be repeatable before feature work expands | 1 h |

No database schema, authentication, API scaffold, Docker setup, or CI/CD deployment runway is needed for this local CLI.

## STEP 1: Establish package and quality skeleton

**Goal:** A pip-installable Python 3.11 package exposes a working help/version command.  
**Time:** ~1 hour  
**Context:** `PROJECT_ARCHITECTURE.md` sections 3, 6, and 11  
**Tasks:**

1. Create `pyproject.toml` with Python 3.11, Click, Rich, build metadata, console entry point, and test/lint extras.
2. Create `src/nginx_stream_insights/__init__.py` and `src/nginx_stream_insights/cli.py`.
3. Create `tests/test_cli.py` for help, version, and option-exclusivity behavior.

**Verification:**

- `python3.11 -m pip install -e '.[dev]'`
- `nginx-stream-insights --help`
- `pytest -q tests/test_cli.py`

**Commit:** `step-1: scaffold installable CLI package`

## STEP 2: Define models and golden contracts

**Goal:** Typed dataclasses and fixtures define parsing, aggregation, and output semantics before implementation.  
**Time:** ~1 hour  
**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 7; `PRD.md` acceptance criteria  
**Tasks:**

1. Create `src/nginx_stream_insights/models.py` with `AccessRecord`, `RankedCount`, `HourlyCount`, and `AnalysisReport`.
2. Create `tests/fixtures/combined.log`, `tests/fixtures/common.log`, and `tests/fixtures/mixed_invalid.log` with hand-verifiable expected values.
3. Create `tests/expected/golden_report.json` containing the canonical report contract.

**Verification:**

- `pytest -q tests/test_models.py`
- `python3.11 -m json.tool tests/expected/golden_report.json >/dev/null`

**Commit:** `step-2: define report models and golden fixtures`

## STEP 3: Implement bounded log parsing

**Goal:** Common/combined lines become records while malformed lines are recoverable diagnostics.  
**Time:** ~2 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections 3 and 8  
**Tasks:**

1. Create `src/nginx_stream_insights/parser.py` with a single-line parsing function and structured failure result.
2. Create `src/nginx_stream_insights/input.py` with file/stdin iterators and explicit ownership/error behavior.
3. Create `tests/test_parser.py` and `tests/test_input.py` covering IPv4, IPv6, timezone, supported/invalid escapes, common format, strict UTF-8 failures, CRLF, missing request, trailing tokens, 1 MiB limits, malformed lines, and unreadable/mid-stream input.

**Verification:**

- `pytest -q tests/test_parser.py tests/test_input.py`
- `ruff check src/nginx_stream_insights/parser.py src/nginx_stream_insights/input.py`

**Commit:** `step-3: parse nginx logs as a stream`

## STEP 4: Implement streaming aggregation

**Goal:** One pass produces all four metrics and diagnostics with deterministic top-10 ties.  
**Time:** ~2 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections 4 and 5  
**Tasks:**

1. Create `src/nginx_stream_insights/aggregate.py` with mutable internal counters and `finalize()` returning `AnalysisReport`.
2. Create `tests/test_aggregate.py` for IP ranking, error-only URL ranking, all 24 hours, User-Agent denominator semantics, empty input, and deterministic ties.
3. Add integration coverage proving malformed records do not corrupt valid aggregates.

**Verification:**

- `pytest -q tests/test_aggregate.py`
- `pytest -q --cov=nginx_stream_insights.aggregate --cov-fail-under=90`

**Commit:** `step-4: compute streaming nginx metrics`

## STEP 5: Add terminal renderer

**Goal:** Default execution displays four readable Rich sections with safe color behavior.  
**Time:** ~1.5 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections 7 and 9  
**Tasks:**

1. Create `src/nginx_stream_insights/renderers/__init__.py` and `renderers/terminal.py`.
2. Escape log-derived values and implement TTY, `--no-color`, and `NO_COLOR` behavior.
3. Create `tests/test_terminal_renderer.py` using a deterministic Rich console.

**Verification:**

- `pytest -q tests/test_terminal_renderer.py`
- `nginx-stream-insights tests/fixtures/combined.log --no-color`

**Commit:** `step-5: render colored terminal report`

## STEP 6: Add JSON renderer

**Goal:** `--json` emits only the versioned machine-readable document on stdout.  
**Time:** ~1 hour  
**Context:** `PROJECT_ARCHITECTURE.md` sections 6 and 7  
**Tasks:**

1. Create `src/nginx_stream_insights/renderers/json.py` with explicit schema mapping.
2. Wire `--json` through `cli.py` without terminal formatting.
3. Create `tests/test_json_renderer.py` and compare full output with `tests/expected/golden_report.json`.

**Verification:**

- `pytest -q tests/test_json_renderer.py`
- `nginx-stream-insights --json tests/fixtures/combined.log | python3.11 -m json.tool >/dev/null`

**Commit:** `step-6: add stable JSON pipeline output`

## STEP 7: Add CSV renderer

**Goal:** `--csv` emits correctly quoted normalized rows with a stable header.  
**Time:** ~1 hour  
**Context:** `PROJECT_ARCHITECTURE.md` sections 6 and 7  
**Tasks:**

1. Create `src/nginx_stream_insights/renderers/csv.py` using the standard-library CSV writer.
2. Wire `--csv` and mutual exclusion through `cli.py`.
3. Create `tests/test_csv_renderer.py` for every section, canonical row ordering, empty-input rows, six-decimal shares, commas/quotes, and no ANSI escapes.

**Verification:**

- `pytest -q tests/test_csv_renderer.py tests/test_cli.py`
- `nginx-stream-insights --csv tests/fixtures/combined.log | python3.11 -c 'import csv,sys; list(csv.DictReader(sys.stdin))'`

**Commit:** `step-7: add normalized CSV pipeline output`

## STEP 8: Integrate golden flows and harden UX

**Goal:** File, stdin, empty, malformed, and failure flows meet the PRD as one installed command.  
**Time:** ~1.5 hours  
**Context:** `PRD.md` P0 stories and `PROJECT_ARCHITECTURE.md` sections 6, 8, and 9  
**Tasks:**

1. Complete orchestration and stderr/exit-code mapping in `src/nginx_stream_insights/cli.py`.
2. Create `tests/test_end_to_end.py` for file input, piped stdin, all formats, empty input, mixed invalid input, unreadable/mid-stream failures, output failures, and closed downstream pipes.
3. Update command help and `README.md` from verified behavior.

**Verification:**

- `pytest -q`
- `nginx-stream-insights --json - < tests/fixtures/combined.log`
- `ruff check src tests`

**Commit:** `step-8: complete CLI golden flows`

## STEP 9: Prove packaging and performance

**Goal:** Clean installation works and a correct representative 1 GB run completes in under 30 seconds on the recorded laptop.  
**Time:** ~3 hours  
**Context:** `PROJECT_ARCHITECTURE.md` sections 11 and 12; `STRATEGIC_PLAN.md` Definition of Done  
**Tasks:**

1. Create `benchmarks/generate_fixture.py` and `benchmarks/README.md` implementing the exact `baseline-v1` and `cardinality-v1` profiles from architecture section 12; keep generated data out of Git.
2. Create `tests/test_performance_smoke.py` for bounded CI-sized performance regression detection.
3. Build wheel/sdist, install the wheel in a clean environment, and record warm/cold cache state, three-run baseline timing, peak RSS, correctness, and cardinality-profile evidence in `benchmarks/results.md`.
4. Update `README.md` with verified install, examples, limitations, supported formats, and privacy guidance.

**Verification:**

- `python3.11 -m build && python3.11 -m twine check dist/*`
- `pytest -q && ruff check src tests benchmarks`
- `/usr/bin/time -v nginx-stream-insights --json benchmarks/fixture-1gb.log >/dev/null`

**Commit:** `step-9: verify distribution and 1GB performance target`

## Sprint boundaries

The one-weekend schedule uses short delivery blocks rather than multi-week sprints.

| Block | Steps | Goal | Duration |
|---|---|---|---|
| Saturday AM | 1–3 | Runnable package and correct parser | 4 h |
| Saturday PM | 4–5 | Complete analysis and terminal value path | 4 h |
| Sunday AM | 6–8 | Pipeline formats and end-to-end behavior | 4 h |
| Sunday PM | 9 | Packaging, documentation, and performance evidence | 3 h |

## Dependency and rollback policy

Steps are dependency-ordered and WIP remains one. Each step is accepted only with its listed verification. If a benchmark fails, profile the parser/aggregator and revise the spec explicitly; do not silently introduce persistence, multiprocessing, or approximate counting.

See `CLAUDE_CODE_GUIDE.md` for step prompts and `PRD.md` for acceptance criteria.
